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
"""Maya 2027 application plugin.

Finds the Maya install and launches it with the dedaverse environment. Set the
MAYA_2027_LOCATION env var to override the default Autodesk install location.

Maya runs the maya-usd that Autodesk ships (USD 25.11) unless DEDAVERSE_MAYAUSD_DIR names the
install directory of a maya-usd built from source, such as the bdeda/maya-usd fork on USD 26.08
(it holds mayaUSD.mod; see that repository's doc/build_with_usd_26.md). Its modules then go
first on MAYA_MODULE_PATH and bring their own USD, so Autodesk's USD is not added to the
environment. DEDACAM_BUILD_DIR must then point at a dedacam Maya build made against that USD.

"""
import os
import logging
import subprocess
from pathlib import Path

import deda.core


__version__ = '0.1.0'
__vendor__ = 'Autodesk'

log = logging.getLogger('deda.plugins.maya')

MAYA_VERSION = '2027'
# Pure-python dependencies for deda (requests, click, ...) installed for Maya's own interpreter.
# Maya's Python (3.13) differs from the dedaverse venv, so the venv site-packages must not be shared.
_DEPS_DIR = Path.home() / '.dedaverse' / 'maya' / 'site-packages'
_USD_ROOT = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Autodesk' / 'MayaUSD' / f'Maya{MAYA_VERSION}'
# Dedacam's staged Maya module (dedacam.mod); override the build dir with DEDACAM_BUILD_DIR.
_DEDACAM_BUILD_DIR = Path(os.environ.get('DEDACAM_BUILD_DIR', r'F:\git\bdeda\camera\build'))
# Opt in to a maya-usd built from source (the bdeda/maya-usd fork, on a newer USD than Maya ships):
# the directory of its install, which holds mayaUSD.mod.
ENV_MAYAUSD_DIR = 'DEDAVERSE_MAYAUSD_DIR'
_DEFAULT_LOCATION = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Autodesk' / f'Maya{MAYA_VERSION}'


def _is_foreign_usd(entry):
    """Return True if a PATH/PYTHONPATH entry belongs to a USD build other than Maya's.

    maya-usd fails to load next to another USD build, so these are dropped for the Maya session.
    """
    d = Path(entry)
    try:
        return (any(d.glob('usd_*.dll')) or (d / 'pxr').is_dir() or (d / 'usd' / 'plugInfo.json').is_file()
                or (d.parent / 'lib' / 'usd' / 'plugInfo.json').is_file())
    except OSError:
        # Unreadable entries (e.g. protected WindowsApps folders) cannot be inspected; keep them.
        return False


def _strip_usd(value):
    """Return a PATH-style string without the entries that belong to another USD build."""
    return os.pathsep.join(e for e in value.split(os.pathsep) if e and not _is_foreign_usd(e))


class Maya(deda.core.Application):
    """Autodesk Maya 2027. This plugin finds the Maya install and launches it with the
    appropriate environment for the dedaverse system.

    """

    icon_path = str(Path(__file__).parent / 'mayaico.png')

    def find(self):
        """Find maya.exe from MAYA_2027_LOCATION or the default Autodesk install location.

        Returns:
            (str) Full path of the executable, or None if Maya 2027 was not found.

        """
        location = os.environ.get(f'MAYA_{MAYA_VERSION}_LOCATION')
        root = Path(location) if location else _DEFAULT_LOCATION
        exe = root / 'bin' / 'maya.exe'
        if not exe.is_file():
            log.warning(f'Maya {MAYA_VERSION} not found at {exe}')
            return None
        self.set_executable(str(exe))
        return self._executable

    def setup_env(self, env):
        """Expose the deda and dedaverse python packages (and their dependencies) to Maya.

        Args:
            env: (dict) The original env.

        Returns:
            dict: The env with PYTHONPATH and PATH extended.

        """
        # Other USD builds on the global env (e.g. USD_ROOT) break maya-usd, so drop them first.
        env['PATH'] = _strip_usd(env.get('PATH', ''))
        env['PYTHONPATH'] = _strip_usd(env.get('PYTHONPATH', ''))
        env.pop('USD_ROOT', None)
        env.pop('PXR_PLUGINPATH_NAME', None)
        modules = []
        custom_mayausd = os.environ.get(ENV_MAYAUSD_DIR)
        if custom_mayausd and not (Path(custom_mayausd) / 'mayaUSD.mod').is_file():
            log.warning(f'{ENV_MAYAUSD_DIR}={custom_mayausd} has no mayaUSD.mod; using the maya-usd that Maya ships.')
            custom_mayausd = None
        if custom_mayausd:
            # First, so its modules win over Autodesk's of the same name. It brings its own USD
            # (and Python modules) through its module file.
            modules.append(custom_mayausd)
        dedacam_module = _DEDACAM_BUILD_DIR / 'maya'
        if (dedacam_module / 'dedacam.mod').is_file():
            modules.append(str(dedacam_module))
        else:
            log.warning(f'Dedacam Maya module not found in {dedacam_module}; dedacam will not be available in Maya.')
        if modules:
            env['MAYA_MODULE_PATH'] = os.pathsep.join(
                modules + ([env['MAYA_MODULE_PATH']] if env.get('MAYA_MODULE_PATH') else []))
        pythonpath = [str(Path(deda.__file__).resolve().parent.parent), str(Path(__file__).parent / 'startup')]
        if _DEPS_DIR.is_dir():
            pythonpath.append(str(_DEPS_DIR))
        else:
            log.warning(f'Maya dependencies not found at {_DEPS_DIR}; importing deda in Maya may fail.')
        # Maya only puts pxr on the path once the MayaUSD plugin loads; deda.core needs it at import.
        # A custom maya-usd supplies its own USD, so do not add Autodesk's.
        usd_dirs = sorted(_USD_ROOT.glob('*/mayausd/USD')) if _USD_ROOT.is_dir() and not custom_mayausd else []
        if usd_dirs:
            usd = usd_dirs[-1]
            pythonpath.append(str(usd / 'lib' / 'python'))
            env['PATH'] = os.pathsep.join([str(usd / 'lib'), str(usd / 'bin'), env.get('PATH', '')])
        existing = env.get('PYTHONPATH')
        env['PYTHONPATH'] = os.pathsep.join(pythonpath + ([existing] if existing else []))
        return env

    def load(self):
        """Load the plugin by locating the Maya executable."""
        log.info('Maya plugin loading...')
        if not self._executable and not self.find():
            return False
        self._loaded = True
        log.info(f'Maya loaded successfully: {self._executable}')
        return True

    def launch(self, *args, **kwargs):
        """Launch Maya without blocking the dedaverse app.

        Returns:
            subprocess.Popen: The running Maya process.

        """
        if not self._executable and not self.find():
            raise FileNotFoundError(f'Maya {MAYA_VERSION} executable not found.')
        cmd = [self._executable, *(str(a) for a in args)]
        env = self.setup_env(os.environ.copy())
        log.info(f'Launching Maya: {cmd}')
        return subprocess.Popen(cmd, env=env)


deda.core.PluginRegistry().register(Maya(f'Maya {MAYA_VERSION}', __version__, __vendor__,
                                         image=Maya.icon_path,
                                         description=Maya.__doc__))
