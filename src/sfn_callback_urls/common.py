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
    return os.environ.get('VERBOSE', '').lower() in ['1', 'true']

DISABLE_PARAMETERS_ENV_VAR_NAME = 'DISABLE_OUTPUT_PARAMETERS'
def get_force_disable_parameters():
    force_disable_parameters = False
    if DISABLE_PARAMETERS_ENV_VAR_NAME in os.environ:
        value = os.environ[DISABLE_PARAMETERS_ENV_VAR_NAME]
        if value.lower() not in ['0', 'false', '1', 'true']:
            print(f'Invalid value for {DISABLE_PARAMETERS_ENV_VAR_NAME}: {value}', file=sys.stderr)
        force_disable_parameters = value.lower() not in ['0', 'false']
    return force_disable_parameters

def send_log_event(log_event):
    print(json.dumps(log_event))

def get_header(request, name):
    for key in request['headers']:
        if key.lower() == name.lower():
            return request['headers'][key]
    return None
