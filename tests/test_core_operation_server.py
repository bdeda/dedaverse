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
"""Unit tests for deda.core.operation._server module."""

import json
import unittest
import urllib.request
from unittest.mock import MagicMock


class _FakeResult:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.stdout = ''
        self.stderr = ''

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class TestOperationServer(unittest.TestCase):
    """Test the OperationServer tick loop and HTTP endpoints."""

    def test_module_imports(self):
        try:
            from deda.core.operation import _server  # noqa: F401
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")

    def test_tick_once_with_no_tasks(self):
        try:
            from deda.core.operation._server import OperationServer
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        runner = MagicMock()
        op = OperationServer(runner=runner, discover=lambda: [], ready=lambda t: True)
        dispatched = op.tick_once()
        self.assertEqual(dispatched, 0)
        self.assertEqual(op.status.tick_count, 1)
        runner.run.assert_not_called()

    def test_tick_once_dispatches_ready_tasks(self):
        try:
            from deda.core.operation._server import OperationServer
            from deda.core.operation._tasks import Task
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        runner = MagicMock()
        runner.run.return_value = _FakeResult(returncode=0)
        tasks = [Task(id='t1', title='A', body='B')]
        op = OperationServer(runner=runner, discover=lambda: tasks, ready=lambda t: True)
        dispatched = op.tick_once()
        self.assertEqual(dispatched, 1)
        runner.run.assert_called_once()
        self.assertEqual(op.status.last_tick_dispatched, 1)
        self.assertIn('t1:0', op.status.dispatch_log)

    def test_tick_once_skips_not_ready(self):
        try:
            from deda.core.operation._server import OperationServer
            from deda.core.operation._tasks import Task
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        runner = MagicMock()
        tasks = [Task(id='t1', title='A', body='B')]
        op = OperationServer(
            runner=runner, discover=lambda: tasks, ready=lambda t: False
        )
        dispatched = op.tick_once()
        self.assertEqual(dispatched, 0)
        runner.run.assert_not_called()

    def test_tick_once_catches_discover_errors(self):
        try:
            from deda.core.operation._server import OperationServer
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")

        def bad_discover():
            raise RuntimeError('boom')

        runner = MagicMock()
        op = OperationServer(runner=runner, discover=bad_discover)
        dispatched = op.tick_once()
        self.assertEqual(dispatched, 0)
        self.assertIsNotNone(op.status.last_error)
        self.assertIn('discover', op.status.last_error)

    def test_tick_once_catches_task_errors(self):
        try:
            from deda.core.operation._server import OperationServer
            from deda.core.operation._tasks import Task
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        runner = MagicMock()
        runner.run.side_effect = RuntimeError('copilot exploded')
        tasks = [Task(id='t1', title='A', body='B')]
        op = OperationServer(runner=runner, discover=lambda: tasks, ready=lambda t: True)
        dispatched = op.tick_once()
        self.assertEqual(dispatched, 0)
        self.assertIsNotNone(op.status.last_error)
        self.assertIn('t1', op.status.last_error)

    def test_http_status_and_tick_endpoints(self):
        try:
            from deda.core.operation._server import OperationServer
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")

        runner = MagicMock()
        # Use a long interval so the background loop doesn't tick during the test.
        op = OperationServer(
            runner=runner,
            discover=lambda: [],
            ready=lambda t: True,
            interval_sec=3600,
        )
        # Bind to an ephemeral port.
        host, port = op.start(host='127.0.0.1', port=0)
        try:
            with urllib.request.urlopen(
                f'http://{host}:{port}/status', timeout=5
            ) as resp:
                self.assertEqual(resp.status, 200)
                body = json.loads(resp.read().decode('utf-8'))
            self.assertIn('tick_count', body)
            self.assertTrue(body['running'])

            req = urllib.request.Request(
                f'http://{host}:{port}/tick', method='POST', data=b''
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                body = json.loads(resp.read().decode('utf-8'))
            self.assertEqual(body['dispatched'], 0)
        finally:
            op.stop(timeout=2.0)


if __name__ == '__main__':
    unittest.main()
