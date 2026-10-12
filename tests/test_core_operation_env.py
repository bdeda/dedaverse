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
"""Unit tests for deda.core.operation._config env-file handling."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


_OPERATION_ENV_KEYS = (
    'OPERATION_ENV_FILE',
    'OPERATION_HOST',
    'OPERATION_PORT',
    'OPERATION_TICK_INTERVAL_SEC',
    'OPERATION_TASKS_DIR',
    'OPERATION_TEMPLATES_DIR',
    'OPERATION_COPILOT_EXECUTABLE',
    'OPERATION_COPILOT_MODEL',
    'OPERATION_COPILOT_ALLOW_ALL_TOOLS',
    'OPERATION_COPILOT_TIMEOUT_SEC',
)


def _clean_env() -> dict[str, str]:
    """Return a copy of :data:`os.environ` with every OPERATION_* key stripped."""
    return {k: v for k, v in os.environ.items() if k not in _OPERATION_ENV_KEYS}


class TestLoadEnv(unittest.TestCase):
    """Test cases for ``load_env`` parsing and precedence."""

    def test_module_imports(self):
        try:
            from deda.core.operation import _config  # noqa: F401
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")

    def test_parses_keys_and_returns_entries(self):
        try:
            from deda.core.operation._config import load_env
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / '.env'
            env_path.write_text(
                '# a comment\n'
                '\n'
                'OPERATION_HOST=10.0.0.5\n'
                'OPERATION_PORT=9000\n'
                'OPERATION_COPILOT_MODEL="gpt-5"\n'
                'OPERATION_COPILOT_EXECUTABLE=\'/usr/local/bin/copilot\'\n'
                'malformed line with no equals\n',
                encoding='utf-8',
            )
            with patch.dict(os.environ, _clean_env(), clear=True):
                loaded = load_env(env_file=env_path)
                self.assertEqual(loaded['OPERATION_HOST'], '10.0.0.5')
                self.assertEqual(loaded['OPERATION_PORT'], '9000')
                self.assertEqual(loaded['OPERATION_COPILOT_MODEL'], 'gpt-5')
                self.assertEqual(loaded['OPERATION_COPILOT_EXECUTABLE'], '/usr/local/bin/copilot')
                self.assertEqual(os.environ['OPERATION_HOST'], '10.0.0.5')

    def test_does_not_override_existing_env_by_default(self):
        try:
            from deda.core.operation._config import load_env
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / '.env'
            env_path.write_text('OPERATION_HOST=file-wins\n', encoding='utf-8')
            base = _clean_env()
            base['OPERATION_HOST'] = 'shell-wins'
            with patch.dict(os.environ, base, clear=True):
                load_env(env_file=env_path)
                self.assertEqual(os.environ['OPERATION_HOST'], 'shell-wins')

    def test_override_true_replaces_existing_env(self):
        try:
            from deda.core.operation._config import load_env
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / '.env'
            env_path.write_text('OPERATION_HOST=file-wins\n', encoding='utf-8')
            base = _clean_env()
            base['OPERATION_HOST'] = 'shell-wins'
            with patch.dict(os.environ, base, clear=True):
                load_env(env_file=env_path, override=True)
                self.assertEqual(os.environ['OPERATION_HOST'], 'file-wins')

    def test_missing_file_returns_empty(self):
        try:
            from deda.core.operation._config import load_env
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_env(env_file=Path(tmp) / 'does-not-exist.env'), {})

    def test_uses_operation_env_file_var_when_path_omitted(self):
        try:
            from deda.core.operation._config import load_env
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / 'custom.env'
            env_path.write_text('OPERATION_PORT=4242\n', encoding='utf-8')
            base = _clean_env()
            base['OPERATION_ENV_FILE'] = str(env_path)
            with patch.dict(os.environ, base, clear=True):
                loaded = load_env()
                self.assertEqual(loaded['OPERATION_PORT'], '4242')


class TestReloadConfig(unittest.TestCase):
    """Test cases for ``reload_config`` recomputing module globals."""

    def test_reload_applies_env_overrides(self):
        try:
            from deda.core.operation import _config
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        base = _clean_env()
        base.update(
            {
                'OPERATION_HOST': '0.0.0.0',
                'OPERATION_PORT': '11000',
                'OPERATION_TICK_INTERVAL_SEC': '45',
                'OPERATION_COPILOT_EXECUTABLE': '/tmp/copilot',
                'OPERATION_COPILOT_MODEL': 'gpt-5',
                'OPERATION_COPILOT_ALLOW_ALL_TOOLS': 'true',
                'OPERATION_COPILOT_TIMEOUT_SEC': '90.5',
            }
        )
        original = {
            'TICK_INTERVAL_SEC': _config.TICK_INTERVAL_SEC,
            'HOST': _config.HOST,
            'PORT': _config.PORT,
            'COPILOT_EXECUTABLE': _config.COPILOT_EXECUTABLE,
            'COPILOT_MODEL': _config.COPILOT_MODEL,
            'COPILOT_ALLOW_ALL_TOOLS': _config.COPILOT_ALLOW_ALL_TOOLS,
            'COPILOT_TIMEOUT_SEC': _config.COPILOT_TIMEOUT_SEC,
        }
        try:
            with patch.dict(os.environ, base, clear=True):
                _config.reload_config()
                self.assertEqual(_config.HOST, '0.0.0.0')
                self.assertEqual(_config.PORT, 11000)
                self.assertEqual(_config.TICK_INTERVAL_SEC, 45)
                self.assertEqual(_config.COPILOT_EXECUTABLE, '/tmp/copilot')
                self.assertEqual(_config.COPILOT_MODEL, 'gpt-5')
                self.assertTrue(_config.COPILOT_ALLOW_ALL_TOOLS)
                self.assertAlmostEqual(_config.COPILOT_TIMEOUT_SEC, 90.5)
        finally:
            # Restore module-global state for other tests in this process.
            for key, value in original.items():
                setattr(_config, key, value)
            _config.reload_config()


class TestCopilotRunnerEnvFallback(unittest.TestCase):
    """CopilotRunner should fall back to _config module globals when args are omitted."""

    def test_falls_back_to_config_when_args_omitted(self):
        try:
            from deda.core.operation import _config
            from deda.core.operation._runner import CopilotRunner
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        orig = (
            _config.COPILOT_EXECUTABLE,
            _config.COPILOT_MODEL,
            _config.COPILOT_ALLOW_ALL_TOOLS,
            _config.COPILOT_TIMEOUT_SEC,
        )
        try:
            _config.COPILOT_EXECUTABLE = '/fake/copilot'
            _config.COPILOT_MODEL = 'fake-model'
            _config.COPILOT_ALLOW_ALL_TOOLS = True
            _config.COPILOT_TIMEOUT_SEC = 12.5
            runner = CopilotRunner()
            args = runner.build_args('p')
            self.assertEqual(
                args,
                ['/fake/copilot', '-p', 'p', '--model', 'fake-model', '--allow-all-tools'],
            )
            self.assertEqual(runner._timeout, 12.5)
        finally:
            (
                _config.COPILOT_EXECUTABLE,
                _config.COPILOT_MODEL,
                _config.COPILOT_ALLOW_ALL_TOOLS,
                _config.COPILOT_TIMEOUT_SEC,
            ) = orig

    def test_explicit_arg_wins_over_config(self):
        try:
            from deda.core.operation import _config
            from deda.core.operation._runner import CopilotRunner
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        orig_model = _config.COPILOT_MODEL
        try:
            _config.COPILOT_MODEL = 'from-config'
            runner = CopilotRunner(executable='copilot', model='from-arg')
            args = runner.build_args('p')
            self.assertIn('from-arg', args)
            self.assertNotIn('from-config', args)
        finally:
            _config.COPILOT_MODEL = orig_model


if __name__ == '__main__':
    unittest.main()
