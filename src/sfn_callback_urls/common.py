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
import json

def is_verbose():
    """Check before debug print statements. Too lazy to go full logger"""
    return os.environ.get('VERBOSE', '').lower() in ['1', 'true']

def _get_disable_param(name):
    return_value = False
    if name in os.environ:
        value = os.environ[name]
        if value.lower() not in ['0', 'false', '1', 'true']:
            print(f'Invalid value for {name}: {value}', file=sys.stderr)
        return_value = value.lower() not in ['0', 'false']
    return return_value

DISABLE_PARAMETERS_ENV_VAR_NAME = 'DISABLE_OUTPUT_PARAMETERS'
def get_force_disable_parameters():
    """Check for the env var that we'll use to prevent parameterizing the callback fields"""
    return _get_disable_param(DISABLE_PARAMETERS_ENV_VAR_NAME)

DISABLE_POST_ACTION_ENV_VAR_NAME = 'DISABLE_POST_ACTIONS'
def get_disable_post_actions():
    """Check for the env var that we'll use to prevent post actions"""
    return _get_disable_param(DISABLE_POST_ACTION_ENV_VAR_NAME)

def send_log_event(log_event: dict):
    """Dump the log event to stdout, Lambda will put it in CloudWatch"""
    print(json.dumps(log_event))

def get_header(request: dict, name: str):
    """Get a header from the request payload sent by API Gateway proxy integration to Lambda.
    Does not deal with multi-value headers, but that's fine for this app"""
    for key in request['headers']:
        if key.lower() == name.lower():
            return request['headers'][key]
    return None
