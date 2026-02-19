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
"""Ollama API client for interacting with locally hosted Ollama models."""
import base64
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

log = logging.getLogger(__name__)


class OllamaApiClient:
    """Client for interacting with Ollama API."""

    def __init__(self, base_url: str = 'http://localhost:11434'):
        """Initialize the Ollama API client.
        
        Args:
            base_url: Base URL for Ollama API (default: http://localhost:11434)
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError('requests package is required for Ollama API client')
        self.base_url = base_url.rstrip('/')
        self._session = requests.Session()
        self._session.timeout = 30

    def list_models(self) -> List[Dict]:
        """List available models.
        
        Returns:
            List of model dictionaries with 'name', 'modified_at', 'size', etc.
        """
        try:
            response = self._session.get(f'{self.base_url}/api/tags')
            response.raise_for_status()
            data = response.json()
            return data.get('models', [])
        except Exception as e:
            log.error(f'Failed to list models: {e}')
            return []

    def generate_text(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        context: Optional[List[int]] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[str, Dict]:
        """Generate text using a language model.
        
        Args:
            model: Model name (e.g., 'llama2', 'mistral')
            prompt: Input prompt
            system: Optional system message
            context: Optional context tokens from previous conversation
            stream: Whether to stream the response
            **kwargs: Additional parameters (temperature, top_p, etc.)
        
        Returns:
            Generated text string, or response dict if stream=True
        """
        payload = {
            'model': model,
            'prompt': prompt,
            'stream': stream,
        }
        if system:
            payload['system'] = system
        if context:
            payload['context'] = context
        payload.update(kwargs)

        try:
            response = self._session.post(
                f'{self.base_url}/api/generate',
                json=payload,
                stream=stream
            )
            response.raise_for_status()
            
            if stream:
                return response
            else:
                data = response.json()
                return data.get('response', '')
        except Exception as e:
            log.error(f'Failed to generate text: {e}')
            raise

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        stream: bool = False,
        **kwargs
    ) -> Union[str, Dict]:
        """Chat with a model using message history.
        
        Args:
            model: Model name
            messages: List of message dicts with 'role' ('user', 'assistant', 'system') and 'content'
            stream: Whether to stream the response
            **kwargs: Additional parameters
        
        Returns:
            Response text or stream response
        """
        payload = {
            'model': model,
            'messages': messages,
            'stream': stream,
        }
        payload.update(kwargs)

        try:
            response = self._session.post(
                f'{self.base_url}/api/chat',
                json=payload,
                stream=stream
            )
            response.raise_for_status()
            
            if stream:
                return response
            else:
                data = response.json()
                return data.get('message', {}).get('content', '')
        except Exception as e:
            log.error(f'Failed to chat: {e}')
            raise

    def process_image(
        self,
        model: str,
        prompt: str,
        image_path: Union[str, Path],
        system: Optional[str] = None,
        **kwargs
    ) -> str:
        """Process an image using a vision model.
        
        Args:
            model: Vision model name (e.g., 'llava', 'bakllava')
            prompt: Text prompt about the image
            image_path: Path to image file
            system: Optional system message
            **kwargs: Additional parameters
        
        Returns:
            Response text
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f'Image not found: {image_path}')

        # Read and encode image
        with open(image_path, 'rb') as f:
            image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        payload = {
            'model': model,
            'prompt': prompt,
            'images': [image_base64],
            'stream': False,
        }
        if system:
            payload['system'] = system
        payload.update(kwargs)

        try:
            response = self._session.post(
                f'{self.base_url}/api/generate',
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return data.get('response', '')
        except Exception as e:
            log.error(f'Failed to process image: {e}')
            raise

    def generate_image(
        self,
        model: str,
        prompt: str,
        output_path: Optional[Union[str, Path]] = None,
        **kwargs
    ) -> bytes:
        """Generate an image using an image generation model.
        
        Args:
            model: Image generation model name (e.g., 'flux', 'flux-schnell')
            prompt: Text prompt for image generation
            output_path: Optional path to save the image
            **kwargs: Additional parameters
        
        Returns:
            Image bytes
        """
        payload = {
            'model': model,
            'prompt': prompt,
            'stream': False,
        }
        payload.update(kwargs)

        try:
            response = self._session.post(
                f'{self.base_url}/api/generate',
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract image from response (format depends on model)
            # Some models return base64, others return file paths
            if 'image' in data:
                image_data = base64.b64decode(data['image'])
            elif 'response' in data:
                # Some models return base64 in response
                image_data = base64.b64decode(data['response'])
            else:
                raise ValueError('No image data in response')

            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(image_data)

            return image_data
        except Exception as e:
            log.error(f'Failed to generate image: {e}')
            raise

    def generate_3d_from_image(
        self,
        model: str,
        image_path: Union[str, Path],
        prompt: Optional[str] = None,
        output_path: Optional[Union[str, Path]] = None,
        **kwargs
    ) -> bytes:
        """Generate a 3D model from an image.
        
        Args:
            model: 3D generation model name
            image_path: Path to input image
            prompt: Optional text prompt
            output_path: Optional path to save the 3D model
            **kwargs: Additional parameters
        
        Returns:
            3D model file bytes
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f'Image not found: {image_path}')

        # Read and encode image
        with open(image_path, 'rb') as f:
            image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        payload = {
            'model': model,
            'images': [image_base64],
            'stream': False,
        }
        if prompt:
            payload['prompt'] = prompt
        payload.update(kwargs)

        try:
            response = self._session.post(
                f'{self.base_url}/api/generate',
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract 3D model from response
            # Format depends on model (could be OBJ, GLB, etc.)
            if 'model' in data:
                model_data = base64.b64decode(data['model'])
            elif 'response' in data:
                model_data = base64.b64decode(data['response'])
            else:
                raise ValueError('No 3D model data in response')

            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(model_data)

            return model_data
        except Exception as e:
            log.error(f'Failed to generate 3D model: {e}')
            raise

    def pull_model(self, model_name: str, stream: bool = True) -> requests.Response:
        """Pull/download a model from Ollama.
        
        Args:
            model_name: Name of the model to pull (e.g., 'llama3.2', 'flux-schnell')
            stream: Whether to stream the download progress (default: True)
        
        Returns:
            Response object with stream enabled for progress tracking
        """
        # Ensure model name has a tag (default to :latest if not specified)
        original_name = model_name
        if ':' not in model_name:
            model_name = f'{model_name}:latest'
        
        payload = {
            'model': model_name,  # Ollama API expects 'model', not 'name'
            'stream': stream,
        }
        
        log.info(f'Pulling model: {model_name} (original: {original_name})')
        log.debug(f'Pull request payload: {payload}')
        
        try:
            response = self._session.post(
                f'{self.base_url}/api/pull',
                json=payload,
                stream=stream,
                timeout=None  # Downloads can take a long time
            )
            
            log.debug(f'Pull response status: {response.status_code}')
            response.raise_for_status()
            
            # Log response headers for debugging
            log.debug(f'Pull response headers: {dict(response.headers)}')
            
            return response
        except Exception as e:
            log.error(f'Failed to pull model {model_name}: {e}', exc_info=True)
            # Try to get more details if it's an HTTP error
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                response_text = e.response.text
                log.error(f'Response body: {response_text[:500]}')
                # Attach response to exception for better error handling upstream
                e.response_text = response_text
            raise

    def check_connection(self) -> bool:
        """Check if Ollama API is accessible.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = self._session.get(f'{self.base_url}/api/tags', timeout=2)
            return response.status_code == 200
        except Exception:
            return False
