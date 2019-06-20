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

import json

class BaseError(Exception):
    TYPE = 'GenericError'
    
    def __init__(self, message):
        self._message = message

    def code(self):
        return self.__class__.__name__
    
    def message(self):
        return self._message

    def __str__(self):
        return f'{self.code()}:{self.message()}'

class RequestError(BaseError):
    """Base class for general client-caused 400 errors"""
    TYPE = 'RequestError'

class DuplicateActionName(RequestError):
    pass

class ParametersDisabled(RequestError):
    pass

class OutputFormatting(RequestError):
    pass

class InvalidPayload(RequestError):
    pass

class ExpiredPayload(RequestError):
    pass

class EncryptionFailed(RequestError):
    pass

class DecryptionUnsupported(RequestError):
    pass

class EncryptionRequired(RequestError):
    pass

class InvalidAction(RequestError):
    pass

class InvalidDate(RequestError):
    pass

class ActionMismatched(RequestError):
    pass

class PostActionsDisabled(RequestError):
    pass

class InvalidPostActionOutcome(RequestError):
    pass

class InvalidJsonPath(RequestError):
    pass

class InvalidPostActionBody(RequestError):
    pass

class StepFunctionsError(BaseError):
    """Still a 400 error, but resulting from the call to Step Functions"""
    TYPE = 'StepFunctionsError'

class ReturnHttpResponse(Exception):
    """When processing callbacks, sometimes a direct HTTP response is warranted"""
    TYPE = RequestError.TYPE

    def __init__(self, code, message, status_code, headers={}, body=None):
        self._code = code
        self._message = message
        self.status_code = status_code
        self.headers = headers
        self.body = body
    
    def get_response(self):
        body = ''
        if body is not None:
            body = body if isinstance(body, str) else json.dumps(body)
        return {
            'statusCode': self.status_code,
            'headers': self.headers,
            'body': body
        }

    def code(self):
        return self._code
    
    def message(self):
        return self._message
