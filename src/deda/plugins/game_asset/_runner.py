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
"""Run the optimizer pipeline in a background Blender process."""
__all__ = ['JOB_SCRIPT', 'blender_command', 'default_output_dir', 'optimize']

import json
import logging
# Runs Blender with a fixed argument list, never through a shell.
import subprocess  # nosec B404
import tempfile
from collections.abc import Callable
from pathlib import Path

from deda.core.finder import BLENDER_ENV_VAR, find_blender

from ._options import SOURCE_SUFFIXES, OptimizeError, OptimizeOptions, OptimizeResult

log = logging.getLogger(__name__)

JOB_SCRIPT = Path(__file__).with_name('_blender_job.py')
_TAIL_LINES = 25


def blender_command(blender: Path, job_file: Path) -> list[str]:
    """Command line that runs the pipeline job in ``blender`` without UI, user prefs or add-ons.

    Args:
        blender: Blender executable.
        job_file: JSON job written by :func:`optimize`.

    Returns:
        The argument list for ``subprocess``.
    """
    return [str(blender), '--background', '--factory-startup', '--python-exit-code', '1',
            '--python', str(JOB_SCRIPT), '--', str(job_file)]


def default_output_dir(source: Path) -> Path:
    """Where outputs go when no directory is given: ``<source dir>/<source stem>_game``."""
    return source.parent / f'{source.stem}_game'


def optimize(source: Path, output_dir: Path | None = None, options: OptimizeOptions | None = None,
             blender: Path | None = None, on_output: Callable[[str], None] | None = None) -> OptimizeResult:
    """Turn a dense mesh into a game-ready mesh with baked PBR textures.

    Args:
        source: Mesh file (USD/USDZ, GLB/glTF, FBX or OBJ).
        output_dir: Directory for the outputs (default: :func:`default_output_dir`).
        options: Pipeline settings (default: :class:`OptimizeOptions` defaults).
        blender: Blender executable (default: :func:`deda.core.finder.find_blender`).
        on_output: Called with each line Blender prints, for progress display.

    Returns:
        The outputs and measurements.

    Raises:
        OptimizeError: If the source or options are invalid, Blender is missing, or the pipeline fails.
    """
    source = Path(source)
    if not source.is_file():
        raise OptimizeError(f'source not found: {source}')
    if source.suffix.lower() not in SOURCE_SUFFIXES:
        raise OptimizeError(f'unsupported source type {source.suffix!r}; expected one of {SOURCE_SUFFIXES}')
    options = options or OptimizeOptions()
    options.validate()
    blender = blender or find_blender()
    if blender is None:
        raise OptimizeError(f'Blender was not found; install it or set {BLENDER_ENV_VAR} to blender(.exe)')
    output_dir = Path(output_dir) if output_dir else default_output_dir(source)

    with tempfile.TemporaryDirectory(prefix='deda_game_asset_') as tmp:
        job_file = Path(tmp) / 'job.json'
        result_file = Path(tmp) / 'result.json'
        job_file.write_text(json.dumps({'source': str(source.resolve()), 'output_dir': str(output_dir.resolve()),
                                        'options': options.to_dict(), 'result': str(result_file)}),
                            encoding='utf-8')
        log.info('Optimizing %s with %s', source, blender)
        code, tail = _run_blender(blender_command(blender, job_file), on_output)
        if not result_file.is_file():
            raise OptimizeError(f'Blender exited with code {code} before writing a result:\n' + '\n'.join(tail))
        payload = json.loads(result_file.read_text(encoding='utf-8'))
    if 'error' in payload:
        log.debug('Blender job traceback:\n%s', payload.get('traceback', ''))
        raise OptimizeError(payload['error'])
    return OptimizeResult.from_dict(payload)


# --- Internal -------------------------------------------------------------------------

def _run_blender(command: list[str], on_output: Callable[[str], None] | None) -> tuple[int, list[str]]:
    """Run ``command``, forwarding output lines; return the exit code and the last lines printed."""
    tail: list[str] = []
    # Fixed argument list (blender_command), no shell.
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,  # nosec B603
                          text=True, encoding='utf-8', errors='replace') as proc:
        for raw in proc.stdout:
            line = raw.rstrip()
            tail = (tail + [line])[-_TAIL_LINES:]
            if on_output is not None:
                on_output(line)
        code = proc.wait()
    return code, tail
