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

skeleton = lambda: {
    "token": "<from Step Functions>",
    "actions": [
        {
            "name": "<action name 1>",
            "type": "success",
            "output": {
                "<user>": "<defined>"
            },
            "response": {
                "redirect": "https://example.com"
            }
        },
        {
            "name": "<action name 2>",
            "type": "failure",
            "error": "MyErrorCode",
            "cause": "User-friendly message",
        },
        {
            "name": "<action name 3>",
            "type": "heartbeat",
            "response": {
                "json": {
                    "ekg": "thump_thump"
                },
                "html": "<html>thump thump</html>"
            }
        }
    ],
    "expiration": "<RFC3339-formatted datetime>",
    "enable_output_parameters": False,
}

create_urls_input_schema = {
    "type": "object",
    "properties": {
        "token": {
            "type": "string"
        },
        "actions": {
            "type": "array",
            "items": action_schema,
            "minItems": 1,
        },
        "expiration": {
            "type": "string",
            "format": "date-time"
        },
        "enable_output_parameters": {
            "type": "boolean"
        },
        "base_url": {
            "oneOf": [
                {
                    "type": "object",
                    "properties": {
                        "api_id": {
                            "type": "string"
                        },
                        "stage": {
                            "type": "string"
                        },
                        "region": {
                            "type": "string",
                        }
                    },
                    "required": ["api_id", "stage"]
                },
                {
                    "type": "string",
                    "format": "uri"
                }
            ]
        }
    },
    "required": ["token", "actions"],
    "additionalProperties": False
}
