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
"""Unit tests for deda.core.operation._prompts module."""

import tempfile
import unittest
from pathlib import Path


class TestPrompts(unittest.TestCase):
    """Test cases for prompt loader and composer."""

    def test_module_imports(self):
        try:
            from deda.core.operation import _prompts  # noqa: F401
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")

    def test_load_default_template(self):
        try:
            from deda.core.operation._prompts import load_template
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        text = load_template()
        self.assertIn('{task_title}', text)
        self.assertIn('{task_body}', text)

    def test_load_missing_falls_back_to_default(self):
        try:
            from deda.core.operation._prompts import load_template
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        text = load_template(name='does-not-exist')
        # Falls back to default.md shipped with module.
        self.assertIn('{task_title}', text)

    def test_load_raises_when_no_default_present(self):
        try:
            from deda.core.operation._prompts import load_template
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                load_template(name='anything', templates_dir=Path(tmp))

    def test_compose_prompt_substitutes_placeholders(self):
        try:
            from deda.core.operation._prompts import compose_prompt
            from deda.core.operation._tasks import Task
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        task = Task(id='t1', title='my title', body='my body text')
        rendered = compose_prompt(task)
        self.assertIn('my title', rendered)
        self.assertIn('my body text', rendered)

    def test_compose_prompt_leaves_unknown_placeholders(self):
        try:
            from deda.core.operation._prompts import compose_prompt
            from deda.core.operation._tasks import Task
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / 'custom.md').write_text(
                '{task_title} / {task_body} / {future_field}', encoding='utf-8'
            )
            task = Task(id='t1', title='T', body='B', template='custom')
            rendered = compose_prompt(task, templates_dir=tmp_path)
            self.assertEqual(rendered, 'T / B / {future_field}')


if __name__ == '__main__':
    unittest.main()
