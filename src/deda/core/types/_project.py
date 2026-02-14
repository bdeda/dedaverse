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

from pxr import Sdf, Tf, Usd

from deda.core import LayeredConfig
from deda.core._config import _sanitize_prim_name

from ._collection import Collection
from ._entity import Entity

__all__ = ['Project']

# Registry of Project instances by (resolved_rootdir, prim_name) so the same project returns the same instance.
_project_registry: dict[tuple[Path, str], 'Project'] = {}


class Project(Collection):
    """Root entity representing a Dedaverse project.

    A Project is the top-level Collection that contains all assets, sequences,
    and shots. Has a rootdir that points to the project directory on disk.
    The same project (rootdir + prim_name) always returns the same instance;
    the Usd.Stage is stored on the project and reused.
    """

    def __new__(cls, name=None, rootdir=None, parent=None, prim_name=None):
        """Return the existing Project instance for this (rootdir, prim_name) if one exists."""
        if name is None and rootdir is None:
            config = LayeredConfig.instance().current_project
            if config is None:
                return super().__new__(cls)
            root = Path(config.rootdir).resolve()
            pname = getattr(config, 'prim_name', None) or _sanitize_prim_name(config.name)
        else:
            if parent is not None or name is None or rootdir is None:
                return super().__new__(cls)
            if not isinstance(rootdir, (str, Path)):
                return super().__new__(cls)
            root = Path(rootdir).resolve()
            pname = (
                prim_name
                if prim_name is not None
                else _sanitize_prim_name(name) if name else 'Project'
            )
        key = (root, pname)
        existing = _project_registry.get(key)
        if existing is not None:
            existing._reused_from_registry = True
            return existing
        return super().__new__(cls)

    def __init__(
        self,
        name: str | None = None,
        rootdir: str | Path | None = None,
        parent: None = None,
        prim_name: str | None = None,
    ) -> None:
        """Initialize the project.

        When called with no arguments, returns the current project from
        LayeredConfig (project name, rootdir, and prim_name from config).

        Args:
            name: Project display name, or None to use current project from config.
            rootdir: Project root directory on disk, or None to use current project.
            parent: Must be None; Project is always a root entity.
            prim_name: USD prim name (valid identifier) for metadata; used for
                .dedaverse/{prim_name}.usda and the root prim. If None, derived
                from name when loaded from config.

        Raises:
            ValueError: If parent is not None, or prim_name is invalid when provided.
            RuntimeError: If no arguments and no current project is set.
        """
        if getattr(self, '_reused_from_registry', False):
            del self._reused_from_registry
            return
        self._stage = None
        if name is None and rootdir is None:
            config = LayeredConfig.instance().current_project
            if config is None:
                raise RuntimeError("No current project set.")
            Entity.__init__(self, config.name, None)
            self._rootdir = Path(config.rootdir)
            self._prim_name = getattr(config, 'prim_name', None) or _sanitize_prim_name(config.name)
            _project_registry[(self._rootdir.resolve(), self._prim_name)] = self
            return
        if parent is not None:
            raise ValueError("Project parent must be None.")
        Entity.__init__(self, name, None)
        self._rootdir = Path(rootdir) if isinstance(rootdir, str) else rootdir
        if prim_name is not None:
            if not Tf.IsValidIdentifier(prim_name):
                raise ValueError(f"prim_name must be a valid USD identifier: {prim_name!r}")
            self._prim_name = prim_name
        else:
            self._prim_name = _sanitize_prim_name(name) if name else "Project"
        _project_registry[(self._rootdir.resolve(), self._prim_name)] = self

    @property
    def layer(self):
        """Sdf.Layer for the project's USDA stage (metadata_path).

        Uses Sdf.Layer.FindOrOpen with metadata_path as the layer identifier.
        Returns None if the layer cannot be found or opened.
        """
        return Sdf.Layer.FindOrOpen(str(self.metadata_path))

    @property
    def children_metadata_dir(self) -> Path:
        """Directory where child collection/asset USDA files are stored.

        For the project this is the same as metadata_dir (.dedaverse).
        """
        return self.metadata_dir

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
            Path to {project_root}/.dedaverse/{prim_name}.usda.
        """
        return self.metadata_dir / f'{self._prim_name}.usda'

    @property
    def prim_name(self) -> str:
        """USD prim name (valid identifier) used in metadata and for the root prim."""
        return self._prim_name

    @property
    def prim_path(self) -> str:
        """USD prim path; the project file has no prim, so this is for compatibility only."""
        return f'/{self._prim_name}'

    @property
    def rootdir(self) -> Path:
        """Project root directory on disk."""
        return self._rootdir

    def asset_directory_for_prim_path(self, prim_path: str) -> Path:
        """Return the directory under project root that mirrors the prim path.

        The project stage has no root prim; top-level prims are direct children
        (e.g. /Assets, /Assets/Monsters). So /Assets -> rootdir/Assets.

        Args:
            prim_path: USD prim path (e.g. /Assets, /Assets/Monsters).

        Returns:
            Path under project rootdir for this asset/collection.
        """
        segments = prim_path.strip("/").split("/")
        if not segments:
            return self._rootdir
        return self._rootdir.joinpath(*segments)

    @property
    def stage(self):
        """Usd.Stage for the project's USDA metadata file, cached on the project.

        Opens the stage on first access and reuses the same instance. If the
        USDA file does not exist, it is created (find_or_create semantics)
        for backwards compatibility with projects that predate the asset metadata.
        """
        if self._stage is None:
            path = self.metadata_path
            if not path.is_file():
                _create_project_stage_usda(self.rootdir, self.prim_name)
            self._stage = Usd.Stage.Open(str(path))
        return self._stage

    @classmethod
    def create(
        cls,
        name: str,
        rootdir: str | Path,
        prim_name: str | None = None,
        force: bool = False,
    ) -> 'Project':
        """Create the USDA stage for the project and return a Project instance.

        The stage is saved as {project_root}/.dedaverse/{prim_name}.usda with
        a root prim at /{prim_name}. prim_name must be a valid USD identifier.

        Args:
            name: Project display name.
            rootdir: Project root directory on disk (from project config).
            prim_name: USD prim name (valid identifier) for the metadata file and
                root prim. If None, derived from name; must be valid after derivation.
            force: If True, overwrite existing project USDA. If False, raise
                FileExistsError when the file already exists.

        Returns:
            Project instance for the created project.

        Raises:
            ValueError: If prim_name is not a valid USD identifier.
            FileExistsError: If the project USDA file already exists and force is False.
        """
        pname = prim_name if prim_name is not None else _sanitize_prim_name(name)
        if not Tf.IsValidIdentifier(pname):
            raise ValueError(
                f"prim_name must be a valid USD prim identifier: {pname!r}. "
                "Use only letters, numbers, and underscores; must not start with a number."
            )
        root = Path(rootdir) if isinstance(rootdir, str) else Path(rootdir)
        usda_path = root / '.dedaverse' / f'{pname}.usda'
        if usda_path.is_file() and not force:
            raise FileExistsError(
                f"Project metadata already exists: {usda_path}. Use force=True to overwrite."
            )
        if usda_path.is_file() and force:
            _project_registry.pop((root, pname), None)
            usda_path.unlink()
        _create_project_stage_usda(root, pname)
        return cls(name, rootdir, prim_name=pname)

    @classmethod
    def find_or_create(
        cls,
        name: str,
        rootdir: str | Path,
        prim_name: str | None = None,
    ) -> 'Project':
        """Return a Project instance, creating the USDA stage only if it does not exist.

        If {project_root}/.dedaverse/{prim_name}.usda exists, it is not
        overwritten. Otherwise the stage is created with a root prim at /{prim_name}.
        prim_name must be a valid USD identifier.

        Args:
            name: Project display name.
            rootdir: Project root directory on disk (from project config).
            prim_name: USD prim name (valid identifier). If None, derived from name.

        Returns:
            Project instance for the project.

        Raises:
            ValueError: If prim_name is not a valid USD identifier after derivation.
        """
        pname = prim_name if prim_name is not None else _sanitize_prim_name(name)
        if not Tf.IsValidIdentifier(pname):
            raise ValueError(
                f"prim_name must be a valid USD prim identifier: {pname!r}. "
                "Set prim_name on the project config (e.g. in project settings)."
            )
        root = Path(rootdir) if isinstance(rootdir, str) else Path(rootdir)
        usda_path = root / '.dedaverse' / f'{pname}.usda'
        if not usda_path.is_file():
            _create_project_stage_usda(root, pname)
        return cls(name, rootdir, prim_name=pname)


# --- Internal (bottom): alphabetically sorted ---


def _create_project_stage_usda(project_root: Path, prim_name: str) -> Path:
    """Create the project USDA file with no prims; child assets are added as sublayers.

    The project file is unique: it has no root prim. The project is the root of
    all prims (composed from sublayers). prim_name is only used for the filename.

    Args:
        project_root: Project root directory on disk.
        prim_name: Used for the USDA filename ({prim_name}.usda).

    Returns:
        Path to the created USDA file.
    """
    project_root = Path(project_root)
    dedaverse_dir = project_root / '.dedaverse'
    dedaverse_dir.mkdir(parents=True, exist_ok=True)
    usda_path = dedaverse_dir / f'{prim_name}.usda'
    stage = Usd.Stage.CreateNew(str(usda_path))
    stage.GetRootLayer().Save()
    return usda_path
