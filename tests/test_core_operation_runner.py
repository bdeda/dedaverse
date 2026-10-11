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
"""Unit tests for deda.core.operation._runner module."""

import subprocess
import unittest
from unittest.mock import patch


class TestCopilotRunner(unittest.TestCase):
    """Test cases for the CopilotRunner subprocess wrapper."""

    def test_module_imports(self):
        try:
            from deda.core.operation import _runner  # noqa: F401
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")

    def test_resolve_executable_explicit(self):
        try:
            from deda.core.operation._runner import CopilotRunner
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        runner = CopilotRunner(executable='/bin/copilot')
        self.assertEqual(runner.resolve_executable(), '/bin/copilot')

    def test_resolve_executable_missing(self):
        try:
            from deda.core.operation._runner import CopilotRunner
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        runner = CopilotRunner()
        with patch('deda.core.operation._runner.shutil.which', return_value=None):
            with self.assertRaises(FileNotFoundError):
                runner.resolve_executable()

    def test_build_args_minimal(self):
        try:
            from deda.core.operation._runner import CopilotRunner
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        runner = CopilotRunner(executable='copilot')
        args = runner.build_args('hello')
        self.assertEqual(args, ['copilot', '-p', 'hello'])

    def test_build_args_with_options(self):
        try:
            from deda.core.operation._runner import CopilotRunner
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        runner = CopilotRunner(
            executable='copilot', model='gpt-5', allow_all_tools=True
        )
        args = runner.build_args('do it')
        self.assertEqual(
            args,
            ['copilot', '-p', 'do it', '--model', 'gpt-5', '--allow-all-tools'],
        )

    def test_run_returns_result_on_success(self):
        try:
            from deda.core.operation._runner import CopilotRunner
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        runner = CopilotRunner(executable='copilot')
        fake_completed = subprocess.CompletedProcess(
            args=['copilot', '-p', 'x'], returncode=0, stdout='ok', stderr=''
        )
        with patch(
            'deda.core.operation._runner.subprocess.run', return_value=fake_completed
        ) as run_mock:
            result = runner.run('x')
        self.assertTrue(result.ok)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, 'ok')
        run_mock.assert_called_once()

    def test_run_does_not_raise_on_nonzero(self):
        try:
            from deda.core.operation._runner import CopilotRunner
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        runner = CopilotRunner(executable='copilot')
        fake_completed = subprocess.CompletedProcess(
            args=['copilot', '-p', 'x'], returncode=2, stdout='', stderr='boom'
        )
        with patch(
            'deda.core.operation._runner.subprocess.run', return_value=fake_completed
        ):
            result = runner.run('x')
        self.assertFalse(result.ok)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, 'boom')


if __name__ == '__main__':
    unittest.main()
