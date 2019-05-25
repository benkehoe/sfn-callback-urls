import os
import sys
import json

class RequestError(Exception):
    def __init__(self, message):
        self._message = message

    def code(self):
        return self.__class__.__name__
    
    def message(self):
        return self._message

    def __str__(self):
        return f'{self.code()}:{self.message()}'

class ParametersDisabledError(RequestError):
    pass

DISABLE_PARAMETERS_ENV_VAR_NAME = 'DISABLE_OUTPUT_PARAMETERS'
def get_force_disable_parameters():
    force_disable_parameters = False
    if DISABLE_PARAMETERS_ENV_VAR_NAME in os.environ:
        value = os.environ[DISABLE_PARAMETERS_ENV_VAR_NAME]
        print('got value', value)
        if value.lower() not in ['0', 'false', '1', 'true']:
            print(f'Invalid value for {DISABLE_PARAMETERS_ENV_VAR_NAME}: {value}', file=sys.stderr)
        force_disable_parameters = value.lower() in ['1', 'true']
    return force_disable_parameters

def send_log_event(log_event):
    print('*** sending log event')
    print(json.dumps(log_event))
