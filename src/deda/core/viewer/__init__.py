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
"""USDView plugins for Dedaverse."""

__all__ = ['CameraReticlePlugin', 'Playbar', 'UsdViewWidget']

try:
    from ._camera_reticle import CameraReticlePlugin
    from ._playbar import Playbar
    from ._usd_viewer import UsdViewWidget
except ImportError:
    # The 3D viewport needs a USD build with usdview (pxr.Usdviewq); the 2D media modules
    # (_media, _media_view) do not. Running the viewer reports the missing module.
    CameraReticlePlugin = Playbar = UsdViewWidget = None
