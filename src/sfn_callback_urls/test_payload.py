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
import uuid
import datetime
import json
import os

import boto3
import aws_encryption_sdk

from sfn_callback_urls.payload import (
    PayloadBuilder,
    validate_payload_schema, InvalidPayload,
    validate_payload_expiration, ExpiredPayload,
    encode_payload,
    decode_payload, DecryptionUnsupported, EncryptionRequired,
    get_keyring
)
from sfn_callback_urls.exceptions import ParametersDisabled

ENABLE_OUTPUT_PARAMETERS_ENV_NAME = "ENABLE_OUTPUT_PARAMETERS"

PAYLOAD_SKELETON = {
    'iss': 'function name',
    'iat': 0, # unix timestamp
    'tid': '', # transaction id
    'exp': 0, # expiration unix timestamp
    'token': '',
    'name': '', # action_name
    'act': '', # action_type
    'out': {}, # output for the task, for success and optional for failure
    'par': False, # enable the caller to pass parameters for the output
}

def assert_dicts_equal(a, b):
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)

def test_build_basic():
    tid = uuid.uuid4().hex
    ts = datetime.datetime.now()
    token = uuid.uuid4().hex

    action = {
        "name": "foo",
        "type": "success",
        "output": {"bar": "baz"}
    }

    pb = PayloadBuilder(tid, ts, token,
                        request_enable_output_parameters=False,
                        stack_enable_output_parameters=False)
    payload = pb.build(action)

    assert payload['tid'] == tid
    assert payload['iat'] == int(ts.timestamp())
    assert payload['token'] == token

    assert_dicts_equal(payload['action'], action)

    validate_payload_schema(payload)

def test_build_exp():
    now = datetime.datetime.now(datetime.UTC)

    tid = uuid.uuid4().hex
    ts = now - datetime.timedelta(seconds=4)
    exp = now - datetime.timedelta(seconds=2)
    token = uuid.uuid4().hex

    action = {
        "name": "foo",
        "type": "success",
        "output": {"bar": "baz"}
    }

    pb = PayloadBuilder(tid, ts, token, expiration=exp,
                        request_enable_output_parameters=False,
                        stack_enable_output_parameters=False)
    payload = pb.build(action)

    assert payload['tid'] == tid
    assert payload['iat'] == int(ts.timestamp())
    assert payload['exp'] == int(exp.timestamp())
    assert payload['token'] == token

    assert_dicts_equal(payload['action'], action)

    validate_payload_schema(payload)

    with pytest.raises(ExpiredPayload):
        validate_payload_expiration(payload, now)

def test_build_parameters(monkeypatch):
    tid = uuid.uuid4().hex
    ts = datetime.datetime.now(datetime.UTC)
    token = uuid.uuid4().hex

    action = {
        "name": "foo",
        "type": "success",
        "output": {"bar": "baz"}
    }

    pb_enabled = PayloadBuilder(tid, ts, token,
                        request_enable_output_parameters=True,
                        stack_enable_output_parameters=True)

    payload = pb_enabled.build(action)

    pb_disabled = PayloadBuilder(tid, ts, token,
                        request_enable_output_parameters=True,
                        stack_enable_output_parameters=False)

    with pytest.raises(ParametersDisabled):
        payload = pb_disabled.build(action)

def test_validate_payload_basic():
    payload_skeleton = {
        'iss': 'issuer',
        'iat': 0,
        'tid': 'asdf',
        'exp': 0,
        'token': 'jkljkl',
        'action': {
            'name': 'foo',
        },
        'param': False,
    }

    payload = payload_skeleton.copy()
    del payload['action']
    with pytest.raises(InvalidPayload):
        validate_payload_schema(payload_skeleton) # missing action

    payload = payload_skeleton.copy()
    with pytest.raises(InvalidPayload):
        validate_payload_schema(payload_skeleton) # missing action type

    payload = payload_skeleton.copy()
    payload['action']['type'] = 'success'
    with pytest.raises(InvalidPayload): # missing output
        validate_payload_schema(payload)
    payload['action']['output'] = 'foo'
    validate_payload_schema(payload)
    payload['action']['output'] = {}
    validate_payload_schema(payload)

    payload = payload_skeleton.copy()
    payload['action']['type'] = 'failure'
    validate_payload_schema(payload)
    payload['action']['error'] = 'SomeError'
    validate_payload_schema(payload)

    payload = payload_skeleton.copy()
    payload['action']['type'] = 'heartbeat'
    validate_payload_schema(payload)

    payload = payload_skeleton.copy()
    payload['foo'] = 'bar'
    validate_payload_schema(payload) # additional properties are ok

"""
encode decode
- e+d w/o mkp
- e+d w/ mkp
- e w/ mkp, d w/o
- e w/o mkp, d w/
"""

def test_basic_payload_coding():
    payload = {
        'iss': 'issuer',
        'iat': 0,
        'tid': 'asdf',
        'exp': 0,
        'token': 'jkljkl',
        'action': {
            'name': 'foo',
            'type': 'success',
            'output': {}
        },
        'param': False,
        'url': 'https://example.com',
    }

    validate_payload_schema(payload)

    encoded_payload = encode_payload(payload, encryption_client=None, keyring=None)

    decoded_payload = decode_payload(encoded_payload, encryption_client=None, keyring=None)

    validate_payload_schema(decoded_payload)

    assert_dicts_equal(payload, decoded_payload)

@pytest.mark.skipif('KEY_ARN' not in os.environ, reason='Set KEY_ARN env var to test encryption')
def test_encrypted_payload_coding():
    key_arn = os.environ['KEY_ARN']
    session = boto3.Session()

    keyring = get_keyring(session, key_arn)

    client = aws_encryption_sdk.EncryptionSDKClient(commitment_policy=aws_encryption_sdk.CommitmentPolicy.REQUIRE_ENCRYPT_REQUIRE_DECRYPT)

    payload = {
        'iss': 'issuer',
        'iat': 0,
        'tid': 'asdf',
        'exp': 0,
        'token': 'jkljkl',
        'action': {
            'name': 'foo',
            'type': 'success',
            'output': {}
        },
        'param': False,
    }

    validate_payload_schema(payload)

    encoded_payload = encode_payload(payload, encryption_client=client, keyring=keyring)
    assert encoded_payload.startswith('3-')
    decoded_payload = decode_payload(encoded_payload, encryption_client=client, keyring=keyring)
    validate_payload_schema(decoded_payload)
    assert_dicts_equal(payload, decoded_payload)

    encoded_payload = encode_payload(payload, encryption_client=None, keyring=None)
    assert encoded_payload.startswith('1-')
    with pytest.raises(EncryptionRequired):
        decoded_payload = decode_payload(encoded_payload, encryption_client=client, keyring=keyring)

    encoded_payload = encode_payload(payload, encryption_client=client, keyring=keyring)
    assert encoded_payload.startswith('3-')
    with pytest.raises(DecryptionUnsupported):
        decoded_payload = decode_payload(encoded_payload, encryption_client=None, keyring=None)
