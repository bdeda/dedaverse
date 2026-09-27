# 1. Visual Development

Visual development ("visdev") defines *what the project looks and feels like* before large-scale production
begins. Its outputs are the reference materials every downstream artist works against:

- **Concept art** for individual characters, props, vehicles, creatures, and environments.
- **Asset art bibles** — the complete visual specification of a single asset.
- **The project Visual Bible** — the visual language, tone, and rules for the entire project.

These are not one-time deliverables. They are living documents that start small, are published early, and
grow as the production produces and approves new work.

---

## 1.1 Concept development for an asset

Concept development moves from broad exploration to a single, fully specified design.

### Phase A — Brief and research

- **Design brief.** Written by the art director or production designer with story/game design: role of the asset
  in the story or gameplay, personality, age, history, function, constraints (budget tier, screen time,
  camera distance, platform limits for games).
- **Reference gathering.** Mood boards of real-world photography, film stills, historical and cultural sources,
  materials, anatomy, and mechanical reference. Every reference image is tagged with *why* it was chosen
  ("silhouette", "surface wear", "color of the cloth", "attitude").

### Phase B — Exploration

- **Thumbnails and silhouettes.** Dozens of small, fast, black-fill silhouettes to find readable, distinctive
  shapes. Silhouette readability is tested at the smallest size the asset will appear on screen.
- **Shape language exploration.** Variations that push the design toward the project's shape vocabulary
  (see [1.3](#13-the-project-visual-bible)).
- **Color and value studies.** Small color comps testing the palette in the lighting conditions the asset will
  actually appear in, not just on a neutral background.

### Phase C — Refinement

- **Selected direction** is painted at higher fidelity: front and three-quarter views, key costume/material
  callouts, scale against a human reference figure.
- **Expression and pose sheets** (characters/creatures) establish personality: default stance, attitude poses,
  and a first pass of facial expressions.
- **Design review.** The art director, director (film) or creative director (game), and relevant leads review
  against the brief. Changes are cheapest here; the design should be *locked* before 3D begins.

### Phase D — Production-ready specification

Once approved, the concept is expanded into the asset's art bible (below) so a 3D artist who never attended a
review can build the asset faithfully.

---

## 1.2 The asset art bible

An asset art bible is the single source of truth for how one asset looks and behaves. A typical character art
bible contains:

| Section | Contents |
|---------|----------|
| **Overview** | Name, role, personality summary, key design intent in one or two sentences. |
| **Turnarounds** | Orthographic front, side, back, and three-quarter views in a neutral pose (A-pose or T-pose for characters) at a consistent scale. See [Asset Construction §2.1](02_ASSET_CONSTRUCTION.md#21-turnarounds-and-orthographic-reference). |
| **Proportion sheet** | Height, head-count proportions, scale relative to other characters and to set pieces. |
| **Callouts** | Close-up detail of hands, face, hair, props, costume construction (seams, fasteners, layering), material breakdown. |
| **Material and color key** | Swatches with named materials from the project material library, color values, roughness/sheen intent, wear and aging notes. |
| **Expression sheet** | Key facial expressions and mouth shapes that define the character's personality. |
| **Pose and attitude sheet** | Signature body poses and gestures; how the character stands, walks, and reacts. |
| **Deformation intent** | Notes on how cloth, armor, hair, and soft tissue should behave in motion (feeds [Rigging](03_RIGGING_AND_DEFORMATION.md)). |
| **Variants and states** | Damaged/clean, costume changes, age variations, LODs or distance versions. |
| **Do / Don't** | Explicit examples of off-model interpretations to avoid. |
| **Revision history** | What changed, when, and who approved it. |

Props and environments use the same structure with appropriate sections (e.g. environments add plan/elevation
views, set dressing lists, and light-source placement; props add scale, function, and interaction points).

The art bible is updated as the asset progresses: approved 3D renders, final material callouts, and rig pose
tests are appended so the bible reflects the asset *as built*, not just as imagined.

---

## 1.3 The project Visual Bible

Where an art bible describes a single asset, the **Visual Bible** describes the rules that bind every asset and
shot together. It is authored by the production designer / art director with the director (film) or creative
director (game), and approved before full production.

### Core sections

1. **Vision statement.** A short paragraph describing the emotional experience the audience should have, and
   the key visual ideas that support it.
2. **Tone and mood.** The emotional range of the project, often mapped across the story arc or game
   progression ("hopeful and warm in act one, isolated and cold in act two"). Illustrated with color scripts and
   key frames.
3. **Shape language.** The vocabulary of forms (e.g. rounded/soft for safety and friendliness, angular/sharp for
   danger, rectangular/stable for authority) and how it applies to characters, architecture, and props.
4. **Color language.** Master palette, per-location and per-faction palettes, the meaning assigned to specific
   hues, saturation and value ranges, and rules for accent colors.
5. **Color script.** A sequence of small key frames across the whole story or game showing how color and value
   shift with the narrative.
6. **Value and contrast.** Value structure rules (e.g. characters always read against backgrounds by value
   first, color second), acceptable black and white points.
7. **Lighting language.** How light is used to express mood — key-to-fill ratios, color temperature, hard vs.
   soft light, motivated sources, time-of-day treatments, and signature lighting setups for key moments. This
   becomes the reference the lighting department replicates in 3D (see
   [Lighting](06_VFX_LIGHTING_AUDIO.md#62-lighting)).
8. **Material and surface language.** Level of realism vs. stylization, texture density, how wear and grime are
   depicted, edge treatment, specular response. Links to the project material library
   ([Asset Construction §2.6](02_ASSET_CONSTRUCTION.md#26-the-project-material-library)).
9. **Detail and fidelity rules.** How much detail at what screen size/camera distance; where to spend detail and
   where to simplify.
10. **Camera and composition language.** Lens choices, framing conventions, camera movement style, aspect
    ratio (film), or camera behavior and field of view (games).
11. **Effects language.** How fire, smoke, water, magic, destruction, etc. should look — stylized vs. realistic,
    shape and timing of effects (see [VFX](06_VFX_LIGHTING_AUDIO.md#61-visual-effects-vfx)).
12. **Graphic and typographic design.** Titles, UI (games), signage, in-world text.
13. **Reference library.** Curated external reference (films, photographers, painters) with notes on *what* to
    take from each.
14. **Approved exemplars.** The best in-project work, added as it is approved (see below).

---

## 1.4 Making reference available to the team

Reference only steers the project if artists can find the current version quickly while they work.

- **Single, versioned location.** Concept art, art bibles, the Visual Bible, color scripts, and lighting keys are
  stored in the project alongside production assets and versioned the same way. In Dedaverse this means
  keeping them in reference collections (e.g. `Reference/VisualBible`, `Reference/Characters/<name>`) so they
  appear in the asset browser and are versioned by the file manager plugin.
- **Linked from each asset.** Each production asset links to its art bible, and each shot links to its board,
  previz, and color-script key. An artist opening an asset should see its visual target without searching.
- **Clear approval state.** Every reference is marked *exploration*, *approved*, or *superseded*. Only approved
  material is used as a target; superseded material stays in history but is clearly marked.
- **Review-friendly formats.** Layered source files for editing (PSD, Krita, etc.), plus flattened images and
  PDFs for quick viewing, and turntables/videos where motion matters.
- **Side-by-side review.** Reviews place the reference next to the current work at the same angle, framing, and
  lighting. Annotations are captured on the frame and kept with the version being reviewed.
- **Announce changes.** When the Visual Bible or an art bible changes, the change is summarized and
  broadcast (task comments, notifications) to affected teams, with a list of assets or shots that may need
  updating.

---

## 1.5 How the bibles evolve during production

At the start of production, the Visual Bible is mostly painted concept and external reference. As the
production matures, it should increasingly be illustrated with *the project's own approved work*.

1. **Seed.** Initial visual bible from visdev: vision, palettes, shape language, lighting language, key frames.
2. **Prove.** First "hero" assets and a vertical slice (game) or test shots (film) are built. Their approved
   renders are added as exemplars — the first proof that the 2D intent survives translation into 3D.
3. **Expand.** Each newly approved asset adds its art bible to the library and, when it introduces something new
   (a new material type, a new faction, a new location), the Visual Bible gains a corresponding section or
   example.
4. **Refine.** When production discovers that a rule does not work in practice (a color reads poorly under a
   certain lighting setup, a material is too noisy at distance), the rule is amended and the change is
   communicated and versioned.
5. **Lock.** Late in production, the bible is locked to protect consistency; changes require explicit approval
   from the art director.

The result at the end of the project is a complete visual record of the production — valuable for sequels,
marketing, outsourcing partners, and onboarding new team members.

---

## 1.6 Skills involved

See [Roles and Art Skills](07_ROLES_AND_SKILLS.md) for detail. The primary disciplines are:

- Art Director / Production Designer
- Concept Artist (character, creature, environment, prop)
- Illustrator / Key Frame Artist
- Color Script Artist
- Visual Development Artist for lighting (often a lighting lead or key-frame painter)
- Graphic Designer (for typography, UI, and signage)
