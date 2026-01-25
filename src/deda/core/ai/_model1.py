import time

import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

from tensorflow_graphics.geometry.transformation import quaternion
from tensorflow_graphics.math import vector
from tensorflow_graphics.notebooks import threejs_visualization
from tensorflow_graphics.notebooks.resources import tfg_simplified_logo

tf.compat.v1.enable_v2_behavior()

# Loads the Tensorflow Graphics simplified logo.
vertices = tfg_simplified_logo.mesh['vertices'].astype(np.float32)
faces = tfg_simplified_logo.mesh['faces']
num_vertices = vertices.shape[0]