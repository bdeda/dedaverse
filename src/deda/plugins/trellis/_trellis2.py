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
"""Find a local TRELLIS.2 install and run its ``app.py`` Gradio server.

TRELLIS.2 is Linux-only, so on Windows the server is started inside WSL. Everything that
depends on the machine is configurable through environment variables:

``DEDAVERSE_TRELLIS2_DIR``
    The TRELLIS.2 checkout (the folder containing ``app.py``).
``DEDAVERSE_TRELLIS2_ACTIVATE``
    A shell snippet that activates the Python environment, run before ``app.py``,
    e.g. ``conda activate trellis2`` or ``source .venv/bin/activate``.
``DEDAVERSE_TRELLIS2_COMMAND``
    Replaces the whole launch script (it still runs in the install directory).
``DEDAVERSE_TRELLIS2_WSL_DISTRO``
    WSL distribution to use on Windows. Defaults to the WSL default distribution.
"""
import logging
import os
import platform
import shlex
import subprocess
import time
from pathlib import Path, PureWindowsPath

log = logging.getLogger(__name__)

ENV_DIR = 'DEDAVERSE_TRELLIS2_DIR'
ENV_ACTIVATE = 'DEDAVERSE_TRELLIS2_ACTIVATE'
ENV_COMMAND = 'DEDAVERSE_TRELLIS2_COMMAND'
ENV_WSL_DISTRO = 'DEDAVERSE_TRELLIS2_WSL_DISTRO'

DEFAULT_INSTALL_DIR = Path(r'F:\git\bdeda\TRELLIS.2')
DEFAULT_PORT = 7860
MIN_GPU_GB = 24  # what the TRELLIS.2 README asks for; smaller cards may run out of memory
LOG_PATH = Path.home() / '.dedaverse' / 'trellis2' / 'server.log'


def find_install(path: str | Path | None = None) -> Path | None:
    """Return the TRELLIS.2 install directory, or None if there isn't a valid one.

    Args:
        path: Directory to check. Defaults to ``DEDAVERSE_TRELLIS2_DIR``, then
            :data:`DEFAULT_INSTALL_DIR`.
    """
    candidate = Path(path or os.environ.get(ENV_DIR) or DEFAULT_INSTALL_DIR).expanduser()
    if (candidate / 'app.py').is_file() and (candidate / 'trellis2').is_dir():
        return candidate
    return None


def to_wsl_path(path: str | Path) -> str:
    r"""Convert a Windows path to its WSL mount path, e.g. ``F:\a\b`` to ``/mnt/f/a/b``."""
    p = PureWindowsPath(path)   # parse as a Windows path whatever the host is
    if not p.drive:
        return p.as_posix()
    return f'/mnt/{p.drive[0].lower()}' + p.as_posix()[len(p.drive):]


def build_launch_command(install_dir: str | Path, port: int = DEFAULT_PORT,
                         system: str | None = None, env: dict | None = None) -> list[str]:
    """Build the command that starts the TRELLIS.2 server for ``install_dir``.

    Args:
        install_dir: The TRELLIS.2 checkout.
        port: Port for the server, passed to Gradio as ``GRADIO_SERVER_PORT``.
        system: ``platform.system()`` value; defaults to the current one.
        env: Environment to read the overrides from; defaults to ``os.environ``.

    Returns:
        The argument list for :class:`subprocess.Popen`.
    """
    env = os.environ if env is None else env
    system = system or platform.system()
    on_windows = system == 'Windows'
    directory = to_wsl_path(install_dir) if on_windows else str(install_dir)

    run = env.get(ENV_COMMAND) or f'GRADIO_SERVER_PORT={int(port)} exec python app.py'
    steps = [f'cd {shlex.quote(directory)}']
    if env.get(ENV_ACTIVATE):
        steps.append(env[ENV_ACTIVATE])
    steps.append(run)
    script = ' && '.join(steps)

    if not on_windows:
        return ['bash', '-lc', script]
    command = ['wsl']
    if env.get(ENV_WSL_DISTRO):
        command += ['-d', env[ENV_WSL_DISTRO]]
    return command + ['--', 'bash', '-lc', script]


def probe(install_dir: str | Path, timeout: float = 120.0) -> tuple[bool, str]:
    """Check that the Python environment can actually run TRELLIS.2.

    Starts the same shell the server would use and imports ``torch``, ``o_voxel`` and
    ``trellis2``, then reads the GPU memory. This does not load the model.

    Returns:
        ``(ok, message)``. ``message`` says what is missing, or describes the GPU. A GPU
        below :data:`MIN_GPU_GB` still returns ok, with a warning in the message.
    """
    check = ('python -c "import torch, o_voxel, trellis2; '
             "print(torch.cuda.get_device_properties(0).total_memory // 2**30)\"")
    env = dict(os.environ)
    env[ENV_COMMAND] = check
    try:
        proc = subprocess.run(build_launch_command(install_dir, env=env), capture_output=True,
                              text=True, timeout=timeout, check=False)
    except FileNotFoundError as err:
        return False, f'Could not start the shell for TRELLIS.2: {err}'
    except subprocess.TimeoutExpired:
        return False, f'The TRELLIS.2 environment check did not finish within {timeout:.0f}s.'
    if proc.returncode != 0:
        lines = (proc.stderr or proc.stdout or '').strip().splitlines()
        reason = lines[-1] if lines else f'The environment check failed (exit code {proc.returncode}).'
        return False, (f'{reason}\nSet up the TRELLIS.2 Python environment (see its README), and set '
                       f'{ENV_ACTIVATE} to the command that activates it, e.g. "conda activate trellis2".')
    try:
        gpu_gb = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return False, f'Unexpected output from the environment check: {proc.stdout.strip()!r}'
    if gpu_gb < MIN_GPU_GB:
        return True, (f'GPU has {gpu_gb} GB; TRELLIS.2 asks for {MIN_GPU_GB} GB. '
                      'Use 512 resolution and expect out-of-memory errors at higher ones.')
    return True, f'GPU has {gpu_gb} GB.'


class Trellis2Server:
    """Starts, watches and stops the TRELLIS.2 ``app.py`` server as a child process."""

    def __init__(self, install_dir: str | Path, port: int = DEFAULT_PORT, log_path: Path = LOG_PATH):
        self.install_dir = Path(install_dir)
        self.port = port
        self.log_path = Path(log_path)
        self._process = None

    @property
    def url(self) -> str:
        return f'http://127.0.0.1:{self.port}'

    @property
    def running(self) -> bool:
        """True while the server process we started is alive."""
        return self._process is not None and self._process.poll() is None

    def start(self) -> None:
        """Start the server if it is not already running. Returns without waiting for it.

        The model takes minutes to load, so poll :meth:`is_ready` rather than blocking.

        Raises:
            OSError: If the shell (``wsl`` or ``bash``) cannot be started.
        """
        if self.running:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        command = build_launch_command(self.install_dir, self.port)
        log.info(f'Starting TRELLIS.2 server: {command}')
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        with open(self.log_path, 'ab') as log_file:
            self._process = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT,
                                             creationflags=flags)

    def is_ready(self) -> bool:
        """True once the server answers HTTP requests."""
        import requests  # pylint: disable=import-outside-toplevel
        try:
            return requests.get(self.url + '/', timeout=2).status_code == 200
        except requests.RequestException:
            return False

    def wait_until_ready(self, timeout: float = 600.0, poll: float = 3.0) -> bool:
        """Block until the server is ready, it exits, or ``timeout`` seconds pass.

        Returns:
            True if the server is ready; False if it exited or timed out.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.is_ready():
                return True
            if not self.running:
                return False
            time.sleep(poll)
        return False

    def tail_log(self, lines: int = 20) -> str:
        """Return the last ``lines`` lines of the server log, to explain a failed start."""
        try:
            text = self.log_path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            return ''
        return '\n'.join(text.splitlines()[-lines:])

    def stop(self) -> None:
        """Stop the server process, if we started one."""
        if self._process is None:
            return
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
