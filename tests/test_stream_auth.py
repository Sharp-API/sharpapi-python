"""SSE credentials stay in headers across logging, errors and filter encoding."""

import logging
import traceback

import httpx
import pytest
import respx

from sharpapi import SharpAPI
from sharpapi._base import AuthMethod
from sharpapi.exceptions import SharpAPIError

KEY = "audit-dummy-stream-secret"


@pytest.mark.parametrize("auth_method", ["x-api-key", "bearer"])
def test_stream_auth_uses_headers_without_logging_key(auth_method: AuthMethod, caplog):
    with SharpAPI(KEY, auth_method=auth_method) as client, respx.mock as router:
        route = router.get("https://api.sharpapi.io/api/v1/stream").respond(
            200, text='event: snapshot\ndata: {"ok": true}\n\n'
        )
        with caplog.at_level(logging.INFO, logger="httpx"):
            assert list(client.stream.odds().iter_events()) == [("snapshot", {"ok": True})]
        request = route.calls[0].request
        assert KEY not in caplog.text
        assert "api_key" not in request.url.params
        if auth_method == "bearer":
            assert request.headers["Authorization"] == f"Bearer {KEY}"
            assert "X-API-Key" not in request.headers
        else:
            assert request.headers["X-API-Key"] == KEY
            assert "Authorization" not in request.headers


@pytest.mark.parametrize("mode", ["connect", "iter_events"])
@pytest.mark.parametrize("status", [401, 403])
def test_stream_error_traceback_does_not_expose_key(mode, status):
    with SharpAPI(KEY) as client, respx.mock as router:
        router.get("https://api.sharpapi.io/api/v1/stream").respond(status)
        stream = client.stream.odds()
        with pytest.raises((SharpAPIError, httpx.HTTPStatusError)) as error:
            if mode == "connect":
                stream.connect()
            else:
                list(stream.iter_events())
        assert KEY not in "".join(traceback.format_exception(error.value))


def test_stream_filters_cannot_inject_auth_query_or_fragment():
    value = "nba&api_key=injected#fragment +%"
    with SharpAPI(KEY) as client, respx.mock as router:
        route = router.get("https://api.sharpapi.io/api/v1/stream").respond(200)
        assert list(client.stream.odds(league=value).iter_events()) == []
        request = route.calls[0].request
        assert request.url.params["league"] == value
        assert "api_key" not in request.url.params
        assert not request.url.fragment


def test_event_id_cannot_inject_auth_query():
    with SharpAPI(KEY) as client, respx.mock as router:
        route = router.get(host="api.sharpapi.io").respond(200)
        assert list(client.stream.event("event?api_key=injected#fragment").iter_events()) == []
        request = route.calls[0].request
        assert "api_key" not in request.url.params
        assert not request.url.fragment
        assert b"event%3Fapi_key%3Dinjected%23fragment" in request.url.raw_path
