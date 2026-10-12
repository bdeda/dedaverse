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
"""Dedacam camera effects (depth of field, focus zones, depth) in the 3D viewport.

Dedacam's usdview plugin hooks any usdview ``StageView`` without patching it, so the viewer
reuses it. The plugin is built from the dedacam repository
(``-DDEDACAM_BUILD_USDVIEW=ON``) against the same USD the viewer runs on. Set
``DEDACAM_USDVIEW_BUILD_DIR`` to that build directory, the one that holds ``usdview/`` and ``python/``.
"""
import importlib
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)

ENV_BUILD_DIR = 'DEDACAM_USDVIEW_BUILD_DIR'

#: View modes in menu order. ``off`` shows the normal viewport.
MODES = ('off', 'dof', 'zones', 'depth')
MODE_LABELS = {'off': 'Off', 'dof': 'Depth of Field', 'zones': 'Focus Zones', 'depth': 'Depth'}
QUALITY_TIERS = ('low', 'medium', 'high', 'cinematic')


class DedacamUnavailable(RuntimeError):
    """Dedacam cannot be used: not found, or it does not load against this USD."""


def find_build_dir(path: str | Path | None = None) -> Path | None:
    """Return the dedacam usdview build directory, or None if there is not a valid one.

    Args:
        path: Directory to check. Defaults to ``DEDACAM_USDVIEW_BUILD_DIR``.
    """
    value = path or os.environ.get(ENV_BUILD_DIR)
    if not value:
        return None
    candidate = Path(value).expanduser()
    if (candidate / 'usdview' / 'dedacam_usdview').is_dir() and (candidate / 'python').is_dir():
        return candidate
    return None


def load_hook(build_dir: str | Path | None = None):
    """Import and return ``dedacam_usdview.hook`` from a dedacam build.

    Raises:
        DedacamUnavailable: If there is no build, or it fails to import (for example because
            it was built against a different USD than the one running).
    """
    root = find_build_dir(build_dir)
    if root is None:
        raise DedacamUnavailable(
            f'No dedacam usdview build found. Set {ENV_BUILD_DIR} to the build directory that '
            'contains usdview/ and python/ (build dedacam with -DDEDACAM_BUILD_USDVIEW=ON).')
    for entry in (root / 'usdview', root / 'python'):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))
    try:
        return importlib.import_module('dedacam_usdview.hook')
    except ImportError as err:
        raise DedacamUnavailable(
            f'Dedacam in {root} could not be loaded: {err}\n'
            'It must be built against the same USD this viewer runs on.') from err


class DedacamController:
    """Turns dedacam's effects on and off for one ``StageView``."""

    def __init__(self, stage_view, loader=load_hook):
        """
        Args:
            stage_view: The usdview ``StageView`` to hook.
            loader: Returns the dedacam hook module. Replaced in tests.
        """
        self._stage_view = stage_view
        self._loader = loader
        self._hook = None
        self._mode = 'off'
        self._quality = 'cinematic'

    @staticmethod
    def is_available() -> bool:
        """True if a dedacam build is configured. It may still fail to load; see ``set_mode``."""
        return find_build_dir() is not None

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def quality(self) -> str:
        return self._quality

    @property
    def last_error(self) -> str | None:
        """The last error dedacam reported while rendering, or None."""
        state = getattr(self._stage_view, '_dedacam', None)
        return state.get('error') if state else None

    def _ensure_hook(self):
        if self._hook is None:
            self._hook = self._loader()
        return self._hook

    def set_mode(self, mode: str) -> None:
        """Show the viewport through a dedacam view mode, or ``off`` for the normal view.

        Raises:
            ValueError: If ``mode`` is not one of :data:`MODES`.
            DedacamUnavailable: If dedacam is not found or cannot load.
        """
        if mode not in MODES:
            raise ValueError(f'mode must be one of {MODES}, not {mode!r}')
        if mode == 'off':
            if self._hook is not None:
                self._hook.set_view(self._stage_view, None)
            self._mode = 'off'
            return
        hook = self._ensure_hook()
        hook.set_quality(self._quality)
        hook.set_view(self._stage_view, mode)
        self._mode = mode

    def set_quality(self, tier: str) -> None:
        """Set the quality tier (``low`` to ``cinematic``). Applies on the next render."""
        if tier not in QUALITY_TIERS:
            raise ValueError(f'quality must be one of {QUALITY_TIERS}, not {tier!r}')
        self._quality = tier
        if self._hook is not None:
            self._hook.set_quality(tier)
