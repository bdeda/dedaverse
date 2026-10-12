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
"""Copilot CLI subprocess runner.

Minimal wrapper around ``copilot -p <prompt>``. Keeps the flag set tiny on
purpose — the Operation platform (packages/server in the operation repo)
has a much richer adapter; this is the local cousin used for driving the
loop from a Python host.

TODO: flag shape will likely evolve once we decide how ``toolPolicy`` and
filesystem scoping should be expressed in dedaverse (vs the TypeScript
Operation server).
"""

import logging
import shutil
import subprocess
from dataclasses import dataclass

from . import _config

__all__ = ['CopilotRunner', 'RunnerResult']


log = logging.getLogger(__name__)


@dataclass
class RunnerResult:
    """Outcome of one ``copilot`` invocation."""

    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class CopilotRunner:
    """Thin wrapper around the ``copilot`` CLI.

    Each argument defaults to ``None`` so it falls through to the matching
    ``_config.COPILOT_*`` module global — which in turn is populated from
    ``OPERATION_COPILOT_*`` env vars (see :mod:`._config`). Pass an
    explicit value to override config for a single runner instance.

    Args:
        executable: Path or command name. ``None`` → ``_config.COPILOT_EXECUTABLE``,
            which itself defaults to resolving ``copilot`` via ``PATH``.
        model: Optional ``--model`` value (e.g. ``gpt-5``).
        allow_all_tools: If True, pass ``--allow-all-tools`` — convenient for
            local dev; review before using in unattended deployments.
        timeout: Per-invocation timeout in seconds.
    """

    def __init__(
        self,
        executable: str | None = None,
        model: str | None = None,
        allow_all_tools: bool | None = None,
        timeout: float | None = None,
    ) -> None:
        self._executable = executable if executable is not None else _config.COPILOT_EXECUTABLE
        self._model = model if model is not None else _config.COPILOT_MODEL
        self._allow_all_tools = (
            allow_all_tools if allow_all_tools is not None else _config.COPILOT_ALLOW_ALL_TOOLS
        )
        self._timeout = timeout if timeout is not None else _config.COPILOT_TIMEOUT_SEC

    def resolve_executable(self) -> str:
        """Return the copilot executable path; raises if not found."""
        if self._executable:
            return self._executable
        found = shutil.which('copilot')
        if not found:
            raise FileNotFoundError(
                'copilot CLI not found on PATH. Install with '
                '`npm install -g @github/copilot` then `copilot auth login`.'
            )
        return found

    def build_args(self, prompt: str) -> list[str]:
        """Build the argv list passed to :mod:`subprocess`."""
        args: list[str] = [self.resolve_executable(), '-p', prompt]
        if self._model:
            args += ['--model', self._model]
        if self._allow_all_tools:
            args.append('--allow-all-tools')
        return args

    def run(self, prompt: str) -> RunnerResult:
        """Run copilot with ``prompt`` and return stdout/stderr/returncode.

        Never raises on non-zero exit — inspect :attr:`RunnerResult.ok`.
        Propagates :class:`FileNotFoundError` when the CLI is missing, and
        :class:`subprocess.TimeoutExpired` when ``timeout`` is hit.
        """
        args = self.build_args(prompt)
        log.info('operation: invoking copilot (%d arg(s))', len(args))
        completed = subprocess.run(
            args,
            input='',
            capture_output=True,
            text=True,
            timeout=self._timeout,
            check=False,
        )
        return RunnerResult(
            returncode=completed.returncode,
            stdout=completed.stdout or '',
            stderr=completed.stderr or '',
        )
