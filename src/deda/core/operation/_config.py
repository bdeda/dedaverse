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
"""Module-level globals for the Operation server.

These are plain module globals (not a config class) so they can be read and
overridden from tests or an embedding host simply by setting
``deda.core.operation.TICK_INTERVAL_SEC = 30`` before calling
:func:`start_server`.
"""

from pathlib import Path

__all__ = ['HOST', 'PORT', 'TEMPLATES_DIR', 'TICK_INTERVAL_SEC']


TICK_INTERVAL_SEC: int = 5 * 60
"""How often the loop wakes to check for runnable tasks. Start: 5 minutes."""

HOST: str = '127.0.0.1'
"""Loopback interface — Operation is a localhost-only tool."""

PORT: int = 8765
"""Default TCP port for the status/control HTTP server."""

TEMPLATES_DIR: Path = Path(__file__).parent / 'templates'
"""Directory holding prompt template files. Ships with ``default.md``."""
