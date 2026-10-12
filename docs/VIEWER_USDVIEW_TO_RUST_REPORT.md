# Report: Removing usdview Dependency and Upgrading the Dedaverse Viewer to Rust

This document outlines what would be required to (1) remove the Usdviewq/usdview dependency from the Dedaverse viewer and (2) replace or upgrade the viewer with a Rust-based application. It is intended to support planning and estimation, not as a step-by-step implementation plan.

---

## 1. Current Architecture and usdview Dependency

### 1.1 Where Usdviewq Is Used

The Dedaverse viewer lives under `src/deda/core/viewer/`. It depends on **Pixar’s Usdviewq** (the Qt/imaging layer of OpenUSD’s usdview), not the standalone `usdview` binary. Usdviewq is only available when OpenUSD is **built from source with imaging and Python bindings**; the PyPI package `usd-core` does **not** include it.

| File | Usdviewq / pxr usage |
|------|------------------------|
| `_usd_viewer.py` | `StageView` (subclass), `CameraMaskModes`; `_dataModel`, `viewSettings`, `freeCamera._camera`; `Usd`, `Sdf`, `Gf`, `UsdLux`; `computePickFrustum`, `pick()`, Hydra rendering via base `StageView`. |
| `_window.py` | `CameraMaskModes`; `Usd`, `UsdUtils`; window embeds `UsdViewWidget` and reads/writes `viewSettings` (dome light, mask, HUD, bboxes). |
| `_camera_reticle.py` | Optional plugin: `Usdviewq.plugin.PluginContainer`, `StageView` (for usdview-style integration). |

Other viewer modules (`_annotation.py`, `_reticle.py`, `_slate.py`, `_playbar.py`) use **PySide6** and **OpenGL** (or the StageView’s GL context) and **pxr** only for types like `Gf` where needed; they do not directly depend on Usdviewq.

### 1.2 What Usdviewq Provides Today

- **StageView**  
  A Qt/OpenGL widget that:
  - Renders the USD stage via **Hydra** (UsdImagingGL engine).
  - Manages the free camera (orbit/pan/dolly), viewport, and clipping.
  - Provides picking (raycast to prims), `computePickFrustum`, `pick()`.
  - Exposes `_dataModel` (stage, current frame, playback) and `viewSettings` (dome light, camera mask mode, HUD, bboxes, complexity, etc.).

- **CameraMaskModes**  
  Enum for camera mask (e.g. full vs partial) used in `viewSettings.cameraMaskMode`.

- **Integration surface**  
  Dedaverse subclasses `StageView` to add:
  - Annotation overlay (draw strokes), reticle overlay, slate overlay, prim-info overlay.
  - Context menu for variant switching (from picked prim).
  - Camera get/set (free camera matrix) for notes save/load.
  - Dome light texture injection via engine wrapper.

So the **removal of usdview** means replacing **StageView + Hydra rendering + viewSettings + picking and camera** with an implementation that does not use Usdviewq, while preserving as much of the current behavior as possible.

---

## 2. Option A: Remove usdview Only (Stay on Python + Qt)

Goal: keep the viewer in Python and PySide6, but **stop depending on Usdviewq** so that the viewer works with **only `usd-core`** (or a minimal OpenUSD build without imaging).

### 2.1 Gaps to Fill Without StageView

- **Rendering**
  - Today: Hydra (UsdImagingGL) inside StageView.
  - Without Usdviewq: you need another way to draw the stage (e.g. custom GL with usd-core for stage traversal and a simple renderer, or a different rendering backend). Options:
    - **Minimal:** Use `usd-core` to read stage/geometry and render with OpenGL (or a thin wrapper) yourself — significant work (materials, lights, camera).
    - **Alternative backends:** Integrate a different Hydra delegate or a third-party viewer library that can load USD and render (e.g. other C++/Python viewers with a embeddable widget; availability and licensing vary).

- **Camera**
  - Today: `viewSettings.freeCamera._camera` (Gf.Camera), orbit/pan/dolly in StageView.
  - Without Usdviewq: implement a free camera (matrix, projection, view matrix) and wire it to your own renderer and to the existing notes save/load (camera transform list).

- **Picking**
  - Today: `computePickFrustum`, `pick()` from StageView.
  - Without Usdviewq: implement GPU picking (e.g. render prim IDs to a buffer and read back) or CPU raycast using `usd-core` (e.g. UsdGeom, bounding boxes or ray-scene intersection if available).

- **View settings**
  - Today: `viewSettings` (dome light on/off, texture path, camera mask, HUD, bboxes, complexity).
  - Without Usdviewq: keep the same UI (menu/toolbar) but drive your own viewer state and renderer (dome light, mask overlay, HUD, bbox drawing).

### 2.2 Estimated Work (Remove usdview Only)

- **Design**  
  Choose rendering path (custom GL vs third-party viewer lib), document new viewer architecture and how camera/settings map from current `viewSettings`.

- **New viewport widget**  
  Implement or integrate a Qt/OpenGL widget that:
  - Loads a `Usd.Stage` (from `usd-core`), traverses/composes as needed.
  - Renders the stage (geometry, basic shading, dome light if desired).
  - Handles resize, camera (orbit/pan/dolly), and optional camera mask overlay.

- **Picking and prim interaction**  
  Implement picking and map to prim path; reattach variant-set context menu and prim-info overlay to the new widget.

- **Camera and notes**  
  Keep `get_camera_transform` / `set_camera_transform` (4×4 matrix list) and wire them to the new camera so notes save/load still works.

- **Overlays**  
  Port or reattach annotation, reticle, and slate overlays to the new widget (they already use GL or widget coordinates; ensure they draw after the new scene render).

- **Settings persistence**  
  Replace reads/writes to `viewSettings` with your own settings (e.g. same QSettings keys) and drive the new viewer from them.

- **Testing and parity**  
  Regression-test open/save, camera restore, annotations, variant switching, dome light, mask, playbar.

Rough order of magnitude: **several months** for one developer, depending on how much visual parity and performance you want and whether you adopt an existing viewer library.

---

## 3. Option B: Rust-Based Viewer (Upgrade Path)

Goal: replace the current Python/Usdviewq viewer with a **Rust application** that can either run standalone or be embedded (e.g. in the existing Python/Qt app via an embedded process or a native widget).

### 3.1 Rust USD Landscape (as of 2024–2025)

- **openusd-rs**  
  Pure Rust, early stage; focused on reading flattened USD and scene info for rendering. Not a full OpenUSD stack; API still evolving.

- **openusd (mxpv)**  
  Native Rust USDA/USDC support; SDF and format handling. No Hydra/imaging stack.

- **C/C++ OpenUSD from Rust**  
  Rust could call into OpenUSD C APIs (or C++ with a C ABI layer) if you build OpenUSD and expose a minimal C API for stage open, scene query, and optionally rendering. This reuses Pixar’s stack but adds a Rust↔C++ boundary and build complexity.

So today there is **no Rust equivalent of Usdviewq + Hydra**. A “Rust viewer” implies either:
- **Rust front-end + C/C++ OpenUSD/Hydra** (Rust for app/window/UI, C++ for USD and rendering), or
- **Rust-only** using Rust USD crates for stage/data and a Rust or native rendering path (e.g. wgpu, Vulkan, or OpenGL) — more work and limited feature parity with Hydra initially.

### 3.2 Architecture Options for a “Rust Viewer”

**Option B1: Standalone Rust viewer app**

- Rust binary: windowing (e.g. winit), UI (egui, or Qt via Rust bindings), and either:
  - Rust USD crates for stage + your own renderer (wgpu/OpenGL), or
  - FFI to OpenUSD/Hydra (C or C++ shim).
- Dedaverse main app (Python) could **launch** this viewer as a separate process and pass a USD path (e.g. CLI or small RPC). No embedding; simpler process model, no shared UI toolkit.

**Option B2: Rust viewer as a library embedded in Python**

- Build the Rust viewer as a library (e.g. `cdylib`) that:
  - Exposes a C ABI (or Python-callable API via PyO3) that creates a viewport (e.g. window handle or framebuffer).
  - Uses Rust USD and a Rust renderer, or calls into OpenUSD/Hydra via C/C++.
- Python/Qt app loads the library and embeds the viewport (e.g. QWindow from a foreign handle, or receives images and shows them in a QLabel). Complex (threading, event loop, lifecycle).

**Option B3: Rust app that embeds or replaces the “viewer” part of Dedaverse**

- Full Rust application: project open, asset list, and viewer in one Rust binary. The current Python Dedaverse app could be reduced to a “non-viewer” tool (e.g. config, asset metadata, plugins) or deprecated for the “full app” use case. Large scope change.

### 3.3 What the Rust Viewer Would Need to Implement

To match current behavior as much as possible:

- **USD load and composition**  
  Open stage from path (and optionally in-memory). Use Rust USD crates or FFI to OpenUSD.

- **Rendering**  
  - Either: call Hydra/UsdImagingGL via C++ (Rust FFI) for maximum parity, or  
  - Implement a render path in Rust (mesh extraction, materials, lights, dome light) using openusd-rs or similar — substantial effort and likely lower parity (materials, delegates).

- **Camera**  
  Free camera (orbit/pan/dolly), projection, and serialization of 4×4 transform for notes compatibility.

- **Picking**  
  Raycast or GPU picking to prim path for variant menu and prim info.

- **UI**  
  - Menu/toolbar: File (open/recent), View (dome light, mask, HUD, bboxes, reticle, slate), playback (play/pause, frame), aspect ratio, etc.
  - Overlays: camera reticle (action/title safe), slate text, annotation strokes, prim info on hover.
  - Notes integration: load/save annotations and camera with the same format as today (or define an adapter).

- **Playbar**  
  Timeline, current frame, playback; drive stage time and redraw.

- **Interop with Dedaverse (if embedded or launched from Python)**  
  - If launched as subprocess: CLI args (e.g. stage path, initial frame).  
  - If embedded: stable API for “load this stage”, “set frame”, “get/set camera”, “export viewport image” for notes.

### 3.4 Estimated Work (Rust Viewer)

- **With Hydra/OpenUSD via FFI**  
  Design C/C++ shim for stage + Hydra render + camera; Rust window/UI and glue. Order of magnitude: **many months** (3–6+), depending on team size and how much of usdview you replicate.

- **Rust-only (Rust USD crates + own renderer)**  
  No usdview/Hydra dependency; full implementation of rendering and features in Rust. **Larger and longer** (e.g. 6–12+ months) to approach current feature set and quality.

- **Standalone Rust viewer (Option B1)**  
  Reduces integration surface (no embedding); good first step. Embedding (B2) or full Rust app (B3) adds more work on top.

---

## 4. Recommendations and Order of Work

### 4.1 If the Goal Is to Remove the usdview Build Dependency Only

- **Short term:**  
  - Document that the **built-in viewer and usdview require OpenUSD built with imaging and Usdviewq** (as in INSTALLATION.md).  
  - Keep using Usdviewq for the viewer; no code change to remove it yet.

- **Medium term (remove Usdviewq):**  
  - Implement **Option A**: a custom viewport widget using **usd-core** plus either (a) a minimal OpenGL renderer for the stage, or (b) another embeddable USD viewer with a clear license.  
  - This removes the need to build OpenUSD with imaging for Dedaverse and simplifies install, at the cost of development time and possible parity gaps.

### 4.2 If the Goal Is a Rust Viewer

- **Phase 1 – Proof of concept**  
  - Standalone Rust app: open a USD file (via openusd-rs or FFI to usd-core), open a window, render something (e.g. bbox or simple mesh).  
  - Validates Rust USD + rendering path and performance on your target platforms.

- **Phase 2 – Feature parity (subset)**  
  - Free camera, picking, one overlay (e.g. reticle).  
  - Integrate with Dedaverse (e.g. launch from app with path; or later, embed).

- **Phase 3 – Full parity and integration**  
  - Annotations, slate, playbar, notes (camera + annotations), view settings, variant menu.  
  - Decide: standalone only or embedded in Python/Qt.

### 4.3 Dependency and Build Impact

- **Removing usdview (Option A)**  
  - **Dropped:** Usdviewq, and the need to build OpenUSD with imaging for the viewer.  
  - **Still required:** `usd-core` (or equivalent) for stage/open/composition if you keep USD in the viewer at all; PySide6 and OpenGL (or your chosen backend) for the viewport.

- **Rust viewer (Option B)**  
  - **New:** Rust toolchain, Rust USD crates and/or OpenUSD C/C++ build for FFI, and a Rust UI/windowing stack.  
  - **Optional:** Keep Python Dedaverse for everything except the viewport; viewer becomes a separate binary or library.

---

## 5. Summary Table

| Item | Remove usdview only (Python) | Rust viewer (new app/lib) |
|------|------------------------------|----------------------------|
| Usdviewq dependency | Removed; replaced by custom or third-party viewport | N/A (no Usdviewq in Rust) |
| Rendering | You implement or integrate (e.g. usd-core + GL) | Rust renderer or Hydra via FFI |
| Camera / picking / settings | Reimplement in Python against new viewport | Implement in Rust |
| Overlays (reticle, slate, annotations) | Reattach to new widget; logic largely unchanged | Reimplement in Rust |
| Notes (camera + annotations) | Keep format; wire to new camera/overlays | Same format or adapter in Rust |
| Install / build | Simpler (no OpenUSD imaging build) | Rust + deps; optional OpenUSD for FFI |
| Estimated effort | Several months (1 dev) | Many months to a year+ depending on parity and embedding |

---

*Report generated for planning. Implementation details and estimates should be refined with spikes and proof-of-concept work.*
