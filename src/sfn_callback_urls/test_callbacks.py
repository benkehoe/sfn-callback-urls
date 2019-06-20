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
import json
from copy import deepcopy

from sfn_callback_urls.callbacks import (
    get_header,
    get_api_gateway_url,
    get_url,
    load_from_request, InvalidPayload,
    format_output, OutputFormatting,
    format_response
)

def assert_dicts_equal(a, b):
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)

get_request = lambda: {
    "resource": "/urls",
    "path": "/urls",
    "httpMethod": "POST",
    "headers": {
        "cache-control": "no-cache",
        "CloudFront-Forwarded-Proto": "https",
        "CloudFront-Is-Desktop-Viewer": "true",
        "CloudFront-Is-Mobile-Viewer": "false",
        "CloudFront-Is-SmartTV-Viewer": "false",
        "CloudFront-Is-Tablet-Viewer": "false",
        "CloudFront-Viewer-Country": "US",
        "Content-Type": "application/json",
        "headerName": "headerValue",
        "Host": "gy415nuibc.execute-api.us-east-1.amazonaws.com",
        "Postman-Token": "9f583ef0-ed83-4a38-aef3-eb9ce3f7a57f",
        "User-Agent": "PostmanRuntime/2.4.5",
        "Via": "1.1 d98420743a69852491bbdea73f7680bd.cloudfront.net (CloudFront)",
        "X-Amz-Cf-Id": "pn-PWIJc6thYnZm5P0NMgOUglL1DYtl0gdeJky8tqsg8iS_sgsKD1A==",
        "X-Forwarded-For": "54.240.196.186, 54.182.214.83",
        "X-Forwarded-Port": "443",
        "X-Forwarded-Proto": "https"
    },
    "multiValueHeaders":{
        'cache-control':[
        "no-cache"
        ],
        'CloudFront-Forwarded-Proto':[
        "https"
        ],
        'CloudFront-Is-Desktop-Viewer':[
        "true"
        ],
        'CloudFront-Is-Mobile-Viewer':[
        "false"
        ],
        'CloudFront-Is-SmartTV-Viewer':[
        "false"
        ],
        'CloudFront-Is-Tablet-Viewer':[
        "false"
        ],
        'CloudFront-Viewer-Country':[
        "US"
        ],
        '':[
        ""
        ],
        'Content-Type':[
        "application/json"
        ],
        'headerName':[
        "headerValue"
        ],
        'Host':[
        "gy415nuibc.execute-api.us-east-1.amazonaws.com"
        ],
        'Postman-Token':[
        "9f583ef0-ed83-4a38-aef3-eb9ce3f7a57f"
        ],
        'User-Agent':[
        "PostmanRuntime/2.4.5"
        ],
        'Via':[
        "1.1 d98420743a69852491bbdea73f7680bd.cloudfront.net (CloudFront)"
        ],
        'X-Amz-Cf-Id':[
        "pn-PWIJc6thYnZm5P0NMgOUglL1DYtl0gdeJky8tqsg8iS_sgsKD1A=="
        ],
        'X-Forwarded-For':[
        "54.240.196.186, 54.182.214.83"
        ],
        'X-Forwarded-Port':[
        "443"
        ],
        'X-Forwarded-Proto':[
        "https"
        ]
    },
    "queryStringParameters": {
    },
    "multiValueQueryStringParameters":{
        
    },
    "pathParameters": {
    },
    "stageVariables": {
    },
    "requestContext": {
        "accountId": "12345678912",
        "resourceId": "roq9wj",
        "stage": "testStage",
        "requestId": "deef4878-7910-11e6-8f14-25afc3e9ae33",
        "identity": {
            "cognitoIdentityPoolId": None,
            "accountId": None,
            "cognitoIdentityId": None,
            "caller": None,
            "apiKey": None,
            "sourceIp": "192.168.196.186",
            "cognitoAuthenticationType": None,
            "cognitoAuthenticationProvider": None,
            "userArn": None,
            "userAgent": "PostmanRuntime/2.4.5",
            "user": None
        },
        "resourcePath": "/{proxy+}",
        "httpMethod": "POST",
        "apiId": "gy415nuibc"
    },
    "body": "",
    "isBase64Encoded": False
}

def test_format_output_simple():
    output = '$foo'
    formatted = format_output(output, None)
    assert formatted == output

    formatted = format_output(output, {'foo': 'bar'})
    assert formatted == 'bar'

    with pytest.raises(OutputFormatting):
        format_output(output, {})

    output = {'$foo': '$bar'}
    formatted = format_output(output, None)
    assert formatted == output

    formatted = format_output(output, {'foo': 'oof', 'bar': 'rab'})
    assert_dicts_equal(formatted, {'oof': 'rab'})

    with pytest.raises(OutputFormatting):
        format_output(output, {})


@pytest.mark.xfail
def test_load_from_request():
    raise NotImplementedError

def test_format_response():
    payload = {'foo': 'bar'}

    req = get_request()
    resp = format_response(200, payload, req, {}, None)

    assert resp['statusCode'] == 200
    assert get_header(resp, 'content-type') == 'application/json'

    req = get_request()
    req['headers']['Accept'] = 'text/plain'

    resp = format_response(500, payload, req, {}, None)
    assert resp['statusCode'] == 500
    assert get_header(resp, 'content-type') == 'text/plain'

    body = json.loads(resp['body'])
    assert_dicts_equal(payload, body)

    req = get_request()
    req['headers']['Accept'] = 'text/html, application/json'

    redirect = 'https://example.com'
    response_spec = {
        'redirect': redirect
    }

    resp = format_response(200, payload, req, response_spec, None)

    assert resp['statusCode'] == 303
    assert get_header(resp, 'location') == redirect

    resp = format_response(500, payload, req, {}, None)

    assert resp['statusCode'] == 500
    assert get_header(resp, 'content-type') == 'text/html'

