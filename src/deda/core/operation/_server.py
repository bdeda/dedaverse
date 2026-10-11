# ###################################################################################
#
# Copyright 2025 Ben Deda
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ###################################################################################
"""Localhost HTTP server + background tick loop.

- ``GET  /status`` — JSON health snapshot (tick count, interval, last run).
- ``POST /tick``   — force an immediate tick (used in dev / tests).

The tick loop runs in a daemon thread. Each tick:

1. Calls :func:`~deda.core.operation._tasks.discover_tasks`.
2. Filters via :func:`~deda.core.operation._tasks.is_ready_to_run`.
3. Composes a prompt with :func:`~deda.core.operation._prompts.compose_prompt`.
4. Dispatches it through :class:`~deda.core.operation._runner.CopilotRunner`.

Exceptions in any of these steps are logged but do not stop the loop —
the next tick proceeds as usual.
"""

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from . import _config
from ._prompts import compose_prompt
from ._runner import CopilotRunner
from ._tasks import Task, discover_tasks, is_ready_to_run

__all__ = ['OperationServer', 'start_server']


log = logging.getLogger(__name__)


@dataclass
class _Status:
    running: bool = False
    tick_count: int = 0
    interval_sec: int = 0
    last_tick_at: str | None = None
    last_tick_dispatched: int = 0
    last_error: str | None = None
    dispatch_log: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self))


class OperationServer:
    """Embeddable loop + HTTP server.

    Separate from :func:`start_server` so tests can drive single ticks
    directly without binding a socket.
    """

    def __init__(
        self,
        runner: CopilotRunner | None = None,
        discover: Callable[[], list[Task]] = discover_tasks,
        ready: Callable[[Task], bool] = lambda t: is_ready_to_run(t),
        interval_sec: int | None = None,
    ) -> None:
        self._runner = runner if runner is not None else CopilotRunner()
        self._discover = discover
        self._ready = ready
        self._interval_sec = interval_sec if interval_sec is not None else _config.TICK_INTERVAL_SEC
        self._stop = threading.Event()
        self._loop_thread: threading.Thread | None = None
        self._http: ThreadingHTTPServer | None = None
        self._http_thread: threading.Thread | None = None
        self._status = _Status(interval_sec=self._interval_sec)
        self._lock = threading.Lock()

    @property
    def status(self) -> _Status:
        with self._lock:
            return _Status(**asdict(self._status))

    def tick_once(self) -> int:
        """Run one pass of the loop. Returns the number of tasks dispatched."""
        dispatched = 0
        try:
            tasks = self._discover()
        except Exception as err:  # discovery is user-pluggable; never let it crash the loop
            log.exception('operation: discover_tasks failed: %s', err)
            with self._lock:
                self._status.last_error = f'discover: {err}'
            return 0

        for task in tasks:
            try:
                if not self._ready(task):
                    continue
                prompt = compose_prompt(task)
                log.info('operation: dispatching task %s (%s)', task.id, task.title)
                result = self._runner.run(prompt)
                if not result.ok:
                    log.warning(
                        'operation: task %s copilot returncode=%d stderr=%s',
                        task.id,
                        result.returncode,
                        result.stderr.strip()[:200],
                    )
                dispatched += 1
                with self._lock:
                    self._status.dispatch_log.append(f'{task.id}:{result.returncode}')
                    # Bounded — we don't keep forever.
                    self._status.dispatch_log = self._status.dispatch_log[-50:]
            except Exception as err:
                log.exception('operation: task %s failed: %s', task.id, err)
                with self._lock:
                    self._status.last_error = f'task {task.id}: {err}'

        with self._lock:
            self._status.tick_count += 1
            self._status.last_tick_at = datetime.now(timezone.utc).isoformat()
            self._status.last_tick_dispatched = dispatched
        return dispatched

    def _loop(self) -> None:
        log.info('operation: loop started (interval=%ds)', self._interval_sec)
        while not self._stop.is_set():
            self.tick_once()
            # Event.wait returns True when set — lets stop() interrupt the sleep.
            if self._stop.wait(self._interval_sec):
                break
        log.info('operation: loop stopped')

    def start(self, host: str | None = None, port: int | None = None) -> tuple[str, int]:
        """Bind the HTTP server and start the loop thread. Returns (host, port)."""
        if self._http is not None:
            raise RuntimeError('OperationServer already started')
        bind_host = host if host is not None else _config.HOST
        bind_port = port if port is not None else _config.PORT

        handler = _make_handler(self)
        self._http = ThreadingHTTPServer((bind_host, bind_port), handler)
        actual_host, actual_port = self._http.server_address[0], self._http.server_address[1]

        with self._lock:
            self._status.running = True

        self._http_thread = threading.Thread(
            target=self._http.serve_forever, name='operation-http', daemon=True
        )
        self._http_thread.start()

        self._stop.clear()
        self._loop_thread = threading.Thread(
            target=self._loop, name='operation-loop', daemon=True
        )
        self._loop_thread.start()

        log.info('operation: listening on http://%s:%d', actual_host, actual_port)
        return actual_host, int(actual_port)

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the loop to stop, close the HTTP listener, join threads."""
        self._stop.set()
        if self._http is not None:
            self._http.shutdown()
            self._http.server_close()
            self._http = None
        if self._http_thread is not None:
            self._http_thread.join(timeout=timeout)
            self._http_thread = None
        if self._loop_thread is not None:
            self._loop_thread.join(timeout=timeout)
            self._loop_thread = None
        with self._lock:
            self._status.running = False


def _make_handler(server: OperationServer) -> type[BaseHTTPRequestHandler]:
    """Closure factory — binds the handler class to this ``OperationServer``."""

    class _Handler(BaseHTTPRequestHandler):
        def _write_json(self, status: int, body: str) -> None:
            payload = body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802 — stdlib API
            if self.path == '/status':
                self._write_json(200, server.status.to_json())
                return
            self._write_json(404, json.dumps({'error': 'not found'}))

        def do_POST(self) -> None:  # noqa: N802 — stdlib API
            if self.path == '/tick':
                dispatched = server.tick_once()
                self._write_json(200, json.dumps({'dispatched': dispatched}))
                return
            self._write_json(404, json.dumps({'error': 'not found'}))

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            log.debug('operation-http: ' + format, *args)

    return _Handler


def start_server(
    host: str | None = None,
    port: int | None = None,
    runner: CopilotRunner | None = None,
) -> OperationServer:
    """Construct, start, and return an :class:`OperationServer`."""
    op = OperationServer(runner=runner)
    op.start(host=host, port=port)
    return op
