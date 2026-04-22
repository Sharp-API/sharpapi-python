"""SSE streaming client for SharpAPI real-time data."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Iterator
from typing import Any

import httpx

from .exceptions import AuthenticationError, StreamError

logger = logging.getLogger("sharpapi.stream")

EventHandler = Callable[[Any], None]


class EventStream:
    """Server-Sent Events (SSE) stream client.

    Connects to the SharpAPI streaming endpoint and dispatches typed events
    to registered handlers.

    Example::

        stream = client.stream.opportunities(league="nba")

        @stream.on("ev:detected")
        def handle_ev(data):
            print(f"+EV: {data}")

        @stream.on("arb:detected")
        def handle_arb(data):
            print(f"Arb: {data}")

        stream.connect()  # Blocks, processing events
    """

    def __init__(
        self,
        url: str,
        headers: dict[str, str],
        timeout: float = 90.0,
        max_reconnects: int = 5,
        default_retry_ms: int = 3000,
    ):
        self._url = url
        self._headers = headers
        self._timeout = timeout
        self._max_reconnects = max_reconnects
        self._handlers: dict[str, list[EventHandler]] = {}
        self._running = False
        self._last_event_id: str | None = None
        # SSE protocol: server sends `retry: <ms>` to advise reconnect delay.
        # SharpAPI emits `retry: 3000`. We honour it for the first few attempts,
        # then switch to exponential backoff capped at 30s if reconnects keep
        # failing — see connect().
        self._retry_ms = default_retry_ms

    def on(self, event_type: str, handler: EventHandler | None = None):
        """Register a handler for an event type. Can be used as a decorator.

        Args:
            event_type: SSE event name (e.g. "ev:detected", "arb:detected",
                "odds:update", "snapshot", "heartbeat", "error")
            handler: Callback receiving parsed event data. If None, returns
                a decorator.

        Example::

            @stream.on("ev:detected")
            def handle_ev(data):
                print(data)

            # Or without decorator:
            stream.on("arb:detected", my_handler)
        """
        if handler is not None:
            self._handlers.setdefault(event_type, []).append(handler)
            return handler

        def decorator(fn: EventHandler) -> EventHandler:
            self._handlers.setdefault(event_type, []).append(fn)
            return fn

        return decorator

    def off(self, event_type: str, handler: EventHandler) -> None:
        """Remove a handler for an event type."""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def _emit(self, event_type: str, data: Any) -> None:
        for handler in self._handlers.get(event_type, []):
            try:
                handler(data)
            except Exception:
                logger.exception("Handler error for event %s", event_type)
        # Also emit to wildcard handlers
        for handler in self._handlers.get("*", []):
            try:
                handler({"type": event_type, "data": data})
            except Exception:
                logger.exception("Wildcard handler error for event %s", event_type)

    def connect(self) -> None:
        """Connect and block, processing events until disconnect() or error.

        Reconnect policy is hybrid: the first ``HONOR_HINT_FOR`` attempts use
        the server's ``retry:`` hint (default 3 s, updated whenever the server
        sends a new value mid-stream). After that we switch to exponential
        backoff capped at 30 s so we don't hammer a persistently broken server.
        """
        self._running = True
        reconnect_attempts = 0
        # Honour the server's retry hint for the first N attempts; after that
        # the failure is probably structural (server down, auth changed, etc.)
        # and the gentler exponential backoff kicks in.
        HONOR_HINT_FOR = 3

        while self._running and reconnect_attempts <= self._max_reconnects:
            try:
                self._stream_loop()
                if not self._running:
                    break
                # Clean server close — reset backoff so a graceful reconnect
                # doesn't carry forward old failure counts.
                reconnect_attempts = 0
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as e:
                reconnect_attempts += 1
                if reconnect_attempts > self._max_reconnects:
                    raise StreamError(
                        f"Max reconnection attempts ({self._max_reconnects}) reached",
                        code="max_reconnects",
                    ) from e  # noqa: B904

                hint_seconds = self._retry_ms / 1000.0
                if reconnect_attempts <= HONOR_HINT_FOR:
                    delay = hint_seconds
                else:
                    # Exponential ramp anchored on the server's hint, capped at 30 s.
                    excess = reconnect_attempts - HONOR_HINT_FOR
                    delay = min(hint_seconds * (2 ** excess), 30.0)

                logger.warning(
                    "Connection lost, reconnecting in %.1fs (attempt %d/%d)",
                    delay,
                    reconnect_attempts,
                    self._max_reconnects,
                )
                time.sleep(delay)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise AuthenticationError(
                        "Invalid API key", code="invalid_api_key", status=401
                    ) from e
                status = e.response.status_code
                raise StreamError(
                    f"HTTP {status}", code="http_error", status=status
                ) from e

    def _stream_loop(self) -> None:
        headers = {**self._headers, "Accept": "text/event-stream"}
        if self._last_event_id:
            headers["Last-Event-ID"] = self._last_event_id

        with httpx.Client(timeout=httpx.Timeout(self._timeout, connect=10.0)) as http:
            with http.stream("GET", self._url, headers=headers) as response:
                response.raise_for_status()
                for event_type, data in _parse_sse(response.iter_lines()):
                    if not self._running:
                        break
                    if event_type == "__retry__":
                        # Server advised a new reconnect delay — store but don't dispatch.
                        self._retry_ms = data
                        continue
                    self._emit(event_type, data)

    def disconnect(self) -> None:
        """Stop the stream."""
        self._running = False

    def iter_events(self) -> Iterator[tuple[str, Any]]:
        """Iterate over events as (event_type, data) tuples.

        Example::

            for event_type, data in stream.iter_events():
                if event_type == "ev:detected":
                    print(data)
        """
        self._running = True
        headers = {**self._headers, "Accept": "text/event-stream"}
        if self._last_event_id:
            headers["Last-Event-ID"] = self._last_event_id

        with httpx.Client(timeout=httpx.Timeout(self._timeout, connect=10.0)) as http:
            with http.stream("GET", self._url, headers=headers) as response:
                response.raise_for_status()
                for event_type, data in _parse_sse(response.iter_lines()):
                    if not self._running:
                        break
                    yield event_type, data


def _parse_sse(lines: Iterator[str]) -> Iterator[tuple[str, Any]]:
    """Parse SSE text stream into (event_type, parsed_data) tuples.

    Yields a synthetic ``("__retry__", int_ms)`` tuple when the server emits a
    ``retry:`` field so the caller can update its reconnect delay.
    """
    event_type = "message"
    data_lines: list[str] = []

    for line in lines:
        if line.startswith("event:"):
            event_type = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())
        elif line.startswith("id:"):
            pass  # Tracked by httpx/EventSource
        elif line.startswith("retry:"):
            try:
                yield "__retry__", int(line[6:].strip())
            except ValueError:
                pass  # Malformed retry: line — ignore.
        elif line == "" and data_lines:
            # End of event
            raw = "\n".join(data_lines)
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw
            yield event_type, parsed
            event_type = "message"
            data_lines = []
