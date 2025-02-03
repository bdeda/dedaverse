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

import os
import logging

from PySide6 import QtWidgets, QtCore, QtGui

import deda.core

from ._buttons import AddButton


log = logging.getLogger(__name__)


def _uniquify_proj_name(name, projects):
    """Return a unique project name based on the given name, but incremented to
    make it unique for the given list of projects.
    
    """
    if name not in projects:
        return name
    n = 1
    name = f'{name} ({n})'
    while name in projects and n < 1000: # cap it
        n += 1
    return name


class StartProjectDialog(QtWidgets.QDialog):
    
    project_changed = QtCore.Signal()
    
    def __init__(self, config, parent=None):
        super().__init__(parent=parent)
        
        # Create a new project (ProjectConfig), or browse for one.
        self.setWindowTitle('Start a Project')
        self.setMinimumWidth(650)
        
        self._config = config
        name = _uniquify_proj_name('Untitled Project', self._config.projects)
        self._project = deda.core.ProjectConfig(name=name, rootdir='C:\dedaverse')
        
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)
        
        # TODO: Add help text here to tell the user what to do
        help_text = "Choose a project name and root directory."
        lbl = QtWidgets.QLabel(help_text)
        font = lbl.font()
        metrics = QtGui.QFontMetrics(font)        
        vbox.addSpacing(metrics.height())
        vbox.addWidget(lbl, QtCore.Qt.AlignCenter)
        vbox.addSpacing(metrics.height())
        
        grid = QtWidgets.QGridLayout()
        vbox.addLayout(grid)
        
        row = 0
        lbl = QtWidgets.QLabel('Project Name:')
        grid.addWidget(lbl, row, 0)
        self._name_editor = QtWidgets.QLineEdit()
        self._name_editor.setText(self._project.name)
        self._name_editor.textChanged.connect(self._set_project_name)
        grid.addWidget(self._name_editor, row, 1, 1, -1)
        row += 1
        
        lbl = QtWidgets.QLabel('Root Directory:')
        grid.addWidget(lbl, row, 0)
        self._rootdir_editor = QtWidgets.QLineEdit()
        self._rootdir_editor.setText(self._project.rootdir)
        grid.addWidget(self._rootdir_editor, row, 1)        
        browse_btn = QtWidgets.QPushButton('...')
        browse_btn.setFixedSize(browse_btn.sizeHint().height(), browse_btn.sizeHint().height())
        browse_btn.clicked.connect(self._pick_rootdir)
        grid.addWidget(browse_btn, row, 2)
        row += 1  
        
        # TODO: configure asset management plugin
        # configure notifications plugin
        # etc.
        
        vbox.addSpacing(metrics.height())
        vbox.addStretch()
        
        self._btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        self._btns.accepted.connect(self.save_and_close)
        self._btns.rejected.connect(self.close)
        vbox.addWidget(self._btns)
        
        self._validate_proj_root()
        
    def _set_project_name(self, text):
        self._project.name = text
        
    def _pick_rootdir(self):
        # TODO: verify this can work with network paths as a secondarily supported strucuture
        ret = QtWidgets.QFileDialog.getExistingDirectory(self, 'Choose Project Directory', self._project.rootdir)
        if not ret:
            return
        rootdir = os.path.abspath(ret).replace('\\', '/')
        # TODO: move these two cfg_path calculations to a function call on the ProjectConfig class
        cfg_path = os.path.join(rootdir, '.dedaverse', 'project.cfg').replace('\\', '/')
        if os.path.isfile(cfg_path):
            self._project = deda.core.ProjectConfig.load(cfg_path)
            if self._project:
                self._name_editor.setText(self._project.name)
        else:
            self._project.rootdir = ret
            self._project.cfg_path = os.path.join(self._project.rootdir, '.dedaverse', 'project.cfg').replace('\\', '/')                
        self._rootdir_editor.setText(ret)
        self._validate_proj_root()
        
    def _validate_proj_root(self):
        """Validate the project root is unique."""
        name = self._name_editor.text()
        rootdir = self._rootdir_editor.text()
        for proj in self._config.projects:
            if proj.rootdir == rootdir and proj.name == name:
                self._btns.button(QtWidgets.QDialogButtonBox.Save).setEnabled(False)
                self._check_proj_writable()
                return
        data = deda.core.ProjectConfig.load(rootdir)
        if data:
            if data.name != name:
                self._btns.button(QtWidgets.QDialogButtonBox.Save).setEnabled(False)
                self._check_proj_writable()
                return                
        self._btns.button(QtWidgets.QDialogButtonBox.Save).setEnabled(True)
        self._check_proj_writable()
        
    def _check_proj_writable(self):
        """Check if the current project is writable. If not, disable editing the name and rootdir."""
        if self._project and not self._project.is_writable:
            self._name_editor.setReadOnly(True)
            self._rootdir_editor.setReadOnly(True)
            return
        self._name_editor.setReadOnly(False)
        self._rootdir_editor.setReadOnly(False)        
        
    def save_and_close(self):
        if self._project not in self._config.projects:
            self._config.user.add_project(self._project)
        self._config.current_project = self._project
        self._project.save() # try to save, fail gracefully if cfg is not writable
        self._config.save()
        self.close()
        self.project_changed.emit()
        

class ProjectSettingsDialog(QtWidgets.QDialog):
    
    project_changed = QtCore.Signal()
    
    def __init__(self, config, parent=None):
        super().__init__(parent=parent)
        
        self._config = config
        
        self.setWindowTitle('Project Settings')
        self.setMinimumWidth(650)
        
        # project picker
        # project property panel
        
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)
        
        box = QtWidgets.QGroupBox('Available Projects')
        vbox.addWidget(box)
        grid = QtWidgets.QGridLayout()
        box.setLayout(grid)         
        
        lbl = QtWidgets.QLabel('Current Project:')
        grid.addWidget(lbl, 0, 0)
        self._project_cb = QtWidgets.QComboBox()
        for project in self._config.projects:
            self._project_cb.addItem(project.name, project)
        if self._config.current_project:
            self._project_cb.setCurrentText(self._config.current_project.name)
        else:
            self._project_cb.setCurrentIndex(-1)
        self._project_cb.currentIndexChanged.connect(self._current_project_changed)
        grid.addWidget(self._project_cb, 0, 1)
        self._add_proj_btn = AddButton(parent=self)
        self._add_proj_btn.clicked.connect(self._add_project)
        self._add_proj_btn.setToolTip('Add a Project')
        grid.addWidget(self._add_proj_btn, 0, 2)
        
        box = QtWidgets.QGroupBox('Project')
        vbox.addWidget(box)
        
        grid = QtWidgets.QGridLayout()
        box.setLayout(grid)
        
        lbl = QtWidgets.QLabel('Project Name:')
        grid.addWidget(lbl, 0, 0)
        self._project_name_le = QtWidgets.QLineEdit()
        if self._config.current_project:
            self._project_name_le.setText(self._config.current_project.name)
        self._project_name_le.textChanged.connect(self._project_name_changed)
        grid.addWidget(self._project_name_le, 0, 1, 1, -1)
        
        lbl = QtWidgets.QLabel('Root Directory:')
        grid.addWidget(lbl, 1, 0)
        self._project_rootdir_le = QtWidgets.QLineEdit()
        if self._config.current_project:
            self._project_rootdir_le.setText(self._config.current_project.rootdir)        
        grid.addWidget(self._project_rootdir_le, 1, 1, 1, -1)  
        # TODO add dir browser button
        
        # TODO: check for perforce plugin
        #self._perforce_cb = QtWidgets.QCheckBox('Use Perforce')
        #grid.addWidget(self._perforce_cb, 2, 0, 1, -1)  
        
        vbox.addStretch()
        self._btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        self._btns.button(QtWidgets.QDialogButtonBox.Save).setEnabled(False)
        vbox.addWidget(self._btns)
        
        self._btns.accepted.connect(self.save_and_close)
        self._btns.rejected.connect(self.close)
        
    def showEvent(self, event):
        """Update the list of projects in the combobox."""
        self.initialize()
        
    def initialize(self):
        self._project_cb.clear()
        for project in sorted(self._config.projects, key=lambda x: str(x)):
            self._project_cb.addItem(project.name, project)
        if self._config.current_project:
            self._project_cb.setCurrentText(self._config.current_project.name)
        else:
            self._project_cb.setCurrentIndex(-1)
        
    def _add_project(self):
        """Open the start project dialog."""
        dlg = StartProjectDialog(self._config, parent=self)
        dlg.project_changed.connect(self.initialize)
        dlg.exec_()
        self.project_changed.emit()
        
    def _current_project_changed(self, index):
        """User changed the combobox for the current project."""
        self._btns.button(QtWidgets.QDialogButtonBox.Save).setEnabled(True)
        current_project = self._project_cb.currentData()
        val1 = self._project_name_le.blockSignals(True)
        val2 = self._project_rootdir_le.blockSignals(True)
        try:
            if not current_project:
                self._project_name_le.clear()
                self._project_rootdir_le.clear()
                return
            self._project_name_le.setText(current_project.name)
            self._project_rootdir_le.setText(current_project.rootdir)
        finally:
            self._project_name_le.blockSignals(val1)
            self._project_rootdir_le.blockSignals(val2)            
        
    def _project_name_changed(self, proj_name):
        # do not trigger _current_project_changed
        orig_val = self._project_cb.blockSignals(True)
        try:
            if proj_name not in self._config.projects:
                self._project_cb.setCurrentIndex(-1)
            else:
                self._project_cb.setCurrentText(proj_name)
        finally:
            self._project_cb.blockSignals(orig_val)
        self._btns.button(QtWidgets.QDialogButtonBox.Save).setEnabled(True)
        
    def save_and_close(self):
        # new project?
        proj_name = self._project_name_le.text()
        rootdir = self._project_rootdir_le.text()
        if proj_name not in self._config.projects:
            # confirm with user that they want to create a new project with the new name
            ret = QtWidgets.QMessageBox.question(self, 'Create New Project?', 
                                                 f'Do you want to create a new project named "{proj_name}"?')
            if ret != QtWidgets.QMessageBox.Yes:
                log.warning('Cancelled creating a new project.')
                return
            proj = deda.core.ProjectConfig.load(rootdir)
            if not proj:
                proj = deda.core.ProjectConfig(name=proj_name, rootdir=rootdir)
        else:
            proj = self._config.get_project(proj_name)
        assert proj
        self._config.current_project = proj
        self._config.save()
        self.close()
        self.project_changed.emit()
        
        
        