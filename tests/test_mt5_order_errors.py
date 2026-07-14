"""The MT5 proxy must surface bridge/broker errors, not fake a success."""
import httpx
import pytest
from fastapi import HTTPException

from app.routers.mt5 import _result_or_raise


class _Resp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_ok_retcode_passes_through():
    body = {"status": "executed", "retcode": 10009, "order": 123, "price": 1.10}
    assert _result_or_raise(_Resp(200, body)) == body


def test_bridge_503_raises():
    with pytest.raises(HTTPException) as ei:
        _result_or_raise(_Resp(503, {"status": "error", "error": "Symbol NQ1! is not available."}))
    assert ei.value.status_code == 502
    assert "NQ1!" in ei.value.detail


def test_status_error_body_raises_even_on_200():
    # The bug: bridge returned 200 with an error body -> used to look like success.
    with pytest.raises(HTTPException) as ei:
        _result_or_raise(_Resp(200, {"status": "error", "error": "No tick data available"}))
    assert ei.value.status_code == 400
    assert "No tick data" in ei.value.detail


def test_bad_broker_retcode_raises():
    with pytest.raises(HTTPException) as ei:
        _result_or_raise(_Resp(200, {"status": "executed", "retcode": 10016, "comment": "Invalid stops"}))
    assert ei.value.status_code == 400
    assert "10016" in ei.value.detail
    assert "Invalid stops" in ei.value.detail


def test_non_json_raises():
    class _Bad:
        status_code = 200

        def json(self):
            raise ValueError("not json")

    with pytest.raises(HTTPException) as ei:
        _result_or_raise(_Bad())
    assert ei.value.status_code == 502
