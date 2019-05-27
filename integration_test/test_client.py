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

import argparse
import uuid
import json
import time
from collections import namedtuple

import boto3
import aws_encryption_sdk
import requests
from requests_aws4auth import AWS4Auth

def assert_dicts_equal(a, b):
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)

def get_sfn_arn_and_queue_resource(test_stack_name, session):
    # get state machine, queue from stack
    cfn = session.resource('cloudformation')

    stack = cfn.Stack(test_stack_name)

    for output in stack.outputs:
        if output['OutputKey'] == 'StateMachine':
            state_machine_arn = output['OutputValue']
        elif output['OutputKey'] == 'Queue':
            queue_url = output['OutputValue']

    sqs = session.resource('sqs')
    queue = sqs.Queue(queue_url)

    return state_machine_arn, queue

def drain(test_stack_name, session):
    print(f"Getting state machine ARN and Queue from stack {test_stack_name}")
    state_machine_arn, queue = get_sfn_arn_and_queue_resource(test_stack_name, session)
    print(f"Got state machine ARN {state_machine_arn}")
    print(f"Got queue URL {queue.url}")

    step_functions = session.client('stepfunctions')

    print('Stopping state machine executions...')
    next_token=None
    while True:
        args = {
            'stateMachineArn': state_machine_arn,
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
        messages = queue.receive_messages(
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=5,
        )
        for message in messages:
            print(f'Deleting message {message.body}')
            message.delete()
        if len(messages) < max_messages:
            break
    
    print('Done')

def run(api_url, test_stack_name, session):
    # get state machine, queue from stack
    print(f"Getting state machine ARN and Queue from stack {test_stack_name}")
    state_machine_arn, queue = get_sfn_arn_and_queue_resource(test_stack_name, session)

    print(f"Got state machine ARN {state_machine_arn}")
    print(f"Got queue URL {queue.url}")

    step_functions = session.client('stepfunctions')

    #TODO: do this a few times
    
    correlation_id = uuid.uuid4().hex
    print(f'Correlation id: {correlation_id}')

    # create state machine execution

    execution_input = {"cid_in": correlation_id}
    
    print(f'Starting state machine with input {json.dumps(execution_input)}')
    response = step_functions.start_execution(
        stateMachineArn=state_machine_arn,
        name=correlation_id,
        input=json.dumps(execution_input)
    )

    execution_arn = response['executionArn']
    print(f'Execution started: {execution_arn}')

    # get value from queue

    print('Getting SQS message')
    messages = queue.receive_messages()

    assert len(messages) == 1

    message = messages[0]
    print('Got a message')

    payload = json.loads(message.body)

    print(f'Message payload: {payload}')
    
    payload_input = payload['Input']
    assert_dicts_equal(payload_input, execution_input)

    token = payload['TaskToken']
    print(f'Got the token: {token}')

    # call API for url

    output = {"cid_out": correlation_id}

    creds = session.get_credentials().get_frozen_credentials()

    auth = AWS4Auth(creds.access_key, creds.secret_key, session.region_name, 'execute-api', session_token=creds.token)

    url = f'{api_url}/urls'
    body = {
            'token': token,
            'actions': {
                'good': {
                    'type': 'success',
                    'output': output,
                },
                'bad': {
                    'type': 'failure',
                    'error': correlation_id,
                    'response': {
                        'html': 'Hello $hello'
                    }
                },
                'hb': {
                    'type': 'heartbeat',
                    'response': {
                        'redirect': 'https://google.com'
                    }
                }
            },
            "enable_output_parameters": True
        }

    print(f'Getting URLs: {url}')
    print(f'Body: {json.dumps(body)}')
    response = requests.post(url,
        auth=auth,
        json=body
    )

    print(f'Response status: {response.status_code}')
    if response.status_code != 200:
        print(f'Response headers: {response.headers}')
    print(f'Response body: {json.dumps(response.json(), indent=2)}')

    # return

    response = response.json()

    good_url = response['urls']['good']
    bad_url = response['urls']['bad']
    hb_url = response['urls']['hb']

    # call url
    print(f'Calling good URL {good_url}')
    response = requests.get(good_url)

    print(f'Response status: {response.status_code}')
    if response.status_code != 200:
        print(f'Response headers: {response.headers}')
    print(f'Response body: {json.dumps(response.json(), indent=2)}')

    time.sleep(1)

    # check state machine execution
    print(f'Checking state machine execution')
    response = step_functions.describe_execution(
        executionArn=execution_arn
    )

    print(f'Status: {response["status"]}')
    print(f'Response: {response}')

    print('Deleting queue message')
    message.delete()

    print('Complete!')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    
    api_group = parser.add_mutually_exclusive_group(required=True)
    api_group.add_argument('--stack')
    api_group.add_argument('--api')
    
    parser.add_argument('--test-stack', required=True)
    
    parser.add_argument('--drain', action='store_true')

    args = parser.parse_args()

    session = boto3.Session()

    if args.drain:
        drain(args.test_stack, session)
    else:
        if args.stack:
            cfn = session.resource('cloudformation')
            stack = cfn.Stack(args.stack)
            for output in stack.outputs:
                if output['OutputKey'] == 'Api':
                    args.api = output['OutputValue']
                    break
            else:
                parser.exit(f"Couldn't get API url")
                
        drain(args.test_stack, session)
        run(args.api, args.test_stack, session)
