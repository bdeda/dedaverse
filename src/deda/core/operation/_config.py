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
"""Module-level config, sourced from ``.env`` + :data:`os.environ`.

Lookup precedence (highest wins):

1. An explicit value passed to a constructor (e.g.
   ``CopilotRunner(executable=...)`` or ``OperationServer(interval_sec=...)``).
2. A variable already present in :data:`os.environ` when the module is
   imported (set by the shell, a launcher, or a prior ``load_env`` call
   with ``override=True``).
3. A ``KEY=value`` entry in the ``.env`` file at
   ``~/.dedaverse/operation/.env`` — overridable via the
   ``OPERATION_ENV_FILE`` environment variable or ``--env-file`` CLI flag.
   Auto-loaded once on import.
4. The built-in default baked into this module.

Override after import by calling :func:`load_env` then :func:`reload_config`.
"""

import os
from pathlib import Path

__all__ = [
    'COPILOT_ALLOW_ALL_TOOLS',
    'COPILOT_EXECUTABLE',
    'COPILOT_MODEL',
    'COPILOT_TIMEOUT_SEC',
    'DEFAULT_ENV_PATH',
    'HOST',
    'PORT',
    'TASKS_DIR',
    'TEMPLATES_DIR',
    'TICK_INTERVAL_SEC',
    'load_env',
    'reload_config',
]


DEFAULT_ENV_PATH: Path = Path.home() / '.dedaverse' / 'operation' / '.env'
"""Default location of the optional ``.env`` file. Overridable via the
``OPERATION_ENV_FILE`` environment variable or ``--env-file`` CLI flag."""


def load_env(env_file: Path | None = None, override: bool = False) -> dict[str, str]:
    """Merge ``KEY=value`` entries from ``env_file`` into :data:`os.environ`.

    Args:
        env_file: Path to read. ``None`` checks ``OPERATION_ENV_FILE`` in
            the environment first, then falls back to :data:`DEFAULT_ENV_PATH`.
        override: When False (default), values already in ``os.environ``
            are preserved so shell-set variables win. Set True to force
            the file to take precedence.

    Returns:
        Dict of every entry parsed from the file. Whether each was
        written to ``os.environ`` depends on ``override``.
    """
    path = env_file
    if path is None:
        env_override = os.environ.get('OPERATION_ENV_FILE')
        path = Path(env_override) if env_override else DEFAULT_ENV_PATH
    if not path.is_file():
        return {}
    loaded: dict[str, str] = {}
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        loaded[key] = value
        if override or key not in os.environ:
            os.environ[key] = value
    return loaded


def _env_str(key: str, default: str) -> str:
    raw = os.environ.get(key)
    return raw if raw else default


def _env_optional_str(key: str) -> str | None:
    raw = os.environ.get(key)
    return raw if raw else None


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    raw = os.environ.get(key)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def _env_path(key: str, default: Path) -> Path:
    raw = os.environ.get(key)
    return Path(raw).expanduser() if raw else default


def reload_config() -> None:
    """Recompute every module global from the current :data:`os.environ`.

    Call this after :func:`load_env` with ``override=True`` or after
    mutating ``os.environ`` directly, if you need the module globals to
    pick up the new values.
    """
    global TICK_INTERVAL_SEC, HOST, PORT, TEMPLATES_DIR, TASKS_DIR
    global COPILOT_EXECUTABLE, COPILOT_MODEL
    global COPILOT_ALLOW_ALL_TOOLS, COPILOT_TIMEOUT_SEC
    TICK_INTERVAL_SEC = _env_int('OPERATION_TICK_INTERVAL_SEC', 5 * 60)
    HOST = _env_str('OPERATION_HOST', '127.0.0.1')
    PORT = _env_int('OPERATION_PORT', 8765)
    TEMPLATES_DIR = _env_path(
        'OPERATION_TEMPLATES_DIR', Path(__file__).parent / 'templates'
    )
    TASKS_DIR = _env_path(
        'OPERATION_TASKS_DIR', Path.home() / '.dedaverse' / 'operation' / 'tasks'
    )
    COPILOT_EXECUTABLE = _env_optional_str('OPERATION_COPILOT_EXECUTABLE')
    COPILOT_MODEL = _env_optional_str('OPERATION_COPILOT_MODEL')
    COPILOT_ALLOW_ALL_TOOLS = _env_bool('OPERATION_COPILOT_ALLOW_ALL_TOOLS', False)
    COPILOT_TIMEOUT_SEC = _env_float('OPERATION_COPILOT_TIMEOUT_SEC', 600.0)


# Auto-load on import so the module globals below reflect .env values.
load_env()


TICK_INTERVAL_SEC: int = _env_int('OPERATION_TICK_INTERVAL_SEC', 5 * 60)
"""How often the loop wakes to check for runnable tasks. Default: 5 min."""

HOST: str = _env_str('OPERATION_HOST', '127.0.0.1')
"""Loopback interface — Operation is a localhost-only tool."""

PORT: int = _env_int('OPERATION_PORT', 8765)
"""Default TCP port for the status/control HTTP server."""

TEMPLATES_DIR: Path = _env_path(
    'OPERATION_TEMPLATES_DIR', Path(__file__).parent / 'templates'
)
"""Directory holding prompt template files. Ships with ``default.md``."""

TASKS_DIR: Path = _env_path(
    'OPERATION_TASKS_DIR', Path.home() / '.dedaverse' / 'operation' / 'tasks'
)
"""Root of the task drop-box. See :mod:`deda.core.operation._tasks`."""

COPILOT_EXECUTABLE: str | None = _env_optional_str('OPERATION_COPILOT_EXECUTABLE')
"""Explicit path to the ``copilot`` CLI. ``None`` → resolve via ``PATH``."""

COPILOT_MODEL: str | None = _env_optional_str('OPERATION_COPILOT_MODEL')
"""Optional ``--model`` argument passed to ``copilot``."""

COPILOT_ALLOW_ALL_TOOLS: bool = _env_bool('OPERATION_COPILOT_ALLOW_ALL_TOOLS', False)
"""When True, pass ``--allow-all-tools`` to ``copilot``. Off by default."""

COPILOT_TIMEOUT_SEC: float = _env_float('OPERATION_COPILOT_TIMEOUT_SEC', 600.0)
"""Per-invocation timeout for ``subprocess.run`` calls to ``copilot``."""
