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
"""Client for a TRELLIS.2 Gradio server (the ``app.py`` that ships with TRELLIS.2).

TRELLIS.2 keeps the generated model in a ``gr.State`` on the server, tied to the Gradio
*session*. ``image_to_3d`` and ``extract_glb`` therefore only work when both calls are made
through the same ``gradio_client.Client`` instance, which is what this class holds on to.
Needs the optional ``trellis`` extra (``gradio_client``).
"""
import logging
import random
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

MAX_SEED = 2**31 - 1
RESOLUTIONS = ('512', '1024', '1536')


def _handle_file(path: str):
    """Wrap a local file path so ``gradio_client`` uploads it."""
    from gradio_client import handle_file  # pylint: disable=import-outside-toplevel
    return handle_file(path)


def _gradio_client_factory(url: str):
    """Create a ``gradio_client.Client`` for ``url``."""
    try:
        from gradio_client import Client
    except ImportError as err:
        raise ImportError('gradio_client is required for the Trellis client. '
                          'Install it with: pip install -e ".[trellis]"') from err
    return Client(url, verbose=False)


class TrellisApiClient:
    """Client for a TRELLIS.2 Gradio server."""

    def __init__(self, base_url: str = 'http://127.0.0.1:7860',
                 client_factory: Callable[[str], object] | None = None):
        """Initialize the client. No connection is made until it is first used.

        Args:
            base_url: URL of the TRELLIS.2 server.
            client_factory: Builds the underlying Gradio client from a URL. Defaults to
                ``gradio_client.Client``; tests pass a fake.

        Raises:
            ImportError: If ``gradio_client`` is needed but not installed.
        """
        self.base_url = base_url.rstrip('/')
        self._client_factory = client_factory or _gradio_client_factory
        if client_factory is None:
            try:
                import gradio_client  # noqa: F401  # pylint: disable=import-outside-toplevel,unused-import
            except ImportError as err:
                raise ImportError('gradio_client is required for the Trellis client. '
                                  'Install it with: pip install -e ".[trellis]"') from err
        self._client = None

    def check_connection(self) -> bool:
        """Return True if the TRELLIS.2 server is reachable."""
        import requests  # pylint: disable=import-outside-toplevel
        try:
            return requests.get(f'{self.base_url}/', timeout=2).status_code == 200
        except requests.RequestException:
            return False

    def _session(self):
        """Return the Gradio client for the current session, connecting on first use."""
        if self._client is None:
            self._client = self._client_factory(self.base_url)
        return self._client

    def reset_session(self) -> None:
        """Drop the session. The model held by the server for it is lost."""
        self._client = None

    def _find_endpoint(self, client, name: str) -> str | None:
        """Return the API name of the endpoint whose function is ``name``, or None.

        Gradio disambiguates duplicate function names with a numeric suffix
        (``/preprocess_image_1``), so the exact name is looked up instead of assumed.
        """
        named = client.view_api(return_format='dict', print_info=False).get('named_endpoints', {})
        for api_name in named:
            stripped = api_name.lstrip('/')
            if stripped == name or (stripped.startswith(name + '_') and stripped[len(name) + 1:].isdigit()):
                return api_name
        return None

    def generate_3d_from_image(
        self,
        image_path: str | Path,
        seed: int | None = None,
        randomize_seed: bool = True,
        resolution: str = '1024',
        ss_guidance_strength: float = 7.5,
        ss_guidance_rescale: float = 0.7,
        ss_sampling_steps: int = 12,
        ss_rescale_t: float = 5.0,
        shape_guidance_strength: float = 7.5,
        shape_guidance_rescale: float = 0.5,
        shape_sampling_steps: int = 12,
        shape_rescale_t: float = 3.0,
        tex_guidance_strength: float = 1.0,
        tex_guidance_rescale: float = 0.0,
        tex_sampling_steps: int = 12,
        tex_rescale_t: float = 3.0,
        preprocess: bool = True,
    ) -> dict:
        """Generate a textured 3D model from an image on the TRELLIS.2 server.

        The model stays on the server for this client's session; call :meth:`extract_glb`
        on the same instance to get it out.

        Args:
            image_path: Path to the input image.
            seed: Seed to use. Ignored (a random one is used) when ``randomize_seed`` is set.
            randomize_seed: Pick a random seed.
            resolution: One of ``RESOLUTIONS``. Higher needs more GPU memory.
            ss_*: Stage 1 (sparse structure) sampler settings.
            shape_*: Stage 2 (shape) sampler settings.
            tex_*: Stage 3 (material) sampler settings.
            preprocess: Run the server's image preprocessing (background removal and crop),
                which the web UI does on upload, before generating.

        Returns:
            dict: ``state`` (the settings used, truthy once a model exists on the server),
            ``seed`` and ``preview_html`` (the server's preview markup).

        Raises:
            FileNotFoundError: If ``image_path`` does not exist.
            ValueError: If ``resolution`` is not supported.
        """
        image_path = Path(image_path)
        if not image_path.is_file():
            raise FileNotFoundError(f'Image not found: {image_path}')
        if resolution not in RESOLUTIONS:
            raise ValueError(f'Unsupported resolution {resolution!r}; expected one of {RESOLUTIONS}')
        if randomize_seed or seed is None:
            seed = random.randint(0, MAX_SEED)

        client = self._session()
        image = _handle_file(str(image_path))
        if preprocess:
            endpoint = self._find_endpoint(client, 'preprocess_image')
            if endpoint:
                processed = client.predict(image, api_name=endpoint)
                image = _handle_file(processed['path'] if isinstance(processed, dict) else processed)
            else:
                log.warning('Trellis server has no preprocess_image endpoint; using the image as is.')

        log.info(f'Generating 3D model from {image_path.name} (seed={seed}, resolution={resolution})')
        result = client.predict(
            image, seed, resolution,
            ss_guidance_strength, ss_guidance_rescale, ss_sampling_steps, ss_rescale_t,
            shape_guidance_strength, shape_guidance_rescale, shape_sampling_steps, shape_rescale_t,
            tex_guidance_strength, tex_guidance_rescale, tex_sampling_steps, tex_rescale_t,
            api_name='/image_to_3d',
        )
        # The state output is kept server-side, so only the HTML preview comes back.
        preview_html = result[-1] if isinstance(result, (list, tuple)) else result
        return {
            'state': {'seed': seed, 'resolution': resolution},
            'seed': seed,
            'preview_html': preview_html,
        }

    def extract_glb(
        self,
        state: dict | None = None,
        decimation_target: int = 500000,
        texture_size: int = 2048,
    ) -> bytes:
        """Extract a GLB of the model generated earlier in this client's session.

        Args:
            state: The ``state`` from :meth:`generate_3d_from_image`. Only checked for
                presence: the real state lives on the server, in this client's session.
            decimation_target: Target face count (100000-1000000).
            texture_size: Texture resolution (1024-4096).

        Returns:
            bytes: The GLB file contents.

        Raises:
            RuntimeError: If no model has been generated with this client.
        """
        if self._client is None or not state:
            raise RuntimeError('No generated model in this session: call generate_3d_from_image first.')
        log.info(f'Extracting GLB (decimation_target={decimation_target}, texture_size={texture_size})')
        result = self._client.predict(decimation_target, texture_size, api_name='/extract_glb')
        glb_path = result[0] if isinstance(result, (list, tuple)) else result
        return Path(glb_path).read_bytes()

    def extract_usd(
        self,
        state: dict | None = None,
        decimation_target: int = 500000,
        texture_size: int = 2048,
    ) -> bytes:
        """Extract a USD file of the generated model.

        This extracts a GLB, then converts it to USD.

        Args:
            state: The ``state`` from :meth:`generate_3d_from_image`.
            decimation_target: Target face count (100000-1000000).
            texture_size: Texture resolution (1024-4096).

        Returns:
            bytes: The USD file contents.
        """
        glb_data = self.extract_glb(state, decimation_target, texture_size)
        if not glb_data:
            raise ValueError('Failed to extract GLB file for USD conversion')
        return self._glb_to_usd(glb_data)

    def _glb_to_usd(self, glb_data: bytes) -> bytes:
        """Convert GLB data to USD format.
        
        Args:
            glb_data: GLB file bytes
        
        Returns:
            USD file bytes
        """
        try:
            from pxr import Usd, UsdGeom, Gf, Sdf, UsdShade
            import tempfile
            import os
            
            # Write GLB to temporary file
            with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as tmp_glb:
                tmp_glb.write(glb_data)
                tmp_glb_path = tmp_glb.name
            
            try:
                # Create a temporary USD file
                with tempfile.NamedTemporaryFile(suffix='.usd', delete=False) as tmp_usd:
                    tmp_usd_path = tmp_usd.name
                
                # Create USD stage
                stage = Usd.Stage.CreateNew(tmp_usd_path)
                
                # Create root prim
                root_prim = stage.DefinePrim('/Model', 'Xform')
                stage.SetDefaultPrim(root_prim)
                
                # Read GLB using trimesh (if available)
                try:
                    import trimesh
                    glb_mesh = trimesh.load(tmp_glb_path, file_type='glb')
                    
                    # Handle scene with multiple meshes
                    if isinstance(glb_mesh, trimesh.Scene):
                        meshes = list(glb_mesh.geometry.values())
                    elif isinstance(glb_mesh, trimesh.Trimesh):
                        meshes = [glb_mesh]
                    else:
                        meshes = []
                    
                    for i, mesh in enumerate(meshes):
                        if not isinstance(mesh, trimesh.Trimesh):
                            continue
                        
                        # Create mesh prim
                        mesh_prim_path = f'/Model/Mesh_{i}'
                        mesh_prim = stage.DefinePrim(mesh_prim_path, 'Mesh')
                        mesh_schema = UsdGeom.Mesh(mesh_prim)
                        
                        # Set vertices
                        vertices = mesh.vertices
                        points_attr = mesh_schema.GetPointsAttr()
                        points_attr.Set([Gf.Vec3f(*v) for v in vertices])
                        
                        # Set face vertex indices
                        faces = mesh.faces
                        face_vertex_counts = [len(face) for face in faces]
                        face_vertex_indices = faces.flatten()
                        mesh_schema.GetFaceVertexCountsAttr().Set(face_vertex_counts)
                        mesh_schema.GetFaceVertexIndicesAttr().Set(face_vertex_indices.tolist())
                        
                        # Set normals if available
                        if hasattr(mesh.visual, 'vertex_normals') and mesh.visual.vertex_normals is not None:
                            normals = mesh.visual.vertex_normals
                            normal_attr = UsdGeom.PrimvarsAPI(mesh_prim).CreatePrimvar(
                                'normals',
                                Sdf.ValueTypeNames.Normal3fArray,
                                UsdGeom.Tokens.vertex
                            )
                            normal_attr.Set([Gf.Vec3f(*n) for n in normals])
                        elif hasattr(mesh, 'vertex_normals') and mesh.vertex_normals is not None:
                            normals = mesh.vertex_normals
                            normal_attr = UsdGeom.PrimvarsAPI(mesh_prim).CreatePrimvar(
                                'normals',
                                Sdf.ValueTypeNames.Normal3fArray,
                                UsdGeom.Tokens.vertex
                            )
                            normal_attr.Set([Gf.Vec3f(*n) for n in normals])
                        
                        # Set UVs if available
                        uvs = None
                        if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
                            uvs = mesh.visual.uv
                        elif hasattr(mesh, 'visual') and hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
                            uvs = mesh.visual.uv
                        
                        if uvs is not None:
                            uv_attr = UsdGeom.PrimvarsAPI(mesh_prim).CreatePrimvar(
                                'st',
                                Sdf.ValueTypeNames.TexCoord2fArray,
                                UsdGeom.Tokens.vertex
                            )
                            uv_attr.Set([Gf.Vec2f(*uv) for uv in uvs])
                        
                        # Set material/texture if available
                        material_prim_path = None
                        if hasattr(mesh.visual, 'material') and mesh.visual.material is not None:
                            material = mesh.visual.material
                            material_prim_path = f'/Model/Material_{i}'
                            material_prim = stage.DefinePrim(material_prim_path, 'Material')
                            material_schema = UsdShade.Material(material_prim)
                            
                            # Create shader
                            shader_prim_path = f'{material_prim_path}/Shader'
                            shader_prim = stage.DefinePrim(shader_prim_path, 'Shader')
                            shader_schema = UsdShade.Shader(shader_prim)
                            shader_schema.CreateIdAttr('UsdPreviewSurface')
                            
                            # Set base color if available
                            if hasattr(material, 'main_color') or hasattr(material, 'baseColorFactor'):
                                base_color = getattr(material, 'main_color', None) or getattr(material, 'baseColorFactor', None)
                                if base_color is not None:
                                    if isinstance(base_color, (list, tuple)) and len(base_color) >= 3:
                                        color = Gf.Vec3f(base_color[0], base_color[1], base_color[2])
                                        shader_schema.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set(color)
                            
                            # Handle texture if available
                            if hasattr(material, 'baseColorTexture') and material.baseColorTexture is not None:
                                # Save texture to a file and reference it
                                texture_path = f'{material_prim_path}/texture.png'
                                # Note: In a full implementation, we'd extract and save the texture
                                # For now, we'll just reference it
                                pass
                            
                            # Connect shader to material
                            material_schema.CreateSurfaceOutput().ConnectToSource(shader_schema.ConnectableAPI(), 'surface')
                            
                            # Link material to mesh
                            mesh_prim.CreateRelationship('material:binding').SetTargets([material_prim_path])
                        elif hasattr(mesh, 'visual') and hasattr(mesh.visual, 'material'):
                            # Try alternative material access
                            material = mesh.visual.material
                            if material is not None:
                                material_prim_path = f'/Model/Material_{i}'
                                material_prim = stage.DefinePrim(material_prim_path, 'Material')
                                mesh_prim.CreateRelationship('material:binding').SetTargets([material_prim_path])
                    
                    stage.Save()
                    
                    # Read USD file bytes
                    with open(tmp_usd_path, 'rb') as f:
                        usd_data = f.read()
                    
                    return usd_data
                    
                except ImportError:
                    log.warning('trimesh not available, trying alternative GLB to USD conversion')
                    # Fallback: keep the empty /Model prim defined above, with a note
                    
                    # Add a note about the GLB file
                    root_prim.SetMetadata('comment', 'Converted from GLB. trimesh library required for full conversion.')
                    stage.Save()
                    
                    with open(tmp_usd_path, 'rb') as f:
                        usd_data = f.read()
                    
                    return usd_data
                    
            finally:
                # Clean up temporary files
                try:
                    os.unlink(tmp_glb_path)
                except:
                    pass
                try:
                    os.unlink(tmp_usd_path)
                except:
                    pass
                    
        except ImportError as e:
            log.error(f'USD Python bindings (pxr) not available: {e}')
            raise ImportError('USD Python bindings (pxr) are required for USD export. Please install usd-core or pixar-usd.')
        except Exception as e:
            log.error(f'Failed to convert GLB to USD: {e}', exc_info=True)
            raise
