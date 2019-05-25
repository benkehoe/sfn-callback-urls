import os
import sys
import base64
import json
import datetime

import aws_encryption_sdk
import jsonschema

from .common import get_force_disable_parameters, RequestError, ParametersDisabledError

class InvalidPayloadError(RequestError):
    pass

class ExpiredPayloadError(RequestError):
    pass

class DecryptionUnsupportedError(RequestError):
    pass

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

PAYLOAD_SCHEMA = {
    "type": "object",
    "properties": {
        "iss": {"type": "string"},
        "iat": {"type": "number"},
        "tid": {"type": "string"},
        "exp": {"type": "number"},
        "token": {"type": "string"},
        "name": {
            "type": "string"
        },
        "act": {
            "type": "string",
            "enum": ["success", "failure", "heartbeat"]
        },
        "data": {
            "type": "object"
        },
        "par": {
            "type": "boolean"
        }
    },
    "required": ["token", "name", "act", "data"],
    "allOf": [
        {
            "if": {
                "properties": { "act": { "const": "success" } }
            },
            "then": {
                "properties": {
                    "data": {
                        "type": "object",
                        "properties": {
                            "output": {
                                "type": "object"
                            }
                        },
                        "required": ["output"]
                    },
                    
                },
                "required": ["data"],
            }
        },
        {
            "if": {
                "properties": { "act": { "const": "failure" } }
            },
            "then": {
                "properties": {
                    "data": {
                        "type": "object",
                        "properties": {
                            "error": {
                                "type": "string"
                            },
                            "reason": {
                                "type": "string"
                            },
                        }
                    }
                }
            }
        }
    ]
}

class PayloadBuilder:
    def __init__(self, 
            transaction_id,
            timestamp, 
            token,
            enable_output_parameters=False,
            expiration=None):
        self.transaction_id = transaction_id
        self.timestamp = timestamp
        self.token = token
        self.enable_output_parameters = enable_output_parameters
        self.expiration = expiration

        self.issuer = os.environ.get('AWS_LAMBDA_FUNCTION_NAME')
    
    def build(self, action_name, action_type, action_data, log_event={}):
        payload = {
            'token': self.token,
            'iat': int(self.timestamp.timestamp()),
            'tid': self.transaction_id,
            #exp: expiration
            #name: action_name
            #act: action_type
            #data: data for the action
            #par: enable the caller to pass parameters for the output
        }
        if self.issuer:
            payload['iss'] = self.issuer
        if self.expiration:
            payload['exp'] = int(self.expiration.timestamp())
        
        payload['name'] = action_name
        payload['act'] = action_type
        
        if action_data is not None:
            payload['data'] = action_data
        
        force_disable_parameters = get_force_disable_parameters()
        log_event['force_disable_parameters'] = force_disable_parameters
        if self.enable_output_parameters:
            if force_disable_parameters:
                log_event['enable_parameter_conflict'] = True
                print('Request asked for parameters, but they are disabled', file=sys.stderr)
                raise ParametersDisabledError('Parameters are disabled')
            else:
                log_event['parameters_enabled'] = True
                payload['par'] = True
        
        return payload

def encode_payload(payload, master_key_provider):
    payload_string = json.dumps(payload).encode()
    
    if not master_key_provider:
        return '1-' + str(base64.urlsafe_b64encode(payload_string), 'ascii')
    else:
        try:
            ciphertext, encryptor_header = aws_encryption_sdk.encrypt(
                source=payload_string,
                key_provider=master_key_provider
            )
        except aws_encryption_sdk.exceptions.AWSEncryptionSDKClientError as e:
            # unexpected
            raise 

        return '2-' + str(base64.urlsafe_b64encode(ciphertext), 'ascii')

def validate_payload_schema(payload):
    try:
        jsonschema.validate(payload, PAYLOAD_SCHEMA)
    except jsonschema.ValidationError as e:
        raise InvalidPayloadError(f'Failed schema validation ({e})')

def validate_payload_expiration(payload, timestamp=None):
    timestamp = timestamp or datetime.datetime.now()
    if 'exp' in payload:
        exp = datetime.datetime.fromtimestamp(payload['exp'])
        if exp < timestamp:
            raise ExpiredPayloadError(f'Response expired on {exp.isoformat()}')

def decode_payload(payload, master_key_provider):
    assert isinstance(payload, str)
    parts = payload.split('-', 1)
    if len(parts) != 2:
        raise InvalidPayloadError('Missing format id')
    
    version, base64_payload = parts

    try:
        binary_payload = base64.urlsafe_b64decode(base64_payload)
    except base64.binascii.Error as e:
        raise InvalidPayloadError(f'Base64 error ({str(e)})')

    if version == '1':
        try:
            loaded_payload = json.loads(binary_payload)
        except json.JSONDecodeError as e:
            raise InvalidPayloadError(f'JSON error ({str(e)})')
    elif version == '2':
        if not master_key_provider:
            raise DecryptionUnsupportedError('No key found')
        try:
            decrypted_payload, decrypted_header = aws_encryption_sdk.decrypt(
                source=binary_payload,
                key_provider=master_key_provider
            )
        except aws_encryption_sdk.exceptions.AWSEncryptionSDKClientError as e:
            raise InvalidPayloadError(f'Decryption error ({type(e).__name__}:{str(e)})')
        
        try:
            loaded_payload = json.loads(decrypted_payload)
        except json.JSONDecodeError as e:
            raise InvalidPayloadError(f'JSON error ({str(e)})')
    else:
        raise InvalidPayloadError('Unknown format id')

    return loaded_payload
