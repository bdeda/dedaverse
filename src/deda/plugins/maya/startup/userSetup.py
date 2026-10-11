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
"""Maya startup hook for the dedaverse environment.

Maya runs ``userSetup.py`` from ``sys.path`` at startup; ``deda.plugins.maya`` puts this
folder on ``PYTHONPATH`` when it launches Maya, so the Deda menu only appears in sessions
launched from dedaverse.
"""
from maya import cmds


def _build_deda_menu():
    try:
        from deda.plugins.maya import _menu
        _menu.build()
    except Exception as err:  # pylint: disable=broad-except
        # A broken dedaverse setup must never stop Maya from starting.
        import traceback
        cmds.warning(f'Deda menu failed to load: {err}')
        traceback.print_exc()


# The Qt main window and menu bar do not exist yet while userSetup runs, so build the menu once
# Maya is idle. Batch and standalone Maya (maya -batch, mayapy, Render) have no UI at all, and
# deferring there blocks maya.standalone.initialize, so leave them alone.
if not cmds.about(batch=True):
    cmds.evalDeferred(_build_deda_menu, lowestPriority=True)
