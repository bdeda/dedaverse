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
"""Options and results for the game asset optimizer.

Standard library only: this module is also imported by the job that runs inside Blender's Python.
"""
__all__ = ['NORMAL_CONVENTIONS', 'OptimizeError', 'OptimizeOptions', 'OptimizeResult', 'SOURCE_SUFFIXES',
           'TEXTURE_SIZES', 'UV_METHODS']

from dataclasses import asdict, dataclass, field, fields

NORMAL_CONVENTIONS = ('opengl', 'directx')
SOURCE_SUFFIXES = ('.usd', '.usda', '.usdc', '.usdz', '.glb', '.gltf', '.fbx', '.obj')
TEXTURE_SIZES = (256, 512, 1024, 2048, 4096, 8192)
UV_METHODS = ('auto', 'symmetry', 'seams')


class OptimizeError(RuntimeError):
    """Raised when an asset cannot be optimized."""


@dataclass
class OptimizeOptions:  # pylint: disable=too-many-instance-attributes
    """Settings for one optimizer run.

    The defaults are the pipeline that won the comparison in docs/GAME_ASSET_OPTIMIZER.md:
    collapse-decimate to the budget, unwrap flat assets with a planar projection per side (other shapes
    with seams found on a smoothed copy), bake at 2K.

    Attributes:
        target_tris: Triangle budget for the game mesh. Meshes already under it are not decimated.
        texture_size: Width/height of the baked BaseColor, Normal and ORM maps.
        normal_convention: ``'opengl'`` (Blender, glTF, Unity) or ``'directx'`` (Unreal).
        margin_px: UV island padding, in pixels at ``texture_size``.
        uv_method: ``'symmetry'`` (find the mid-plane, planar-project front and back, unwrap the side walls),
            ``'seams'`` (seams from a smoothed copy, for round or irregular shapes) or ``'auto'`` (symmetry
            when the front and back cover most of the surface).
        seam_smooth_iterations: Smoothing passes on the copy used to find UV islands.
        seam_angle: Smart UV Project angle limit (degrees) on the smoothed copy.
        merge_distance: Vertex weld distance as a fraction of the bounding-box diagonal.
        bake_samples: Cycles samples per bake pass.
        use_gpu: Try to bake on the GPU (falls back to the CPU when none is available).
        export_fbx: Write ``<name>.fbx`` (Unreal, Maya).
        export_glb: Write ``<name>.glb`` with embedded textures (Godot, web, Unreal).
        keep_blend: Also save the working ``.blend`` (high and low poly) for inspection.
        name: Base name for the outputs (defaults to the source file's stem).
    """

    target_tris: int = 12000
    texture_size: int = 2048
    normal_convention: str = 'opengl'
    margin_px: int = 8
    uv_method: str = 'auto'
    seam_smooth_iterations: int = 60
    seam_angle: float = 66.0
    merge_distance: float = 1e-5
    bake_samples: int = 4
    use_gpu: bool = True
    export_fbx: bool = True
    export_glb: bool = True
    keep_blend: bool = False
    name: str = ''

    @classmethod
    def from_dict(cls, data: dict) -> 'OptimizeOptions':
        """Build options from a dict, ignoring unknown keys.

        Args:
            data: Mapping of option names to values.

        Returns:
            The options, validated.

        Raises:
            OptimizeError: If a value is out of range.
        """
        known = {f.name for f in fields(cls)}
        options = cls(**{k: v for k, v in data.items() if k in known})
        options.validate()
        return options

    @property
    def margin_fraction(self) -> float:
        """UV island margin as a fraction of the 0-1 UV square."""
        return self.margin_px / self.texture_size

    def to_dict(self) -> dict:
        """Return the options as a JSON-serialisable dict."""
        return asdict(self)

    def validate(self) -> None:
        """Check every option is usable.

        Raises:
            OptimizeError: Naming the first invalid option.
        """
        checks = (
            (self.target_tris >= 12, f'target_tris must be at least 12, got {self.target_tris}'),
            (self.texture_size in TEXTURE_SIZES,
             f'texture_size must be one of {TEXTURE_SIZES}, got {self.texture_size}'),
            (self.normal_convention in NORMAL_CONVENTIONS,
             f'normal_convention must be one of {NORMAL_CONVENTIONS}, got {self.normal_convention!r}'),
            (0 <= self.margin_px <= self.texture_size // 8,
             f'margin_px must be between 0 and {self.texture_size // 8}, got {self.margin_px}'),
            (self.uv_method in UV_METHODS, f'uv_method must be one of {UV_METHODS}, got {self.uv_method!r}'),
            (self.seam_smooth_iterations >= 0, 'seam_smooth_iterations cannot be negative'),
            (1.0 <= self.seam_angle <= 89.0, f'seam_angle must be between 1 and 89 degrees, got {self.seam_angle}'),
            (self.merge_distance >= 0, 'merge_distance cannot be negative'),
            (self.bake_samples >= 1, 'bake_samples must be at least 1'),
            (self.export_fbx or self.export_glb, 'enable at least one of export_fbx and export_glb'),
        )
        for ok, message in checks:
            if not ok:
                raise OptimizeError(message)


@dataclass
class OptimizeResult:  # pylint: disable=too-many-instance-attributes
    """What an optimizer run produced.

    Attributes:
        source: The input file.
        output_dir: Directory holding every output.
        meshes: Exported mesh files (FBX and/or GLB).
        textures: Baked texture files keyed by ``basecolor``, ``normal`` and ``orm``.
        blend: The saved ``.blend``, when ``keep_blend`` was set.
        report: Path of the JSON report.
        stats: Measurements: triangle/vertex counts before and after, UV metrics, surface error.
        timings: Seconds spent per pipeline step.
        warnings: Non-fatal problems worth showing the user.
    """

    source: str
    output_dir: str
    meshes: list[str] = field(default_factory=list)
    textures: dict[str, str] = field(default_factory=dict)
    blend: str = ''
    report: str = ''
    stats: dict = field(default_factory=dict)
    timings: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> 'OptimizeResult':
        """Build a result from the dict written by the Blender job, ignoring unknown keys."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def summary(self) -> str:
        """One line describing the reduction, e.g. for a log or the command line."""
        before = self.stats.get('source', {})
        after = self.stats.get('game', {})
        error = self.stats.get('surface_error', {})
        return (f'{before.get("tris", "?")} -> {after.get("tris", "?")} tris, '
                f'{after.get("gpu_verts", "?")} GPU verts, {after.get("uv_islands", "?")} UV islands, '
                f'mean error {error.get("mean_pct", "?")}% of size')

    def to_dict(self) -> dict:
        """Return the result as a JSON-serialisable dict."""
        return asdict(self)
