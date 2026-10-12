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
"""fal.ai service plugin: generate images and 3D meshes with hosted models.

Pick a task (image from text, image from image, edit an image, 3D mesh from an image), let the plugin
recommend a model for it or choose one, set its parameters and run it. Written art direction and a
reference image (a moodboard, a sketch, or a viewer snapshot with annotations on it) steer the result.

Needs the ``fal`` extra (``pip install -e ".[fal]"``) and a fal.ai key in ``FAL_KEY``.
"""
import logging

from deda.core import PluginRegistry, Service, Tool

from ._client import ENV_API_KEY, FalClient, FalError, FalRequest, FalResult
from ._models import (
    IMAGE_EDIT, IMAGE_TO_3D, IMAGE_TO_IMAGE, TASKS, TEXT_TO_IMAGE, FalModel, all_models, models_for, recommend,
    task_for,
)
from ._notes import load_notes, notes_to_direction

__all__ = [
    'ENV_API_KEY', 'FalClient', 'FalError', 'FalModel', 'FalRequest', 'FalResult', 'FalService', 'FalTool',
    'IMAGE_EDIT', 'IMAGE_TO_3D', 'IMAGE_TO_IMAGE', 'TASKS', 'TEXT_TO_IMAGE', 'all_models', 'load_notes',
    'models_for', 'notes_to_direction', 'recommend', 'task_for',
]

log = logging.getLogger(__name__)


class FalService(Service):
    """Service plugin that owns the fal.ai client and chooses models."""

    PLUGIN_NAME = 'fal'

    def __init__(self):
        super().__init__(name=self.PLUGIN_NAME, url='https://fal.ai',
                         description='fal.ai hosted models: images, art direction and 3D meshes')
        self._client = None

    @property
    def client(self) -> FalClient:
        """The fal.ai client (created on first use; reads ``FAL_KEY``)."""
        if self._client is None:
            self._client = FalClient()
        return self._client

    def load(self) -> bool:
        """Register the service. It stays usable without a key; running a model asks for one."""
        if not self.client.has_key:
            log.info(f'fal.ai: no {ENV_API_KEY} set yet; enter a key in the tool before running a model.')
        self._loaded = True
        return True

    def models(self, task: str | None = None) -> list[FalModel]:
        """The registered models, optionally only those that do ``task``."""
        return models_for(task) if task else all_models()

    def recommend(self, task: str, speed: str | None = None, has_reference: bool = False) -> FalModel:
        """The model to use for ``task`` (see :func:`deda.plugins.fal.recommend`)."""
        return recommend(task, speed=speed, has_reference=has_reference)

    def run(self, request: FalRequest, on_status=None) -> FalResult:
        """Run ``request`` and return the downloaded result."""
        return self.client.run(request, on_status=on_status)


class FalTool(Tool):
    """The fal.ai window."""

    def __init__(self):
        super().__init__(name='fal', description='Generate images and 3D meshes with fal.ai models')
        self._service = None

    def load(self) -> bool:
        self._service = PluginRegistry().get(FalService.PLUGIN_NAME)
        if not self._service:
            log.warning('fal service not found in registry')
        self._loaded = True
        return True

    def initialize_window(self, parent):
        from ._tool_window import FalToolWindow
        if self._window_instance is None:
            self._window_instance = FalToolWindow(service=self._service, parent=parent)
        return self._window_instance


def _register_plugins():
    try:
        service = FalService()
        PluginRegistry().register(service)
        PluginRegistry().register(FalTool())
    except Exception as exc:  # pylint: disable=broad-except
        log.error(f'Failed to register fal plugins: {exc}', exc_info=True)


_register_plugins()
