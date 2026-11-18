# Plan: learned UV-island (seam) prediction from our game assets

## Goal
Given a triangle mesh, predict where UV seams should go so the resulting islands can be fed to an unwrapper (PartUV, Blender, xatlas, etc.). Train on the UV layouts artists already made for our existing assets.

## Approach in one paragraph
Work on the **face-adjacency (dual) graph**. Each mesh edge shared by two faces is labelled *seam* if the two faces sit in different UV islands in the artist's layout. A graph network predicts P(seam) per edge. Islands = connected components after cutting edges above a threshold, with tiny islands merged away. This needs no SAM masks, no multi-view rendering and no per-shape optimization, which is what makes SAMPart3D's `train.py` the wrong starting point. It also uses no third-party weights, so there is no licence question for the baseline.

## Files
Package `deda.core.ai.uv_seams` (`src/deda/core/ai/uv_seams/`):

| Module | Needs torch | Contents |
|---|---|---|
| `_geometry.py` | no | weld, face graph, labels, features, island decoding, synthetic boxes |
| `_data.py` | no | `.npz` and synthetic sources, dataset, batching, grouped train/val split |
| `_metrics.py` | no | seam-edge precision/recall/F1, best threshold, island-count error |
| `_options.py` | no | `TrainConfig`, learning-rate schedule |
| `_model.py` | **yes** | `SeamNet` (message passing + per-mesh context) |
| `_trainer.py` | **yes** | `train`, `evaluate`, `predict`, checkpoints |
| `__main__.py` | imports it lazily | `python -m deda.core.ai.uv_seams train / predict` |

The torch-free modules need only numpy (already a dependency; connected components are done in numpy, so there is no scipy requirement). PyTorch stays optional: it is not installed in CI, and importing the package never imports it (`SeamNet`, `train`, `predict` etc. load on first access).

Relation to the existing `deda.plugins.game_asset` optimizer: its `--uv seams` mode derives seams from Smart UV Project on a smoothed copy. A trained seam model could replace or complement that step; Phase 2 compares them on distortion and packing.

## Phase 0: Data audit (before any training)
1. Export each asset to `.npz`: `vertices (V,3)`, `faces (F,3)`, plus either `face_island (F,)` or `faces_uv (F,3)` + `uv (U,2)`. Face order in `faces_uv` must match `faces`.
2. Triangulate consistently. Keep the artist's triangulation.
3. Filter and report counts for each of these:
   - multiple UV sets (pick the primary lightmap/albedo set)
   - overlapping or mirrored UVs (islands stacked on each other: labels become ambiguous; drop or flag)
   - non-manifold or degenerate faces
   - face counts (decimate or LOD-pick above the `--max-faces` limit)
4. Split by **asset family** (variants, LODs and colour swaps together), not by file, or validation will look better than reality. Use `--group-regex` for this, e.g. `--group-regex "^(.*?)(?:_lod\d+)?$"` keeps every LOD of an asset on one side of the split; without it each file is its own group.
5. Look at 20 random labelled meshes in a viewer. Confirm the seams look like what an artist would call a seam.

**Gate:** at least a few thousand clean assets and a seam-edge fraction in a sane range (typically a few percent of edges).

## Phase 1: Baseline (this script)
- **Input features:** face normal, centroid, relative area. Per edge: dihedral cosine, convexity, relative edge length and centroid distance. Meshes are normalized to a unit box and vertices are welded by position first. Game assets duplicate vertices at seams, so skipping the weld would leak the label.
- **Model:** 8 message-passing layers (hidden 128) with a per-mesh global-context vector in each layer, so the net can reason about closed seam loops and not only local neighbourhoods. The edge head is symmetric in the two faces.
- **Loss:** weighted BCE (`pos_weight` estimated from data because seams are rare).
- **Training:** AdamW, warmup + cosine, grad clip, optional bf16, rotation augmentation (`yaw` by default, assuming Y-up; use `full` if orientation is arbitrary), atomic checkpoints, `--resume`.
- **Eval (per epoch):** seam-edge precision/recall/F1 at several thresholds (best threshold saved in the checkpoint) and island-count MAE.

**Gate:** seam F1 clearly above a trivial baseline (threshold on dihedral angle alone; compute this before trusting any number).

## Phase 2: Evaluate what actually matters
Edge F1 against artist seams undersells a good model, since valid seam placements differ. Add downstream metrics on held-out assets:
- unwrap with predicted seams vs artist seams: **stretch/distortion**, island count, **packing efficiency**, total seam length
- fraction of seam length on hard edges / low-visibility areas
- a short blind artist review (20 assets, predicted vs original)

## Phase 3: Improvements (only if Phase 2 says they are needed)
1. Contrastive face-embedding head (pull same-island faces together). This is the part of SAMPart3D worth borrowing, and it handles closed regions better than edge cuts.
2. Stronger global context: transformer over face tokens, or a pretrained point/mesh backbone (check its licence first).
3. Closed-loop decoding: ensure the cut graph disconnects the mesh into discs (genus handling), e.g. min-cut / spanning-tree repair of predicted seams.
4. Condition on style (texel-density target, hard-surface vs organic) if artists use different conventions per asset class.
5. Per-edge features from surface curvature, symmetry, or UV-distortion estimates.

## Risks
| Risk | Mitigation |
|---|---|
| Labels reflect artist habit, not a unique answer | Judge by downstream distortion, not only edge F1 |
| Overlapping/mirrored UVs corrupt labels | Detect and drop in Phase 0 |
| Predicted seams don't disconnect a closed mesh | Decoding repair (Phase 3.3); always run an unwrapper afterwards |
| Memory on large meshes | `--max-faces`, smaller batch, bf16, decimate |
| Train/val leakage via variants | Split by asset family |
| Orientation conventions | Choose `--rot-aug` to match your assets (yaw assumes Y-up) |

## Status (be aware)
- **Tested in CI (no torch needed):** geometry, data, metrics, config, CLI and the lazy package API: about 130 tests in `tests/test_uv_seams_*.py` covering every line of the torch-free modules except two lines the coverage config excludes.
- **Written but not yet run:** `_model.py` and `_trainer.py`, and their tests (`tests/test_uv_seams_trainer.py`, skipped wherever torch is missing). They were developed on a machine without PyTorch, so **run them on your GPU box first**:

```
python -m pytest tests/test_uv_seams_trainer.py
python -m deda.core.ai.uv_seams train --synthetic 200 --epochs 5 --out runs/smoke
```
On the synthetic boxes, seam F1 should climb towards 1.0 within a few epochs (the seams are just 90-degree edges). If it does not, there is a bug to fix before touching real data.

## Open questions for you
1. Output a seam set for a downstream unwrapper, or final islands directly? (This plan assumes seams.)
2. Roughly how many assets, typical triangle counts, and are UV sets/overlaps consistent?
3. Y-up or arbitrary orientation? GPU/VRAM available?
