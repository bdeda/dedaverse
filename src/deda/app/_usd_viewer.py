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
__all__ = ['UsdViewWidget']


from PySide6 import QtWidgets, QtCore

from pxr import Usd
from pxr.Usdviewq.stageView import StageView


class UsdViewWidget(QtWidgets.QWidget):
    """3D Viewport for rendering a USD scene."""
    
    def __init__(self, stage=None, parent=None):
        super().__init__(parent=parent)
        
        self._view = StageView(parent=self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._view)
        layout.setContentsMargins(0, 0, 0, 0)

        if stage:
            self.stage = stage
        else:
            self.stage = Usd.Stage.CreateInMemory()

        self._view._dataModel.viewSettings.domeLightEnabled = True
        self._view._dataModel.viewSettings.domeLightTexturesVisible = True    

    @property
    def viewSettings(self):
        return self._view._dataModel.viewSettings

    @property
    def stage(self):
        return self._view._dataModel.stage

    @stage.setter
    def stage(self, stage):
        self._view.closeRenderer()
        self._view._dataModel.stage = None
        self._view.setUpdatesEnabled(False)
        try:
            self._view._dataModel.stage = stage or Usd.Stage.CreateInMemory()
            earliest = Usd.TimeCode.EarliestTime() # TODO: set to first frame of the stage time
            self._view._dataModel.currentFrame = Usd.TimeCode(earliest)

            self.viewSettings.domeLightEnabled = True
            self.viewSettings.domeLightTexturesVisible = True 

            self.update_view(resetCam=True, forceComputeBBox=True)
        finally:
            self._view.setUpdatesEnabled(True)


    def closeEvent(self, event):
        self._view.closeRenderer()

    def update_view(self, resetCam=False, forceComputeBBox=False):
        if self._view._dataModel.stage:
            self._view.updateView(resetCam=resetCam, forceComputeBBox=forceComputeBBox)

    def keyPressEvent(self, event):
        key = event.key()
        if key == QtCore.Qt.Key_F:
            self.update_view(resetCam=True, forceComputeBBox=True)        
        
        

if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    stage = Usd.Stage.Open('F:\\cube_from_blender.usda')
    w = UsdViewWidget()#stage=stage)
    w.show()
    w.stage = stage
    app.exec_()