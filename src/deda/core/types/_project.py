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
"""Project type for the asset system."""

from pathlib import Path

from pxr import Sdf, Usd

from deda.core import LayeredConfig

from ._collection import Collection
from ._entity import Entity

__all__ = ['Project']


class Project(Collection):
    """Root entity representing a Dedaverse project.

    A Project is the top-level Collection that contains all assets, sequences,
    and shots. Has a rootdir that points to the project directory on disk.
    """

    def __init__(
        self,
        name: str | None = None,
        rootdir: str | Path | None = None,
        parent: None = None,
    ) -> None:
        """Initialize the project.

        When called with no arguments, returns the current project from
        LayeredConfig (project name and rootdir from config).

        Args:
            name: Project display name, or None to use current project from config.
            rootdir: Project root directory on disk, or None to use current project.
            parent: Must be None; Project is always a root entity.

        Raises:
            ValueError: If parent is not None.
            RuntimeError: If no arguments and no current project is set.
        """
        if name is None and rootdir is None:
            config = LayeredConfig.instance().current_project
            if config is None:
                raise RuntimeError("No current project set.")
            Entity.__init__(self, config.name, None)
            self._rootdir = Path(config.rootdir)
            return
        if parent is not None:
            raise ValueError("Project parent must be None.")
        Entity.__init__(self, name, None)
        self._rootdir = Path(rootdir) if isinstance(rootdir, str) else rootdir

    @property
    def layer(self):
        """Sdf.Layer for the project's USDA stage (metadata_path).

        Uses Sdf.Layer.FindOrOpen with metadata_path as the layer identifier.
        Returns None if the layer cannot be found or opened.
        """
        return Sdf.Layer.FindOrOpen(str(self.metadata_path))

    @property
    def rootdir(self) -> Path:
        """Project root directory on disk."""
        return self._rootdir

    @property
    def metadata_dir(self) -> Path:
        """Path to the .dedaverse directory under the project root.

        Returns:
            Path to {project_root}/.dedaverse.
        """
        return self.rootdir / '.dedaverse'

    @property
    def metadata_path(self) -> Path:
        """Path to the project's USDA stage file.

        Returns:
            Path to {project_root}/.dedaverse/{project_name}.usda.
        """
        return self.metadata_dir / f'{self._name}.usda'

    @classmethod
    def create(cls, name: str, rootdir: str | Path, force: bool = False) -> 'Project':
        """Create the USDA stage for the project and return a Project instance.

        The stage is saved as {project_root}/.dedaverse/{project_name}.usda.
        project_root should come from the project config (rootdir).

        Args:
            name: Project name (used for the .usda filename).
            rootdir: Project root directory on disk (from project config).
            force: If True, overwrite existing project USDA. If False, raise
                FileExistsError when the file already exists.

        Returns:
            Project instance for the created project.

        Raises:
            FileExistsError: If the project USDA file already exists and force is False.
        """
        root = Path(rootdir) if isinstance(rootdir, str) else Path(rootdir)
        usda_path = root / '.dedaverse' / f'{name}.usda'
        if usda_path.is_file() and not force:
            raise FileExistsError(
                f"Project metadata already exists: {usda_path}. Use force=True to overwrite."
            )
        if usda_path.is_file() and force:
            usda_path.unlink()  # CreateNew does not overwrite; remove so it can create
        _create_project_stage_usda(root, name)
        return cls(name, rootdir)

    @classmethod
    def find_or_create(cls, name: str, rootdir: str | Path) -> 'Project':
        """Return a Project instance, creating the USDA stage only if it does not exist.

        If {project_root}/.dedaverse/{project_name}.usda exists, it is not
        overwritten; the existing project metadata is used. Otherwise the stage
        is created as for create().

        Args:
            name: Project name (used for the .usda filename).
            rootdir: Project root directory on disk (from project config).

        Returns:
            Project instance for the project.
        """
        root = Path(rootdir) if isinstance(rootdir, str) else Path(rootdir)
        usda_path = root / '.dedaverse' / f'{name}.usda'
        if not usda_path.is_file():
            _create_project_stage_usda(root, name)
        return cls(name, rootdir)


# --- Internal (bottom): alphabetically sorted ---


def _create_project_stage_usda(project_root: Path, project_name: str) -> Path:
    """Create a new USDA stage at project_root/.dedaverse/{project_name}.usda.

    Ensures .dedaverse exists, creates the stage, and saves it.
    Usd.Stage.CreateNew does not overwrite an existing file; it can raise if
    the path already exists. Caller must remove the file first when overwriting.

    Args:
        project_root: Project root directory on disk.
        project_name: Project name (used for the .usda filename).

    Returns:
        Path to the created USDA file.
    """
    project_root = Path(project_root)
    dedaverse_dir = project_root / '.dedaverse'
    dedaverse_dir.mkdir(parents=True, exist_ok=True)
    usda_path = dedaverse_dir / f'{project_name}.usda'
    stage = Usd.Stage.CreateNew(str(usda_path))
    stage.GetRootLayer().Save()
    return usda_path
