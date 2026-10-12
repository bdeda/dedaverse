# Mesh and UV editing: design

Plan for editing USD stage data in the Dedaverse viewer, starting with meshes: a UV editor, procedural UV
optimisation, and a quad remesher modelled on ZBrush's ZRemesher.

Status: **Phase 0 (UV viewer) is implemented**; everything else is design.

---

## 1. Principles

- **Non-destructive, USD-native.** Edits are opinions on a layer, never rewrites of the source asset. The
  original mesh stays reachable underneath.
- **Pure core, thin UI.** Algorithms are numpy functions over plain arrays with no Qt and no `pxr` in the
  hot path (as `deda.core.viewer._uv` already is), so they are unit-testable and reusable from the CLI, Maya
  and Houdini plugins, and agent roles (`modeller`, `surfacing-lookdev-artist`).
- **Measure before and after.** Every optimiser reports quality metrics so the result is comparable and
  testable, not "looks better".
- **Load nothing when closed.** Panels read the stage only while visible (the UV editor already does this).

## 2. Phase 0: UV viewer (done)

Files: `core/viewer/_uv.py` (data), `core/viewer/_uv_panel.py` (UI), wired in `_window.py`.

- A floating `QDockWidget` (`UvEditorDock`), toggled by **View > UV Editor**; visibility and geometry persist
  in the viewer's `QSettings`.
- Modelled on the Maya UV Editor: canvas with display toggles on top, UV Sets list on the side. Restyled to the
  app's dark neutral palette (rgb 20/30/50 greys, one blue accent, Consolas readouts).
- Canvas: pan (MMB or Alt+LMB), zoom to cursor (wheel), `F` frames the UVs, `Home` frames 0-1. Display:
  UDIM tile grid and numbers, checker, per-shell tint, shell borders, flipped faces.
- Data: any `texCoord2f[]` / `float2[]` primvar is a UV set; `faceVarying`, `vertex`/`varying`, `uniform`,
  `constant` and indexed forms resolve to one UV per face corner. Shells are connected by shared UV *edges*
  (corner-touching shells stay separate, as in Maya). Flipped = winding opposite to the majority of the set.
- Meshes come from a picker (all `UsdGeom.Mesh` prims). `UvEditorPanel.show_prim(path)` exists so viewport
  picking can drive it later.
- Known limits: read-only; samples at the default time (falls back to the earliest sample); per-shell tint
  and flipped fills switch off above 50k faces (one polygon per face); no interactive picking yet.

## 3. Phase 1: edit infrastructure (prerequisite for any tool that writes)

1. **Edit layer.** All writes go to one dedicated sublayer (`<asset>.edits.usda`) set as the edit target via
   `Usd.EditContext`. Nothing is authored on the asset's own layers.
2. **Undo.** Wrap each tool operation in `Sdf.ChangeBlock` and record the layer state it replaces
   (`Sdf.Layer.ExportToString` is too coarse for big meshes; store the replaced attribute values, per
   operation). A bounded undo stack lives in the viewer window; Ctrl+Z / Ctrl+Y.
3. **Selection model.** The viewer has none today (picking only feeds the Ctrl-hover overlay and variant menu).
   Add `selection_changed(list[Sdf.Path])` on the viewport; the UV editor and later tools follow it.
4. **Operation record.** Each tool writes `dedaverse:edit:*` customData on the prim (tool, parameters, metrics)
   so results are reproducible and an agent can see what was done.

## 4. Phase 2: UV tools

Order by value / difficulty:

| Tool | What | Method |
|------|------|--------|
| Distortion view | Heat-map of stretch per face | Singular values of the per-face UV Jacobian: conformal = sigma1/sigma2, area ratio = sigma1*sigma2 vs 3D area, normalised to the set mean |
| Texel density | Report and equalise density per shell | `sqrt(uvArea / area3D)` per shell; uniform scale per shell to the target |
| Pack | Arrange shells into 0-1 or UDIM tiles | Rotate-to-minimum-bbox + MaxRects / skyline, padding in texels, tile-aware |
| Unwrap | New UVs from seams | LSCM first (linear, robust), then SLIM / ABF++ for lower distortion |
| Auto-seams | Propose cuts | Curvature + angle thresholds, minimum-spanning cut tree to make shells discs |
| Transfer | Carry UVs across a topology change | Closest-point barycentric lookup from old to new mesh (needed after remeshing, see 5.6) |

Interactive editing (move/rotate/scale shells, sew/cut, pin) comes after the above, on the Phase 1 edit
stack. Shell selection reuses `UvLayout.island_labels()`.

## 5. Phase 3: quad remesher (ZRemesher-style)

### 5.1 What "reverse engineering" means here

ZRemesher is closed source. This is inference from its documented behaviour, its parameters, and the published
research that every modern quad remesher builds on. It is **not** disassembly of ZBrush, which its licence
forbids and which would not be needed: the problem is well studied.

### 5.2 Observable behaviour of ZRemesher

- Input: any triangle or polygon mesh, dense sculpt meshes included. Output: an almost all-quad mesh with
  regular grid-like patches, few irregular vertices, and edge loops that follow the form (around eyes and
  mouths, down limbs).
- Controls: **Target Polygon Count** (with Half/Same/Double shortcuts); **Adaptive Size** (0 = uniform quads,
  100 = quads shrink where curvature is high); **Curves Strength** and guide curves drawn on the surface
  (loops are forced along them); **Use Polygroups** (patch borders in the input become loop borders);
  **Freeze Border / Freeze Groups**; **Detect Edges** (sharp creases are kept); **Smooth Groups**; symmetry;
  and a painted density mask (paint = smaller quads).
- Result is on-surface but not identical to it, so the workflow re-projects the new mesh onto the original and
  recovers detail (project through subdivision levels).
- Deterministic for a fixed input and settings.

### 5.3 Inferred pipeline

The behaviour (guide curves, polygroup borders, a size parameter, regular patches with singularities)
matches a **field-guided, integer-grid quad meshing** pipeline:

1. **Preprocess.** Weld, remove degenerate and non-manifold geometry, optionally decimate very dense input
   to a working resolution (the remesher does not need the sculpt's full detail to decide flow).
2. **Feature and constraint set.** Sharp edges (dihedral angle), polygroup/`GeomSubset` borders, boundary
   loops, and guide curves become hard alignment constraints.
3. **Orientation field.** A smooth 4-RoSy cross field over the surface (four directions 90 degrees apart),
   initialised from principal curvature directions and constraint tangents, then smoothed by minimising
   misalignment between neighbours. Singularities (valence 3 and 5 vertices in the result) appear where
   the field cannot be smooth; their count is the main topology-quality lever.
4. **Size field.** Target edge length from the requested face count, modulated by curvature
   (Adaptive Size) and the painted density mask.
5. **Parametrisation.** Compute a global parametrisation whose grid lines follow the field at the size field's
   spacing, with integer translations and 90-degree rotations across cuts so patches stitch seamlessly
   (Quadcover / mixed-integer quadrangulation family).
6. **Extraction.** Trace the integer grid back onto the surface to get vertices, edges and quads (QEx-style),
   then handle the few leftover triangles/pentagons.
7. **Cleanup.** Remove tiny faces and valence-2 vertices, relax with tangential smoothing, snap constraint
   loops to the guide curves and borders.
8. **Reproject.** Project vertices onto the input surface (closest point, normal-aware) to stay within a
   tolerance.

### 5.4 Published methods to build on

| Method | Role | Notes |
|--------|------|-------|
| Instant Meshes (Jakob et al. 2015) | Orientation and position fields by local smoothing on a hierarchy, then extraction | Fast, no global solve; BSD-3 code available; weaker at large structure and constraints |
| QuadriFlow (Huang et al. 2018) | Integer grid via min-cost flow, guarantees a manifold quad result | Slower, better regularity |
| Mixed-integer quadrangulation (Bommes et al. 2009), QEx (Ebke et al. 2013) | Global parametrisation and robust extraction | The academic reference for steps 5-6 |
| Quad Remesher / QuadWild (Pietroni et al. 2021) | Constraint-aware, feature-aligned results close to ZRemesher's | QuadWild is the closest open design to ZRemesher's guide-curve behaviour |

Recommendation: do not start from a blank page.

- **Stage A (fast value):** an `IRemesher` interface plus a backend that shells out to an Instant Meshes /
  QuadriFlow executable. Gets target count, crease detection and symmetry now; guide curves and polygroups
  via pre-subdividing and post-snapping.
- **Stage B (own the core):** a numpy implementation of steps 3-8 (field smoothing is vectorisable; the
  extraction needs compiled code, so numba or a small C++ extension), only if Stage A's constraints fall short.

Open decision for the owner: acceptable dependency model (bundled executable vs Python extension vs
pure-Python) and licence constraints (QuadWild is GPL, Instant Meshes BSD-3, QuadriFlow MIT).

### 5.5 Proposed API

```python
@dataclass
class RemeshParams:
    target_faces: int = 5000
    adaptive: float = 0.5          # 0 uniform .. 1 curvature-adaptive
    detect_edges: bool = True      # keep creases above crease_angle
    crease_angle: float = 40.0
    use_polygroups: bool = False   # UsdGeom.Subset borders become hard loops
    guide_curves: list[np.ndarray] = field(default_factory=list)   # polylines on the surface
    guide_strength: float = 1.0
    density_primvar: str | None = None   # per-vertex scale, painted
    symmetry: str | None = None          # 'x' | 'y' | 'z'
    freeze_border: bool = False

@dataclass
class RemeshResult:
    points: np.ndarray; face_counts: np.ndarray; face_indices: np.ndarray
    metrics: RemeshMetrics

def remesh(points, face_counts, face_indices, params) -> RemeshResult: ...
```

Placed in a new `deda/core/mesh/` package (`_topology.py`, `_curvature.py`, `_field.py`, `_extract.py`,
`_project.py`, `_remesh.py`), separate from the viewer.

### 5.6 USD integration

- Remeshed geometry is authored as a **variant** of the mesh prim (`topology = original | remeshed`) on the
  edit layer, so switching back is one variant selection, and the existing variant context menu in the viewer
  already surfaces it.
- Remeshing invalidates UVs and any primvars. After a remesh run **Transfer** (section 4) for every UV set and
  primvar, or flag the UV set as stale in the UV editor. The UV editor's set list is the natural place to show
  "needs transfer".
- Polygroups map to `UsdGeom.Subset` (family `polygroup`); painted density is a `float[]` vertex primvar.

### 5.7 Quality metrics and tests

Reported in `RemeshResult.metrics`, asserted in tests on small analytic meshes (sphere, cube, torus, a plane
with a bump) so every algorithm change has a number:

- quad ratio (target above 95 percent), irregular-vertex count, face-count error vs target
- minimum angle and aspect ratio distribution, Jacobian sign (no inverted quads)
- Hausdorff / mean distance to the input (as a fraction of bounding-box diagonal)
- guide-curve adherence: mean distance from guide polylines to the nearest result edge path
- determinism: same input and params give identical output

## 6. Suggested order

1. Phase 1 edit infrastructure (selection, edit layer, undo): unblocks everything that writes.
2. UV distortion heat-map and texel density (read-only, builds on Phase 0).
3. UV transfer, then packing, then LSCM unwrap.
4. Remesh Stage A behind `IRemesher`, with the viewer command and metrics.
5. Guide-curve drawing in the viewport; interactive UV editing; remesh Stage B if needed.
