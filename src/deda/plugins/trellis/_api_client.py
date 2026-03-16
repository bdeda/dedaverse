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
"""Trellis API client for interacting with Trellis server (Gradio)."""
import base64
import json
import logging
import mimetypes
from pathlib import Path
from typing import Dict, List, Optional, Union

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

log = logging.getLogger(__name__)


class TrellisApiClient:
    """Client for interacting with Trellis API (Gradio)."""

    def __init__(self, base_url: str = 'http://127.0.0.1:7860'):
        """Initialize the Trellis API client.
        
        Args:
            base_url: Base URL for Trellis server (default: http://127.0.0.1:7860)
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError('requests package is required for Trellis API client')
        self.base_url = base_url.rstrip('/')
        self._session = requests.Session()
        self._session.timeout = 300  # Longer timeout for 3D generation

    def check_connection(self) -> bool:
        """Check if Trellis server is accessible.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = self._session.get(f'{self.base_url}/', timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def get_api_info(self) -> Optional[Dict]:
        """Get API information from Gradio.
        
        Returns:
            API info dict or None if unavailable
        """
        try:
            log.debug(f'Attempting to get API info from {self.base_url}/api/')
            response = self._session.get(f'{self.base_url}/api/', timeout=10)
            response.raise_for_status()
            api_info = response.json()
            log.debug(f'Successfully retrieved API info: {list(api_info.keys()) if isinstance(api_info, dict) else "non-dict"}')
            return api_info
        except requests.exceptions.Timeout:
            log.error(f'Timeout connecting to Trellis API at {self.base_url}/api/')
            return None
        except requests.exceptions.ConnectionError as e:
            log.error(f'Connection error to Trellis API at {self.base_url}/api/: {e}')
            return None
        except requests.exceptions.HTTPError as e:
            log.error(f'HTTP error getting API info: {e} (status: {e.response.status_code if hasattr(e, "response") else "unknown"})')
            return None
        except Exception as e:
            log.error(f'Failed to get API info: {e}', exc_info=True)
            return None

    def generate_3d_from_image(
        self,
        image_path: Union[str, Path],
        seed: Optional[int] = None,
        randomize_seed: bool = True,
        ss_guidance_strength: float = 7.5,
        ss_sampling_steps: int = 12,
        slat_guidance_strength: float = 3.0,
        slat_sampling_steps: int = 12,
        is_multiimage: bool = False,
        multiimages: Optional[List[Union[str, Path]]] = None,
        multiimage_algo: str = "stochastic",
    ) -> Dict:
        """Generate a 3D model from an image using Trellis.
        
        Args:
            image_path: Path to input image file
            seed: Random seed (if None and randomize_seed=False, uses 0)
            randomize_seed: Whether to randomize the seed
            ss_guidance_strength: Guidance strength for sparse structure generation (0.0-10.0)
            ss_sampling_steps: Number of sampling steps for sparse structure (1-50)
            slat_guidance_strength: Guidance strength for structured latent generation (0.0-10.0)
            slat_sampling_steps: Number of sampling steps for structured latent (1-50)
            is_multiimage: Whether to use multi-image mode
            multiimages: List of image paths for multi-image mode
            multiimage_algo: Algorithm for multi-image generation ("stochastic" or "multidiffusion")
        
        Returns:
            Dict containing state and video_path
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f'Image not found: {image_path}')

        # Read image file
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        # For Gradio API, we need to send the image file directly, not base64
        # Gradio expects file uploads in a specific format
        # First, get the API info to find the correct endpoint
        api_info = self.get_api_info()
        
        # Find the image_to_3d endpoint
        endpoint_name = None
        if api_info:
            # Try to find endpoint in named_endpoints
            named_endpoints = api_info.get('named_endpoints', {})
            if isinstance(named_endpoints, dict):
                for endpoint_key, endpoint_value in named_endpoints.items():
                    if 'image_to_3d' in endpoint_key.lower() or 'image_to_3d' in str(endpoint_value).lower():
                        endpoint_name = endpoint_key
                        log.info(f'Found endpoint in API info: {endpoint_name}')
                        break
            
            # Also check if there's a direct endpoint list
            if not endpoint_name and 'endpoints' in api_info:
                for endpoint in api_info.get('endpoints', []):
                    if isinstance(endpoint, dict) and 'name' in endpoint:
                        if 'image_to_3d' in endpoint['name'].lower():
                            endpoint_name = endpoint.get('path', '/api/image_to_3d')
                            log.info(f'Found endpoint in endpoints list: {endpoint_name}')
                            break
        
        if not endpoint_name:
            # Try common Gradio endpoint naming patterns
            endpoint_name = '/api/image_to_3d'
            log.info(f'Using default endpoint: {endpoint_name}')
        
        # If we couldn't get API info, log a warning but continue with default endpoint
        if not api_info:
            log.warning('Could not get API info from Trellis server, using default endpoint. '
                       'This may fail if the endpoint structure is different.')
        
        # Gradio/FastAPI expects JSON with base64-encoded images
        # Detect image MIME type
        image_mime_type, _ = mimetypes.guess_type(str(image_path))
        if not image_mime_type or not image_mime_type.startswith('image/'):
            # Default to PNG if we can't detect it
            image_mime_type = 'image/png'
            log.warning(f'Could not detect image MIME type for {image_path}, defaulting to image/png')
        
        # Convert image to base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        image_data_uri = f"data:{image_mime_type};base64,{image_base64}"
        
        # Prepare multi-images if needed
        multiimage_list = []
        if is_multiimage and multiimages:
            for img_path in multiimages:
                img_path = Path(img_path)
                if not img_path.exists():
                    log.warning(f'Multi-image file not found: {img_path}')
                    continue
                with open(img_path, 'rb') as f:
                    img_data = f.read()
                img_mime_type, _ = mimetypes.guess_type(str(img_path))
                if not img_mime_type or not img_mime_type.startswith('image/'):
                    img_mime_type = 'image/png'
                img_base64 = base64.b64encode(img_data).decode('utf-8')
                multiimage_list.append(f"data:{img_mime_type};base64,{img_base64}")
        
        # Prepare JSON payload for Gradio API
        # Gradio expects data as a list matching the function signature
        payload = {
            "data": [
                image_data_uri,  # image
                multiimage_list,  # multiimages
                is_multiimage,
                seed if seed is not None else 0,
                ss_guidance_strength,
                ss_sampling_steps,
                slat_guidance_strength,
                slat_sampling_steps,
                multiimage_algo,
            ]
        }
        
        # Try the request with proper error handling
        try:
            log.info(f'Calling Trellis API endpoint: {self.base_url}{endpoint_name}')
            log.debug(f'Payload structure: data array with {len(payload["data"])} elements')
            log.debug(f'Payload types: {[type(x).__name__ for x in payload["data"]]}')
            log.debug(f'Image data URI length: {len(image_data_uri)} characters')
            
            # Call Gradio API endpoint with JSON payload
            response = self._session.post(
                f'{self.base_url}{endpoint_name}',
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=600  # 3D generation can take a long time
            )
            
            # Log response details before raising for status
            log.debug(f'Response status: {response.status_code}')
            log.debug(f'Response headers: {dict(response.headers)}')
            
            if response.status_code != 200:
                # Try to get error details
                try:
                    error_detail = response.json()
                    log.error(f'Server error response (JSON): {json.dumps(error_detail, indent=2)}')
                except:
                    error_text = response.text[:2000] if hasattr(response, 'text') else 'No error text available'
                    log.error(f'Server error text: {error_text}')
            
            response.raise_for_status()
            result = response.json()
            
            log.debug(f'API response keys: {list(result.keys()) if isinstance(result, dict) else "non-dict"}')
            
            # Gradio returns data in a specific format
            if 'data' in result:
                return {
                    'state': result['data'][0] if len(result['data']) > 0 else None,
                    'video_path': result['data'][1] if len(result['data']) > 1 else None,
                }
            return result
        except requests.exceptions.HTTPError as e:
            error_msg = f'HTTP {e.response.status_code} error generating 3D model: {e}'
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    log.error(f'{error_msg}\nError response (JSON): {json.dumps(error_detail, indent=2)}')
                    # Include error detail in the exception message
                    if isinstance(error_detail, dict):
                        if 'detail' in error_detail:
                            detail = error_detail['detail']
                            if isinstance(detail, str):
                                error_msg = f'{error_msg}\nServer details: {detail}'
                            elif isinstance(detail, list) and len(detail) > 0:
                                # Pydantic validation errors
                                first_error = detail[0]
                                if isinstance(first_error, dict):
                                    error_msg = f'{error_msg}\nValidation error: {first_error.get("msg", "Unknown")} at {first_error.get("loc", [])}'
                        elif 'error' in error_detail:
                            error_msg = f'{error_msg}\nServer error: {error_detail["error"]}'
                except Exception as json_err:
                    error_text = e.response.text[:2000] if hasattr(e.response, 'text') else 'No error text available'
                    log.error(f'{error_msg}\nError response text: {error_text}\n(JSON parse error: {json_err})')
                    error_msg = f'{error_msg}\nServer response: {error_text[:500]}'
            else:
                log.error(error_msg)
            raise RuntimeError(error_msg) from e
        except Exception as e:
            log.error(f'Failed to generate 3D model: {e}', exc_info=True)
            raise

    def extract_glb(
        self,
        state: Dict,
        mesh_simplify: float = 0.95,
        texture_size: int = 1024,
    ) -> bytes:
        """Extract a GLB file from the generated 3D model state.
        
        Args:
            state: State dict from generate_3d_from_image
            mesh_simplify: Mesh simplification factor (0.9-0.98)
            texture_size: Texture resolution (512-2048)
        
        Returns:
            GLB file bytes
        """
        payload = {
            "data": [
                state,  # state
                mesh_simplify,  # mesh_simplify
                texture_size,  # texture_size
            ]
        }
        
        try:
            response = self._session.post(
                f'{self.base_url}/api/extract_glb',
                json=payload,
                timeout=300
            )
            response.raise_for_status()
            result = response.json()
            
            # Gradio returns file path or data
            if 'data' in result and len(result['data']) > 0:
                glb_path = result['data'][0]
                # Download the GLB file
                if glb_path.startswith('http'):
                    glb_response = self._session.get(glb_path)
                    glb_response.raise_for_status()
                    return glb_response.content
                else:
                    # If it's a local path, we'd need to access it differently
                    # For now, return the path info
                    log.warning(f'GLB file path returned: {glb_path}')
                    return None
            return None
        except Exception as e:
            log.error(f'Failed to extract GLB: {e}', exc_info=True)
            raise

    def extract_gaussian(self, state: Dict) -> bytes:
        """Extract a Gaussian (PLY) file from the generated 3D model state.
        
        Args:
            state: State dict from generate_3d_from_image
        
        Returns:
            PLY file bytes
        """
        payload = {
            "data": [state]
        }
        
        try:
            response = self._session.post(
                f'{self.base_url}/api/extract_gaussian',
                json=payload,
                timeout=300
            )
            response.raise_for_status()
            result = response.json()
            
            if 'data' in result and len(result['data']) > 0:
                ply_path = result['data'][0]
                if ply_path.startswith('http'):
                    ply_response = self._session.get(ply_path)
                    ply_response.raise_for_status()
                    return ply_response.content
                else:
                    log.warning(f'PLY file path returned: {ply_path}')
                    return None
            return None
        except Exception as e:
            log.error(f'Failed to extract Gaussian: {e}', exc_info=True)
            raise

    def extract_usd(
        self,
        state: Dict,
        mesh_simplify: float = 0.95,
        texture_size: int = 1024,
    ) -> bytes:
        """Extract a USD file from the generated 3D model state.
        
        This method first extracts a GLB file, then converts it to USD format.
        
        Args:
            state: State dict from generate_3d_from_image
            mesh_simplify: Mesh simplification factor (0.9-0.98)
            texture_size: Texture resolution (512-2048)
        
        Returns:
            USD file bytes
        """
        # First extract GLB
        glb_data = self.extract_glb(state, mesh_simplify, texture_size)
        if not glb_data:
            raise ValueError('Failed to extract GLB file for USD conversion')
        
        # Convert GLB to USD
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
                    # Fallback: create a basic USD file with a note
                    stage = Usd.Stage.CreateNew(tmp_usd_path)
                    root_prim = stage.DefinePrim('/Model', 'Xform')
                    stage.SetDefaultPrim(root_prim)
                    
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
