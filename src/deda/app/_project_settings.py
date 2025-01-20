# ###################################################################################
#
# Copyright 2024 Ben Deda
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
__all__ = ['ProjectSettingsDialog', 'StartProjectDialog']

from PySide6 import QtWidgets

import deda.core

# pip install https://github.com/NVIDIA/warp/releases/download/v1.4.2/warp_lang-1.4.2+cu11-py3-none-win_amd64.whl


class StartProjectDialog(QtWidgets.QDialog):
    
    def __init__(self, config, parent=None):
        super().__init__(parent=parent)
        
        # Create a new project (ProjectConfig), or browse for one.
        self.setWindowTitle('Start a Project')
        
        self._config = config        
        self._project = deda.core.ProjectConfig(name='My Project', rootdir='C:\dedaverse')
        
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)
        
        grid = QtWidgets.QGridLayout()
        vbox.addLayout(grid)
        vbox.addStretch()
        
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self.save_and_close)
        btns.rejected.connect(self.close)
        vbox.addWidget(btns)
        
    def save_and_close(self):
        if self._project not in self._config.projects:
            self._config.user.projects.append(self._project)
        self._config.current_project = self._project
        self._config.save()
        self.close()
        

class ProjectSettingsDialog(QtWidgets.QDialog):
    
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        
        self.setWindowTitle('Project Settings')
        
        # project picker
        # project property panel
        
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)
        
        box = QtWidgets.QGroupBox('Available Projects')
        vbox.addWidget(box)
        grid = QtWidgets.QGridLayout()
        box.setLayout(grid)         
        
        lbl = QtWidgets.QLabel('Project')
        grid.addWidget(lbl, 0, 0)
        self._project_cb = QtWidgets.QComboBox()
        projects = deda.core.UserConfig().projects
        for project in projects:
            self._project_cb.addItem(project.name, project)
        grid.addWidget(self._project_cb, 0, 1, 1, -1)
        
        box = QtWidgets.QGroupBox('Project')
        vbox.addWidget(box)
        
        grid = QtWidgets.QGridLayout()
        box.setLayout(grid)
        
        lbl = QtWidgets.QLabel('Project Name')
        grid.addWidget(lbl, 0, 0)
        self._project_name_le = QtWidgets.QLineEdit()
        grid.addWidget(self._project_name_le, 0, 1, 1, -1)
        
        lbl = QtWidgets.QLabel('Root Directory')
        grid.addWidget(lbl, 1, 0)
        self._project_rootdir_le = QtWidgets.QLineEdit()
        grid.addWidget(self._project_rootdir_le, 1, 1, 1, -1)  
        # TODO add dir browser button
        
        self._perforce_cb = QtWidgets.QCheckBox('Use Perforce')
        grid.addWidget(self._perforce_cb, 2, 0, 1, -1)  
        
        vbox.addStretch()
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        btns.button(QtWidgets.QDialogButtonBox.Save).setEnabled(False)
        vbox.addWidget(btns)
        
        btns.accepted.connect(self.save_and_close)
        btns.rejected.connect(self.close)
        
    def save_and_close(self):
        # TODO: save the project settings
        self.close()
        
        
        