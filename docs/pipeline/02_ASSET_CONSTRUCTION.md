# 2. Asset Construction (3D)

This document describes how an approved 2D design becomes a finished 3D asset: turnarounds, modeling,
UV layout, texturing, and material/shader setup. It also covers how a project-wide material library keeps
every asset aligned with the [Visual Bible](01_VISUAL_DEVELOPMENT.md#13-the-project-visual-bible).

```
Approved concept / art bible
        │
        ▼
Turnarounds & orthographic reference ─► Part breakdown ─► Blockout ─► High-res sculpt ─► Retopology
                                                                                            │
        ┌───────────────────────────────────────────────────────────────────────────────────┘
        ▼
    UV layout ─► Baking ─► Texture painting ─► Material & shader setup ─► Look-dev review ─► Publish
```

---

## 2.1 Turnarounds and orthographic reference

The modeler needs consistent, scaled views of the asset from multiple angles. Ideally these come from the
concept stage as part of the [art bible](01_VISUAL_DEVELOPMENT.md#12-the-asset-art-bible). When they do not
exist, they are produced before modeling begins.

### Required views

- **Orthographic:** front, back, left, right, top (and bottom where relevant, e.g. vehicles, shoes).
- **Perspective:** three-quarter front and three-quarter back, which reveal form that orthographic views hide.
- **Detail callouts:** head/face (front and profile), hands, feet, props, and any complex construction.
- **Neutral pose:** characters are drawn in the rig-friendly pose the project uses (A-pose or T-pose), with
  fingers slightly spread and a neutral facial expression.

### Producing turnarounds when concept provides only one view

1. **Painted turnaround.** A concept or turnaround artist paints the missing views using horizontal
   guide lines for key landmarks (eye line, chin, shoulders, waist, knees) so all views align.
2. **3D-assisted turnaround.** A quick blockout or sculpt is rendered from fixed orthographic and perspective
   cameras, then painted over to match the concept. This guarantees proportional consistency between views.
3. **Generated turnarounds.** Image-generation or multi-view synthesis tools can propose missing angles from a
   single concept. These are treated as *drafts*: they are painted over and approved by the concept artist or
   art director before use, because they frequently drift in proportion and detail.

### Rendering turnaround images

When a 3D blockout is used, render turnarounds with a standard **turnaround rig** so every asset is presented
the same way:

- Orthographic cameras for the six axis views plus perspective cameras at 45° increments around the asset,
  at a consistent height and focal length.
- A neutral, even lighting setup (and optionally the project's standard look-dev light rig).
- A neutral grey background, a scale reference figure, and a ground grid.
- Consistent resolution and naming (e.g. `<asset>_turn_front_v###.png`) so images can be compared across
  versions.

These images are the input to modeling and are kept with the asset so later reviews can compare the 3D model
against them from matching angles.

---

## 2.2 Part breakdown: build in smaller pieces

Assets are built as **separate, well-defined parts** rather than as one monolithic mesh. For a character, a
typical breakdown is:

- Body (sometimes split: head, torso, arms, hands, legs)
- Eyes, teeth, tongue, inner mouth
- Hair, eyebrows, eyelashes
- Each clothing layer (undershirt, shirt, jacket, belt, trousers, boots)
- Accessories and props (jewelry, weapons, bags)

Benefits:

- **Fidelity.** Each part gets its own texel density budget and UV space, so small but important parts (face,
  hands, eyes) receive appropriate resolution.
- **Parallel work.** Multiple artists can work on different parts at the same time.
- **Reuse.** Boots, belts, and props can be shared across characters; environment pieces become modular kits.
- **Rigging and simulation.** Cloth, hair, and rigid accessories often need different deformation methods;
  separate parts make this possible.
- **Iteration.** Changing one part does not require re-publishing the whole asset.

Each part is tracked as an element of the asset so its status, owner, and version history are visible
independently.

---

## 2.3 Modeling

### Blockout

A low-detail proxy built directly against the turnarounds to establish proportions, silhouette, and scale in
the project's units. The blockout is reviewed with the concept overlaid from each orthographic camera before
any detail work begins. Blockouts are also published early so layout, rigging, and animation can start using a
stand-in.

### High-resolution sculpt

Sculpting (e.g. ZBrush, Blender) adds anatomy, fabric folds, surface detail, and wear. Detail level follows the
Visual Bible's fidelity rules — what detail is visible at the asset's expected camera distance.

### Retopology

The production mesh is rebuilt with clean, animation-friendly topology:

- Edge loops follow muscle flow and deformation areas (around the eyes, mouth, shoulders, elbows, knees, and
  fingers) so that rigging can deform the mesh cleanly.
- Polygon budgets per part, per LOD (games) or per camera distance (film).
- Quads preferred; triangles and n-gons only where they will not deform.
- Consistent scale, orientation, pivot, and naming conventions.

### Model review

The model is rendered from the same turnaround cameras as the reference and compared side by side. Silhouette,
proportions, and key landmarks must match the art bible before the model moves to UVs.

---

## 2.4 UV layout

- **Texel density.** A project-wide target texel density (e.g. pixels per meter at a given texture resolution)
  keeps surface detail consistent across assets. Hero areas (face, hands) may receive a deliberate higher
  density.
- **Seams** are placed where they are least visible and where the texture artist expects them (natural
  garment seams, hairlines, under arms).
- **Distortion** is minimized and checked with a checker map.
- **UDIMs or atlases.** Film assets commonly use multiple UDIM tiles per part; game assets pack parts into
  atlases or trim sheets within platform texture limits.
- **Mirroring/overlap** only where the design is truly symmetrical and unique detail is not needed.
- **Padding** sufficient for mipmapping (games) and texture filtering.

---

## 2.5 Baking, texture painting, and material setup

### Baking

Detail from the high-resolution sculpt is baked onto the production mesh: normal, displacement, ambient
occlusion, curvature, thickness, and position/ID maps. These drive both the look and smart-material masks in
texturing tools.

### Texture painting

Textures are painted (e.g. Substance Painter, Mari, Photoshop) using the **material library** as the starting
point, not from scratch:

1. Assign base library materials to each region using ID maps.
2. Layer the asset-specific story — wear, dirt, fading, damage, age — following the art bible's material and
   color key.
3. Hand-paint unique details (logos, patterns, tattoos, painted markings).
4. Validate values against the Visual Bible: base color stays within the approved albedo range, roughness
   ranges match the material library, accent colors are used per the color language.

Typical output channels (PBR metal/rough): base color, metallic, roughness, normal, height/displacement,
ambient occlusion, emissive, opacity, subsurface/transmission masks.

### Material and shader setup

- Textures are connected into the project's standard shaders (e.g. a USD Preview Surface / MaterialX / OpenPBR
  network for offline, or the engine's master materials for games).
- Parameters beyond textures — subsurface radius for skin, sheen for cloth, coat for car paint, anisotropy for
  hair and brushed metal — are tuned per the material library's presets.
- Specialized shading: eyes (cornea, iris, sclera, tear line), hair/fur, skin, and transparent materials each
  have dedicated shader templates.

### Look-development review

Assets are reviewed in the project's **standard look-dev environment**: a fixed set of lighting conditions
derived from the Visual Bible's lighting language (e.g. neutral studio, key daylight, key night/interior) with
color charts and chrome/grey reference spheres. The render is compared against the art bible's color and
material key. The asset should look correct under all standard lighting setups, not just one.

---

## 2.6 The project material library

A material library standardizes the look of the project and makes texturing faster and more consistent.

### What it contains

- **Base materials** — calibrated physically plausible starting points: skin types, fabrics (cotton, wool,
  leather, silk), metals (steel, brass, gold, painted metal), woods, stones, plastics, glass, organic surfaces.
- **Stylization presets** — the project's interpretation of each material according to the Visual Bible
  (exaggerated edge highlights, simplified noise, painterly color variation, etc.).
- **Wear and weathering layers** — dust, dirt, rust, scratches, edge wear, water staining, at the project's
  approved intensity ranges.
- **Tileable textures and trim sheets** for environments and hard-surface assets.
- **Shader templates** for complex surfaces (skin, eyes, hair, glass, water, emissive).
- **Reference renders** of each material on a standard shaderball under each look-dev lighting setup.

### How it is built up

1. **Seed.** Look-dev artists create an initial set from the Visual Bible's material language and the first hero
   assets' needs.
2. **Validate.** Each material is rendered on the shaderball under all standard lighting setups and approved by
   the art director.
3. **Harvest.** When an asset introduces a successful new material, it is generalized and added to the library,
   with its approval render.
4. **Version.** Materials are versioned; changes are communicated so assets that use a material can be updated
   or deliberately pinned to an older version.
5. **Govern.** A look-dev lead owns the library. Artists request new entries rather than creating one-off
   variations that fragment the look.

### Keeping textures aligned with the visual direction

- Use calibrated albedo/value ranges from the library, checked with value and color-picker tools.
- Review assets together in context (a character next to its environment) under the Visual Bible's key lighting
  setups, not only in isolation.
- Maintain consistent texel density and texture resolution so detail frequency is uniform across assets.
- Add approved asset renders back into the art bible and, where exemplary, the Visual Bible.

---

## 2.7 Publishing

A finished asset is published as a versioned set of elements (model per part, textures, materials, look-dev
renders, turntable). In Dedaverse, each element is versioned through the configured file manager and linked to
the asset's metadata so downstream departments (rigging, layout, lighting) always pick up the current approved
version. See [ASSET_METADATA_DESIGN.md](../ASSET_METADATA_DESIGN.md) for how asset content directories mirror the
asset hierarchy.

---

## 2.8 Skills involved

- Turnaround / Concept Artist
- 3D Modeler (organic and hard-surface)
- Digital Sculptor
- Retopology / Topology Artist
- UV Artist (often part of the modeler's role)
- Texture Artist / Surfacing Artist
- Look-Development Artist / Shader Artist
- Material Library Lead (often the look-dev lead)
- Groom Artist (hair and fur)

See [Roles and Art Skills](07_ROLES_AND_SKILLS.md).
