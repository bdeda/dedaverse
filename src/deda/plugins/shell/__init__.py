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
"""Shell application plugin - launches a cross-platform terminal with dedaverse env."""

import os
import platform
import subprocess
from pathlib import Path

import deda.core

__version__ = '0.1.0'
__vendor__ = 'Deda'


def _find_shell_executable():
    """Return (executable_path, shell_args) for the platform."""
    system = platform.system()
    if system == 'Windows':
        comspec = os.environ.get('COMSPEC', 'cmd.exe')
        if comspec == 'cmd.exe' or '\\' not in comspec:
            system_root = os.environ.get('SystemRoot', 'C:\\Windows')
            comspec = os.path.join(system_root, 'System32', 'cmd.exe')
        return comspec, ['/k']
    return os.environ.get('SHELL', '/bin/bash'), []


class Shell(deda.core.Application):
    """Application plugin that launches a shell inheriting the Dedaverse environment."""

    def __init__(self):
        exe, _ = _find_shell_executable()
        icon_path = Path(__file__).parent / 'cmd_icon.png'
        if not icon_path.is_file():
            icon_path = Path(__file__).parent / 'shell_icon.png'
        super().__init__(
            'Shell',
            version=__version__,
            vendor=__vendor__,
            description='Launch a terminal/shell with the Dedaverse environment',
            executable=exe,
            image=str(icon_path) if icon_path.is_file() else None,
        )

    def find(self):
        exe, _ = _find_shell_executable()
        self.set_executable(exe)
        return exe

    def launch(self, *args, **kwargs):
        """Launch a new shell window. Uses Popen so the process runs detached."""
        exe, shell_args = _find_shell_executable()
        cmd = [exe] + shell_args
        env = os.environ.copy()
        env = self.setup_env(env)

        popen_kwargs = {'env': env}
        if platform.system() == 'Windows':
            popen_kwargs['creationflags'] = subprocess.CREATE_NEW_CONSOLE

        return subprocess.Popen(cmd, **popen_kwargs)


_shell_plugin = Shell()
_shell_plugin.find()
deda.core.PluginRegistry().register(_shell_plugin)
