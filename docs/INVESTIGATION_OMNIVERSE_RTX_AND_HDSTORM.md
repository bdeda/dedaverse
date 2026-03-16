# Investigation: Omniverse RTX Source Availability and RTX via HdStorm or Custom Renderer

This document summarizes findings on: (1) whether **Omniverse RTX Renderer** source code is available, and (2) whether **RTX GPU functionality** can be leveraged through **HdStorm** or a **custom Hydra render delegate**.

---

## 1. Omniverse RTX Renderer — Source and Licensing

### 1.1 Is Source Available?

**No.** The Omniverse RTX Renderer is **proprietary** and **binary-only**.

- **Owner:** NVIDIA. The renderer is part of the Omniverse platform (Kit, USD View, Create, etc.).
- **Distribution:** Provided as compiled libraries/binaries under the **NVIDIA Omniverse License Agreement**. No public source release for the RTX Renderer core.
- **What *is* open or shared:**
  - **NVIDIA-Omniverse** on GitHub: many repos exist (e.g. kit-app-template, kit-project-template, PhysX, USD-related samples). These are **templates, samples, and companion code** for building Kit apps and extensions — not the RTX Renderer implementation.
  - **Kit SDK:** You get headers, docs, and a way to build extensions and apps that *use* the RTX viewport; the viewport/renderer implementation itself is not in the public repos.
- **Licenses:** Omniverse Renderer documentation states that NVIDIA and its licensors retain all IP; use, reproduction, or distribution without an express license is prohibited. Some bundled third-party components (e.g. gRPC) may be open source, but the RTX Renderer is not.

**Conclusion:** You cannot “take Omniverse RTX source” and embed or modify it in Dedaverse. You can only **use** the RTX Renderer by running Omniverse apps (e.g. USD View) or by building on top of the Omniverse stack (Kit + their binaries) under their license.

---

## 2. Leveraging RTX Through HdStorm

### 2.1 What HdStorm Is

- **HdStorm** is Pixar’s **real-time** Hydra render delegate shipped with OpenUSD.
- **Backends:** Wraps **HdSt** (Storm) and uses the **Hydra Graphics Interface (Hgi)** for:
  - **OpenGL** (original)
  - **Metal** (HgiMetal, macOS/iOS)
  - **Vulkan** (HgiVulkan, experimental from OpenUSD 24.08)
- **Rendering model:** **Rasterization**. Storm is designed for fast, interactive viewport rendering (draw calls, meshes, basic shading). It does **not** implement ray tracing, path tracing, DOF, or motion blur.

### 2.2 Does HdStorm Use RTX or Ray Tracing?

**No.** HdStorm does not use NVIDIA RTX (OptiX / RT Cores) or Vulkan ray tracing (VK_KHR_ray_tracing_pipeline). The Vulkan backend in OpenUSD is for **portability and performance of the same raster pipeline** (e.g. moving from OpenGL to Vulkan), not for adding ray tracing.

- There is no public code path in Storm that builds acceleration structures or runs ray-tracing pipelines.
- So you **cannot** “turn on RTX in HdStorm” or “enable RTX via Storm” without changing Storm itself.

### 2.3 Could HdStorm Be Extended to Use RTX?

**Theoretically possible, but not “leveraging through” in a small way.**

- **Option A — Fork/extend Storm:** Add a Vulkan ray tracing pass (VK_KHR_ray_tracing_pipeline) or an OptiX backend inside HdSt/HdStorm. That would mean:
  - Significant changes to Storm’s architecture (scene representation, materials, lighting).
  - Maintaining a fork of OpenUSD’s imaging stack.
  - Not something the OpenUSD project currently does upstream for Storm.
- **Option B — Hybrid:** Keep Storm for the main viewport and add a separate “quality” pass (e.g. a small path tracer) that runs on the side; that’s closer to a **custom delegate** than to “RTX through HdStorm.”

**Conclusion:** RTX GPU functionality is **not** available “through HdStorm” as shipped. Getting RTX-style ray tracing in a Hydra-based viewer means using a **different** render delegate (production delegate or custom), not configuring or lightly extending Storm.

---

## 3. Custom Renderer: Leveraging RTX via a Hydra Delegate

This is the **practical** way to use RTX-class hardware (or any GPU ray tracing) with USD/Hydra without Omniverse’s closed RTX Renderer.

### 3.1 How It Works

- **Hydra** is pluggable: the viewer (e.g. usdview, or a Dedaverse viewport using UsdImagingGLEngine) asks for a **render delegate** by plugin id.
- A **custom delegate** can:
  - Consume the same scene data (via the scene delegate / render index).
  - Render with **any** backend: OptiX (NVIDIA), DXR (DirectX Raytracing), or **Vulkan ray tracing** (VK_KHR_ray_tracing_pipeline), which is supported on NVIDIA RTX and other GPUs.

So you **can** leverage RTX (or Vulkan RT) by **implementing a custom Hydra render delegate** that drives one of these APIs.

### 3.2 Existing and Example Work

- **ExampleHydraRenderDelegate (parsaiej)**  
  - [GitHub](https://github.com/parsaiej/ExampleHydraRenderDelegate)  
  - “Dead-simple” Hydra render delegate; works in Houdini Solaris, OpenUSD USD View, and a standalone sample.  
  - Good **reference** for the plugin contract and integration; it does not implement ray tracing itself.

- **HydraVulkanRT (abau171)**  
  - [GitHub](https://github.com/abau171/hydravulkanrt)  
  - **Vulkan-based** Hydra render delegate **with ray tracing support** (Vulkan RT extensions).  
  - Shows that a **custom delegate** can use GPU ray tracing (Vulkan RT runs on RTX and other capable GPUs) and be used in Hydra-based viewports.

- **OpenUSD built-in examples**  
  - HdStorm, HdTiny, HdEmbree are reference delegates. HdEmbree is CPU ray tracing; it proves the pattern for a ray-tracing delegate, but not GPU.

### 3.3 What You Would Do for “RTX via Custom Renderer”

1. **Choose the GPU RT API:**
   - **Vulkan ray tracing** (VK_KHR_ray_tracing_pipeline): Cross-vendor, works on RTX and AMD; **HydraVulkanRT** is a proof of concept.
   - **OptiX:** NVIDIA-only, very capable on RTX; no public Hydra delegate using it, you’d write one.
   - **DXR:** Windows/DirectX 12; again, you’d implement a delegate that talks to DXR.

2. **Implement a Hydra render delegate** that:
   - Implements the delegate interface (or Hydra 2.0 `HdRenderer` if targeting newer USD).
   - Translates Hydra scene (meshes, materials, lights, camera) into your backend’s structures (e.g. BLAS/TLAS for Vulkan RT, OptiX geometries, etc.).
   - Renders with ray tracing (path tracing, shadows, reflections, optionally DOF/motion blur if you implement them).
   - Can be registered as a plugin and selected in the viewer (e.g. “Storm” vs “MyRTXDelegate”).

3. **Integration with Dedaverse:**  
   If the Dedaverse viewer continues to use **UsdImagingGLEngine** (or equivalent) and supports **renderer plugin selection**, then once your delegate is built and registered, users could select it and get RTX-backed (or Vulkan RT–backed) rendering without changing the rest of the app.

**Conclusion:** RTX (and similar GPU ray tracing) **can** be leveraged via a **custom Hydra render delegate** (e.g. Vulkan RT or OptiX). It is **not** available by “turning something on” in HdStorm; it requires a separate delegate implementation, as in HydraVulkanRT or a new OptiX/DXR-based delegate.

---

## 4. Summary Table

| Question | Answer |
|----------|--------|
| Is Omniverse RTX Renderer source available? | **No.** Proprietary, binary-only; no public source. |
| Can we use RTX “through” HdStorm? | **No.** Storm is rasterization-only; no RT in upstream Storm. |
| Can we leverage RTX with a custom renderer? | **Yes.** Implement a **custom Hydra render delegate** that uses Vulkan RT, OptiX, or DXR. |
| Existing open example for GPU RT in Hydra? | **HydraVulkanRT** (Vulkan ray tracing); works on RTX and other Vulkan-RT GPUs. |

---

## 5. Recommendations

- **Do not** plan on “using Omniverse RTX source” or “embedding Omniverse RTX” in Dedaverse; it is not available as source.
- **Do not** assume HdStorm can be “switched” to RTX; it would require a different or new delegate.
- **Do** consider a **custom Hydra render delegate** (Vulkan RT or OptiX) if the goal is RTX-class quality inside the current viewer architecture; **HydraVulkanRT** is a useful reference and starting point.
- **Do** consider **Omniverse as an external option**: run or embed Omniverse USD View (with their RTX Renderer) for high-quality preview when that fits the workflow and license, and keep Dedaverse’s built-in viewport as a fast Storm (or custom) delegate.

---

*Investigation based on public documentation, GitHub repositories, and OpenUSD/Hydra documentation as of 2025. NVIDIA and Pixar product details should be confirmed against current vendor materials.*
