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

import json
import base64
import datetime
import os
import uuid
import sys
import traceback
from collections import namedtuple
import time

import boto3
import botocore.exceptions
import aws_encryption_sdk
import jsonschema

from sfn_callback_urls.callbacks import load_from_request, format_output
from sfn_callback_urls.payload import decode_payload, validate_payload_schema, validate_payload_expiration
from sfn_callback_urls.common import send_log_event, get_force_disable_parameters, RequestError, BaseError

class ActionMismatchedError(RequestError):
    pass

class ParametersDisabledError(RequestError):
    pass

class StepFunctionsError(BaseError):
    TYPE = 'StepFunctionsError'

BOTO3_SESSION = boto3.Session()
MASTER_KEY_PROVIDER = None
if 'KEY_ID' in os.environ:
    MASTER_KEY_PROVIDER = aws_encryption_sdk.KMSMasterKeyProvider(
        key_ids = [os.environ['KEY_ID']],
        botocore_session = BOTO3_SESSION._session
    )

def handler(event, context):
    print(f'Received event: {event}')

    timestamp = datetime.datetime.now()

    log_event = {
        'timestamp': timestamp.isoformat(),
    }

    try:
        response = {}

        (
            action_name_from_url,
            action_type_from_url,
            encoded_payload,
            parameters
        ) = load_from_request(event)

        decode_start = time.perf_counter()
        payload = decode_payload(encoded_payload, MASTER_KEY_PROVIDER)
        decode_finish = time.perf_counter()
        log_event['decode_time'] = (decode_finish - decode_start)
        
        action_name_in_payload = payload['name']
        if action_name_from_url and action_name_from_url != action_name_in_payload:
            raise ActionMismatchedError(f'The action name says {action_name_from_url} in the url but {action_name_in_payload} in the payload')
        action_name = action_name_in_payload

        action_type_in_payload = payload['act']
        if action_type_from_url and action_type_from_url != action_type_in_payload:
            raise ActionMismatchedError(f'The action type says {action_type_in_payload} in the url but {action_type_in_payload} in the payload')
        action_type = action_type_in_payload

        log_event['action'] = {
            'name': action_name,
            'type': action_type
        }

        validate_payload_schema(payload)
        validate_payload_expiration(payload, timestamp)
        
        force_disable_parameters = get_force_disable_parameters()
        use_parameters = payload.get('par', False)
        if use_parameters and force_disable_parameters:
            raise ParametersDisabledError('Parameters are disabled')
        
        action_data = payload.get('data', {})
        
        client = BOTO3_SESSION.client('stepfunctions')

        method = f'send_task_{action_type}'

        method_params = {
            'taskToken': payload['token']
        }

        if action_type == 'success':
            output = action_data.get('output', {})
            if use_parameters:
                output = format_output(output, parameters)
            method_params['output'] = json.dumps(output)
        elif action_type == 'failure':
            for key in ['error', 'cause']:
                if key in action_data:
                    method_params[key] = action_data[key]
        
        try:
            sfn_call_start = time.perf_counter()
            sfn_response = getattr(client, method)(**method_params)
            sfn_call_finish = time.perf_counter()
            log_event['sfn_call_time'] = (sfn_call_finish-sfn_call_start)
        except botocore.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            errors = [
                'InvalidOutput',
                'InvalidToken',
                'TaskDoesNotExist',
                'TaskTimedOut',

            ]
            if error_code in errors:
                raise StepFunctionsError(error_msg)
            raise

        print(f'Sending response: {json.dumps(response)}')

        send_log_event(log_event)

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
            },
            'body': json.dumps(response)
        }
    except BaseError as e:
        response = {
            'error': e.code(),
            'message': e.message(),
        }
        log_event['error'] = {
            'type': e.TYPE,
            'error': e.code(),
            'message': e.message(),
        }
        send_log_event(log_event)
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
            },
            'body': json.dumps(response)
        }
    except Exception as e:
        traceback.print_exc()
        error_class_name = type(e).__module__ + '.' + type(e).__name__
        response = {
            'error': 'ServiceError',
            'message': f'{error_class_name}: {str(e)}'
        }
        log_event['error'] = {
            'type': 'Unexpected',
            'error': error_class_name,
            'message': str(e),
        }
        send_log_event(log_event)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
            },
            'body': json.dumps(response)
        }
