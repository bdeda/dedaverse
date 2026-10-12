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
"""Run a fal.ai model on a request: upload the inputs, wait for the queue, download the results.

The network goes through ``fal_client`` (the ``fal`` extra: ``pip install -e ".[fal]"``). The API key is read
from ``FAL_KEY`` or given with :meth:`FalClient.set_api_key`; it is never written to disk.
"""
import logging
import mimetypes
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from ._models import AUDIO, IMAGE, MESH, VIDEO, FalModel

log = logging.getLogger(__name__)

ENV_API_KEY = 'FAL_KEY'
DEFAULT_OUTPUT_DIR = Path.home() / 'dedaverse' / 'fal'


class FalError(RuntimeError):
    """The request cannot be run: no key, no fal_client, missing input, or an unusable result."""


@dataclass
class FalRequest:
    """What to run and with which inputs.

    Attributes:
        model: The model to call.
        prompt: The text prompt (ignored by models without one).
        image: The source image, for image-to-image, edit and 3D models.
        video: The source video, for models that add sound to a video.
        reference_image: A second image to steer the result: a moodboard, a sketch or an image with
            annotations drawn on it. Only used by models that take one.
        annotations: Written art direction. It is added to the prompt of models that take direction; speech
            models read their text out verbatim, so it is left out there.
        negative_prompt: Things to avoid, for models that take one.
        params: Overrides of the model's parameters, by argument name.
        output_dir: Where downloaded results are saved.
        filename_prefix: Start of each saved file's name.
    """

    model: FalModel
    prompt: str = ''
    image: Path | None = None
    video: Path | None = None
    reference_image: Path | None = None
    annotations: str = ''
    negative_prompt: str = ''
    params: dict = field(default_factory=dict)
    output_dir: Path = DEFAULT_OUTPUT_DIR
    filename_prefix: str = 'fal'


@dataclass
class FalFile:
    """One file a model produced."""

    url: str
    kind: str
    file_name: str = ''
    content_type: str = ''
    path: Path | None = None   # set once it is downloaded


@dataclass
class FalResult:
    """What a run produced."""

    model: FalModel
    files: list = field(default_factory=list)
    seed: int | None = None
    prompt_used: str = ''
    raw: dict = field(default_factory=dict)

    @property
    def paths(self) -> list[Path]:
        """The downloaded files."""
        return [f.path for f in self.files if f.path is not None]


def _client_factory(key: str):
    try:
        import fal_client
    except ImportError as err:
        raise FalError('fal_client is required for fal.ai. Install it with: pip install -e ".[fal]"') from err
    return fal_client.SyncClient(key=key)


def _download(url: str, destination: Path) -> None:
    import requests
    response = requests.get(url, timeout=300)
    response.raise_for_status()
    destination.write_bytes(response.content)


def describe_status(status) -> str:
    """A short line for a fal queue status (``Queued``, ``InProgress`` or ``Completed``)."""
    name = type(status).__name__
    if name == 'Queued':
        return f'Queued (position {getattr(status, "position", "?")})'
    if name == 'InProgress':
        logs = getattr(status, 'logs', None) or []
        last = logs[-1].get('message') if logs and isinstance(logs[-1], dict) else None
        return f'Running: {last}' if last else 'Running'
    if name == 'Completed':
        return 'Completed'
    return name


def _prompt_for(request: 'FalRequest') -> str:
    """The text to send: the prompt, with the art direction added unless the model reads its text verbatim."""
    if not request.model.direction_in_prompt:
        return request.prompt.strip()
    return compose_prompt(request.prompt, request.annotations)


def compose_prompt(prompt: str, annotations: str) -> str:
    """The prompt with the written art direction added to it."""
    prompt, annotations = prompt.strip(), annotations.strip()
    if prompt and annotations:
        return f'{prompt}\n\nArt direction: {annotations}'
    return prompt or annotations


_DEFAULT_SUFFIX = {IMAGE: '.png', MESH: '.glb', AUDIO: '.wav', VIDEO: '.mp4'}


class FalClient:
    """Calls fal.ai models for :class:`FalRequest` objects."""

    def __init__(self, api_key: str = '', client_factory: Callable[[str], object] | None = None,
                 downloader: Callable[[str, Path], None] | None = None):
        """
        Args:
            api_key: The fal.ai key. Defaults to the ``FAL_KEY`` environment variable.
            client_factory: Builds the underlying ``fal_client.SyncClient`` from a key. Replaced in tests.
            downloader: Saves a URL to a path. Replaced in tests.
        """
        self._api_key = api_key
        self._client_factory = client_factory or _client_factory
        self._downloader = downloader or _download
        self._client = None

    @property
    def api_key(self) -> str:
        """The key in use: the one set on this client, else ``FAL_KEY``."""
        return self._api_key or os.environ.get(ENV_API_KEY, '')

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    def set_api_key(self, key: str) -> None:
        """Use ``key`` from now on. Reconnects on the next run."""
        self._api_key = key.strip()
        self._client = None

    def _session(self):
        if not self.has_key:
            raise FalError(f'No fal.ai API key. Set the {ENV_API_KEY} environment variable or enter the key.')
        if self._client is None:
            self._client = self._client_factory(self.api_key)
        return self._client

    # ------------------------------------------------------------------------------------------

    @staticmethod
    def build_arguments(request: FalRequest, image_url: str | None = None, reference_url: str | None = None,
                        video_url: str | None = None) -> dict:
        """The ``arguments`` to send to the model for ``request``.

        Args:
            request: The request.
            image_url: The uploaded source image URL.
            reference_url: The uploaded reference image URL.
            video_url: The uploaded source video URL.

        Returns:
            The model defaults, overridden by the request's parameters (clamped to their ranges), plus the
            prompt and image inputs the model takes. Arguments that are None are left out.

        Raises:
            ValueError: If the model needs an image, a video or a prompt and none was given.
        """
        model = request.model
        arguments = model.defaults()
        for name, value in request.params.items():
            param = model.param(name)
            arguments[name] = param.coerce(value) if param and value is not None else value
        if model.prompt_arg:
            prompt = _prompt_for(request)
            if not prompt:
                raise ValueError(f'{model.label} needs a prompt')
            arguments[model.prompt_arg] = prompt
        if request.negative_prompt.strip() and model.negative_prompt_arg:
            arguments[model.negative_prompt_arg] = request.negative_prompt.strip()
        if model.image_arg:
            if not image_url:
                raise ValueError(f'{model.label} needs a source image')
            arguments[model.image_arg] = image_url
        if model.video_arg:
            if not video_url:
                raise ValueError(f'{model.label} needs a source video')
            arguments[model.video_arg] = video_url
        if reference_url:
            if model.reference_arg:
                arguments[model.reference_arg] = reference_url
            else:
                log.warning(f'{model.label} takes no reference image; ignoring it')
        return {key: value for key, value in arguments.items() if value is not None}

    def upload(self, path: str | Path) -> str:
        """Upload a local file to fal.ai storage and return its URL.

        Raises:
            FileNotFoundError: If ``path`` is not a file.
            FalError: If there is no key or no ``fal_client``.
        """
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f'File not found: {path}')
        return self._session().upload_file(path)

    def run(self, request: FalRequest, on_status: Callable[[str], None] | None = None) -> FalResult:
        """Run the model and download its results.

        Args:
            request: What to run.
            on_status: Called with a short status line as the request is uploaded, queued and run.

        Returns:
            The result with every file downloaded into ``request.output_dir``.

        Raises:
            FalError: If there is no key, ``fal_client`` is missing, or the model returned nothing usable.
            ValueError: If a required input is missing.
            FileNotFoundError: If an input image does not exist.
        """
        report = on_status or (lambda message: None)
        model = request.model
        if model.image_arg and request.image is None:
            raise ValueError(f'{model.label} needs a source image')
        if model.video_arg and request.video is None:
            raise ValueError(f'{model.label} needs a source video')
        if model.prompt_arg and not _prompt_for(request):
            raise ValueError(f'{model.label} needs a prompt')
        session = self._session()
        image_url = reference_url = video_url = None
        if model.image_arg:
            report('Uploading the source image')
            image_url = self.upload(request.image)
        if model.video_arg:
            report('Uploading the source video')
            video_url = self.upload(request.video)
        if request.reference_image is not None and model.reference_arg:
            report('Uploading the reference image')
            reference_url = self.upload(request.reference_image)
        arguments = self.build_arguments(request, image_url, reference_url, video_url)
        report(f'Sending to {model.endpoint}')
        log.info(f'fal.ai run {model.endpoint}: {sorted(arguments)}')
        raw = session.subscribe(model.endpoint, arguments=arguments, with_logs=True,
                                on_queue_update=lambda status: report(describe_status(status)))
        result = self._parse(model, raw, arguments)
        report('Downloading results')
        self._download_all(result, Path(request.output_dir), request.filename_prefix)
        report('Done')
        return result

    @staticmethod
    def _parse(model: FalModel, raw: dict, arguments: dict) -> FalResult:
        """Turn the model's response into a :class:`FalResult`."""
        entries = raw.get(model.output_field) if isinstance(raw, dict) else None
        if isinstance(entries, dict):
            entries = [entries]
        files = [FalFile(url=entry['url'], kind=model.output_kind, file_name=entry.get('file_name') or '',
                         content_type=entry.get('content_type') or '')
                 for entry in entries or [] if isinstance(entry, dict) and entry.get('url')]
        if not files:
            raise FalError(f'{model.label} returned no {model.output_field!r}: {str(raw)[:200]}')
        return FalResult(model=model, files=files, seed=raw.get('seed'),
                         prompt_used=raw.get('prompt') or arguments.get(model.prompt_arg or '', ''), raw=raw)

    def _download_all(self, result: FalResult, output_dir: Path, prefix: str) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = re.sub(r'[^\w.-]+', '_', prefix).strip('_') or 'fal'
        for index, file in enumerate(result.files, start=1):
            destination = output_dir / f'{stem}_{index:02d}{self._suffix(file)}'
            n = 1
            while destination.exists():          # never overwrite an earlier result
                n += 1
                destination = output_dir / f'{stem}_{index:02d}_{n}{self._suffix(file)}'
            self._downloader(file.url, destination)
            file.path = destination

    @staticmethod
    def _suffix(file: FalFile) -> str:
        suffix = Path(file.file_name).suffix or Path(urlparse(file.url).path).suffix
        if not suffix and file.content_type:
            suffix = mimetypes.guess_extension(file.content_type.split(';')[0].strip()) or ''
        if file.kind == MESH and suffix.lower() in ('', '.png', '.jpg', '.jpeg'):
            return '.glb'        # fal.ai reports some mesh files with an image content type
        return suffix or _DEFAULT_SUFFIX.get(file.kind, '')
