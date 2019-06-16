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

import pytest

import sfn_callback_urls.common

def test_force_disable_parameters(monkeypatch):
    var_name = sfn_callback_urls.common.DISABLE_PARAMETERS_ENV_VAR_NAME
    with monkeypatch.context() as mp:
        mp.delenv(var_name, raising=False)
        assert not sfn_callback_urls.common.get_force_disable_parameters()
    with monkeypatch.context() as mp:
        mp.setenv(var_name, '0')
        assert not sfn_callback_urls.common.get_force_disable_parameters()
    with monkeypatch.context() as mp:
        mp.setenv(var_name, 'False')
        assert not sfn_callback_urls.common.get_force_disable_parameters()
    with monkeypatch.context() as mp:
        mp.setenv(var_name, '1')
        assert sfn_callback_urls.common.get_force_disable_parameters()
    with monkeypatch.context() as mp:
        mp.setenv(var_name, 'True')
        assert sfn_callback_urls.common.get_force_disable_parameters()
    with monkeypatch.context() as mp:
        mp.setenv(var_name, 'true')
        assert sfn_callback_urls.common.get_force_disable_parameters()

def test_disable_post_actions(monkeypatch):
    var_name = sfn_callback_urls.common.DISABLE_POST_ACTION_ENV_VAR_NAME
    with monkeypatch.context() as mp:
        mp.delenv(var_name, raising=False)
        assert not sfn_callback_urls.common.get_disable_post_actions()
    with monkeypatch.context() as mp:
        mp.setenv(var_name, '0')
        assert not sfn_callback_urls.common.get_disable_post_actions()
    with monkeypatch.context() as mp:
        mp.setenv(var_name, 'False')
        assert not sfn_callback_urls.common.get_disable_post_actions()
    with monkeypatch.context() as mp:
        mp.setenv(var_name, '1')
        assert sfn_callback_urls.common.get_disable_post_actions()
    with monkeypatch.context() as mp:
        mp.setenv(var_name, 'True')
        assert sfn_callback_urls.common.get_disable_post_actions()
    with monkeypatch.context() as mp:
        mp.setenv(var_name, 'true')
        assert sfn_callback_urls.common.get_disable_post_actions()
