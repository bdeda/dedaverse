# Alternative Rendering Backends for the Dedaverse Viewer

This document summarizes **alternative rendering backends** that could be used for (or alongside) the Dedaverse USD viewer, including options that **leverage high-end GPUs** and support **production-style quality** (depth of field, motion blur, path tracing). It is intended to inform design choices when replacing or upgrading the current Usdviewq/Hydra-based viewport.

---

## 1. How USD Rendering Works: Hydra and Delegates

USD does not dictate a single renderer. Rendering is handled by **Hydra**, a pluggable framework:

- **Scene delegate** — Translates the USD stage into a representation the renderer understands (e.g. `UsdImagingDelegate`).
- **Render delegate** — The actual renderer (e.g. Storm, RenderMan, Arnold). It receives the scene from the delegate and produces pixels.
- **UsdImagingGLEngine** — The usual entry point in an interactive viewer: it takes a `rendererPluginId` and uses the corresponding Hydra render delegate to draw the stage.

So “alternative backends” here means **different Hydra render delegates** (or non-Hydra renderers that consume USD some other way).

---

## 2. Built-in and Common Hydra Delegates

### 2.1 HdStorm (Storm)

- **What it is:** Pixar’s **real-time** Hydra renderer; the default in usdview and in OpenUSD’s imaging stack.
- **APIs:** OpenGL (original), **Metal** (macOS/iOS via HgiMetal), **Vulkan** (experimental from OpenUSD 24.08, HgiVulkan).
- **Quality:** Optimized for **interactive viewport** use: fast, responsive, good for layout and preview. It does **not** implement production effects like depth of field (DOF) or motion blur; it is a real-time rasterizer.
- **Use case:** Default for Dedaverse’s current viewer when using Usdviewq. Good for responsiveness; not for final-frame quality.

### 2.2 HdPrman (Pixar RenderMan)

- **What it is:** Hydra delegate for **Pixar RenderMan** (RIS/REYES and/or XPU path tracer).
- **Quality:** **Production** renderer: DOF, motion blur, global illumination, path tracing, high-quality materials and lighting.
- **Hardware:** Can use **GPU (XPU)** for acceleration on supported NVIDIA GPUs; CPU fallback.
- **Catch:** Requires a **RenderMan license** and installation; usdview (and thus a Dedaverse viewer using Usdviewq) can switch to it via “Renderer” / `SetRendererPlugin()` if the hdPrman plugin and RenderMan are installed and configured (e.g. `RMANTREE`, `RMAN_SHADER_PATH`).
- **Use case:** High-quality preview or “viewport 2.0” style rendering inside the same app, if you have RenderMan and build/link the delegate.

### 2.3 HdArnold (Arnold)

- **What it is:** Hydra delegate for **Autodesk Arnold**.
- **Quality:** **Production** path tracer: DOF, motion blur, volumetrics, GPU (Arnold GPU) support.
- **Hardware:** Arnold GPU can leverage **NVIDIA RTX** and other supported GPUs for faster production-quality renders.
- **Catch:** Requires **Arnold license** and installation; the Hydra delegate (hdArnold) must be built and registered. Not part of vanilla OpenUSD; provided by Autodesk / Arnold.
- **Use case:** Same idea as HdPrman: swap the delegate in a Hydra-based viewer to get production DOF/motion blur and GPU acceleration, at the cost of license and integration.

### 2.4 HdMoonRay (MoonRay)

- **What it is:** Open-source **DreamWorks MoonRay** Hydra delegate (e.g. [openmoonray.org](https://docs.openmoonray.org/user-reference/tools/hydra/)).
- **Quality:** **Production** path tracer; supports advanced features (DOF, motion blur, etc.).
- **Use case:** Option for a high-quality, open-source-capable backend without a commercial RenderMan/Arnold license; integration and build are non-trivial.

---

## 3. NVIDIA Omniverse RTX

- **What it is:** NVIDIA’s **Omniverse** platform includes a **USD-native** real-time and path-traced viewport (**RTX Renderer**) with multiple modes (e.g. real-time, interactive path tracing, “Photo” for high quality).
- **Quality:** **GPU-accelerated** path tracing on **NVIDIA RTX**; supports production-like quality (DOF, motion blur, global illumination, etc.) when using the path-traced modes.
- **Integration options:**
  - **Omniverse Kit apps** (e.g. USD View, Create): full Omniverse stack; not a drop-in for Dedaverse.
  - **Embedded / streaming:** Omniverse provides an **Embedded Web Viewer** and streaming so a Kit-based USD Viewer (with RTX viewport) can be embedded in a web or other client; the heavy rendering runs on a workstation or server with a capable GPU.
- **Catch:** Tied to **NVIDIA ecosystem** (drivers, RTX GPUs, Omniverse install); not a simple “link one library into Dedaverse” — more like “run an Omniverse viewer and optionally embed or stream it.”
- **Use case:** If the goal is “high-quality GPU viewport with DOF/motion blur” and the environment is NVIDIA-centric, Omniverse is a strong candidate for a **separate** or **embedded** viewer rather than replacing the current viewport in-process.

---

## 4. Other Options (Short)

- **Custom Vulkan/Metal/DX12 + USD:** Implement your own real-time viewer using `usd-core` (or Rust USD crates) and a modern graphics API; add a minimal path tracer or post-process DOF/motion blur for “better than Storm” quality. High effort; full control.
- **Third-party DCC viewers:** Some DCCs (e.g. Maya, Houdini) have USD support and high-quality viewports; they are not designed as embeddable libraries for Dedaverse.
- **Cloud / remote renderers:** Render USD on a farm or cloud service (e.g. GPU instances) and stream or composite the result; quality can be production-grade (DOF, motion blur) but architecture is “viewer as client” rather than local viewport.

---

## 5. Depth of Field and Motion Blur in USD

- **USD conventions:** USD’s rendering documentation and schema support **camera and render settings** that describe DOF (e.g. focal length, aperture, focus distance) and **motion blur** (shutter, samples). So the **data side** is standardized; support depends on the **render delegate**.
- **Who supports it:**
  - **HdStorm:** No DOF or motion blur (real-time viewport).
  - **HdPrman, HdArnold, HdMoonRay:** Yes; production delegates that interpret USD camera and render settings.
  - **Omniverse RTX:** Yes in path-traced modes; quality and performance scale with GPU (e.g. RTX).

So “higher quality with DOF and motion blur” means using a **production Hydra delegate** (Prman, Arnold, MoonRay) or an **Omniverse-style** path-traced viewport, not the default Storm viewport.

---

## 6. Summary Table

| Backend        | Type           | DOF / motion blur | GPU use        | How to use with Dedaverse today                    |
|----------------|----------------|--------------------|----------------|----------------------------------------------------|
| **HdStorm**    | Real-time      | No                 | Yes (GL/Metal/Vulkan) | Default when using Usdviewq.                      |
| **HdPrman**    | Production     | Yes                | Yes (XPU)      | Switch delegate in Usdviewq if RenderMan + plugin installed. |
| **HdArnold**   | Production     | Yes                | Yes (Arnold GPU) | Custom build: register hdArnold; switch delegate.  |
| **HdMoonRay**  | Production     | Yes                | Yes            | Build and register delegate; switch in viewer.     |
| **Omniverse RTX** | Real-time + path trace | Yes (path trace) | Yes (RTX)   | Separate/embedded Omniverse viewer or stream.      |

---

## 7. Practical Next Steps for Dedaverse

- **Keep current stack, add optional “quality” backend:**  
  If you stay on Usdviewq/Hydra, add **renderer selection** in the UI (e.g. Storm vs Prman vs Arnold) and document that production quality (DOF, motion blur) requires installing RenderMan or Arnold and the corresponding Hydra plugin. No change to “remove usdview” — this is an extension of the existing path.

- **After removing Usdviewq (custom viewport):**  
  If you replace StageView with a **custom viewport** (see VIEWER_USDVIEW_TO_RUST_REPORT.md), you can still target **Hydra** by using `UsdImagingGLEngine` (or equivalent) with a **configurable delegate** (Storm, or Prman/Arnold/MoonRay if available). That preserves the option to “leverage higher quality graphics cards” via HdPrman/HdArnold/Omniverse without reimplementing DOF/motion blur yourself.

- **Omniverse as the “premium” viewer:**  
  For “best quality on RTX” without maintaining a full production delegate in-tree, consider offering **Omniverse USD View** (or a custom Kit app) as the recommended high-quality viewer and document “open in Omniverse for DOF/motion blur / path tracing”; Dedaverse would focus on asset/project UX and a fast built-in viewport (Storm or minimal), with Omniverse as the upgrade path.

---

*This document is intended for planning. Availability and APIs of Hydra delegates and Omniverse should be verified against current vendor documentation and OpenUSD release notes.*
