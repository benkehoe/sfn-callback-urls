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

from .action import response_schema

schema = {
    "type": "object",
    "properties": {
        "iss": {"type": "string"},
        "iat": {"type": "number"},
        "tid": {"type": "string"},
        "exp": {"type": "number"},
        "token": {"type": "string"},
        "name": {
            "type": "string"
        },
        "act": {
            "type": "string",
            "enum": ["success", "failure", "heartbeat"]
        },
        "data": {
            "type": "object"
        },
        "par": {
            "type": "boolean"
        },
        "resp": response_schema
    },
    "required": ["token", "name", "act", "data"],
    "allOf": [
        {
            "if": {
                "properties": { "act": { "const": "success" } }
            },
            "then": {
                "properties": {
                    "data": {
                        "type": "object",
                        "properties": {
                            "output": {
                                "type": "object"
                            }
                        },
                        "required": ["output"]
                    },
                    
                },
                "required": ["data"],
            }
        },
        {
            "if": {
                "properties": { "act": { "const": "failure" } }
            },
            "then": {
                "properties": {
                    "data": {
                        "type": "object",
                        "properties": {
                            "error": {
                                "type": "string"
                            },
                            "cause": {
                                "type": "string"
                            },
                        }
                    }
                }
            }
        }
    ]
}
