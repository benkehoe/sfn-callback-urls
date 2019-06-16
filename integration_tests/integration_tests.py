# Copyright 2019 Ben Kehoe
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest

import argparse
import uuid
import json
import time
import os
from collections import namedtuple

import boto3
import aws_encryption_sdk
import requests
from requests_aws4auth import AWS4Auth

def assert_dicts_equal(a, b):
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)

Resources = namedtuple('Resources', ['app_stack', 'test_stack', 'state_machine_arn', 'queue'])

@pytest.fixture(scope='session')
def session():
    return boto3.Session()

@pytest.fixture(scope='session')
def resources(session):
    cfn = session.resource('cloudformation')
    app_stack = cfn.Stack(os.environ['STACK_NAME'])
    test_stack = cfn.Stack(os.environ['TEST_STACK_NAME'])

    # get state machine, queue from stack
    print(f"Getting state machine ARN and Queue from stack {test_stack.stack_name}")
    for output in test_stack.outputs:
        if output['OutputKey'] == 'StateMachine':
            state_machine_arn = output['OutputValue']
        elif output['OutputKey'] == 'Queue':
            queue_url = output['OutputValue']

    sqs = session.resource('sqs')
    queue = sqs.Queue(queue_url)

    print(f"Got state machine ARN {state_machine_arn}")
    print(f"Got queue URL {queue.url}")

    return Resources(
        app_stack,
        test_stack,
        state_machine_arn,
        queue
    )

@pytest.fixture(scope='session')
def drain(resources, session):
    step_functions = session.client('stepfunctions')

    print('Stopping state machine executions...')
    next_token=None
    while True:
        args = {
            'stateMachineArn': resources.state_machine_arn,
            'statusFilter': 'RUNNING',
        }
        if next_token:
            args['nextToken'] = next_token
        response = step_functions.list_executions(
            **args
        )

        for execution in response['executions']:
            execution_arn = execution['executionArn']
            print(f'Stopping execution {execution_arn}')
            response = step_functions.stop_execution(
                executionArn=execution_arn
            )
        if not response.get('nextToken'):
            break
        next_token = response['nextToken']
    
    print(f'Draining queue...')
    while True:
        max_messages = 10
        messages = resources.queue.receive_messages(
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=5,
        )
        for message in messages:
            print(f'Deleting message {message.body}')
            message.delete()
        if len(messages) < max_messages:
            break
    
    print('Done')

StateMachineExecution = namedtuple('StateMachineExecution', ['correlation_id', 'token', 'execution_arn'])

@pytest.fixture
def state_machine_execution(resources, session):
    step_functions = session.client('stepfunctions')

    correlation_id = uuid.uuid4().hex
    print(f'Correlation id: {correlation_id}')

    execution_input = {"cid_in": correlation_id}
    
    print(f'Starting state machine with input {json.dumps(execution_input)}')
    response = step_functions.start_execution(
        stateMachineArn=resources.state_machine_arn,
        name=correlation_id,
        input=json.dumps(execution_input)
    )

    execution_arn = response['executionArn']
    print(f'Execution started: {execution_arn}')

    print('Getting SQS message')
    messages = resources.queue.receive_messages(
        WaitTimeSeconds=5
    )

    assert len(messages) == 1

    message = messages[0]
    print('Got a message')

    payload = json.loads(message.body)

    print(f'Message payload: {payload}')
    
    payload_input = payload['Input']
    assert_dicts_equal(payload_input, execution_input)

    token = payload['TaskToken']
    print(f'Got the token: {token}')

    yield StateMachineExecution(correlation_id, token, execution_arn)

    print('Deleting queue message')
    message.delete()

def create_urls_with_api(create_urls_input, resources, session):
    for output in resources.app_stack.outputs:
        if output['OutputKey'] == 'Api':
            api_url = output['OutputValue']
            break

    creds = session.get_credentials().get_frozen_credentials()

    auth = AWS4Auth(creds.access_key, creds.secret_key, session.region_name, 'execute-api', session_token=creds.token)

    url = f'{api_url}/urls'
    print(f'Getting URLs: {url}')
    print(f'Body: {json.dumps(create_urls_input)}')
    response = requests.post(url,
        auth=auth,
        json=create_urls_input
    )

    print(f'Response status: {response.status_code}')
    if response.status_code != 200:
        print(f'Response headers: {response.headers}')
        raise Exception('API call failed')
    print(f'Response body: {json.dumps(response.json(), indent=2)}')

    response = response.json()

    return response

def create_urls_with_lambda(create_urls_input, resources, session):
    for output in resources.app_stack.outputs:
        if output['OutputKey'] == 'Function':
            function_name = output['OutputValue']
            break

    response = boto3.client('lambda').invoke(
        FunctionName=function_name,
        Payload=json.dumps(create_urls_input)
    )
    return json.loads(response['Payload'].read())

def _run_test(
        state_machine_execution, resources, session,
        actions,
        action_index=0,
        validate_execution=True,
        expiration=None,
        enable_output_parameters=None,
        create_with='api',
        callback_method='get',
        post_body=None
        ):
    create_urls_input = {
        'token': state_machine_execution.token,
        'actions': actions,
    }
    if expiration is not None:
        create_urls_input['expiration'] = expiration.isoformat()
    if enable_output_parameters is not None:
        create_urls_input['enable_output_parameters'] = enable_output_parameters

    action = actions[action_index]
    action_name = action['name']
    action_type = action['type']

    if create_with == 'api':
        response = create_urls_with_api(create_urls_input, resources, session)
    elif create_with == 'function':
        response = create_urls_with_lambda(create_urls_input, resources, session)
    else:
        raise ValueError(f'bad create_with {create_with}')

    assert 'urls' in response
    assert action_name in response['urls']

    url = response['urls'][action_name]

    print(f'Calling URL {url}')
    response = requests.get(url)

    print(f'Response status: {response.status_code}')
    if response.status_code != 200:
        print(f'Response headers: {response.headers}')
    print(f'Response body: {json.dumps(response.json(), indent=2)}')

    if validate_execution is False:
        return response

    client = session.client('stepfunctions')

    print(f'Checking state machine execution')
    start = time.time()
    while time.time() - start < 2:
        response = client.describe_execution(
            executionArn=state_machine_execution.execution_arn
        )
        if action_type == 'heartbeat' or response["status"] != 'RUNNING':
            break
    else:
        assert False, "Timed out waiting for state machine to finish"


    print(f'Status: {response["status"]}')
    print(f'Response: {response}')

    if callable(validate_execution):
        validate_execution(response)
    else:
        action.validate(response)

    print('Complete!')

class Actions:
    class success(dict):
        def __init__(self, name, output, response=None):
            action = {
                'name': name,
                'type': 'success',
                'output': output
            }
            if response is not None:
                action['response'] = response
            super().__init__(action.items())
        
        def validate(self, response):
            assert response["status"] == 'SUCCEEDED'
            assert_dicts_equal(json.loads(response["output"]), self['output'])
    
    class failure(dict):
        def __init__(self, name, error=None, cause=None, response=None):
            action = {
                'name': name,
                'type': 'failure',
            }
            if error is not None:
                action['error'] = error
            if cause is not None:
                action['cause'] = cause
            if response is not None:
                action['response'] = response
            super().__init__(action.items())
        
        def validate(self, response):
            assert response["status"] == 'FAILED'
            #TODO: how to find the error and cause?

    class heartbeat(dict):
        def __init__(self, name, response=None):
            action = {
                'name': name,
                'type': 'heartbeat'
            }
            if response is not None:
                action['response'] = response
            super().__init__(action.items())
        
        def validate(self, response):
            assert response["status"] == 'RUNNING'
    
def test_basic_success(state_machine_execution, resources, session, drain):
    action_name = uuid.uuid4().hex
    task_output = {"cid_out": state_machine_execution.correlation_id}
    actions = [
        Actions.success(action_name, task_output)
    ]
    
    _run_test(
        state_machine_execution, resources, session,
        actions=actions,
    )

def test_basic_failure(state_machine_execution, resources, session, drain):
    action_name = uuid.uuid4().hex
    actions = [
        Actions.failure(action_name)
    ]
    
    _run_test(
        state_machine_execution, resources, session,
        actions=actions,
    )

