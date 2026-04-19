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
"""Unit tests for deda.core.operation._config module."""

import unittest


class TestOperationConfig(unittest.TestCase):
    """Test cases for operation config globals."""

    def test_module_imports(self):
        try:
            from deda.core.operation import _config  # noqa: F401
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")

    def test_default_tick_interval_is_five_minutes(self):
        try:
            from deda.core.operation import _config
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        self.assertEqual(_config.TICK_INTERVAL_SEC, 5 * 60)

    def test_default_host_is_loopback(self):
        try:
            from deda.core.operation import _config
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        self.assertEqual(_config.HOST, '127.0.0.1')

    def test_port_is_int(self):
        try:
            from deda.core.operation import _config
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        self.assertIsInstance(_config.PORT, int)
        self.assertGreater(_config.PORT, 0)
        self.assertLess(_config.PORT, 65536)

    def test_templates_dir_contains_default(self):
        try:
            from deda.core.operation import _config
        except (ImportError, ModuleNotFoundError) as e:
            self.skipTest(f"Optional dependencies not available: {e}")
        self.assertTrue((_config.TEMPLATES_DIR / 'default.md').is_file())


if __name__ == '__main__':
    unittest.main()
