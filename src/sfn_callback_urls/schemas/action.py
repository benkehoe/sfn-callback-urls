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

name_pattern = r"^\w+$"

action_response_schema = {
    "type": "object",
    "properties": {
        "json": {
            "type": "object"
        },
        "html": {
            "type": "string"
        },
        "text": {
            "type": "string"
        },
        "redirect": {
            "type": "string",
            "format": "uri"
        }
    }
}

def _get_action_schema(
        type_schema,
        properties={},
        required=[],
        schema={}):
    ts = {
        "type": "string"
    }
    ts.update(type_schema)
    props = {
        "name": {
            "type": "string",
            "pattern": name_pattern
        },
        "type": ts,
        "response": action_response_schema
    }
    props.update(properties)
    req = ["name", "type"]
    req.extend(required)
    s = {
        "type": "object",
        "properties": props,
        "required": req
    }
    s.update(schema)
    return s

def _get_post_outcome_schema(
        type_schema,
        properties={},
        required=[],
        schema={}):
    p = {
        "schema": {
            "type": "object"
        }
    }
    p.update(properties)
    req = ["schema"]
    req.extend(required)
    return _get_action_schema(
        type_schema,
        properties=p,
        required=req,
        schema=schema
    )

post_outcome_success_schema = _get_post_outcome_schema(
    type_schema={"const": "success"},
    schema={
        "oneOf": [
            {
                "properties": {
                    "output_body": {
                        "const": True,
                    }
                },
                "required": ["output_body"]
            },
            {
                "properties": {
                    "output_path": {
                        "type": "string"
                    }
                },
                "required": ["output_path"]
            },
            {
                "properties": {
                    "output": {}
                },
                "required": ["output"]
            }
        ]
    }
)
post_outcome_failure_schema = _get_post_outcome_schema(
    type_schema={"const": "failure"},
    properties={
        "error": {
            "type": "string"
        },
        "error_path": {
            "type": "string"
        },
        "cause": {
            "type": "string"
        },
        "cause_path": {
            "type": "string"
        }
    },
    schema={
        "allOf": [
            {
                "not": {
                    "required": ["error", "error_path"]
                }
            },
            {
                "not": {
                    "required": ["cause", "cause_path"]
                }
            }
        ]
    }
)
post_outcome_heartbeat_schema = _get_post_outcome_schema(
    type_schema={"const": "heartbeat"}
)

post_outcome_schema = {
    "oneOf": [
        post_outcome_success_schema,
        post_outcome_failure_schema,
        post_outcome_heartbeat_schema
    ]
}

post_action_schema = _get_action_schema(
    type_schema={"const": "post"},
    properties={
        "outcomes": {
            "type": "array",
            "items": post_outcome_schema,
            "minItems": 1
        }
    }
)

success_action_schema = _get_action_schema(
    type_schema={"const": "success"},
    properties={
        "output": {}
    },
    required=["output"]
)

failure_action_schema = _get_action_schema(
    type_schema={"const": "failure"},
    properties={
        "error": {
            "type": "string"
        },
        "cause": {
            "type": "string"
        }
    },
)

heartbeat_action_schema = _get_action_schema(
    type_schema={"const": "heartbeat"}
)

action_schema = {
    "oneOf": [
        success_action_schema,
        failure_action_schema,
        heartbeat_action_schema,
        post_action_schema
    ]
}
