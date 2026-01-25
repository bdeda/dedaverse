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
"""This is the event filter class that handles the drag and mouse move events for the DCCs that are dedaverse enabled.

The goal of this event filter is to catch when a dedaverse object is dragged and dropped into a DCC application. It will
be up to the DCC plugin to provide a handler for the drag/drop events and do any DCC sepecific logic to handle the object.

"""

__all__ = ['install_event_filter']

import logging

#import maya.cmds as cmds
#import maya.mel as mel
#import maya.OpenMayaUI as OpenMayaUI
#import maya.OpenMaya as OpenMaya

from PySide6 import QtGui, QtCore, QtWidgets


log = logging.getLogger('deda.eventfilter')


class EventFilter(QtCore.QObject):
    
    dragEnter = QtCore.Signal(object, object) 
    dragMove = QtCore.Signal(object, object, object)
    drop = QtCore.Signal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._dragged_object = None

    def handle_drag_enter(self, obj, event):
        """Handle the drag enter event. This will get the 
        dragged dedaverse object from the metadata, and 
        track the drag move event, providing a reference 
        to the tracked object to the handler via the signals.
        
        Args:
            obj: The Qt window object from the original event.
            event: The original event object.
            
        Returns:
            None 

        """
        if self._dragged_object:
            return
        #if obj.objectName():
            #try:
                #cmds.setFocus(obj.objectName())
            #except RuntimeError as err:
                #pass
        #ctx = cmds.currentCtx()
        #c = cmds.contextInfo(ctx, c=1)
        #if c == 'AssetDropTool':
        #    return
        #self._tracking = True

        if not event.mimeData():
            return        
        self._dragged_object = event.mimeData()
        if not self._dragged_object:
            return
        # TODO: handle more filtering to the specific mime data structure (ie, json.loads mimedata.text())
        log.debug(self._dragged_object)
        self.dragEnter.emit(obj, self._dragged_object)
        # Prevent maya from trying to import our data
        # make sure the mime data urls when doing a drag and drop action in maya, the urls are empty so Maya does not trigger an import
        #event.mimeData().setUrls('') 

        # determine context from Maya setup
        #context = cmds.setMenuMode()
        #if 'model' in context:
            ## Import mesh
            #pass
        #elif 'rig' in context:
            ## Import?
            #pass
        #elif 'anim' in context:
            ## reference rig, or apply anim data to rig, or...?
            #pass

        # for now, assume usd file
        # create stage node and load usda
        #node = cmds.createNode('mayaUsdProxyShape', skipSelect=True, name='stageShape1')
        #cmds.connectAttr('time1.outTime', node+'.time')
        #stage_nodes = cmds.ls(node, type='mayaUsdProxyShape', long=True)
        #node = stage_nodes[0]
        # track node transform via drag moves

    def handle_drag_move(self, obj, event):
        """Handle the drag move event.
        
        Args:
            obj: The Qt window object from the original event.
            event: The original event object.
            
        Returns:
            None 

        """
        #if not self._view:
        #    return
        if not self._dragged_object:
            # We are not tracking a drag event, so early out.
            return
        
        mouse_pos = obj.mapFromGlobal(QtGui.QCursor.pos())
        # TODO: emit signal with obj and mouse_pos
        self.dragMove.emit(obj, mouse_pos, self._dragged_object)
        
        #mouseButtons = QtWidgets.QApplication.mouseButtons()
        #if not mouseButtons:
        #    self._view.refresh()
        #    return

        # NOTE: artist wanted to flip the behavior here.
        #      The default would be no raycast while SHIFT and CTRL would work for raycast
        #
        #      SHIFT = raycast assuming the Y Axis is up vector
        #      CTRL = raycast, using the Y Axis Normal from the surface below object
        #if event.keyboardModifiers() in [QtCore.Qt.SHIFT, QtCore.Qt.CTRL]:
            ## get the current mouse position, rather than using the event position
            ## linux has a strange "feature" where the mouse events are buffered, but we need
            ## to have the position unbuffered for usability
            #mousePos = obj.mapFromGlobal(QtGui.QCursor.pos())

            #ret = self._worldPointFromScreen(mousePos.x(),
                                             #self._view.portHeight() - mousePos.y())

            #if ret:
                #hit_point, normal = ret
                #for node in self._nodes:
                    #cmds.xform(node, absolute=True,
                               #translation=[hit_point.x, hit_point.y, hit_point.z])
                    #if event.keyboardModifiers() == QtCore.Qt.CTRL:
                        #self._orientNodeToNormal(node, normal)
                    #elif (normal.x, normal.y, normal.z) == (0, -1, 0):
                        #cmds.xform(node, rotation=(0, 0, 180))
                    #else:
                        #self._orientNodeToNormal(node, [normal.x, 0, normal.z], [0,0,1])
        #else:
            #for node in self._nodes:
                #cmds.xform(node, absolute=1, translation=[0, 0, 0])
                #self._orientNodeToNormal(node, [0, 1, 0])
        #self._view.refresh()


    def handle_drop(self, obj, event):
        """Handle the drop or mouseButtonRelease events.
        
        Args:
            obj: The Qt window object from the original event.
            event: The original event object.
            
        Returns:
            None 

        """
        if not self._dragged_object:
            return
        # release the mime data we were tracking.
        log.debug(f'{self._dragged_object} dropped!')
        self._dragged_object = None


    def eventFilter(self, obj, event):
        """Event filter override.
        
        Args:
            obj: The QObject target for the event.
            event: The event object.
            
        Returns:
            None 
            
        """
        #self._view = OpenMayaUI.M3dView.active3dView()
        #if not self._view:
        #    return False
        if event.type() in (QtCore.QEvent.Drop, QtCore.QEvent.MouseButtonRelease):
            self.handle_drop(obj, event)
        elif event.type() == QtCore.QEvent.DragEnter:
            self.handle_drag_enter(obj, event)
        elif event.type() == QtCore.QEvent.DragMove:
            self.handle_drag_move(obj, event)
        return False


    '''
    def _worldPointFromScreen(self, x, y):
        pos = OpenMaya.MPoint()
        vec = OpenMaya.MVector()
        self._view.viewToWorld(x, y, pos, vec)

        # get the position on the grid in 3d space
        # Select from screen
        origSel = cmds.ls(sl=True)
        OpenMaya.MGlobal.selectFromScreen(x, y, x-1, y-1,
                                          OpenMaya.MGlobal.kReplaceList,
                                          OpenMaya.MGlobal.kSurfaceSelectMethod)
        objects = OpenMaya.MSelectionList()
        OpenMaya.MGlobal.getActiveSelectionList(objects)
        if origSel:
            cmds.select(origSel)
        else:
            cmds.select(clear=True)
        remove = list()
        dag = OpenMaya.MDagPath()
        nodes = self._nodesChildren + self._nodes
        for i in range(objects.length()):
            objects.getDagPath(i, dag)
            if dag.fullPathName() in nodes:
                remove.append(i)
                break
        for rem in sorted(remove)[::-1]:
            objects.remove(rem)
        if objects.length() > 0:
            hitPoints = {}
            fpoint = OpenMaya.MFloatPoint(pos.x, pos.y, pos.z)
            mesh_dag = OpenMaya.MDagPath()
            for i in range(objects.length()):
                objects.getDagPath(i, mesh_dag)
                try:
                    meshFn = OpenMaya.MFnMesh(mesh_dag)
                    ret = self._getPointOnMesh(meshFn, pos, vec)
                    if ret:
                        hitPoint, normal = ret
                        dist = fpoint.distanceTo(hitPoint)
                        hitPoints[dist] = ret
                        break
                        #return ret
                except RuntimeError as err:
                    pass
            if hitPoints:
                closest = sorted(hitPoints.keys())[0]
                return hitPoints[closest]

        # R(t)
        # x = pos.x + vec.x * t
        # y = pos.y + vec.y * t = 1
        # z = pos.z + vec.z * t
        t = -pos.y
        if vec.y != 0: # ortho views will be zero
            t = -pos.y / vec.y
        x = pos.x + vec.x * t
        #y = 0
        z = pos.z + vec.z * t
        return OpenMaya.MFloatPoint(x, 0, z), OpenMaya.MFloatPoint(0, 1, 0)


    def _orientNodeToNormal(self, node, normal, nodeVec=(0,1,0)):
        """Orient the nodes +y object space to the normal of the surface.

        """
        if isinstance(normal, (list, tuple)) and len(normal) >= 3:
            vecN = OpenMaya.MVector(normal[0], normal[1], normal[2]).normal()
        else:
            vecN = OpenMaya.MVector(normal.x, normal.y, normal.z).normal()
            normal = (vecN.x, vecN.y, vecN.z)
        vecY = OpenMaya.MVector(nodeVec[0], nodeVec[1], nodeVec[2])
        quat = OpenMaya.MQuaternion(vecY, vecN)
        matrix = OpenMaya.MTransformationMatrix()
        mtx = matrix.rotateTo(quat)
        erot = mtx.eulerRotation()
        if tuple(map(float, normal)) == (0., 0., -1.) and tuple(map(float, nodeVec)) == (0., 0., 1.):
            cmds.xform(node, rotation=(0, 180, 0))
        else:
            cmds.xform(node, rotation=(OpenMaya.MAngle(erot.x).asDegrees(),
                                       OpenMaya.MAngle(erot.y).asDegrees(),
                                       OpenMaya.MAngle(erot.z).asDegrees()))


    def _getPointOnMesh(self, meshFn, pos, vec):
        """Get a point on the mesh using a raycast from the view's camera.

        """
        hit_point = OpenMaya.MFloatPoint()

        ray_source_float = OpenMaya.MFloatPoint(pos.x, pos.y, pos.z)
        ray_direction_float = OpenMaya.MFloatVector(vec.x, vec.y, vec.z)

        face_idx_util = OpenMaya.MScriptUtil()
        face_idx_util.createFromInt(-1)
        face_int_ptr = face_idx_util.asIntPtr()

        accelParams = meshFn.autoUniformGridParams()

        ret = meshFn.closestIntersection(
            ray_source_float,
            ray_direction_float,
            None,
            None,
            False,
            OpenMaya.MSpace.kWorld,
            10000,
            False,
            accelParams,
            hit_point,
            None,
            face_int_ptr,
            None,
            None,
            None,
            0.0001
        )
        if not ret:
            return
        normal = OpenMaya.MVector()
        faceId = face_idx_util.getInt(face_int_ptr)
        if faceId > -1:
            meshFn.getPolygonNormal(faceId, normal, OpenMaya.MSpace.kWorld)
            return hit_point, OpenMaya.MFloatPoint(normal.x, normal.y, normal.z)
        else:
            return hit_point, OpenMaya.MFloatPoint(0, 1, 0)
    '''


def install_event_filter(handler):
    """Install the event filter for the application. This function should be called in the startup
    processes of the GUI modes of the various applications that we support. The caller should be 
    an installed startup script for the DCC application and provide the handler that DCC plugin 
    will use to handle the dedaverse object on the DCC side via import, reference, manual construction, 
    move, augmentation, etc.
    
    Args:
        handler: (object) The object that will handle the signals emitted from the eventfilter.
                
    Returns:
        None
        
    """
    import deda.app
    window = deda.app.get_top_window()
    if not window:
        log.error('Top window not found!')
        return
    filter_obj = EventFilter(parent=window)
    QtWidgets.QApplication.instance().installEventFilter(filter_obj)