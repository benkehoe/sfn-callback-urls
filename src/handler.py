import json
import base64
import datetime
import os
import urllib.parse
import uuid
import sys
import traceback

import jwt
import dateutil.parser
import boto3
import botocore.exceptions

class RequestError(Exception):
    pass

def send_log_event(log_event):
    print(json.dumps(log_event)) #TODO: CloudWatch Events?

ACTIONS = ['success', 'failure', 'heartbeat']

DISABLE_PARAMETERS_ENV_VAR_NAME = 'DISABLE_OUTPUT_PARAMETERS'
def get_force_disable_parameters():
    force_disable_parameters = False
    if DISABLE_PARAMETERS_ENV_VAR_NAME in os.environ:
        value = os.environ[DISABLE_PARAMETERS_ENV_VAR_NAME]
        if value.lower() not in ['0', 'false', '1', 'true']:
            print(f'Invalid value for {DISABLE_PARAMETERS_ENV_VAR_NAME}: {value}', file=sys.stderr)
        force_disable_parameters = value.lower() in ['1', 'true']
    return force_disable_parameters

CREATE_EVENT_SKELETON = {
    'token': '',
    'expiration': '',
    'actions': {
        'name1': {
            'type': 'success',
            'output': {},
        },
        'name2': {
            'type': 'failure',
            'error': '',
            'cause': '',
        },
        'name3': {
            'type': 'heartbeat',
        }
    },
    'enable_output_parameters': False,
    'api': {
        'api_id': '',
        'stage_id': '',
        'region': '',
    }
}

PAYLOAD_SKELETON = {
    'token': '',
    'iss': 'function name',
    'iat': 0, # unix timestamp
    'tid': '', # transaction id
    'exp': 0, # expiration unix timestamp
    'name': '', # action_name
    'act': '', # action_type
    'out': {}, # output for the task, for success and optional for failure
    'par': False, # enable the caller to pass parameters for the output
}

CALLBACK_EVENT_SKELETON = {
    'action_name': '',
    'action_type': '',
    'payload': '',
    'parameters': {},
}

boto3_session = boto3.Session()

def get_encode_args(event, context):
    return {
        'key': None,
        'algorithm': 'none',
    }

def get_decode_args(event, context):
    return {
        'key': None,
        'algorithms': ['none'],
        'verify': False,
    }

def create_url_handler(event, context):
    print(f'Received event: {event}')

    transaction_id = uuid.uuid4().hex
    timestamp = datetime.datetime.now()

    log_event = {
        'transaction_id': transaction_id,
        'timestamp': timestamp.isoformat(),
        'actions': [],
    }

    try:
        api_spec = event.get('api', {})
        region = api_spec.get('region') or boto3_session.region_name
        api_id = api_spec.get('api_id', os.environ.get('API_ID'))
        stage_id = api_spec.get('stage_id', os.environ.get('STAGE_ID'))
        log_event.update({
            'api_id': api_id,
            'stage_id': stage_id,
            'region': region,
        })
        missing = []
        if not api_id:
            missing.append('API id')
        if not stage_id:
            missing.append('stage id')
        if missing:
            message = 'Missing ' + ' and '.join(missing)
            raise RequestError(f'MissingApiParameters:{message}')

        response = {
            'transaction_id': transaction_id,
            'urls': {},
        }
        
        expiration = None
        if 'expiration' in event:
            try:
                expiration = dateutil.parser.parse(event['expiration'])
                log_event['expiration_delta'] = (expiration - timestamp).total_seconds()
            except Exception as e:
                pass
        response['expiration'] = expiration.isoformat()
        
        url_template = 'https://{api_id}.{region}.execute-api.amazonaws.com/{stage_id}/{path}?{query}'

        def get_url(action_name, action_type, action_data):
            payload = {
                'token': event['token'],
                'iat': int(timestamp.timestamp()),
                'tid': transaction_id,
                #exp: expiration
                #name: action_name
                #act: action_type
                #data: data for the action
                #par: enable the caller to pass parameters for the output
            }
            if 'AWS_LAMBDA_FUNCTION_NAME' in os.environ:
                payload['iss'] = os.environ['AWS_LAMBDA_FUNCTION_NAME']
            if expiration:
                payload['exp'] = int(expiration.timestamp()),
            
            payload['name'] = action_name
            payload['act'] = action_type
            
            if action_data:
                payload['data'] = action_data
            
            force_disable_parameters = get_force_disable_parameters()
            log_event['force_disable_parameters'] = force_disable_parameters
            if event.get('enable_output_parameters'):
                if force_disable_parameters:
                    log_event['enable_parameter_conflict'] = True
                    print('Request asked for parameters, but they are disabled', file=sys.stderr)
                    raise RequestError('ParametersDisabled:Parameters are disabled')
                else:
                    log_event['parameters_enabled'] = True
                    payload['par'] = True
            
            print(f'Encoding {action_name} ({action_type}) payload: {json.dumps(payload)}')

            encoded_payload = jwt.encode(payload, **get_encode_args(event, context))
            print(encoded_payload)
            query = urllib.parse.urlencode([
                ('action', action_name),
                ('type', action_type),
                ('payload', encoded_payload)
            ])

            return url_template.format(
                api_id=api_id,
                region=region,
                stage_id=stage_id,
                path='respond',
                query=query,
            )

        actions = {}
        for action_name, action_data in event['actions'].items():
            action_type = action_data['type']
            actions[action_name] = action_type
            payload_data = {}
            
            if action_type == 'success':
                payload_data['output'] = action_data['output']
            elif action_type == 'failure':
                for key in ['error', 'cause']:
                    if key in action_data:
                        payload_data[key] = action_data[key]
            elif action_type != 'heartbeat':
                raise ValueError(f'Unexpected action type {action_type}')

            response['urls'][action_name] = get_url(action_name, action_type, payload_data)

        log_event['actions'] = actions
        
        print(f'Sending response: {json.dumps(response)}')

        send_log_event(log_event)

        return response
    except RequestError as e:
        error, msg = str(e).split(':')
        response = {
            'transaction_id': transaction_id,
            'error': error,
            'message': msg,
        }
        log_event['error'] = {
            'type': 'RequestError',
            'error': error,
            'message': msg,
        }
        send_log_event(log_event)
        return response
    except Exception as e:
        traceback.print_exc()
        error_class_name = type(e).__module__ + '.' + type(e).__name__
        log_event['error'] = {
            'type': 'Unexpected',
            'error': error_class_name,
            'message': str(e),
        }
        send_log_event(log_event)
        raise

def format_output(output, parameters):
    if isinstance(output, dict):
        for key in output:
            output[key] = format_output(output[key], parameters)
    elif isinstance(output, list):
        for i in range(len(output)):
            output[i] = format_output(output[i], parameters)
    elif isinstance(output, str):
        try:
            output = output.format(**parameters)
        except (IndexError, KeyError) as e:
            raise RequestError(f'OutputFormattingError:Formatting the output with the parameters failed ({e})')
    return output

def callback_handler(event, context):
    print(f'Received event: {event}')

    timestamp = datetime.datetime.now()

    log_event = {
        'timestamp': timestamp.isoformat(),
    }

    try:
        response = {}

        action_name_from_url = event['action_name']
        action_type_from_url = event['action_type']
        encoded_payload = event['payload']
        parameters = event.get('parameters', {})

        try:
            payload = jwt.decode(encoded_payload, **get_decode_args(event, context))
        except Exception as e:
            raise
        
        action_name_in_payload = payload['name']
        if action_name_from_url != action_name_in_payload:
            raise RequestError(f'ActionMismatched:The action name says {action_name_from_url} in the url but {action_name_in_payload} in the payload')
        action_name = action_name_in_payload

        action_type_in_payload = payload['act']
        if action_type_from_url != action_type_in_payload:
            raise RequestError(f'ActionMismatched:The action type says {action_type_in_payload} in the url but {action_type_in_payload} in the payload')
        action_type = action_type_in_payload

        log_event['action'] = {
            'name': action_name,
            'type': action_type
        }
        
        force_disable_parameters = get_force_disable_parameters()
        use_parameters = payload.get('par', False)
        if use_parameters and force_disable_parameters:
            print('Request asked for parameters, but they are disabled', file=sys.stderr)
            raise RequestError('ParametersDisabled:Parameters are disabled')
        
        action_data = payload['data']
        
        client = boto3.client('stepfunctions')

        method = f'send_task_{action_type}'

        method_params = {
            'taskToken': payload['token']
        }

        if action_type == 'success':
            output = action_data['output']
            if use_parameters:
                output = format_output(output, parameters)
            method_params['output'] = json.dumps(output)
        elif action_type == 'failure':
            for key in ['error', 'cause']:
                if key in action_data:
                    method_params[key] = action_data[key]
        
        try:
            sfn_response = getattr(client, method)(**method_params)
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
                response = {
                    'error': error_code,
                    'message': error_msg,
                }
                log_event['error'] = {
                    'type': 'StepFunctionsError',
                    'error': error_code,
                    'message': error_msg,
                }
                send_log_event(log_event)
                return response
            raise

        send_log_event(log_event)

        return response
    except RequestError as e:
        error, msg = str(e).split(':')
        response = {
            'error': error,
            'message': msg,
        }
        log_event['error'] = {
            'type': 'RequestError',
            'error': error,
            'message': msg,
        }
        send_log_event(log_event)
        return response
    except Exception as e:
        traceback.print_exc()
        error_class_name = type(e).__module__ + '.' + type(e).__name__
        log_event['error'] = {
            'type': 'Unexpected',
            'error': error_class_name,
            'message': str(e),
        }
        send_log_event(log_event)
        raise
