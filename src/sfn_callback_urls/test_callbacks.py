import pytest

from sfn_callback_urls.callbacks import (
    get_url,
    load_from_request, InvalidPayloadError
)

@pytest.mark.xfail
def test_load_from_request():
    raise NotImplementedError
