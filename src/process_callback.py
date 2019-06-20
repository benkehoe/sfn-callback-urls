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
from collections import namedtuple, OrderedDict
import time

import boto3
import botocore.exceptions
import aws_encryption_sdk
import jsonschema

from sfn_callback_urls.callbacks import (
    load_from_request,
    prepare_method_params,
    format_response
)
from sfn_callback_urls.payload import (
    decode_payload,
    validate_payload_schema,
    validate_payload_expiration
)
from sfn_callback_urls.post_actions import (
    load_post_action_body,
    process_post_action
)
from sfn_callback_urls.common import (
    send_log_event,
    get_force_disable_parameters,
    get_disable_post_actions,
    is_verbose,
    get_header
)

from sfn_callback_urls.exceptions import (
    ReturnHttpResponse,
    BaseError,
    ActionMismatched,
    ParametersDisabled,
    PostActionsDisabled,
    InvalidPostActionBody,
    StepFunctionsError
)

BOTO3_SESSION = boto3.Session()
STEP_FUNCTIONS_CLIENT = BOTO3_SESSION.client('stepfunctions')
MASTER_KEY_PROVIDER = None
if 'KEY_ID' in os.environ:
    MASTER_KEY_PROVIDER = aws_encryption_sdk.KMSMasterKeyProvider(
        key_ids = [os.environ['KEY_ID']],
        botocore_session = BOTO3_SESSION._session
    )

def handler(request, context):
    if is_verbose():
        print(f'Request: {json.dumps(request)}')

    timestamp = datetime.datetime.now()

    log_event = {
        'timestamp': timestamp.isoformat(),
    }

    try:
        response = OrderedDict() # ordered so it appears sensibly in the HTML output

        (
            action_name_from_url,
            action_type_from_url,
            encoded_payload,
            parameters
        ) = load_from_request(request)

        decode_start = time.perf_counter()
        payload = decode_payload(encoded_payload, MASTER_KEY_PROVIDER)
        decode_finish = time.perf_counter()
        log_event['decode_time'] = (decode_finish - decode_start)

        validate_payload_schema(payload)

        if is_verbose():
            print(f'Payload: {json.dumps(payload)}')
        
        # use the same transaction id given out in the create urls call
        log_event['transaction_id'] = payload['tid']
        response['transaction_id'] = payload['tid']
        
        validate_payload_expiration(payload, timestamp)
        
        # we put the action name and type in the query string directly for convenience
        # but we only trust the version that's in the payload. If the query string
        # versions differ from the payload, something funny is going on and we reject
        # the request. But if they are absent, it's not a problem.

        action_name_in_payload = payload['action']['name']
        if action_name_from_url and action_name_from_url != action_name_in_payload:
            raise ActionMismatched(f'The action name says {action_name_from_url} in the url but {action_name_in_payload} in the payload')
        action_name = action_name_in_payload

        action_type_in_payload = payload['action']['type']
        if action_type_from_url and action_type_from_url != action_type_in_payload:
            raise ActionMismatched(f'The action type says {action_type_in_payload} in the url but {action_type_in_payload} in the payload')
        action_type = action_type_in_payload

        log_event['action'] = {
            'name': action_name,
            'type': action_type
        }
        response['action'] = OrderedDict((
            ('name', action_name),
            ('type', action_type),
        ))

        # If parameters are disabled, refuse to service a request
        # that has parameters enabled, even though it was presumably
        # valid at creation time to have parameters enabled.
        force_disable_parameters = get_force_disable_parameters()
        use_parameters = payload.get('param', False)
        if use_parameters and force_disable_parameters:
            raise ParametersDisabled('Parameters are disabled')
        if not use_parameters:
            parameters = None
        
        action = payload['action']

        response_spec = action.get('response', {})

        outcome_name = action_name
        outcome_type = action_type

        if action_type == 'post':
            (
                post_outcome_name,
                post_outcome_type,
                outcome_response_spec,
                method_params
            ) = process_post_action(action, request, parameters, log_event)
            outcome_name = outcome_name + '.' + post_outcome_name
            outcome_type = post_outcome_type
            
            if outcome_response_spec is not None:
                response_spec = outcome_response_spec
        else:
            method_params = prepare_method_params(action, parameters, log_event=log_event)
        
        log_event['outcome_name'] = outcome_name
        log_event['outcome_type'] = outcome_type

        if is_verbose():
            print(f'Input for {outcome_type}: {json.dumps(method_params)}')

        method = f'send_task_{outcome_type}'
        method_params['taskToken'] = payload['token']

        try:
            sfn_call_start = time.perf_counter()
            sfn_response = getattr(STEP_FUNCTIONS_CLIENT, method)(**method_params)
            sfn_call_finish = time.perf_counter()
            log_event['sfn_call_time'] = (sfn_call_finish-sfn_call_start)
        except botocore.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            # These errors are related to the state machine itself, and
            # should be 400 errors.
            # Other ClientErrors, like invalid permissions, should be
            # considered 500 errors.
            errors = [
                'InvalidOutput',
                'InvalidToken',
                'TaskDoesNotExist',
                'TaskTimedOut',
            ]
            if error_code in errors:
                raise StepFunctionsError(f'{error_code}:{error_msg}')
            raise

        return_value = format_response(200, response, request, response_spec, parameters, log_event)

        send_log_event(log_event)

        if is_verbose():
            print(f'Response: {json.dumps(return_value)}')

        return return_value
    except ReturnHttpResponse as e:
        log_event['error'] = {
            'type': e.TYPE,
            'error': e.code(),
            'message': e.message(),
        }
        return_value = e.get_response()
        send_log_event(log_event)
        if is_verbose():
            print(f'Response: {json.dumps(return_value)}')
        return return_value
    except BaseError as e:
        response = OrderedDict((
            ('error', e.code()),
            ('message', e.message()),
        ))
        log_event['error'] = {
            'type': e.TYPE,
            'error': e.code(),
            'message': e.message(),
        }
        return_value = format_response(400, response, request, {}, None, log_event)
        send_log_event(log_event)
        if is_verbose():
            print(f'Response: {json.dumps(return_value)}')
        return return_value
    except Exception as e:
        traceback.print_exc()
        error_class_name = type(e).__module__ + '.' + type(e).__name__
        response = OrderedDict((
            ('error', 'ServiceError'),
            ('message', f'{error_class_name}: {str(e)}'),
        ))
        log_event['error'] = {
            'type': 'Unexpected',
            'error': error_class_name,
            'message': str(e),
        }
        return_value = format_response(500, response, request, {}, None, log_event)
        send_log_event(log_event)
        if is_verbose():
            print(f'Response: {json.dumps(return_value)}')
        return return_value
