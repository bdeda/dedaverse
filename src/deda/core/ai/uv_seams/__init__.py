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
"""Predict UV seams (and so UV islands) on game meshes with a model trained on existing assets.

Task: for every mesh edge shared by two faces, predict whether it is a seam. Cutting the predicted seams
splits the mesh into islands, which can feed an unwrapper. Labels come for free from the UV layouts artists
already made. See ``docs/UV_ISLAND_MODEL_PLAN.md``.

The geometry, data, metric and configuration code is numpy only and is imported eagerly. The PyTorch parts
(:class:`SeamNet`, :func:`train`, :func:`evaluate`, :func:`predict`, :class:`SeamPrediction`) and the USD reader
(:class:`UsdSource`, :func:`list_usd_meshes`, :func:`load_usd_mesh`, :func:`split_usd_sources`) are loaded on first
access, so importing this package never requires torch or pxr.

Command line::

    python -m deda.core.ai.uv_seams train --synthetic 200 --epochs 5 --out runs/smoke
    python -m deda.core.ai.uv_seams train --data-dir data/npz --out runs/exp1 --epochs 100 --amp
    python -m deda.core.ai.uv_seams train --usd /art/hero /art/props/crate.usd --out runs/usd1 --uv-set st
    python -m deda.core.ai.uv_seams predict --weights runs/exp1/best.pt --mesh asset.npz
"""
import importlib

from ._data import (ROTATION_MODES, Batch, MeshSeamDataset, MeshSource, NpzSource, SyntheticSource, collate_samples,
                    estimate_pos_weight, random_rotation, regex_group_key, split_paths)
from ._geometry import (EDGE_DIM, NODE_DIM, UV_TOL, WELD_TOL, SeamSample, UvLayout, build_dual_graph, decode_islands,
                        edge_features, face_geometry, islands_from_uv, label_components, make_synthetic_box,
                        node_features, normalize_vertices, prepare_sample, seam_labels, uv_seam_labels, weld_vertices)
from ._metrics import EdgeCounts, best_threshold, island_count_error
from ._options import TrainConfig, lr_scale
from ._usd_arrays import USD_SUFFIXES, UV_INTERPOLATIONS, find_usd_files, usd_mesh_to_arrays, z_up_to_y_up

__all__ = ['EDGE_DIM', 'NODE_DIM', 'ROTATION_MODES', 'USD_SUFFIXES', 'UV_INTERPOLATIONS', 'UV_TOL', 'WELD_TOL',
           'Batch', 'EdgeCounts', 'MeshSeamDataset', 'MeshSource', 'NpzSource', 'SeamSample', 'SyntheticSource',
           'TrainConfig', 'UvLayout', 'best_threshold', 'build_dual_graph', 'collate_samples', 'decode_islands',
           'edge_features', 'estimate_pos_weight', 'face_geometry', 'find_usd_files', 'island_count_error',
           'islands_from_uv', 'label_components', 'lr_scale', 'make_synthetic_box', 'node_features',
           'normalize_vertices', 'prepare_sample', 'random_rotation', 'regex_group_key', 'seam_labels', 'split_paths',
           'usd_mesh_to_arrays', 'uv_seam_labels', 'weld_vertices', 'z_up_to_y_up']

# Public names loaded on first access, and the private module that defines each: the PyTorch parts need torch,
# the USD reader needs pxr.
_LAZY_NAMES = {'SeamNet': '_model', 'SeamPrediction': '_trainer', 'evaluate': '_trainer', 'predict': '_trainer',
               'train': '_trainer', 'UsdMeshRef': '_usd', 'UsdSource': '_usd', 'list_usd_meshes': '_usd',
               'load_usd_mesh': '_usd', 'split_usd_sources': '_usd'}


def __getattr__(name: str):
    """Load the torch- and pxr-backed names lazily (PEP 562)."""
    module = _LAZY_NAMES.get(name)
    if module is None:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    return getattr(importlib.import_module(f'.{module}', __name__), name)
