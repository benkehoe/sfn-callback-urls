import pytest
import uuid
import datetime
import json

from sfn_callback_urls.payload import (
    PayloadBuilder,
    validate_payload_schema, InvalidPayloadError,
    validate_payload_expiration, ExpiredPayloadError,
    encode_payload,
    decode_payload
)
from sfn_callback_urls.common import DISABLE_PARAMETERS_ENV_VAR_NAME, ParametersDisabledError

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
    
    an = 'foo'
    at = 'success'
    ad = {'output': {'bar': 'baz'}}

    pb = PayloadBuilder(tid, ts, token)
    payload = pb.build(an, at, ad)

    assert payload['tid'] == tid
    assert payload['iat'] == int(ts.timestamp())
    assert payload['token'] == token

    assert payload['name'] == an
    assert payload['act'] == at
    assert_dicts_equal(payload['data'], ad)

    validate_payload_schema(payload)

def test_build_exp():
    now = datetime.datetime.now()

    tid = uuid.uuid4().hex
    ts = now - datetime.timedelta(seconds=4)
    exp = now - datetime.timedelta(seconds=2)
    token = uuid.uuid4().hex
    
    an = 'foo'
    at = 'success'
    ad = {'output': {'bar': 'baz'}}

    pb = PayloadBuilder(tid, ts, token, expiration=exp)
    payload = pb.build(an, at, ad)

    assert payload['tid'] == tid
    assert payload['iat'] == int(ts.timestamp())
    assert payload['exp'] == int(exp.timestamp())
    assert payload['token'] == token

    assert payload['name'] == an
    assert payload['act'] == at
    assert_dicts_equal(payload['data'], ad)

    validate_payload_schema(payload)

    with pytest.raises(ExpiredPayloadError):
        validate_payload_expiration(payload, now)

def test_build_parameters(monkeypatch):
    tid = uuid.uuid4().hex
    ts = datetime.datetime.now()
    token = uuid.uuid4().hex
    
    an = 'foo'
    at = 'success'
    ad = {'output': {'bar': 'baz'}}

    pb = PayloadBuilder(tid, ts, token, enable_output_parameters=True)

    with monkeypatch.context() as mp:
        mp.delenv(DISABLE_PARAMETERS_ENV_VAR_NAME, raising=False)

        payload = pb.build(an, at, ad)
    
    with monkeypatch.context() as mp:
        mp.setenv(DISABLE_PARAMETERS_ENV_VAR_NAME, 'true')

        with pytest.raises(ParametersDisabledError):
            payload = pb.build(an, at, ad)

def test_validate_payload_basic():
    payload_skeleton = {
        'iss': 'issuer',
        'iat': 0,
        'tid': 'asdf',
        'exp': 0,
        'token': 'jkljkl',
        'name': 'foo',
        'par': False,
    }

    # missing actions
    with pytest.raises(InvalidPayloadError):
        validate_payload_schema(payload_skeleton)

    payload = payload_skeleton.copy()
    payload['act'] = 'success'
    with pytest.raises(InvalidPayloadError): # missing data
        validate_payload_schema(payload)
    payload['data'] = {}
    with pytest.raises(InvalidPayloadError): # missing output
        validate_payload_schema(payload)
    payload['data']['output'] = 'foo'
    with pytest.raises(InvalidPayloadError): # output isn't object
        validate_payload_schema(payload)
    payload['data']['output'] = {}
    validate_payload_schema(payload)

    payload = payload_skeleton.copy()
    payload['act'] = 'failure'
    with pytest.raises(InvalidPayloadError): # missing data
        validate_payload_schema(payload)
    payload['data'] = {}
    validate_payload_schema(payload)

    payload = payload_skeleton.copy()
    payload['act'] = 'heartbeat'
    with pytest.raises(InvalidPayloadError): # missing data
        validate_payload_schema(payload)
    payload['data'] = {}
    validate_payload_schema(payload)

    payload_skeleton['act'] = 'heartbeat'

    payload = payload_skeleton.copy()
    payload['foo'] = 'bar'

    with pytest.raises(InvalidPayloadError):
        validate_payload_schema(payload)

@pytest.mark.xfail
def test_extended_schema_validation():
    raise NotImplementedError

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
        'name': 'foo',
        'act': 'success',
        'data': {
            'output': {}
        },
        'par': False,
    }

    validate_payload_schema(payload)

    encoded_payload = encode_payload(payload, None)

    decoded_payload = decode_payload(encoded_payload, None)

    validate_payload_schema(decoded_payload)

    assert_dicts_equal(payload, decoded_payload)

@pytest.mark.xfail
def test_encrypted_payload_coding():
    raise NotImplementedError
