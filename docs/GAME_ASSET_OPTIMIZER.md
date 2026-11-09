# Game Asset Optimizer

`deda.plugins.game_asset` turns a dense mesh (for example a ComfyUI / Hunyuan3D / TRELLIS output) into a
game-ready asset: a mesh at a triangle budget, a clean UV layout, and baked BaseColor / Normal / ORM maps.
It runs the work in a background Blender, so Blender must be installed (developed and tested on 5.2).

## Use

```bash
python -m deda.plugins.game_asset axe.usdz                      # writes axe_game/ next to the input
python -m deda.plugins.game_asset axe.usdz -o out --tris 8000 --texture-size 1024 --normals directx
python -m deda.plugins.game_asset sword.glb --uv symmetry        # force the per-side planar layout
python -m deda.plugins.game_asset a.usdz b.glb -o out           # one sub-directory per input
python -m deda.plugins.game_asset                               # open the window
```

In the app: **Game Asset Optimizer** in the main menu. From Python:

```python
from deda.plugins.game_asset import OptimizeOptions, optimize
result = optimize(Path('axe.usdz'), Path('out'), OptimizeOptions(target_tris=12000))
print(result.summary(), result.meshes, result.textures)
```

Inputs: USD/USDA/USDC/USDZ, GLB/glTF, FBX, OBJ. Blender is found from `DEDAVERSE_BLENDER`, the standard
install folders, then `PATH` (`deda.core.finder.find_blender`).

### Outputs

| File | Contents |
|------|----------|
| `<name>.glb` | Game mesh with embedded textures (glTF; normal map always OpenGL) |
| `<name>.fbx` | Game mesh referencing the PNGs next to it |
| `T_<name>_BaseColor.png` | Albedo (sRGB) |
| `T_<name>_Normal.png` | Tangent-space normal map, OpenGL (Y+) or DirectX (Y-) per `--normals` |
| `T_<name>_ORM.png` | Linear: R = 1 (no AO), G = roughness, B = metallic |
| `<name>_report.json` | Triangle/vertex counts, UV metrics, surface error, bake settings, timings |
| `<name>.blend` | Source and game mesh, with `--keep-blend` |

### Engine notes

- **Unreal:** use `--normals directx` (or tick *Flip Green Channel* on the normal texture). Set the ORM texture
  to *Masks* compression with sRGB off. Generate LODs on import (Static Mesh > LOD Settings): the benchmark
  below shows auto-LODs on the 12k mesh were the fastest option.
- **Godot / Unity / web:** use the GLB as-is.

## Pipeline

1. **Import** and join every mesh into one world-space object (the source; kept for baking).
2. **Weld** vertices closer than `merge_distance` x size. Generated meshes are often split along every UV
   seam (the test axe had 133k open edges); welding makes them watertight so decimation works.
3. **Collapse-decimate** to `target_tris`, shade smooth, drop sharp-edge/custom-normal data.
4. **Unwrap** (`--uv`, default `auto`):
   - **`symmetry`, for flat assets** (blades, shields, planks), laid out the way an artist would: find the
     mid-plane (the thinnest principal axis, refined by testing how well the mesh mirrors onto itself),
     planar-project every face turned to the front or the back (the back mirrored so it reads the right
     way round), and unwrap only the side walls. Facing is judged on a smoothed copy, so surface noise
     does not punch holes in the projections.
   - **`seams`, for round or irregular shapes:** Smart UV Project runs on a heavily smoothed copy of the
     game mesh (same topology), its island borders become seams, and the real shape is unwrapped
     (angle-based) along them.
   - **`auto`** uses `symmetry` when the front and back projections would cover at least 55% of the
     surface, otherwise `seams`. The report's `uv` section records the choice, the mirror error and the
     projected share.

   Either way, islands under 8 faces (noise slivers) join the neighbour they share the longest border
   with, then islands are scale-averaged and packed.
5. **Measure** the surface distance between source and game mesh; size the bake cage from it.
6. **Bake** BaseColor and ORM through emission (exact source values: a diffuse-colour bake turns metals
   black) and the tangent-space normal map, selected-to-active, on the GPU when available.
7. **Export** GLB, then FBX, and write the report.

## Why these defaults

Measured on a 700k-triangle AI-generated axe (USDZ from ComfyUI, 4K PBR textures), Blender 5.2,
Unreal 5.5, RTX 4060 Ti.

### UV methods (on the same 12k-triangle mesh)

| Method | Islands | UV space used | Area distortion | GPU verts |
|--------|--------:|--------------:|----------------:|----------:|
| Smart UV Project 66° | 1,322 | 38% | 0.13 | 12.5k |
| Smart UV Project 45° | 3,041 | 21% | 0.06 | 17.3k |
| Lightmap Pack | 12,000 | 33% | 0.78 | 36k |
| Smart UV + Minimum Stretch / Conformal relax | 1,322 | 30-35% | 0.18-1.0 | 12.6k |
| Sharp-edge seams 45° + unwrap | 505 | 55% | 3.29 (451 flipped) | 10.5k |
| Zeeks Auto UV Unwrap add-on (auto seams) | 1,198 | 35% | 1.89 | 12.3k |
| Seams from smoothed copy + angle-based | 201 | 41% | 0.89 | 7.6k |
| Seams from smoothed copy + sliver merge (`seams`) | 33 | 50% | 0.76 | 7.1k |
| **Mid-plane + planar projection per side + sliver merge (`symmetry`, `auto` picks it for flat assets)** | 54 | 38% | **0.35** | 7.3k |

Every angle-based splitter shatters noisy generated surfaces into hundreds of islands. Finding the islands on
a smoothed copy gives a readable layout with 40% fewer GPU vertices than Smart UV, but cuts the blade faces
into pieces and spreads texels unevenly. Projecting each side of the mid-plane keeps the whole front and the
whole back as one island each (blade, wolf head and handle together, ready to paint over) with far more even
texel density. It packs looser (38% of the square against 50%): Blender's packer cannot nest the two large
interlocking sides any tighter (CONVEX and bounding-box packing were worse, 35% and 29%). Merging islands under
8 faces into their neighbours removed the strip of single-triangle slivers from both methods.

### Reduction methods (12k-triangle budget)

| Method | Mean error | p99 error | Notes |
|--------|-----------:|----------:|-------|
| **Collapse decimate (chosen)** | **0.012%** | 0.06% | Keeps the silhouette; uneven triangles |
| Decimate guided by curvature weights | 0.012-0.013% | 0.05% | No better: collapse already spends triangles where error is |
| QuadriFlow remesh | 0.113% | 0.96% | Clean quads and the best UVs (44 islands), but rounds off teeth and notches thin edges |

Errors are percentages of the bounding-box diagonal. QuadriFlow is the better choice when the mesh has to
deform or be edited by hand.

### Unreal 5.5 runtime (1080p, Lumen, virtual shadow maps)

| Variant | 1 axe, GPU ms | 400 axes, GPU ms | Est. memory |
|---------|--------------:|-----------------:|------------:|
| Original 700k | 7.28 | **75.7** | 44 MB |
| Original + Nanite | 7.72 | 8.32 | 44 MB + Nanite pools (~1 GB, shared) |
| Original + UE auto-LODs | 7.33 | 7.55 | 45 MB |
| UE built-in reduce to 12k (4K textures) | 7.21 | 8.26 | 27 MB |
| Decimate 12k + 2K bake | 7.33 | 8.09 | 11 MB |
| **Decimate 12k + 2K bake + UE auto-LODs** | 7.23 | **7.54** | **11 MB** |
| QuadriFlow 12.5k + 2K bake | 7.24 | 8.22 | 11 MB |

The scene's fixed cost (lighting, sky, TSR) is about 7.2 ms, so one dense prop is effectively free; 400 copies
of the original cost 68 ms of geometry passes. The reduced mesh with LODs ties for the fastest frame at a
quarter of the memory. One run per scenario: differences under ~0.5 ms are noise.
