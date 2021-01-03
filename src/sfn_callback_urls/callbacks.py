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

import urllib
import json
import string

from .exceptions import (
    ReturnHttpResponse,
    OutputFormatting,
    InvalidPayload,
    InvalidPostActionBody
)
from .common import get_header, is_verbose

ACTION_NAME_QUERY_PARAM = 'action'
ACTION_TYPE_QUERY_PARAM = 'type'
PAYLOAD_QUERY_PARAM = 'data'

CALLBACK_PATH = 'respond'

def get_api_gateway_url(api_id, stage_id, region):
    url_template = 'https://{api_id}.execute-api.{region}.amazonaws.com/{stage_id}'

    return url_template.format(
        api_id=api_id,
        region=region,
        stage_id=stage_id
    )

def get_url(base_url, action_name, action_type, payload, log_event={}):
    if base_url.endswith('/'):
        base_url = base_url[:-1]

    query = urllib.parse.urlencode([
        (ACTION_NAME_QUERY_PARAM, action_name),
        (ACTION_TYPE_QUERY_PARAM, action_type),
        (PAYLOAD_QUERY_PARAM, payload)
    ])

    url_template = '{base_url}/{path}?{query}'

    return url_template.format(
        base_url=base_url,
        path=CALLBACK_PATH,
        query=query,
    )

def load_from_request(request):
    query_parameters = request['queryStringParameters']

    # these don't have to be present
    action_name = query_parameters.get(ACTION_NAME_QUERY_PARAM)
    action_type = query_parameters.get(ACTION_TYPE_QUERY_PARAM)

    if PAYLOAD_QUERY_PARAM not in query_parameters:
        raise InvalidPayload('Missing payload')

    payload = query_parameters[PAYLOAD_QUERY_PARAM]

    # for parameterizing the output, grab everything in the
    # query string except the payload.
    parameters = {}
    for k, v in query_parameters.items():
        if k not in [PAYLOAD_QUERY_PARAM]:
            parameters[k] = v

    return action_name, action_type, payload, parameters

def prepare_method_params(action, parameters, log_event={}):
    action_type = action['type']
    method_params = {}
    if action_type == 'success':
        output = action.get('output', {})
        output = format_output(output, parameters)
        method_params['output'] = json.dumps(output)
    elif action_type == 'failure':
        for key in ['error', 'cause']:
            if key in action:
                method_params[key] = format_output(action[key], parameters)

    return method_params

def format_output(output, parameters):
    # Apply string templating to all strings contained within output (recursively)
    if parameters is None:
        return output

    if isinstance(output, dict):
        return dict(
            (
                format_output(key, parameters),
                format_output(value, parameters)
            ) for key, value in output.items()
        )
    elif isinstance(output, list):
        return list(format_output(item, parameters) for item in output)
    elif isinstance(output, str):
        try:
            return string.Template(output).substitute(parameters)
        except (IndexError, KeyError) as e:
            raise OutputFormatting(f'Formatting the output with the parameters failed ({e})')
    return output

HTML_TEMPLATE = """<html>
<head>
<title>{message}</title>
<body>
{message}<br>
Details:
<pre>
{json}
</pre>
</body>
</html>
"""

def format_response(status_code, response, request, response_spec, parameters, log_event={}):
    if is_verbose():
        print(f'Response spec: {json.dumps(response_spec)}')
    if 'redirect' in response_spec:
        log_event['redirect'] = response_spec['redirect']
        return {
            "statusCode": 303,
            "headers": {
                "Location": response_spec['redirect']
            }
        }

    if 'json' in response_spec:
        json_override = True
        json_body = json.dumps(format_output(response_spec['json'], parameters))
    else:
        json_override = False
        json_body = json.dumps(response)

    if 'html' in response_spec:
        html_override = True
        html_body = format_output(response_spec['html'], parameters)
    else:
        html_override = False
        if status_code == 200:
            message = "Response accepted!"
        else:
            message = "Response rejected!"
        html_body = HTML_TEMPLATE.format(
            message = message,
            json=json.dumps(response, indent=2)
        )

    if 'text' in response_spec:
        text_override = True
        text_body = format_output(response_spec['text'], parameters)
    else:
        text_override = False
        text_body = json.dumps(response, indent=2)

    content_type = None

    accept = get_header(request, 'Accept')
    if accept:
        for value in accept.split(','):
            value = value.split(';')[0].strip()
            if value in ['application/json', 'text/html', 'text/plain']:
                content_type = value
                break
    log_event['accept'] = content_type

    if content_type is None:
        content_type = 'application/json'

    if content_type == 'application/json':
        if json_override:
            log_event['response_override'] = 'json'
        body = json_body
    elif content_type == 'text/html':
        if html_override:
            log_event['response_override'] = 'html'
        body = html_body
    elif content_type == 'text/plain':
        if text_override:
            log_event['response_override'] = 'text'
        body = text_body

    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': content_type,
        },
        'body': body
    }


