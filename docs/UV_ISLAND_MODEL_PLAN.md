# Plan: learned UV-island (seam) prediction from our game assets

## Goal
Given a triangle mesh, predict where UV seams should go so the resulting islands can be fed to an unwrapper (PartUV, Blender, xatlas, etc.). Train on the UV layouts artists already made for our existing assets.

## Approach in one paragraph
Work on the **face-adjacency (dual) graph**. Each mesh edge shared by two faces is labelled *seam* if the two faces sit in different UV islands in the artist's layout. A graph network predicts P(seam) per edge. Islands = connected components after cutting edges above a threshold, with tiny islands merged away. This needs no SAM masks, no multi-view rendering and no per-shape optimization, which is what makes SAMPart3D's `train.py` the wrong starting point. It also uses no third-party weights, so there is no licence question for the baseline.

## Files
Live in `tools/uv_islands/`, deliberately **outside `src/deda`**: the baseline is experimental, so it stays out of the pylint, coverage and bandit gates until it is promoted.
- `tools/uv_islands/uv_geometry.py`: welding, dual graph, labels, features, decoding, synthetic data (numpy + scipy; tested)
- `tools/uv_islands/train_uv_islands.py`: dataset, model, train/eval loop, `predict` command (PyTorch; syntax-checked only, see Status)

Dependencies: `torch` and `numpy` are already in `pyproject.toml`; **`scipy` is not** (used for connected components). Adding it, and the move into `src/deda/core/ai/` with unit tests, are follow-ups that need your approval per AGENTS.md.

Relation to the existing `deda.plugins.game_asset` optimizer: its `--uv seams` mode derives seams from Smart UV Project on a smoothed copy. A trained seam model could replace or complement that step; Phase 2 compares them on distortion and packing.

## Phase 0: Data audit (before any training)
1. Export each asset to `.npz`: `vertices (V,3)`, `faces (F,3)`, plus either `face_island (F,)` or `faces_uv (F,3)` + `uv (U,2)`. Face order in `faces_uv` must match `faces`.
2. Triangulate consistently. Keep the artist's triangulation.
3. Filter and report counts for each of these:
   - multiple UV sets (pick the primary lightmap/albedo set)
   - overlapping or mirrored UVs (islands stacked on each other: labels become ambiguous; drop or flag)
   - non-manifold or degenerate faces
   - face counts (decimate or LOD-pick above the `--max-faces` limit)
4. Split by **asset family** (variants, LODs and colour swaps together), not by file, or validation will look better than reality. The script splits by file as a placeholder; replace it with your family key.
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
- `uv_geometry.py` was run and verified: welding, dual-graph edge counts, seam counts on synthetic boxes (12n seams), island decoding, small-island merging, UV-to-island extraction.
- `train_uv_islands.py` compiles but **was not executed**: this sandbox has no PyTorch and cannot install it. Run the smoke test first on your GPU box:

```
python tools/uv_islands/train_uv_islands.py train --synthetic 200 --epochs 5 --out runs/smoke
```
On the synthetic boxes, seam F1 should climb towards 1.0 within a few epochs (the seams are just 90-degree edges). If it does not, there is a bug to fix before touching real data.

## Open questions for you
1. Output a seam set for a downstream unwrapper, or final islands directly? (This plan assumes seams.)
2. Roughly how many assets, typical triangle counts, and are UV sets/overlaps consistent?
3. Y-up or arbitrary orientation? GPU/VRAM available?
