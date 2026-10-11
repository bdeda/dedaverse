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
"""Builds the Deda menu inside Maya from the registered dedaverse Tool plugins."""
import logging

import deda.core
import deda.app

log = logging.getLogger('deda.plugins.maya')


def build():
    """Import the plugin modules and let each Tool plugin add its action to the Deda menu.

    Only Tool plugins are loaded: Application and file-manager plugins are not meaningful
    inside a DCC, and their load() calls may need packages Maya does not ship.

    Returns:
        (list(str)) The names of the tool plugins that loaded.

    """
    # initialize_plugins() imports each plugin under its bare folder name, and this one is called
    # "maya", which would replace Maya's own maya package. Having it already imported makes it skip.
    import deda.plugins.maya  # pylint: disable=import-outside-toplevel,unused-import
    deda.core.initialize()
    deda.app.get_main_menu()  # create the menu first so the menu keeps its place in the bar
    loaded = []
    for plugin in deda.core.PluginRegistry().iter_plugins(deda.core.Tool):
        try:
            if plugin.load() is not False:
                loaded.append(plugin.name)
        except Exception as err:  # pylint: disable=broad-except
            log.error(f'Failed to load tool plugin {plugin.name} in Maya: {err}')
            log.exception(err)
    log.info(f'Deda menu tools: {loaded}')
    return loaded
