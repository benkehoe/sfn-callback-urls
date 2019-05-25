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
