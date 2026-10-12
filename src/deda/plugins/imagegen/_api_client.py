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
"""Image generation API client supporting Gemini, Ollama, and generic web services."""
import base64
import enum
import json
import logging
import mimetypes
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    from google import genai as new_genai
    from google.genai import types as genai_types
    NEW_GENAI_AVAILABLE = True
except ImportError:
    NEW_GENAI_AVAILABLE = False

log = logging.getLogger(__name__)


class ImageGenBackend(str, enum.Enum):
    """Supported image generation backends."""
    GEMINI = 'gemini'
    OLLAMA = 'ollama'
    GENERIC = 'generic'


@dataclass
class ImageGenRequest:
    """Describes an image generation request.

    Attributes:
        prompt: Primary text prompt describing the desired image.
        negative_prompt: Things to avoid in the generated image (backend-dependent).
        reference_images: Local image paths to use as visual references or context.
        documentation: Free-form design documentation text prepended to the prompt.
        width: Desired output image width in pixels.
        height: Desired output image height in pixels.
        num_images: Number of images to generate per request.
        output_dir: Directory where generated images are saved.
        filename_prefix: Prefix for saved filenames (e.g. "hero_shot").
        model: Override the default model for the active backend.
        extra_params: Any additional backend-specific parameters passed through.
    """
    prompt: str
    negative_prompt: str = ''
    reference_images: list[Path] = field(default_factory=list)
    documentation: str = ''
    width: int = 1024
    height: int = 1024
    num_images: int = 1
    output_dir: Path = field(default_factory=lambda: Path.home() / 'dedaverse' / 'imagegen')
    filename_prefix: str = 'imagegen'
    model: str = ''
    extra_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageGenResult:
    """Result of a completed image generation request.

    Attributes:
        images: Paths to locally saved images.
        prompt_used: The final prompt sent to the backend.
        backend: Backend name used.
        model: Model name used.
        metadata: Any additional response metadata from the backend.
    """
    images: list[Path]
    prompt_used: str
    backend: str
    model: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _read_image_b64(path: Path) -> tuple[str, str]:
    """Read an image file and return (mime_type, base64_data)."""
    mime_type, _ = mimetypes.guess_type(str(path))
    if not mime_type:
        mime_type = 'image/jpeg'
    data = path.read_bytes()
    return mime_type, base64.b64encode(data).decode('utf-8')


def _build_full_prompt(request: ImageGenRequest) -> str:
    """Combine documentation and prompt into a single prompt string."""
    parts = []
    if request.documentation.strip():
        parts.append(f'Design context:\n{request.documentation.strip()}')
    parts.append(request.prompt.strip())
    return '\n\n'.join(parts)


def _save_image(data: bytes, output_dir: Path, prefix: str, index: int, ext: str = '.jpg') -> Path:
    """Save raw image bytes to disk and return the saved path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    filename = f'{prefix}_{timestamp}_{index:03d}{ext}'
    path = output_dir / filename
    path.write_bytes(data)
    log.info(f'Saved generated image: {path}')
    return path


# ---------------------------------------------------------------------------
# Backend clients
# ---------------------------------------------------------------------------

class GeminiImageGenClient:
    """Generates images via Google Gemini / Imagen APIs.

    Install the required package:
        pip install google-generativeai          # for Gemini generative models
        pip install google-genai                 # for Imagen 3 (recommended)

    Set GEMINI_API_KEY environment variable or pass api_key directly.

    Supported models:
        gemini-2.0-flash-preview-image-generation  (requires google-generativeai)
        imagen-3.0-generate-002                    (requires google-genai)
    """

    DEFAULT_MODEL = 'imagen-3.0-generate-002'

    def __init__(self, api_key: str = '', model: str = ''):
        self._api_key = api_key
        self._model = model or self.DEFAULT_MODEL

    @property
    def model(self) -> str:
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        self._model = value

    def set_api_key(self, key: str) -> None:
        self._api_key = key

    def generate(self, request: ImageGenRequest) -> ImageGenResult:
        """Generate images using Gemini / Imagen."""
        model = request.model or self._model

        if model.startswith('imagen') and NEW_GENAI_AVAILABLE:
            return self._generate_imagen(request, model)
        if GENAI_AVAILABLE:
            return self._generate_gemini(request, model)
        raise ImportError(
            'No Gemini library found. Install google-genai (for Imagen) or '
            'google-generativeai (for Gemini models).'
        )

    def _generate_imagen(self, request: ImageGenRequest, model: str) -> ImageGenResult:
        """Use google-genai package to call Imagen 3."""
        client = new_genai.Client(api_key=self._api_key)
        full_prompt = _build_full_prompt(request)

        config = genai_types.GenerateImagesConfig(
            number_of_images=request.num_images,
            output_mime_type='image/jpeg',
            aspect_ratio=self._aspect_ratio(request.width, request.height),
            negative_prompt=request.negative_prompt or None,
        )

        try:
            response = client.models.generate_images(
                model=model,
                prompt=full_prompt,
                config=config,
            )
        except Exception as exc:
            log.error(f'Imagen generation failed: {exc}')
            raise

        saved = []
        for i, img in enumerate(response.generated_images):
            path = _save_image(
                img.image.image_bytes,
                request.output_dir,
                request.filename_prefix,
                i,
                '.jpg',
            )
            saved.append(path)

        return ImageGenResult(
            images=saved,
            prompt_used=full_prompt,
            backend=ImageGenBackend.GEMINI,
            model=model,
        )

    def _generate_gemini(self, request: ImageGenRequest, model: str) -> ImageGenResult:
        """Use google-generativeai package with a Gemini generative model."""
        genai.configure(api_key=self._api_key)
        full_prompt = _build_full_prompt(request)

        parts: list[Any] = [full_prompt]

        for img_path in request.reference_images:
            p = Path(img_path)
            if not p.exists():
                log.warning(f'Reference image not found, skipping: {p}')
                continue
            mime_type, b64 = _read_image_b64(p)
            parts.append({'inline_data': {'mime_type': mime_type, 'data': b64}})

        gen_model = genai.GenerativeModel(model)
        saved = []

        for i in range(request.num_images):
            try:
                response = gen_model.generate_content(
                    contents=parts,
                    generation_config=genai.GenerationConfig(
                        response_modalities=['image', 'text'],
                    ),
                )
            except Exception as exc:
                log.error(f'Gemini generation failed (attempt {i}): {exc}')
                raise

            for candidate in response.candidates:
                for part in candidate.content.parts:
                    inline = getattr(part, 'inline_data', None)
                    if inline and inline.data:
                        raw = base64.b64decode(inline.data)
                        ext = '.jpg' if 'jpeg' in inline.mime_type else '.png'
                        path = _save_image(raw, request.output_dir, request.filename_prefix, i, ext)
                        saved.append(path)

        return ImageGenResult(
            images=saved,
            prompt_used=full_prompt,
            backend=ImageGenBackend.GEMINI,
            model=model,
        )

    @staticmethod
    def _aspect_ratio(width: int, height: int) -> str:
        """Map pixel dimensions to an Imagen aspect-ratio string."""
        ratio = width / height
        if ratio >= 1.7:
            return '16:9'
        if ratio >= 1.2:
            return '4:3'
        if ratio <= 0.6:
            return '9:16'
        if ratio <= 0.85:
            return '3:4'
        return '1:1'


class OllamaImageGenClient:
    """Generates images via a locally running Ollama instance.

    Ollama image generation requires a model that supports the generate endpoint
    with image output (e.g. stable-diffusion via Ollama's SDXL support).

    Reference images are passed as base64 in the 'images' field of the request.
    """

    DEFAULT_URL = 'http://localhost:11434'
    DEFAULT_MODEL = 'stable-diffusion'

    def __init__(self, base_url: str = '', model: str = ''):
        if not REQUESTS_AVAILABLE:
            raise ImportError('requests package required for Ollama client')
        self._base_url = (base_url or self.DEFAULT_URL).rstrip('/')
        self._model = model or self.DEFAULT_MODEL

    @property
    def base_url(self) -> str:
        return self._base_url

    @base_url.setter
    def base_url(self, value: str) -> None:
        self._base_url = value.rstrip('/')

    @property
    def model(self) -> str:
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        self._model = value

    def check_connection(self) -> bool:
        try:
            r = requests.get(f'{self._base_url}/api/tags', timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def generate(self, request: ImageGenRequest) -> ImageGenResult:
        model = request.model or self._model
        full_prompt = _build_full_prompt(request)

        images_b64 = []
        for img_path in request.reference_images:
            p = Path(img_path)
            if p.exists():
                _, b64 = _read_image_b64(p)
                images_b64.append(b64)

        payload: dict[str, Any] = {
            'model': model,
            'prompt': full_prompt,
            'stream': False,
        }
        if images_b64:
            payload['images'] = images_b64
        if request.negative_prompt:
            payload['negative_prompt'] = request.negative_prompt
        payload.update(request.extra_params)

        try:
            response = requests.post(
                f'{self._base_url}/api/generate',
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
        except Exception as exc:
            log.error(f'Ollama generation failed: {exc}')
            raise

        data = response.json()
        saved = []

        for i, b64_img in enumerate(data.get('images', [])):
            raw = base64.b64decode(b64_img)
            path = _save_image(raw, request.output_dir, request.filename_prefix, i, '.png')
            saved.append(path)

        if not saved and data.get('response'):
            log.warning('Ollama returned text instead of images — model may not support image generation')

        return ImageGenResult(
            images=saved,
            prompt_used=full_prompt,
            backend=ImageGenBackend.OLLAMA,
            model=model,
            metadata={'raw_response': data},
        )


class GenericWebServiceClient:
    """Generates images by calling a configurable REST endpoint.

    The request body and image extraction are controlled by simple templates
    so users can adapt to Automatic1111, ComfyUI, StabilityAI, Replicate, etc.

    Configuration:
        endpoint: Full URL including path, e.g. "http://localhost:7860/sdapi/v1/txt2img"
        payload_template: Python dict with {prompt}, {negative_prompt}, {width},
            {height} placeholders (string-formatted at call time).
        image_json_path: Dot-separated key path to extract base64 images from the
            response JSON, e.g. "images" or "output.images".
        auth_header: Optional authorization header value (Bearer token, API key).
        image_format: File extension for saved images (default: 'png').
    """

    def __init__(
        self,
        endpoint: str = '',
        payload_template: dict[str, Any] | None = None,
        image_json_path: str = 'images',
        auth_header: str = '',
        image_format: str = 'png',
    ):
        if not REQUESTS_AVAILABLE:
            raise ImportError('requests package required for generic web service client')
        self._endpoint = endpoint
        self._payload_template = payload_template or {
            'prompt': '{prompt}',
            'negative_prompt': '{negative_prompt}',
            'width': '{width}',
            'height': '{height}',
            'n_iter': '{num_images}',
        }
        self._image_json_path = image_json_path
        self._auth_header = auth_header
        self._image_format = image_format.lstrip('.')

    @property
    def endpoint(self) -> str:
        return self._endpoint

    @endpoint.setter
    def endpoint(self, value: str) -> None:
        self._endpoint = value

    def generate(self, request: ImageGenRequest) -> ImageGenResult:
        if not self._endpoint:
            raise ValueError('Generic web service endpoint is not configured')

        full_prompt = _build_full_prompt(request)
        payload = self._build_payload(request, full_prompt)

        headers: dict[str, str] = {'Content-Type': 'application/json'}
        if self._auth_header:
            headers['Authorization'] = self._auth_header

        try:
            response = requests.post(
                self._endpoint,
                json=payload,
                headers=headers,
                timeout=180,
            )
            response.raise_for_status()
        except Exception as exc:
            log.error(f'Generic web service generation failed: {exc}')
            raise

        data = response.json()
        image_list = self._extract_images(data)
        saved = []

        for i, b64_img in enumerate(image_list):
            if isinstance(b64_img, str):
                raw = base64.b64decode(b64_img)
            else:
                raw = bytes(b64_img)
            ext = f'.{self._image_format}'
            path = _save_image(raw, request.output_dir, request.filename_prefix, i, ext)
            saved.append(path)

        return ImageGenResult(
            images=saved,
            prompt_used=full_prompt,
            backend=ImageGenBackend.GENERIC,
            model=request.model or 'unknown',
            metadata={'endpoint': self._endpoint},
        )

    def _build_payload(self, request: ImageGenRequest, full_prompt: str) -> dict[str, Any]:
        """Expand the payload template with request values."""
        substitutions = {
            'prompt': full_prompt,
            'negative_prompt': request.negative_prompt,
            'width': request.width,
            'height': request.height,
            'num_images': request.num_images,
        }
        result: dict[str, Any] = {}
        for key, value in self._payload_template.items():
            if isinstance(value, str) and '{' in value:
                field_name = value.strip('{}')
                result[key] = substitutions.get(field_name, value)
            else:
                result[key] = value
        result.update(request.extra_params)
        return result

    def _extract_images(self, data: dict[str, Any]) -> list[Any]:
        """Walk the dot-separated path to find the image list in the response."""
        node: Any = data
        for key in self._image_json_path.split('.'):
            if isinstance(node, dict):
                node = node.get(key, [])
            else:
                return []
        if isinstance(node, list):
            return node
        return [node] if node else []


# ---------------------------------------------------------------------------
# Unified facade
# ---------------------------------------------------------------------------

class ImageGenClient:
    """Unified image generation client.

    Delegates to one of:  GeminiImageGenClient | OllamaImageGenClient | GenericWebServiceClient

    Configure the active backend via the ``backend`` property or at construction time.
    Each backend is lazily created and cached; call configure_*() to change settings.
    """

    def __init__(
        self,
        backend: ImageGenBackend = ImageGenBackend.GEMINI,
        *,
        gemini_api_key: str = '',
        gemini_model: str = '',
        ollama_url: str = '',
        ollama_model: str = '',
        generic_endpoint: str = '',
        generic_payload_template: dict[str, Any] | None = None,
        generic_image_json_path: str = 'images',
        generic_auth_header: str = '',
        generic_image_format: str = 'png',
    ):
        self._backend = backend
        self._gemini: GeminiImageGenClient | None = None
        self._ollama: OllamaImageGenClient | None = None
        self._generic: GenericWebServiceClient | None = None

        self._gemini_api_key = gemini_api_key
        self._gemini_model = gemini_model
        self._ollama_url = ollama_url
        self._ollama_model = ollama_model
        self._generic_endpoint = generic_endpoint
        self._generic_payload_template = generic_payload_template
        self._generic_image_json_path = generic_image_json_path
        self._generic_auth_header = generic_auth_header
        self._generic_image_format = generic_image_format

    @property
    def backend(self) -> ImageGenBackend:
        return self._backend

    @backend.setter
    def backend(self, value: ImageGenBackend) -> None:
        self._backend = value

    # -- Gemini configuration -----------------------------------------------

    def configure_gemini(self, api_key: str = '', model: str = '') -> None:
        """Update Gemini backend settings (creates or resets the client)."""
        self._gemini_api_key = api_key or self._gemini_api_key
        self._gemini_model = model or self._gemini_model
        self._gemini = None  # force rebuild

    # -- Ollama configuration -----------------------------------------------

    def configure_ollama(self, url: str = '', model: str = '') -> None:
        """Update Ollama backend settings (creates or resets the client)."""
        self._ollama_url = url or self._ollama_url
        self._ollama_model = model or self._ollama_model
        self._ollama = None

    # -- Generic configuration ----------------------------------------------

    def configure_generic(
        self,
        endpoint: str = '',
        payload_template: dict[str, Any] | None = None,
        image_json_path: str = '',
        auth_header: str = '',
        image_format: str = '',
    ) -> None:
        """Update generic web service backend settings."""
        self._generic_endpoint = endpoint or self._generic_endpoint
        if payload_template:
            self._generic_payload_template = payload_template
        self._generic_image_json_path = image_json_path or self._generic_image_json_path
        self._generic_auth_header = auth_header or self._generic_auth_header
        self._generic_image_format = image_format or self._generic_image_format
        self._generic = None

    # -- Generation ---------------------------------------------------------

    def generate(self, request: ImageGenRequest) -> ImageGenResult:
        """Generate images using the active backend.

        Args:
            request: Fully-populated ImageGenRequest.

        Returns:
            ImageGenResult with paths to saved images.

        Raises:
            ImportError: Required library not installed.
            ValueError: Missing configuration.
            requests.HTTPError: Network or server error.
        """
        client = self._get_active_client()
        log.info(f'Generating images via {self._backend} backend')
        return client.generate(request)

    def _get_active_client(self) -> GeminiImageGenClient | OllamaImageGenClient | GenericWebServiceClient:
        if self._backend == ImageGenBackend.GEMINI:
            if self._gemini is None:
                self._gemini = GeminiImageGenClient(
                    api_key=self._gemini_api_key,
                    model=self._gemini_model,
                )
            return self._gemini

        if self._backend == ImageGenBackend.OLLAMA:
            if self._ollama is None:
                self._ollama = OllamaImageGenClient(
                    base_url=self._ollama_url,
                    model=self._ollama_model,
                )
            return self._ollama

        if self._backend == ImageGenBackend.GENERIC:
            if self._generic is None:
                self._generic = GenericWebServiceClient(
                    endpoint=self._generic_endpoint,
                    payload_template=self._generic_payload_template,
                    image_json_path=self._generic_image_json_path,
                    auth_header=self._generic_auth_header,
                    image_format=self._generic_image_format,
                )
            return self._generic

        raise ValueError(f'Unknown backend: {self._backend}')
