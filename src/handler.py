import json
import base64
import datetime
import os
import urllib.parse

import jwt
import dateutil.parser
import boto3
import botocore.exceptions

ACTIONS = ['success', 'failure', 'heartbeat']

DEFAULT_KEY = ''

EVENT_SKELETON = {
    'token': '',
    'expiration': '',
    'actions': {
        'success': '',
        'failure': [
            {
                'name': '',
                'error': '',
                'cause': ''
            }
        ],
        'heartbeat': True,
    },
    'disable_parameters': ''
}

def create_url(event, context):
    api_id = os.environ['API_ID']
    stage_id = os.environ['STAGE_ID']
    region = os.environ['AWS_REGION']

    print(f'Received event: {event}')

    timestamp = datetime.datetime.now()

    expiration = None
    if 'expiration' in event:
        try:
            expiration = dateutil.parser.parse(event['expiration'])
            
        except Exception as e:
            pass
    
    allow = event.get('actions', ','.join(ACTIONS))

    url_template = 'https://{api_id}.{region}.execute-api.amazonaws.com/{stage_id}/{path}?{query}'

    def get_url(action, output):
        payload = {
            'token': event['token'],
            'iat': int(timestamp.timestamp()),
            #exp
            #act
            #allow
            #out_s
            #out_f
            #out_p
        }
        payload['exp'] = int(expiration.timestamp()),
        payload['act'] = action
        payload['allow'] = allow
        
        if output:
            payload['out'] = output
        
        if 'disable_parameters' in event:
            payload['dop'] = event['disable_parameters']
        
        print(f'Encoding {action} payload: {json.dumps(payload)}')

        encoded_payload = jwt.encode(payload, DEFAULT_KEY, algorithm='HS256')
        query = urllib.parse.urlencode(
            ('action', action),
            ('payload', encoded_payload)
        )

        return url_template.format(
            api_id=api_id,
            region=region,
            stage_id=stage_id,
            path='respond',
            query=query,
        )

    response = {
        'urls': {}
    }

    if 'success' in event['actions']:
        response['urls']['success'] = get_url('success', event['actions']['success'])
    
    for failure in event['actions'].get('failure', []):
        name = failure['name']
        if name in ['success', 'heartbeat']:
            raise ValueError
        data = {}
        for key in ['error', 'cause']:
            if key in failure:
                data[key] = failure[key]
        response['urls'][name] = get_url('failure', data)
    
    if event['actions'].get('heartbeat', False):
        response['urls']['heartbeat'] = get_url('heartbeat', None)
    
    print(f'Sending response: {json.dumps(response)}')

    return response

def format_output(output, parameters):
    #TODO: walk output object, format with parameters
    return output

def handle_callback(event, context):
    disable_output_parameters = os.environ.get('DISABLE_OUTPUT_PARAMETERS', 'false').lower() in ['1','true']

    action_from_url = event['action']
    encoded_payload = event['payload']
    parameters = event.get('parameters', {})

    try:
        payload = jwt.decode(encoded_payload, DEFAULT_KEY, algorithms=['HS256'])
    except Exception as e:
        raise
    
    action_in_payload = payload['act']
    if action_from_url != action_in_payload:
        raise ValueError
    action = action_in_payload
    
    disable_output_parameters |= payload.get('dop', False)

    output = payload.get('out')

    if output and not disable_output_parameters:
        output = format_output(output, parameters)
    
    client = boto3.client('stepfunctions')

    method = f'send_task_{action}'

    method_params = {
        'taskToken': payload['token']
    }

    if action == 'success':
        method_params['output'] = payload['out']
    elif action == 'failure':
        for key in ['error', 'cause']:
            if key in payload['out']:
                method_params[key] = payload['out'][key]
    
    try:
        response = getattr(client, method)(**method_params)
        return {}
    except botocore.exceptions.ClientError as e:
        #TODO: catch SFN errors
        raise
