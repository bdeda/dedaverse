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
"""Entity types for the asset system.

Entity is the base class for all asset system types (Element, Asset, etc.).
Each entity is backed by a USD file where the default prim is the location
from which metadata is serialized.
"""

from pathlib import Path

from pxr import Kind, Sdf, Usd

from ._asset_id import AssetID

__all__ = ['Entity']


class Entity:
    """Base class for all asset system types (Element, Asset, etc.).

    Provides common attributes: name, parent, project, path, and metadata_path.
    Subclasses must override from_path() to implement type-specific path parsing.
    """

    def __init__(self, name: str, parent: 'Entity | None') -> None:
        """Initialize the entity.

        Args:
            name: Display name of the entity.
            parent: Parent entity, or None if this is a root entity.
        """
        self._name = name
        self._parent = parent
        
    
        
    @property
    def metadata(self):
        """Custom data on this entity's prim (e.g. title, description, asset_type).

        Returns a dict-like of the prim's customData. Only valid for entities
        with a prim (e.g. Asset, Collection). Returns an empty dict if the
        prim is invalid or has no custom data.
        """
        if not hasattr(self, 'prim'):
            return {}
        prim = self.prim
        if not prim.IsValid():
            return {}
        try:
            custom = prim.GetCustomData()
        except RuntimeError:
            return {}
        return dict(custom) if custom else {}
    
    @property
    def metadata_path(self) -> Path | None:
        """The dedaverse metadata path relative to the project rootdir.

        Returns:
            Path to the metadata file, or None if not yet resolved.
        """
        return None

    @property
    def name(self) -> str:
        """Display name of the entity."""
        return self._name

    @property
    def parent(self) -> 'Entity | None':
        """Parent entity, or None if this is a root entity."""
        return self._parent

    @property
    def prim_path(self) -> str:
        """USD prim path for this entity in the project stage.

        The project has no prim; its stage composes sublayers. Direct children
        of the project are top-level prims (e.g. /Assets). Other children are
        {parent.prim_path}/{name}.
        """
        if self._parent is None:
            return f'/{self._name}'
        if self._parent.parent is None:
            return f'/{self._name}'
        return f'{self._parent.prim_path}/{self._name}'

    @property
    def path(self) -> Path:
        """File system path for this entity.

        For the project root, returns the project rootdir. For children,
        returns the path relative to the project (implementation pending).

        Returns:
            Path to the entity on disk.
        """
        proj = self.project
        if self is proj and hasattr(proj, 'rootdir'):
            rootdir = proj.rootdir
            return Path(rootdir) if isinstance(rootdir, str) else rootdir
        return Path()

    @property
    def project(self) -> 'Entity':
        """The root (project) entity, found by walking up the parent chain."""
        item: Entity | None = self
        while item is not None:
            if item.parent is None:
                return item
            item = item.parent
        return self

    def get_edit_target(self):
        """Return the best layer to edit for this entity's prim.

        For the stage's pseudo-root prim, returns the stage's root layer.
        Otherwise, walks the prim's spec stack and returns the first layer
        that has a defining opinion (Sdf.SpecifierDef) and a non-anonymous
        identifier, so edits go to a persistent, class-level layer.

        Returns:
            Sdf.Layer to use as the edit target, or None if no suitable
            layer is found (e.g. prim is defined only on anonymous layers).

        Note:
            Requires self.prim (e.g. on Asset and subclasses). Not defined
            on Entity when prim is not available.
        """
        prim = self.prim
        if not prim.IsValid():
            return None
        try:
            stage = prim.GetStage()
            if prim.IsPseudoRoot():
                return stage.GetRootLayer()
            for spec in prim.GetPrimStack():
                if spec.specifier != Sdf.SpecifierDef:
                    continue
                if _layer_is_anonymous(spec.layer):
                    continue
                return spec.layer
        except RuntimeError:
            return None
        return None

    def get_metadata(self, name: str, default=None):
        """Return custom metadata from this entity's prim.

        Reads from the prim's custom data (e.g. Usd.Prim.GetCustomDataByKey).
        Only valid for entities that have a prim (e.g. Asset, Collection).
        Handles expired prims by returning default if the prim is invalid when accessed.

        Args:
            name: Key for the custom metadata (use lowercase snake_case).
            default: Value to return if the key is missing.

        Returns:
            The stored value, or default if the key is not set or prim is invalid.
        """
        if not hasattr(self, 'prim'):
            return default
        prim = self.prim
        if not prim.IsValid():
            return default
        try:
            custom = prim.GetCustomData()
        except RuntimeError:
            return default
        if not custom:
            return default
        return custom.get(name, default)

    def set_metadata(self, name: str, value) -> None:
        """Set custom metadata on this entity's prim and save the edit target layer.

        Uses Usd.Prim.SetCustomDataByKey to store the value. The value must be
        a type that USD accepts for custom data (e.g. str, int, float, bool,
        list, dict, or types convertible to VtValue). The stage's edit target
        is set to this entity's edit layer, then the layer is saved to disk.

        Args:
            name: Key for the custom metadata.
            value: Value to set; must be a type supported by SetCustomDataByKey.

        Raises:
            RuntimeError: If no edit target is available for this entity.
            Exception: If the value type is not supported by USD or save fails.

        Note:
            Requires self.prim (e.g. on Asset and subclasses).
        """
        prim = self.prim
        if not prim.IsValid():
            raise RuntimeError("Prim is not valid; cannot set metadata.")
        layer = self.get_edit_target()
        if layer is None:
            raise RuntimeError("No edit target for this entity; cannot set metadata.")
        try:
            stage = prim.GetStage()
            stage.SetEditTarget(Usd.EditTarget(layer))
            prim.SetCustomDataByKey(name, value)
            layer.Save()
        except RuntimeError as e:
            raise RuntimeError("Prim is not valid or expired; cannot set metadata.") from e

    @classmethod
    def from_prim(cls, prim, parent: 'Entity | None') -> 'Entity':
        """Construct the appropriate entity (Collection or Asset) from a prim.

        The parent is required so the entity does not need to look it up.
        Collection is returned when the prim has Kind group; otherwise Asset.

        Args:
            prim: Usd.Prim for the entity (e.g. a child of a collection).
            parent: Parent entity (Collection or Project). Must not be None.

        Returns:
            Collection or Asset instance for the given prim.

        Raises:
            ValueError: If parent is None or prim is invalid.
        """
        if parent is None:
            raise ValueError("parent is required for Entity.from_prim")
        if not prim or not prim.IsValid():
            raise ValueError("prim is invalid")
        name = prim.GetName()
        if not name:
            raise ValueError("prim has no name")
        kind = Usd.ModelAPI(prim).GetKind()
        from ._asset import Asset
        from ._collection import Collection
        if kind == Kind.Tokens.group:
            return Collection(name, parent)
        return Asset(name, parent)

    @classmethod
    def from_path(cls, path: str) -> 'Entity | None':
        """Return the proper entity type (Project, Collection, or Asset) from a file path.

        Accepts a project root directory (containing .dedaverse) or a path to a
        USDA metadata file under .dedaverse. Returns None if the path is invalid
        or not under a Dedaverse project.

        Args:
            path: File path string: project root dir, or .dedaverse/*.usda path.

        Returns:
            Project, Collection, or Asset instance, or None if the path is invalid.
        """
        p = Path(path).resolve()
        if not p.exists():
            return None
        if p.is_dir():
            return _project_from_root(p)
        if p.is_file() and p.suffix.lower() in ('.usda', '.usd', '.usdc', '.usdz'):
            entity = _entity_from_metadata_path(p)
            if entity is not None:
                return entity
            return _element_from_content_path(p)
        return None


# --- Internal ---


def _layer_is_anonymous(layer) -> bool:
    """Return True if the layer is anonymous (in-memory only). Works across USD Python binding variants."""
    try:
        return layer.IsAnonymous()
    except AttributeError:
        ident = getattr(layer, 'identifier', None) or ''
        return not ident or str(ident).startswith('anon:')


def _entity_from_metadata_path(meta_path: Path) -> 'Entity | None':
    """Resolve Project/Collection/Asset from a path to a USDA file under .dedaverse."""
    meta_path = meta_path.resolve()
    dedaverse = meta_path.parent
    while dedaverse != dedaverse.parent:
        if (dedaverse / '.dedaverse').is_dir():
            break
        dedaverse = dedaverse.parent
    else:
        return None
    dedaverse = dedaverse / '.dedaverse'
    try:
        rel = meta_path.relative_to(dedaverse)
    except ValueError:
        return None
    parts = list(rel.parts)
    if not parts:
        return None
    from ._project import Project
    from ._collection import Collection
    from ._asset import Asset
    project_stage = next(
        (f for f in dedaverse.iterdir() if f.is_file() and f.suffix.lower() == '.usda'),
        None,
    )
    if not project_stage:
        return None
    rootdir = dedaverse.parent
    prim_name = project_stage.stem
    proj = Project(rootdir.name, rootdir, prim_name=prim_name)
    if len(parts) == 1:
        name = Path(parts[0]).stem
        kind = _kind_of_usda(meta_path)
        if kind == Kind.Tokens.group:
            return Collection(name, proj)
        return Asset(name, proj)
    parent_meta = dedaverse / Path(*parts[:-2]) / (parts[-2].removesuffix('.usda') + '.usda')
    parent_entity = _entity_from_metadata_path(parent_meta)
    if parent_entity is None:
        return None
    name = Path(parts[-1]).stem
    kind = _kind_of_usda(meta_path)
    if kind == Kind.Tokens.group:
        return Collection(name, parent_entity)
    return Asset(name, parent_entity)


def _kind_of_usda(usda_path: Path):
    """Return the Kind of the default prim in the USDA file, or None."""
    try:
        stage = Usd.Stage.Open(str(usda_path))
        if not stage:
            return None
        default_prim = stage.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            return None
        return Usd.ModelAPI(default_prim).GetKind()
    except Exception:
        return None


def _element_from_content_path(content_file_path: Path) -> 'Entity | None':
    """Resolve an Element from a content file path under the project root (not under .dedaverse)."""
    content_file_path = content_file_path.resolve()
    rootdir = content_file_path.parent
    while rootdir != rootdir.parent:
        if (rootdir / '.dedaverse').is_dir():
            break
        rootdir = rootdir.parent
    else:
        return None
    proj = _project_from_root(rootdir)
    if proj is None:
        return None
    try:
        rel = content_file_path.parent.relative_to(Path(proj.rootdir))
    except ValueError:
        return None
    segments = list(rel.parts)
    if not segments:
        return None
    from ._asset import Asset
    from ._collection import Collection
    from ._element import Element
    current = proj
    stage = proj.stage if hasattr(proj, 'stage') else None
    for seg in segments:
        prim_path = f'{current.prim_path}/{seg}'
        kind = None
        if stage:
            prim = stage.GetPrimAtPath(prim_path)
            if prim and prim.IsValid():
                kind = Usd.ModelAPI(prim).GetKind()
        if kind == Kind.Tokens.group:
            current = Collection(seg, current)
        else:
            current = Asset(seg, current)
    return Element(content_file_path.stem, current)


def _project_from_root(rootdir: Path) -> 'Entity | None':
    """Return a Project instance from a project root directory (containing .dedaverse)."""
    dedaverse = rootdir / '.dedaverse'
    if not dedaverse.is_dir():
        return None
    project_stage = next(
        (f for f in dedaverse.iterdir() if f.is_file() and f.suffix.lower() == '.usda'),
        None,
    )
    if not project_stage:
        return None
    from ._project import Project
    prim_name = project_stage.stem
    return Project(rootdir.name, rootdir, prim_name=prim_name)