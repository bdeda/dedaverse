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
"""Unit tests for deda.core.operation._tasks module."""

import unittest


class TestTask(unittest.TestCase):
    """Test cases for Task dataclass."""

    def test_module_imports(self):
        try:
            from deda.core.operation import _tasks  # noqa: F401
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")

    def test_task_creation_minimal(self):
        try:
            from deda.core.operation._tasks import Task
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        t = Task(id='t1', title='hello', body='world')
        self.assertEqual(t.id, 't1')
        self.assertEqual(t.title, 'hello')
        self.assertEqual(t.body, 'world')
        self.assertIsNone(t.template)
        self.assertEqual(t.metadata, {})

    def test_discover_tasks_stub_returns_empty(self):
        try:
            from deda.core.operation._tasks import discover_tasks
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        self.assertEqual(discover_tasks(), [])

    def test_is_ready_to_run_stub_returns_true(self):
        try:
            from deda.core.operation._tasks import Task, is_ready_to_run
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        self.assertTrue(is_ready_to_run(Task(id='t1', title='x', body='y')))


if __name__ == '__main__':
    unittest.main()
