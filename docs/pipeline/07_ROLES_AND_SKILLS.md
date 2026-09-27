# 7. Roles and Art Skills

This document defines the art and technical-art skills needed at each step of the pipeline. Small teams will
combine many roles into one person; large productions split them further. The skills — not the job titles — are
what the project must cover.

---

## 7.1 Leadership and direction

| Role | Responsibilities | Key skills |
|------|------------------|------------|
| **Director** (film) / **Creative Director** (game) | Owns the overall creative vision; approves story, look, and performance. | Storytelling, visual communication, decision-making, giving actionable feedback. |
| **Art Director / Production Designer** | Owns the Visual Bible; approves concept, materials, and look. | Design, color theory, composition, art history and reference, team leadership, consistency review. |
| **Animation Supervisor** | Owns performance quality and animation style. | Acting, animation principles, directing animators and actors. |
| **VFX Supervisor** | Owns effects look and technical approach. | Physics intuition, simulation, compositing, technical planning. |
| **Look-Dev / Lighting Lead** | Owns the material library and the lighting language in 3D. | Physically based rendering, color science, photography and cinematography. |

---

## 7.2 Visual development

### Concept Artist (character, creature, environment, prop)
- Drawing and painting, anatomy, perspective, and mechanical construction.
- Shape language, silhouette design, and color and value theory.
- Rapid ideation (thumbnails), plus rendering a design to finished quality.
- Research and reference gathering; designing to a brief and to production constraints.
- Tools: Photoshop, Krita, Procreate; 3D blockouts in Blender or ZBrush for paint-overs.

### Illustrator / Key Frame Artist
- Painting full scenes that establish mood, lighting, and composition for key story moments.
- Strong understanding of light, atmosphere, and cinematic composition.

### Color Script Artist
- Color and value storytelling across a whole sequence or film.
- Simplifying scenes to their essential color and light relationships.

### Turnaround Artist
- Precise orthographic drawing and proportion consistency across views.
- Understanding of 3D form, often using 3D blockouts to assist.

### Graphic Designer
- Typography, logo and signage design, UI design (games), and in-world graphics.

---

## 7.3 Asset construction

### 3D Modeler (organic and hard-surface)
- Reading orthographic and perspective reference accurately.
- Polygon modeling, proportions, and scale.
- Hard-surface techniques (bevels, booleans, subdivision control) or organic anatomy.
- Tools: Maya, Blender, 3ds Max, Houdini.

### Digital Sculptor
- Anatomy (human and animal), fabric behavior, and surface detail.
- Sculpting at multiple levels of detail; sculpting corrective and facial shapes for rigging.
- Tools: ZBrush, Blender, Mudbox.

### Topology / Retopology Artist
- Edge-flow for deformation, polygon budgeting, and LOD creation.

### UV Artist
- Seam placement, distortion minimization, texel-density management, UDIM and atlas layout.

### Texture / Surfacing Artist
- Painting physically based textures; understanding of how real materials age and wear.
- Baking maps and using masks, generators, and smart materials.
- Color accuracy against the Visual Bible.
- Tools: Substance Painter, Substance Designer, Mari, Photoshop.

### Look-Development / Shader Artist
- Shader networks (MaterialX, OpenPBR, USD Preview Surface, engine materials).
- Specialized shading: skin, eyes, hair, glass, cloth.
- Building and governing the material library; standard look-dev lighting.
- Rendering (Arnold, RenderMan, Karma, Cycles, engine renderers).

### Groom Artist
- Hair and fur creation, styling, and shading; simulation setup with CFX.

---

## 7.4 Rigging and deformation

### Character TD / Rigger
- Anatomy and joint mechanics.
- Skeleton placement and orientation, skin weight painting, corrective shapes.
- Control-rig design for animators; scripting (Python, MEL) for automation.
- Engine and renderer constraints (joint limits, influences per vertex).

### Facial Rigger / Facial TD
- Facial anatomy and FACS.
- Blend-shape and joint-based facial systems; phoneme/viseme design including tongue and teeth.
- Evaluating readability of expressions and speech.

### Creature / Deformation / CFX TD
- Muscle, skin sliding, and jiggle systems.
- Cloth and hair simulation setup and shot simulation.

### Paint-over Artist (pose targets)
- Painting over 3D renders to define target deformations and expressions.

---

## 7.5 Animation

### Character Animator
- The principles of animation (timing, spacing, arcs, weight, anticipation, follow-through, overlap).
- Acting and performance; recording and interpreting video reference.
- Posing for camera and silhouette.
- Tools: Maya, Blender, MotionBuilder.

### Facial Animator
- Lip-sync, eye animation, and subtle emotion.
- Working from audio and facial capture data.

### Motion Capture Technician / Solver
- Operating capture systems, calibration, marker/suit setup, and solving.

### Mocap Cleanup and Retargeting Artist
- Cleaning noise and contact issues; retargeting between different proportions.
- Layering hand-keyed animation over capture data.

### Gameplay Animator / Animation Technical Artist (games)
- Cycles and blend-friendly clips; state machines, blend trees, root motion, and IK.

### Performance / Voice Actor
- Physical and vocal performance that becomes the basis for animation.

---

## 7.6 Story, editorial, previz and layout

### Story / Storyboard Artist
- Fast, clear drawing; visual storytelling; cinematic grammar (shot sizes, screen direction, continuity).
- Staging and acting in drawings; iterating quickly on notes.

### Editor
- Pacing, rhythm, shot selection, and continuity.
- Cutting with scratch audio and temp music; managing the evolving cut.
- Tools: Avid, Premiere, DaVinci Resolve.

### Previz Artist
- Fast 3D staging and animation; camera and lens knowledge.
- Communicating intent with rough assets.

### Layout Artist
- Cinematography: camera placement, lens selection, and camera animation.
- Scene assembly with published assets; continuity across shots.

### Set Dresser
- Composing environments for camera; understanding of the world's design language.

---

## 7.7 VFX, lighting and compositing

### FX Artist / FX TD
- Physics-based simulation (fluids, pyro, rigid bodies, particles, cloth, crowds).
- Procedural workflows and scripting (VEX, Python).
- Artistic timing and shape design of effects.
- Tools: Houdini, EmberGen.

### Real-time VFX Artist (games)
- Particle systems and effect shaders in engine.
- Flipbook and texture authoring outside the engine.
- Performance optimization.

### Lighting Artist / Lighting TD
- Photography and cinematography lighting principles.
- Color theory and color management.
- Render optimization and AOVs; in-engine lighting (baked and dynamic) for games.

### Compositor
- Integrating render passes, FX, and plates; keying, roto, and color.
- Tools: Nuke, Fusion, After Effects.

### Colorist
- Final color grade matching the color script across the whole film.

---

## 7.8 Audio

- **Voice Director** — directing actors to the intended performance.
- **Dialogue Editor** — selecting and editing takes, syncing to picture.
- **Sound Designer** — designing and layering effects and ambiences.
- **Foley Artist** — performing synchronized everyday sounds.
- **Composer / Music Editor** — score composition and fitting music to picture or game state.
- **Re-recording Mixer / Audio Implementer** — final mix (film) or middleware/engine implementation (games).

---

## 7.9 Pipeline step × skill matrix

**P** = primary owner, **S** = supporting / reviewing.

| Pipeline step | Art Dir | Concept | Story | Editor | Previz/Layout | Modeler/Sculptor | Texture/Look-dev | Rigger/Facial TD | Animator | Mocap | FX | Lighting/Comp | Audio |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Concept & asset art bible | P | P | | | | S | S | S | S | | | | |
| Visual Bible & lighting language | P | P | S | | S | | S | | | | S | S | |
| Turnarounds | S | P | | | | S | | | | | | | |
| Modeling & sculpting | S | S | | | | P | | S | | | | | |
| UVs, texturing & materials | S | S | | | | S | P | | | | | S | |
| Material library | P | | | | | | P | | | | | S | |
| Pose targets & deformation | S | P | | | | S | | P | S | | | | |
| Facial rig, FACS, lip-sync tests | S | S | | | | S | | P | P | | | | S |
| Storyboards | S | S | P | S | | | | | | | | | S |
| Editorial cut | | | S | P | S | | | | | | | | S |
| Previz & layout | S | | S | S | P | | | | S | | | | |
| Performance definition | | | S | S | | | | | P | S | | | P |
| Blocking & refinement | | | | S | S | | | S | P | S | | | |
| Mocap (body & face) | | | | | | | | S | S | P | | | |
| VFX | S | S | | | | | | | | | P | S | S |
| Lighting & compositing | P | | | S | | | S | | | | S | P | |
| Dialogue, ambience & music | | | S | S | | | | | S | | | | P |
