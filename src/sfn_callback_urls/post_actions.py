import json

import jsonschema
import jsonschema.validators

from .common import get_header, get_disable_post_actions
from .callbacks import prepare_method_params

from .exceptions import (
    PostActionsDisabled,
    InvalidPostActionOutcome,
    InvalidPostActionBody,
    ReturnHttpResponse
)

def validate_post_action(action):
    if get_disable_post_actions():
        raise PostActionsDisabled('Post actions are disabled')
    for outcome in action['outcomes']:
        schema = outcome['schema']
        try:
            v = jsonschema.validators.validator_for(schema)
            v.check_schema(schema)
        except jsonschema.exceptions.SchemaError as e:
            raise InvalidPostActionOutcome(f'Bad schema: {str(e)}')
        except Exception as e:
            raise InvalidPostActionOutcome(f'Bad schema: {str(e)}')
        
        for key in ['output_path', 'error_path', 'cause_path']:
            if key in outcome:
                pass #TODO: JSONPath

def load_post_action_body(request, log_event={}):
    if request['httpMethod'] != 'POST':
        raise ReturnHttpResponse(
            'PostActionNotPosted',
            f'HTTP method was {request["httpMethod"]}',
            405,
            headers={
                'Allow': 'POST'
            }
        )
    
    if get_header(request, 'content-type') == 'application/json':
        try:
            return json.loads(request['body'])
        except json.JSONDecodeError as e:
            raise ReturnHttpResponse(
                'InvalidPostActionBody',
                str(e),
                400,
                headers={
                    'Content-Type': 'application/json',
                },
                body={
                    'error': 'InvalidJSON',
                    'message': f'{str(e)}',
                }
            )
    else:
        raise ReturnHttpResponse(
            'InvalidPostActionBody',
            'Post action body must be JSON',
            415
        )
    #TODO: multipart/form-data

def _process_post_action(action, body, parameters, log_event={}):
    outcomes = action['outcomes']
    
    log_event['post_outcome_names'] = [o['name'] for o in outcomes]
    log_event['post_outcome_types'] = [o['type'] for o in outcomes]
    log_event['post_outcomes_num'] = len(outcomes)
    
    for outcome_index, outcome in enumerate(outcomes):
        outcome_body_schema = outcome['schema']
        try:
            jsonschema.validate(body, outcome_body_schema)
        except jsonschema.ValidationError as e:
            continue
        
        outcome_name = outcome['name']
        outcome_type = outcome['type']
        
        log_event['post_outcome_index'] = outcome_index
        
        response_spec = outcome.get('response')

        if outcome.get('output_body', False):
            outcome['output'] = body
        
        # TODO: JSONPath
        # for key in ['output', 'error', 'cause']:
        #     path_key = f'{key}_path'
        #     if path_key in outcome:
        #         path = outcome[path_key]
        #         outcome[key] = jsonpath(body, path)
        
        method_params = prepare_method_params(outcome, parameters, log_event=log_event)
        break
    else:
        raise InvalidPostActionBody('Body does not match any outcome')
    
    return (
        outcome_name,
        outcome_type,
        response_spec,
        method_params
    )

def process_post_action(action, request, parameters, log_event={}):
    if get_disable_post_actions():
        raise PostActionsDisabled('Post actions are disabled')
    
    body = load_post_action_body(request, log_event)
    
    return _process_post_action(action, body, parameters, log_event=log_event)
