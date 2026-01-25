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

from pxr import Usd, UsdSkel
import numpy

import os
#os.environ["TF_CPP_MIN_VLOG_LEVEL"] = "2"
#os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf
print(tf.config.list_physical_devices('GPU'))

from tensorflow import keras
import keras.saving
from tensorflow.keras import layers



from tensorflow_graphics.geometry.transformation import quaternion
from tensorflow_graphics.math import vector
from tensorflow_graphics.notebooks import threejs_visualization
from tensorflow_graphics.notebooks.resources import tfg_simplified_logo



#tf.compat.v1.enable_v2_behavior()

#print(tf.config.list_physical_devices('GPU'))


def usdskel_to_nparray(skel_prim):
    """Convert the usd skeleton to a numpy array of jopint transformation matrices for each joint on each frame."""
    skelCache = UsdSkel.Cache()
    stage = prim.GetStage()
    skel = UsdSkel.Skeleton.Get(stage, skel_prim.GetPath())
    skelQuery = skelCache.GetSkelQuery(skel)    
    
    poses = list()
    for frame in range(int(stage.GetStartTimeCode()), int(stage.GetEndTimeCode) + 1):
        skelSpaceXforms = skelQuery.ComputeJointSkelTransforms(Usd.TimeCode(frame))
        poses.append(numpy.array(skelSpaceXforms))
    return numpy.array(poses)
    
    
def nparray_to_usdskel(nparray, parent_prim):
    """Convert the nparray back to a usdskel."""
    

vertices = None

@keras.saving.register_keras_serializable()
def pose_estimation_loss(y_true, y_pred):
    """Pose estimation loss used for training.

    This loss measures the average of squared distance between some vertices
    of the mesh in 'rest pose' and the transformed mesh to which the predicted
    inverse pose is applied. Comparing this loss with a regular L2 loss on the
    quaternion and translation values is left as exercise to the interested
    reader.

    Args:
      y_true: The ground-truth value.
      y_pred: The prediction we want to evaluate the loss for.

    Returns:
      A scalar value containing the loss described in the description above.
    """
    # y_true.shape : (batch, 7)
    y_true_q, y_true_t = tf.split(y_true, (4, 3), axis=-1)
    # y_pred.shape : (batch, 7)
    y_pred_q, y_pred_t = tf.split(y_pred, (4, 3), axis=-1)

    # vertices.shape: (num_vertices, 3)
    # corners.shape:(num_vertices, 1, 3)
    corners = tf.expand_dims(vertices, axis=1)

    # transformed_corners.shape: (num_vertices, batch, 3)
    # q and t shapes get pre-pre-padded with 1's following standard broadcast rules.
    transformed_corners = quaternion.rotate(corners, y_pred_q) + y_pred_t

    # recovered_corners.shape: (num_vertices, batch, 3)
    recovered_corners = quaternion.rotate(transformed_corners - y_true_t,
                                        quaternion.inverse(y_true_q))

    # vertex_error.shape: (num_vertices, batch)
    vertex_error = tf.reduce_sum((recovered_corners - corners)**2, axis=-1)

    return tf.reduce_mean(vertex_error)


def generate_training_data(num_samples):
    # random_angles.shape: (num_samples, 3)
    random_angles = np.random.uniform(-np.pi, np.pi,
                                    (num_samples, 3)).astype(np.float32)

    # random_quaternion.shape: (num_samples, 4)
    random_quaternion = quaternion.from_euler(random_angles)

    # random_translation.shape: (num_samples, 3)
    random_translation = np.random.uniform(-2.0, 2.0,
                                         (num_samples, 3)).astype(np.float32)

    # data.shape : (num_samples, num_vertices, 3)
    data = quaternion.rotate(vertices[tf.newaxis, :, :],
                           random_quaternion[:, tf.newaxis, :]
                           ) + random_translation[:, tf.newaxis, :]

    # target.shape : (num_samples, 4+3)
    target = tf.concat((random_quaternion, random_translation), axis=-1)

    return np.array(data), np.array(target)  
  
# Callback allowing to display the progression of the training task.
class ProgressTracker(keras.callbacks.Callback):

    def __init__(self, num_epochs, step=5):
        self.num_epochs = num_epochs
        self.current_epoch = 0.
        self.step = step
        self.last_percentage_report = 0

    def on_epoch_end(self, batch, logs={}):
        self.current_epoch += 1.
        training_percentage = int(self.current_epoch * 100.0 / self.num_epochs)
        if training_percentage - self.last_percentage_report >= self.step:
            print('Training ' + str(
                training_percentage) + '% complete. Training loss: ' + str(
                    logs.get('loss')) + ' | Validation loss: ' + str(
                        logs.get('val_loss')))
            self.last_percentage_report = training_percentage  
    
def _main():
    
    # Loads the Tensorflow Graphics simplified logo.
    global vertices
    vertices = tfg_simplified_logo.mesh['vertices'].astype(np.float32)
    faces = tfg_simplified_logo.mesh['faces']
    num_vertices = vertices.shape[0]
    
    model_path = r"D:\my_ai_models\my_model.keras"
    if os.path.isfile(model_path):
        model = keras.saving.load_model(model_path)
    else:    
        # Constructs the model.
        model = keras.Sequential()
        model.add(layers.Flatten(input_shape=(num_vertices, 3)))
        model.add(layers.Dense(64, activation=tf.nn.tanh))
        model.add(layers.Dense(64, activation=tf.nn.relu))
        model.add(layers.Dense(7))  
        
        optimizer = keras.optimizers.Adam()
        model.compile(loss=pose_estimation_loss, optimizer=optimizer)
    model.summary()
    
    num_samples = 10000    
    data, target = generate_training_data(num_samples)
    
    reduce_lr_callback = keras.callbacks.ReduceLROnPlateau(monitor='val_loss',
                                                           factor=0.5,
                                                           patience=10,
                                                           verbose=0,
                                                           mode='auto',
                                                           min_delta=0.0001,
                                                           cooldown=0,
                                                           min_lr=0) 
    # google internal 1
    # Everything is now in place to train.
    EPOCHS = 100
    pt = ProgressTracker(EPOCHS)
    history = model.fit(
        data,
        target,
        epochs=EPOCHS,
        validation_split=0.2,
        verbose=0,
        batch_size=32,
        callbacks=[reduce_lr_callback, pt])
    
    model.save(model_path)
    
    plt.plot(history.history['loss'])
    plt.plot(history.history['val_loss'])
    plt.ylim([0, 1])
    plt.legend(['loss', 'val loss'], loc='upper left')
    plt.xlabel('Train epoch')
    _ = plt.ylabel('Error [mean square distance]')    
    
    
if __name__ == '__main__':
    
    #path = r"F:\usd_exports\IGC_T3_hlv_sorM_1040.usd"
    #stage = Usd.Stage.Open(path)
    #prim = stage.GetPrimAtPath('/SKEL/Position_Main_00_M_JNT')
    #ret = usdskel_to_nparray(prim)
    #print(ret)
    
    _main()