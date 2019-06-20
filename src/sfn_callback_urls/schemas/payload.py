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

from .action import action_schema

# This looks a lot like a JWT, because that's what the original implementation
# used. But since we're encrypting the payload anyway, there isn't much utility
# to signing it, and if encryption is disabled, there's no key to sign it with
# either.

skeleton = lambda: {
    'token': '<token from Step Functions>',
    'iss': '<set to the Lambda function arn>',
    'iat': 0, # unix timestamp
    'tid': '', # transaction id
    'exp': 0, # expiration unix timestamp
    'action': {}, # the action definition
    'param': False, # optional, enable the caller to pass parameters for the output
}

payload_schema = {
    "type": "object",
    "properties": {
        "iss": {"type": "string"},
        "iat": {"type": "number"},
        "tid": {"type": "string"},
        "exp": {"type": "number"},
        "token": {"type": "string"},
        "action": action_schema,
        "param": {
            "type": "boolean"
        }
    },
    "required": ["token", "action"],
}
