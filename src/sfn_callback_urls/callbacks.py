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

from .payload import InvalidPayloadError

ACTION_NAME_QUERY_PARAM = 'action'
ACTION_TYPE_QUERY_PARAM = 'type'
PAYLOAD_QUERY_PARAM = 'data'

CALLBACK_PATH = 'respond'

def get_url(action_name, action_type, payload,
        api_id,
        stage_id,
        region,
        log_event={}):
    
    query = urllib.parse.urlencode([
        (ACTION_NAME_QUERY_PARAM, action_name),
        (ACTION_TYPE_QUERY_PARAM, action_type),
        (PAYLOAD_QUERY_PARAM, payload)
    ])

    url_template = 'https://{api_id}.execute-api.{region}.amazonaws.com/{stage_id}/{path}?{query}'

    return url_template.format(
        api_id=api_id,
        region=region,
        stage_id=stage_id,
        path=CALLBACK_PATH,
        query=query,
    )

def load_from_request(event):
    query_parameters = event['queryStringParameters']

    action_name = query_parameters.get(ACTION_NAME_QUERY_PARAM)
    action_type = query_parameters.get(ACTION_TYPE_QUERY_PARAM)

    if PAYLOAD_QUERY_PARAM not in query_parameters:
        raise InvalidPayloadError('Missing payload')
    
    payload = query_parameters[PAYLOAD_QUERY_PARAM]

    parameters = {}
    for k, v in query_parameters.items():
        if k not in [ACTION_NAME_QUERY_PARAM, ACTION_TYPE_QUERY_PARAM, PAYLOAD_QUERY_PARAM]:
            parameters[k] = v
    
    return action_name, action_type, payload, parameters

