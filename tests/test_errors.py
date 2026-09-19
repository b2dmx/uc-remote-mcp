"""Failures should say what the remote said.

Every diagnosis during integration work came from the API's own error body --
"Driver not connected", "Setup data not provided for field: api_key". httpx's
default message is just a status code and a URL, which reads as "something went
wrong" and sends people guessing.
"""

import httpx
import pytest

from uc_remote_mcp.client.rest import UCClient


def response(status: int, body=None, text: str = "") -> httpx.Response:
    req = httpx.Request("POST", "http://remote/api/intg/setup")
    if body is not None:
        return httpx.Response(status, json=body, request=req)
    return httpx.Response(status, text=text, request=req)


class TestRaise:
    def test_success_does_not_raise(self):
        assert UCClient._raise(response(200, {"ok": True})) is None

    def test_code_and_message_both_appear(self):
        with pytest.raises(httpx.HTTPStatusError) as e:
            UCClient._raise(
                response(503, {"code": "SERVICE_UNAVAILABLE", "message": "Driver not connected"})
            )
        assert "SERVICE_UNAVAILABLE" in str(e.value)
        assert "Driver not connected" in str(e.value)

    def test_message_alone_is_enough(self):
        with pytest.raises(httpx.HTTPStatusError) as e:
            UCClient._raise(response(400, {"message": "Setup data not provided for field: api_key"}))
        assert "api_key" in str(e.value)

    def test_method_and_path_are_named(self):
        with pytest.raises(httpx.HTTPStatusError) as e:
            UCClient._raise(response(404, {"code": "NOT_FOUND"}))
        assert "POST" in str(e.value) and "/api/intg/setup" in str(e.value)

    def test_non_json_body_still_says_something(self):
        with pytest.raises(httpx.HTTPStatusError) as e:
            UCClient._raise(response(500, text="upstream exploded"))
        assert "upstream exploded" in str(e.value)

    def test_empty_body_does_not_break_it(self):
        with pytest.raises(httpx.HTTPStatusError) as e:
            UCClient._raise(response(411, text=""))
        assert "411" in str(e.value)

    def test_the_response_is_still_attached(self):
        # Callers branch on the status -- a 404 means "finished" to a setup
        # flow, and 503 means "retry" -- so it has to survive.
        with pytest.raises(httpx.HTTPStatusError) as e:
            UCClient._raise(response(404, {"code": "NOT_FOUND"}))
        assert e.value.response.status_code == 404
