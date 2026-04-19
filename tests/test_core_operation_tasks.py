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

import tempfile
import unittest
from pathlib import Path


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

    def test_default_status_is_open(self):
        try:
            from deda.core.operation._tasks import Task, TaskStatus
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        self.assertIs(Task(id='t1', title='x', body='y').status, TaskStatus.OPEN)


class TestTaskStatus(unittest.TestCase):
    """Test cases for TaskStatus parsing and values."""

    def test_canonical_values(self):
        try:
            from deda.core.operation._tasks import TaskStatus
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        self.assertEqual(TaskStatus.OPEN.value, 'Open')
        self.assertEqual(TaskStatus.IN_PROGRESS.value, 'In-Progress')
        self.assertEqual(TaskStatus.BLOCKED.value, 'Blocked')
        self.assertEqual(TaskStatus.READY_FOR_REVIEW.value, 'Ready-for-Review')
        self.assertEqual(TaskStatus.CLOSED.value, 'Closed')
        self.assertEqual(TaskStatus.RESOLVED.value, 'Resolved')

    def test_parse_canonical(self):
        try:
            from deda.core.operation._tasks import TaskStatus
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        self.assertIs(TaskStatus.parse('Open'), TaskStatus.OPEN)
        self.assertIs(TaskStatus.parse('In-Progress'), TaskStatus.IN_PROGRESS)
        self.assertIs(TaskStatus.parse('Ready-for-Review'), TaskStatus.READY_FOR_REVIEW)

    def test_parse_is_case_and_separator_insensitive(self):
        try:
            from deda.core.operation._tasks import TaskStatus
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        self.assertIs(TaskStatus.parse('open'), TaskStatus.OPEN)
        self.assertIs(TaskStatus.parse('in progress'), TaskStatus.IN_PROGRESS)
        self.assertIs(TaskStatus.parse('IN_PROGRESS'), TaskStatus.IN_PROGRESS)
        self.assertIs(TaskStatus.parse('ready for review'), TaskStatus.READY_FOR_REVIEW)
        self.assertIs(TaskStatus.parse('ready_for_review'), TaskStatus.READY_FOR_REVIEW)

    def test_parse_empty_defaults_to_open(self):
        try:
            from deda.core.operation._tasks import TaskStatus
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        self.assertIs(TaskStatus.parse(None), TaskStatus.OPEN)
        self.assertIs(TaskStatus.parse(''), TaskStatus.OPEN)
        self.assertIs(TaskStatus.parse('   '), TaskStatus.OPEN)

    def test_parse_unknown_falls_back_to_open(self):
        try:
            from deda.core.operation._tasks import TaskStatus
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        self.assertIs(TaskStatus.parse('WontFix'), TaskStatus.OPEN)


class TestIsReadyToRun(unittest.TestCase):
    """Test cases for the status-gated readiness check."""

    def test_open_is_runnable(self):
        try:
            from deda.core.operation._tasks import Task, TaskStatus, is_ready_to_run
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        t = Task(id='t1', title='x', body='y', status=TaskStatus.OPEN)
        self.assertTrue(is_ready_to_run(t))

    def test_non_open_statuses_are_skipped(self):
        try:
            from deda.core.operation._tasks import Task, TaskStatus, is_ready_to_run
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        for status in (
            TaskStatus.IN_PROGRESS,
            TaskStatus.BLOCKED,
            TaskStatus.READY_FOR_REVIEW,
            TaskStatus.CLOSED,
            TaskStatus.RESOLVED,
        ):
            t = Task(id='t1', title='x', body='y', status=status)
            self.assertFalse(is_ready_to_run(t), f'{status} should not be runnable')


class TestDiscoverTasks(unittest.TestCase):
    """Test cases for filesystem task discovery."""

    def test_missing_directory_returns_empty(self):
        try:
            from deda.core.operation._tasks import discover_tasks
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(discover_tasks(Path(tmp) / 'does-not-exist'), [])

    def test_empty_directory_returns_empty(self):
        try:
            from deda.core.operation._tasks import discover_tasks
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(discover_tasks(Path(tmp)), [])

    def test_discovers_task_and_extracts_front_matter(self):
        try:
            from deda.core.operation._tasks import discover_tasks
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            task1 = tmp_path / 'task1'
            task1.mkdir()
            (task1 / 'task.md').write_text(
                '---\n'
                'title: Rewrite auth\n'
                'template: rewrite\n'
                'priority: high\n'
                '---\n'
                '\n'
                'Replace the legacy session store with the new one.\n',
                encoding='utf-8',
            )
            tasks = discover_tasks(tmp_path)
            self.assertEqual(len(tasks), 1)
            t = tasks[0]
            self.assertEqual(t.id, 'task1')
            self.assertEqual(t.title, 'Rewrite auth')
            self.assertEqual(t.template, 'rewrite')
            self.assertIn('Replace the legacy session store', t.body)
            self.assertEqual(t.metadata.get('priority'), 'high')
            self.assertEqual(t.metadata.get('attachments'), [])

    def test_title_falls_back_to_h1_then_dir_name(self):
        try:
            from deda.core.operation._tasks import discover_tasks
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / 'task1').mkdir()
            (tmp_path / 'task1' / 'task.md').write_text(
                '# Hello from H1\n\nbody content\n', encoding='utf-8'
            )
            (tmp_path / 'task2').mkdir()
            (tmp_path / 'task2' / 'task.md').write_text('no title anywhere\n', encoding='utf-8')
            tasks = discover_tasks(tmp_path)
            self.assertEqual([t.title for t in tasks], ['Hello from H1', 'task2'])

    def test_sorts_numerically_not_lexically(self):
        try:
            from deda.core.operation._tasks import discover_tasks
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for n in (1, 2, 10, 11):
                (tmp_path / f'task{n}').mkdir()
                (tmp_path / f'task{n}' / 'task.md').write_text(
                    f'title: t{n}\n', encoding='utf-8'
                )
            tasks = discover_tasks(tmp_path)
            self.assertEqual([t.id for t in tasks], ['task1', 'task2', 'task10', 'task11'])

    def test_collects_sibling_attachments(self):
        try:
            from deda.core.operation._tasks import discover_tasks
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            task1 = tmp_path / 'task1'
            task1.mkdir()
            (task1 / 'task.md').write_text('body\n', encoding='utf-8')
            (task1 / 'ref.png').write_bytes(b'\x89PNG')
            (task1 / 'spec.md').write_text('spec\n', encoding='utf-8')
            tasks = discover_tasks(tmp_path)
            self.assertEqual(len(tasks), 1)
            attachments = tasks[0].metadata['attachments']
            self.assertEqual(len(attachments), 2)
            names = sorted(Path(p).name for p in attachments)
            self.assertEqual(names, ['ref.png', 'spec.md'])

    def test_status_is_read_from_front_matter(self):
        try:
            from deda.core.operation._tasks import TaskStatus, discover_tasks
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cases = {
                'task1': 'Open',
                'task2': 'In-Progress',
                'task3': 'blocked',            # lowercase
                'task4': 'ready for review',   # spaces
                'task5': 'Resolved',
            }
            for dir_name, raw in cases.items():
                (tmp_path / dir_name).mkdir()
                (tmp_path / dir_name / 'task.md').write_text(
                    f'---\nstatus: {raw}\n---\n\nbody\n', encoding='utf-8'
                )
            tasks = {t.id: t for t in discover_tasks(tmp_path)}
            self.assertIs(tasks['task1'].status, TaskStatus.OPEN)
            self.assertIs(tasks['task2'].status, TaskStatus.IN_PROGRESS)
            self.assertIs(tasks['task3'].status, TaskStatus.BLOCKED)
            self.assertIs(tasks['task4'].status, TaskStatus.READY_FOR_REVIEW)
            self.assertIs(tasks['task5'].status, TaskStatus.RESOLVED)

    def test_missing_status_defaults_to_open(self):
        try:
            from deda.core.operation._tasks import TaskStatus, discover_tasks
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / 'task1').mkdir()
            (tmp_path / 'task1' / 'task.md').write_text(
                'no front-matter here\n', encoding='utf-8'
            )
            tasks = discover_tasks(tmp_path)
            self.assertEqual(len(tasks), 1)
            self.assertIs(tasks[0].status, TaskStatus.OPEN)

    def test_skips_non_task_dirs_and_missing_task_md(self):
        try:
            from deda.core.operation._tasks import discover_tasks
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / 'task1').mkdir()
            (tmp_path / 'task1' / 'task.md').write_text('ok\n', encoding='utf-8')
            (tmp_path / 'notes').mkdir()  # wrong name
            (tmp_path / 'task2').mkdir()  # no task.md
            (tmp_path / 'readme.md').write_text('top-level file', encoding='utf-8')
            tasks = discover_tasks(tmp_path)
            self.assertEqual([t.id for t in tasks], ['task1'])


if __name__ == '__main__':
    unittest.main()
