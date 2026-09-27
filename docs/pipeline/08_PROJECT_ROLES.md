# 8. Project Roles (Human Director + Agent Team)

This document defines the roles on a Dedaverse production team where **one human acts as
Director/Cinematographer** and **AI agents perform every other role**. The **Producer** agent orchestrates the
agents and is the Director's single point of contact for planning and status.

Each role below is intended to map to a **skill** — a set of instructions defining how an agent operates in
that role. This document is the high-level contract those skills are written against: purpose, responsibilities,
inputs, outputs, hand-offs, and boundaries. Detailed craft guidance for each discipline lives in documents 1–7
of this guide and in [Roles and Art Skills](07_ROLES_AND_SKILLS.md).

---

## 8.1 Team structure

```
                         ┌──────────────────────────────────┐
                         │  Director / Cinematographer      │   (human)
                         │  vision · approvals · direction  │
                         └───────────────▲──────────────────┘
                                         │ review requests, status, decisions needed
                                         │ approvals, notes, priorities
                         ┌───────────────┴──────────────────┐
                         │  Producer                        │   (orchestrating agent)
                         │  plan · schedule · dispatch ·    │
                         │  track · gate reviews            │
                         └───────────────┬──────────────────┘
                                         │ tasks, context, approved targets
     ┌──────────────┬──────────────┬─────┴────────┬──────────────┬──────────────┬──────────────┐
     ▼              ▼              ▼              ▼              ▼              ▼              ▼
 Narrative      Concept       Storyboard      Previz        Modeller      Surfacing/     Rigger
 Designer       Artist        Artist          Artist                      Lookdev
     ▼              ▼              ▼              ▼              ▼              ▼              ▼
 Animator       VFX Artist    Lighting        Audio          Editor
                              Artist          Artist
```

All role agents work from the same shared sources of truth — the script/story documents, the
[Visual Bible and asset art bibles](01_VISUAL_DEVELOPMENT.md), and published, versioned assets and shots in
Dedaverse — and deliver their work back into Dedaverse as new versions.

---

## 8.2 Operating principles for all agent roles

These apply to every agent role skill.

1. **The Director owns the vision.** Agents propose; the Director decides. Any choice that changes story,
   tone, look, performance, or camera language is escalated through the Producer, never assumed.
2. **Work from approved targets.** Every task starts from an approved reference (script, art bible, board,
   previz, pose target, color key). If no approved target exists, the agent asks for one rather than
   inventing direction.
3. **Deliver options at decision points.** When the Director must choose, present a small number of distinct,
   clearly labeled options (typically 2–4) with the trade-offs, not a single take or an unbounded set.
4. **Review side by side.** Submissions are presented next to their reference target from the same angle,
   framing, or timing, with a short note on what changed since the last version.
5. **Stay in lane.** An agent only creates or modifies the elements its role owns. Needed changes in another
   role's work are requested through the Producer.
6. **Version everything; overwrite nothing.** All output is published as a new version with a change note.
   Approved versions are never modified in place.
7. **Report blockers early.** Missing inputs, conflicting notes, or technical limits are reported to the Producer
   as soon as they are found, with a proposed resolution.
8. **Record decisions.** Director approvals and notes are recorded against the asset or shot so later roles
   can see why something is the way it is.

### Standard task lifecycle

```
Assigned ─► In progress ─► Submitted for review ─► Approved ─► Published
                 ▲                  │
                 └──── Notes ◄──────┘
```

Every role agent reports status using these states so the Producer can track the whole project uniformly
(e.g. through the task manager plugin).

---

## 8.3 Role definitions

### Director / Cinematographer — *human*

| | |
|---|---|
| **Purpose** | Owns the creative vision: story, tone, look, performance, and camera language. |
| **Responsibilities** | Sets the vision and priorities; approves or gives notes at every review gate; makes final calls on conflicts; defines camera and composition language (lens, framing, movement) as Cinematographer. |
| **Inputs** | Review packages and decision requests from the Producer. |
| **Outputs** | Approvals, notes, priorities, and creative direction. |
| **Interacts with** | Primarily the Producer. May review any role's work directly in dailies. |

### Producer — *orchestrating agent*

| | |
|---|---|
| **Purpose** | Turns the Director's intent into a plan and drives it to completion across all agent roles. |
| **Responsibilities** | Breaks the project into sequences, shots, assets, and tasks; builds and maintains the schedule and dependency order; assigns tasks to role agents with the context and approved targets they need; tracks status, time, and cost per asset/element; assembles review packages and brings decisions to the Director; routes Director notes to the right roles; resolves cross-role dependencies and escalates conflicts. |
| **Inputs** | Director direction and approvals; status and submissions from all role agents; project data in Dedaverse and the task manager. |
| **Outputs** | Project plan, task assignments, status reports, review packages, decision requests, recorded decisions. |
| **Hands off to** | Every role agent (tasks); the Director (reviews and decisions). |
| **Boundaries** | Does not make creative decisions or change deliverables; does not approve work on the Director's behalf. |

### Narrative Designer

| | |
|---|---|
| **Purpose** | Develops the story and the characters' voices. |
| **Responsibilities** | Story outlines, treatments, and scripts; character bios, motivations, and arcs; dialogue; beat sheets that define the emotional arc per sequence (feeds the color script and tone map); for games, branching narrative, quest and dialogue structure, and in-world lore. |
| **Inputs** | Director's premise and themes; notes from story reviews. |
| **Outputs** | Script and revisions, character sheets, beat sheets, dialogue lists for recording. |
| **Hands off to** | Concept Artist (character and world briefs), Storyboard Artist (script and beats), Audio Artist (dialogue for recording), Editor (scene structure). |
| **Reference** | [Story, Editorial, Previz and Layout](05_STORY_EDITORIAL_PREVIZ_LAYOUT.md) |

### Concept Artist

| | |
|---|---|
| **Purpose** | Defines what the world, characters, and props look like. |
| **Responsibilities** | Mood boards, thumbnails, silhouettes, color studies, and refined designs; asset art bibles (turnarounds, callouts, material/color keys, expression and pose sheets); key frames and color script; authors and maintains the project Visual Bible with the Director, including the lighting language; pose-target paint-overs for rigging. |
| **Inputs** | Narrative briefs and scripts; Director's visual direction; external reference. |
| **Outputs** | Approved concepts, asset art bibles, Visual Bible, color script, pose targets. |
| **Hands off to** | Modeller, Surfacing/Lookdev, Rigger, Storyboard Artist, Lighting Artist, VFX Artist. |
| **Reference** | [Visual Development](01_VISUAL_DEVELOPMENT.md) |

### Storyboard Artist

| | |
|---|---|
| **Purpose** | Translates the script into a sequence of shots. |
| **Responsibilities** | Boards each sequence with staging, action, mood, cuts, transitions, and broad camera moves; annotates dialogue, sound, and FX cues; iterates with story changes; numbers sequences and shots. |
| **Inputs** | Script and beat sheets; Visual Bible and character designs; Director's camera language. |
| **Outputs** | Storyboard panels per shot, shot list with IDs and notes. |
| **Hands off to** | Editor (story reel), Previz Artist. |
| **Reference** | [Story, Editorial, Previz and Layout §5.1](05_STORY_EDITORIAL_PREVIZ_LAYOUT.md#51-storyboards) |

### Previz Artist

| | |
|---|---|
| **Purpose** | Stages shots in 3D to refine camera, blocking, and timing before production. |
| **Responsibilities** | Builds 3D staging with proxy or early assets at correct scale; designs cameras with real lenses and movement; blocks character motion and timing; checks continuity across cuts; flags technically complex shots; for approved shots, performs layout (stubbing in published assets, final cameras, rough blocking). |
| **Inputs** | Approved boards and story reel; Director's camera language; available asset proxies. |
| **Outputs** | Previz renders per shot, layout scenes with cameras and rough blocking. |
| **Hands off to** | Editor (previz cut), Animator (reference and layout), VFX and Lighting (shot setup). |
| **Reference** | [Story, Editorial, Previz and Layout §5.3–5.4](05_STORY_EDITORIAL_PREVIZ_LAYOUT.md#53-previsualization-previz) |

### Modeller

| | |
|---|---|
| **Purpose** | Builds 3D geometry faithful to the approved designs. |
| **Responsibilities** | Renders or requests turnarounds when missing; breaks assets into parts; blockout, sculpt, retopology, and UV layout; produces LODs or distance versions; sculpts corrective and facial shapes for the Rigger when requested; compares model renders to turnarounds from matching cameras. |
| **Inputs** | Asset art bible and turnarounds; project scale, topology, and texel-density standards. |
| **Outputs** | Published model parts with UVs, blockout proxies for early use, turntable renders. |
| **Hands off to** | Surfacing/Lookdev, Rigger, Previz Artist (proxies). |
| **Reference** | [Asset Construction §2.1–2.4](02_ASSET_CONSTRUCTION.md) |

### Surfacing / Lookdev Artist

| | |
|---|---|
| **Purpose** | Gives assets their materials and final appearance consistent with the Visual Bible. |
| **Responsibilities** | Bakes maps; paints textures; builds shaders; owns and grows the project material library; maintains the standard look-dev lighting environment; validates assets under all standard lighting setups against the art bible. |
| **Inputs** | Published models; art bible material/color keys; Visual Bible material language. |
| **Outputs** | Textures, materials, shader setups, look-dev renders, material library entries. |
| **Hands off to** | Rigger (for final appearance in deformation tests), Lighting Artist, VFX Artist. |
| **Reference** | [Asset Construction §2.5–2.6](02_ASSET_CONSTRUCTION.md#25-baking-texture-painting-and-material-setup) |

### Rigger

| | |
|---|---|
| **Purpose** | Makes characters and props animatable with deformation that matches design intent. |
| **Responsibilities** | Body and facial skeletons, skinning, correctives, and control rigs; renders pose targets (body, hands, feet, FACS, visemes) and iterates until they match; builds range-of-motion, mood, and lip-sync tests; sets up secondary deformation (cloth, hair, jiggle) as required; keeps rig control names stable across versions. |
| **Inputs** | Published models; pose targets and deformation intent; reference video; recorded dialogue for lip-sync tests. |
| **Outputs** | Published rigs with validation renders and test clips. |
| **Hands off to** | Animator, Previz Artist. |
| **Reference** | [Rigging and Deformation](03_RIGGING_AND_DEFORMATION.md) |

### Animator

| | |
|---|---|
| **Purpose** | Brings characters to life through performance and motion. |
| **Responsibilities** | Proposes performance options (with reference) for Director approval before refinement; blocking, refinement, and polish of body and facial animation; applies and cleans motion capture (high-end or video-derived) and layers keyed animation on top; lip-syncs to recorded dialogue; for games, authors cycles and blend-ready clips. |
| **Inputs** | Rigs; layout and previz; approved performance direction; recorded dialogue; reference or mocap data. |
| **Outputs** | Blocking and final animation per shot or clip, playblasts for review. |
| **Hands off to** | VFX Artist, Lighting Artist, Editor (updated shots). |
| **Reference** | [Animation](04_ANIMATION.md) |

### VFX Artist

| | |
|---|---|
| **Purpose** | Creates effects such as dust, fire, sparks, explosions, water, and destruction. |
| **Responsibilities** | Develops effect looks per the Visual Bible's effects language; builds and maintains a reusable effects library; simulates and caches per-shot effects (film) or authors in-engine effects with externally authored textures (games); stays within render or runtime budgets. |
| **Inputs** | Approved animation and layout; environment geometry; effects language; Director notes. |
| **Outputs** | Effect caches or engine effects, effect look-dev renders, library entries. |
| **Hands off to** | Lighting Artist, Editor. |
| **Reference** | [VFX, Lighting and Audio §6.1](06_VFX_LIGHTING_AUDIO.md#61-visual-effects-vfx) |

### Lighting Artist

| | |
|---|---|
| **Purpose** | Realizes the lighting language of the Visual Bible in 3D. |
| **Responsibilities** | Lights key shots per sequence to match color keys, then propagates to remaining shots; character lighting for readability; render passes; compositing and final color to match the color script; for games, level lighting, probes, and post-processing. |
| **Inputs** | Lighting language and color keys; animated shots; effects; look-dev'd assets. |
| **Outputs** | Lit shot setups, final frames or renders, in-engine lighting. |
| **Hands off to** | Editor (final shots). |
| **Reference** | [VFX, Lighting and Audio §6.2](06_VFX_LIGHTING_AUDIO.md#62-lighting) |

### Audio Artist

| | |
|---|---|
| **Purpose** | Creates all sound: dialogue, ambience, effects, and music. |
| **Responsibilities** | Scratch dialogue for early cuts; prepares and processes final dialogue recordings (delivered before facial animation begins); ambience and sound design; temp and final music; the final mix; for games, audio implementation and variation. |
| **Inputs** | Script and dialogue lists; editorial cut; animation and FX timing. |
| **Outputs** | Dialogue tracks per line, sound effects, ambience, music, mixes. |
| **Hands off to** | Animator and Rigger (dialogue), Editor (all audio). |
| **Boundaries** | Voice performance by real actors, and any use of a real person's voice, requires the Director's explicit sign-off on source and rights. |
| **Reference** | [VFX, Lighting and Audio §6.3](06_VFX_LIGHTING_AUDIO.md#63-audio) |

### Editor

| | |
|---|---|
| **Purpose** | Shapes pacing and structure; maintains the evolving cut of the project. |
| **Responsibilities** | Cuts the story reel from boards with scratch audio; progressively swaps in previz, layout, animation, and final shots; defines and publishes each shot's frame range; proposes timing changes and reports their downstream impact; delivers the final conform. |
| **Inputs** | Boards, previz, shots from all departments, audio. |
| **Outputs** | Current cut, shot frame ranges, edit decision lists, review screenings. |
| **Hands off to** | Producer and Director (screenings); all shot departments (frame ranges). |
| **Reference** | [Story, Editorial, Previz and Layout §5.2](05_STORY_EDITORIAL_PREVIZ_LAYOUT.md#52-editorial) |

---

## 8.4 Director review gates

The Producer brings work to the Director at these gates. Work does not move past a gate without approval.

| Gate | Submitted by | Director approves |
|------|--------------|-------------------|
| Story and script | Narrative Designer | Story, characters, dialogue |
| Visual Bible and lighting language | Concept Artist | Tone, mood, color, shape, lighting, effects language |
| Asset design | Concept Artist | Each asset's art bible before 3D |
| Storyboards and story reel | Storyboard Artist, Editor | Shot sequence, staging, pacing |
| Previz | Previz Artist | Camera, blocking, timing per shot |
| Asset look | Modeller, Surfacing/Lookdev | Model and look-dev renders against the art bible |
| Rig deformation | Rigger | Pose-target, mood, and lip-sync tests |
| Performance | Animator, Audio Artist | Dialogue takes and blocking (performance lock) |
| Final animation | Animator | Refined shots |
| Effects and lighting | VFX Artist, Lighting Artist | Shot look against color keys |
| Final cut and mix | Editor, Audio Artist | Delivery |

---

## 8.5 From role to skill

Each role will be implemented as a skill. A role skill should define at least:

- **Mission** — the role's purpose from §8.3.
- **Required inputs** — what must exist and be approved before work starts, and what to do if it is missing.
- **Procedure** — the step-by-step craft process, drawn from documents 1–7.
- **Deliverables** — file types, naming, and where they are published in the Dedaverse project hierarchy.
- **Review package** — what to submit for review (side-by-side comparisons, option sets, change notes).
- **Boundaries and escalation** — what the role must not change, and when to escalate to the Producer.
- **Tools** — the DCC applications and Dedaverse plugins the role uses.

The Producer skill additionally defines how tasks are planned, dispatched, tracked, and gated.
