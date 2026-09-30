# Production Role Skills

These skills define how AI agents operate as members of a Dedaverse production team. They implement the roles
described in [docs/pipeline/08_PROJECT_ROLES.md](../../docs/pipeline/08_PROJECT_ROLES.md).

- The **Director/Cinematographer is a human**. There is no Director skill. Every agent treats the Director as
  the final authority on story, tone, look, performance, and camera.
- The **Producer** agent orchestrates: it plans the work, assigns tasks to role agents, tracks status, and
  brings review packages and decisions to the Director.
- Every other role is an agent that loads the matching skill below.

| Skill | Role | Primary process doc |
|-------|------|---------------------|
| [`producer`](producer/SKILL.md) | Producer (orchestrator) | [08 Project Roles](../../docs/pipeline/08_PROJECT_ROLES.md) |
| [`narrative-designer`](narrative-designer/SKILL.md) | Narrative Designer | [05 Story, Editorial, Previz and Layout](../../docs/pipeline/05_STORY_EDITORIAL_PREVIZ_LAYOUT.md) |
| [`concept-artist`](concept-artist/SKILL.md) | Concept Artist | [01 Visual Development](../../docs/pipeline/01_VISUAL_DEVELOPMENT.md) |
| [`storyboard-artist`](storyboard-artist/SKILL.md) | Storyboard Artist | [05 Story, Editorial, Previz and Layout](../../docs/pipeline/05_STORY_EDITORIAL_PREVIZ_LAYOUT.md) |
| [`previz-artist`](previz-artist/SKILL.md) | Previz Artist (and layout) | [05 Story, Editorial, Previz and Layout](../../docs/pipeline/05_STORY_EDITORIAL_PREVIZ_LAYOUT.md) |
| [`modeller`](modeller/SKILL.md) | Modeller | [02 Asset Construction](../../docs/pipeline/02_ASSET_CONSTRUCTION.md) |
| [`surfacing-lookdev-artist`](surfacing-lookdev-artist/SKILL.md) | Surfacing/Lookdev Artist | [02 Asset Construction](../../docs/pipeline/02_ASSET_CONSTRUCTION.md) |
| [`rigger`](rigger/SKILL.md) | Rigger | [03 Rigging and Deformation](../../docs/pipeline/03_RIGGING_AND_DEFORMATION.md) |
| [`animator`](animator/SKILL.md) | Animator | [04 Animation](../../docs/pipeline/04_ANIMATION.md) |
| [`vfx-artist`](vfx-artist/SKILL.md) | VFX Artist | [06 VFX, Lighting and Audio](../../docs/pipeline/06_VFX_LIGHTING_AUDIO.md) |
| [`lighting-artist`](lighting-artist/SKILL.md) | Lighting Artist | [06 VFX, Lighting and Audio](../../docs/pipeline/06_VFX_LIGHTING_AUDIO.md) |
| [`audio-artist`](audio-artist/SKILL.md) | Audio Artist | [06 VFX, Lighting and Audio](../../docs/pipeline/06_VFX_LIGHTING_AUDIO.md) |
| [`editor`](editor/SKILL.md) | Editor | [05 Story, Editorial, Previz and Layout](../../docs/pipeline/05_STORY_EDITORIAL_PREVIZ_LAYOUT.md) |

Each skill lives in `.github/skills/<skill-name>/SKILL.md`, with YAML front matter (`name`, `description`)
followed by the operating instructions.

---

## Shared conventions (all role skills)

Every role skill follows these conventions. A skill may add to them but must not contradict them.

### 1. Rules of engagement

1. **The Director decides.** Never make or assume a creative decision that changes story, tone, look,
   performance, or camera language. Propose options and escalate through the Producer.
2. **Work only from approved targets.** Before starting, confirm the approved inputs listed in your skill exist.
   If one is missing or only in *exploration* state, stop and report the gap to the Producer.
3. **Stay in your lane.** Only create or modify the elements your role owns. Request changes to another
   role's work through the Producer.
4. **Never overwrite approved work.** Publish every change as a new version with a change note.
5. **Escalate early.** Report blockers, conflicting notes, and technical limits as soon as you find them, with a
   proposed resolution.
6. **Unit tests and tooling rules still apply.** When a task changes code in this repository, follow
   [AGENTS.md](../../AGENTS.md).

### 2. Where work lives in a Dedaverse project

Dedaverse stores asset content in directories that mirror the asset's USD prim path
(see [docs/ASSET_METADATA_DESIGN.md](../../docs/ASSET_METADATA_DESIGN.md)):

```
{project_root}/{prim path}/          e.g. {project_root}/Assets/Characters/Hero/
```

Within an asset's or shot's content directory, role skills use one subfolder per element:

| Element folder | Owner |
|----------------|-------|
| `story/` | Narrative Designer |
| `concept/` | Concept Artist |
| `boards/` | Storyboard Artist |
| `previz/`, `layout/` | Previz Artist |
| `model/` | Modeller |
| `textures/`, `lookdev/` | Surfacing/Lookdev Artist |
| `rig/` | Rigger |
| `anim/` | Animator |
| `fx/` | VFX Artist |
| `lighting/`, `comp/` | Lighting Artist |
| `audio/` | Audio Artist |
| `edit/` | Editor |
| `review/` | Any role (review packages) |

Project-wide material lives in dedicated collections, for example:

| Collection (prim path) | Contents |
|------------------------|----------|
| `/Reference/VisualBible` | The Visual Bible, color script, lighting language |
| `/Reference/MaterialLibrary` | Project material library |
| `/Reference/FXLibrary` | Reusable effects library |
| `/Story` | Scripts, beat sheets, character sheets, dialogue lists |
| `/Editorial` | The current cut, shot frame ranges, edit decision lists |
| `/Assets/...` | Characters, props, environments |
| `/Sequences/<SEQ>/<SHOT>` | Shots, e.g. `/Sequences/SQ010/SH0040` |

The element folders and collection names are the *default convention*. If the project's configuration or the
Producer specifies different names, use those.

### 3. Naming and versioning

- File names: `<entity>_<element>_<descriptor>_v###.<ext>`, e.g. `Hero_model_body_v003.usd`,
  `SH0040_anim_blocking_v002.mov`.
- Increment the version for every publish. Never reuse or overwrite a version number.
- Source files are versioned through the project's configured file manager plugin (e.g. Perforce or the local
  filesystem). Submit with a change note that states what changed and why.

### 4. Task status

Report status to the Producer using exactly these states (mirrored in the task manager, e.g. Jira, when
configured):

```
Assigned ─► In progress ─► Submitted for review ─► Approved ─► Published
                 ▲                  │
                 └──── Notes ◄──────┘
```

### 5. Review package

Every submission for review contains:

1. **Task reference** — asset or shot, element, task ID, version.
2. **Target** — the approved reference being matched (concept, board, pose target, color key, previz, ...).
3. **Side-by-side** — the current work next to the target from the same angle, framing, lighting, or timing.
4. **Change note** — what changed since the previous version and which notes it addresses.
   Confirm that cost records for this work are in the task ledger (§6).
5. **Options** (when a decision is needed) — 2–4 clearly labeled, distinct options with trade-offs and a
   recommendation.
6. **Open issues** — known problems, risks, and anything blocked.

Save the package to the entity's `review/` folder and send it to the Producer.

### 6. Cost recording

Every cost is recorded when it is incurred, in the project ledger defined in
[docs/pipeline/09_COST_TRACKING.md](../../docs/pipeline/09_COST_TRACKING.md). The Director relies on it to learn
what each asset cost to build.

- **Only work on a task.** Every task brief names your ledger file: `.dedaverse/cost-ledger/tasks/<task_id>.jsonl`.
  Only you write to it.
- **Record your model usage** (`agent_usage`) at the end of every work session and at every submission. Use the
  token counts the model runtime reports; do not estimate. If the runtime reports no usage, record an estimate
  with `measured: false`, `source: "estimate"`, and the method in `note`, and tell the Producer.
- **Record machine time** (`compute`) from the job log for every render, simulation, bake, or solve you run,
  including failed jobs.
- **Tag rework**: set `rework: true` with a `rework_reason` (`director-change`, `review-notes`, or `defect`)
  when you are redoing submitted work.
- **Never edit or delete a record.** Fix a mistake by appending a correction record.
- Director time and external spend are recorded by the Producer.

A submission without up-to-date cost records is incomplete and will be returned.

### 7. Blocker report

```
Blocker: <one line>
Task: <asset/shot, element, task ID>
Missing / conflicting: <input or note>
Impact: <what cannot proceed; downstream roles affected>
Proposed resolution: <what you recommend, and who must act>
```
