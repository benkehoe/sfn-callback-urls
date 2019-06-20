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

import os
import sys
import base64
import json
import datetime

import aws_encryption_sdk
import jsonschema

from .common import get_force_disable_parameters

from .exceptions import (
    ParametersDisabled,
    InvalidPayload,
    ExpiredPayload,
    EncryptionFailed,
    DecryptionUnsupported,
    EncryptionRequired
)

from .schemas.payload import payload_schema

class PayloadBuilder:
    def __init__(self,
            transaction_id,
            timestamp, 
            token,
            enable_output_parameters=False,
            expiration=None,
            issuer=None):
        self.transaction_id = transaction_id
        self.timestamp = timestamp
        self.token = token
        self.enable_output_parameters = enable_output_parameters
        self.expiration = expiration

        self.issuer = issuer
    
    def build(self, action, log_event={}):
        payload = {
            'token': self.token,
            'iat': int(self.timestamp.timestamp()),
            'tid': self.transaction_id,
        }
        if self.issuer:
            payload['iss'] = self.issuer
        if self.expiration:
            payload['exp'] = int(self.expiration.timestamp())
        
        payload['action'] = action
        
        force_disable_parameters = get_force_disable_parameters()
        log_event['force_disable_parameters'] = force_disable_parameters
        if self.enable_output_parameters:
            if action['type'] == 'post':
                pass # POST actions are parameterized by the POST body
            elif force_disable_parameters:
                log_event['enable_parameter_conflict'] = True
                raise ParametersDisabled('Parameters are disabled')
            else:
                log_event['parameters_enabled'] = True
                payload['param'] = True
        
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
        except aws_encryption_sdk.exceptions.GenerateKeyError as e:
            # This can happen if the key policy does not allow the sfn-callback-urls IAM role
            # to use the key.
            raise EncryptionFailed(f'Failed to create DEK; check your key policy ({str(e)})')
        except aws_encryption_sdk.exceptions.AWSEncryptionSDKClientError as e:
            # unexpected, turn into a 500 error
            raise 

        return '2-' + str(base64.urlsafe_b64encode(ciphertext), 'ascii')

def validate_payload_schema(payload):
    try:
        jsonschema.validate(payload, payload_schema)
    except jsonschema.ValidationError as e:
        raise InvalidPayload(f'Failed schema validation ({e})')

def validate_payload_expiration(payload, timestamp=None):
    timestamp = timestamp or datetime.datetime.now()
    if 'exp' in payload:
        exp = datetime.datetime.fromtimestamp(payload['exp'])
        if exp < timestamp:
            raise ExpiredPayload(f'Response expired on {exp.isoformat()}')

def decode_payload(payload, master_key_provider):
    assert isinstance(payload, str)
    parts = payload.split('-', 1)
    if len(parts) != 2:
        raise InvalidPayload('Missing format id')
    
    version, base64_payload = parts

    try:
        binary_payload = base64.urlsafe_b64decode(base64_payload)
    except base64.binascii.Error as e:
        raise InvalidPayload(f'Base64 error ({str(e)})')

    if version == '1':
        # sfn-callback-urls to make an authenticated call on behalf of an
        # unauthenticated caller. With encryption turned off, the caller may pass in
        # a payload that was not created by a create_urls call by an authenticated 
        # caller, and is therefore an opportunity for escalation of privileges.
        # Therefore, we only process unencrypted payloads if encryption is actually disabled.
        if master_key_provider:
            raise EncryptionRequired('Only encrypted payloads are supported')
        try:
            loaded_payload = json.loads(binary_payload)
        except json.JSONDecodeError as e:
            raise InvalidPayload(f'JSON error ({str(e)})')
    elif version == '2':
        if not master_key_provider:
            raise DecryptionUnsupported('No key found')
        try:
            decrypted_payload, decrypted_header = aws_encryption_sdk.decrypt(
                source=binary_payload,
                key_provider=master_key_provider
            )
        except aws_encryption_sdk.exceptions.AWSEncryptionSDKClientError as e:
            raise InvalidPayload(f'Decryption error ({type(e).__name__}:{str(e)})')
        
        try:
            loaded_payload = json.loads(decrypted_payload)
        except json.JSONDecodeError as e:
            raise InvalidPayload(f'JSON error ({str(e)})')
    else:
        raise InvalidPayload('Unknown format id')

    return loaded_payload
