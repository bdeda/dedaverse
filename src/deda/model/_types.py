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


def all_default_asset_types():
    """Default asset types available to include in a project.
    
    An asset type is a container of parts that go together to produce the final result 
    in the delivered project. The asset types map to the projects production templates 
    for tasking out the production of the elements that belong to that asset type.
    
    For Diablo, this list would include Monster, Class, NPC, Mount, """
    return [
        'Collection', # generic collection of child assets
        'Sequence',   # collection of shots
        'Shot',       # linear media deliverable rendered as an image sequence or movie
        'Asset',      # generic asset, no defined structure
        'Character',  # rigged and animated mesh, includes additional elements not included in simple assets
        'Actor',      # implies additional work for setup in a game engine with control systems and gameplay systems
        'Prop',
        'Set',
        'Kit',        # This is an assembly with a layout for use by artists to work on related objects in a grid context
        ]


def all_default_element_types():
    """Elements are the things being produced as consumables or deliverables for various pipesteps of a production.
    
    This is a general list, but can be expanded for a site/project/user based on the complexity of the project 
    and the scale of the production. Bigger teams will typically have a more granular set of elements being produced 
    by the team members
    
    """
    return [
        'Animation',     # animation curve data or baked animation data
        'Assembly',      # a collection of elements from various assets.
        'Audio',         # audio file for VO, lip sync, shot tracks, etc.
        'Bind',          # bind info for attaching mesh to joints via alternative means other than skinned with skin weights
        'Cache',         # any data (super generic) that is baked into a form for delivery into another pipestep
        'Camera',        # camera information for viewing data in downstream pipesteps
        'Comp',          # composite (nuke, AfterEffects, etc.)
        'Document',      # documnetation, script for a sequence or shot, etc.
        'Edit',          # edit deliverable from editorial (Premiere project)
        'EDL',           # Information about the edit cuts and sequencial order of shots
        'FaceSet',       # sets of faces with an identifier that can be used in a material assignment or otehr purpose
        'Guides',        # 2d/3d geometric guides for use in producing other elements
        'Image',         # simple image 
        'ImageSequence', # Multiple images intended to be viewed in sequential order, or converted to a video/movie
        'Layout',        # The 2d or 3d position data for an assembly. Assemblies are the recipies, layouts are the spacial data. (markerset for Diablo)
        'Light',         # light for lighitng a digital scene
        'Look',          # all materials, shaders and textures as a fully combined assembly
        'Material',      # the material definitions
        'Mesh',          # Mesh data
        'Notes',         # feedback attached to a specific set of elements or assets
        'Rig',           # The control rig used to position joints via animation or simulation processes
        'Script',        # python script, lua, perl, bat files, ps files, etc, for simple tasks, produced by artists for specific scenarios
        'Shader',        # Shader definition for use in a material
        'Simulation',    # Houdini setups or other setups that 
        'Skeleton',      # The joint information with position and orientaions
        'SkinnedMesh',   # mesh with joints and skin weights
        'SkinWeights',   # vert index to skin weight mapping for each joint in a skeleton
        'Texture',       # Simple texture image for use as a texture in a material
        'UVSet',         # UV data separate from teh Mesh. This is not necessarily separate from the mesh, but some productions will do this when there are multiple depts editing this data.
        'Video',         # playblast, final render with audio, etc.
        ]
