# 10. Tooling and Process Gaps

Documents 1–9 define **what** each pipeline step produces, **who** owns it, and **who approves** it. This document
reviews them against the current Dedaverse codebase and identifies where the **how** is missing. That covers how an
agent gets its inputs, how it produces a deliverable, how the deliverable is submitted, and how the Director reviews
it. It then proposes the tools and process definitions needed for the specialized agents to execute each step
effectively.

Everything in §10.3 onward is a **proposal**. Nothing in it exists yet unless stated.

**Summary.** The process is well defined at the level of responsibilities, hand-offs, and review gates. It is
under-defined at the level of execution. Most steps cannot be performed end-to-end by an agent today, because
Dedaverse has no way to store approval state, no way for an agent to resolve pinned inputs or submit work, no review
inbox for the Director, and no scriptable access to the DCC applications that produce the deliverables.

---

## 10.1 Current capability inventory

| Capability the pipeline docs assume | Current state | Where |
|---|---|---|
| Versioned file storage | Perforce file manager implemented (`add`, `rename`, `delete`, `get_latest`, `get_version`, `checkout`, `commit`). No local-filesystem file manager exists. | `src/deda/core/_plugin.py` (`FileManager`), `src/deda/plugins/perforce/` |
| Task tracking | `TaskManager` interface has only `get_task` and `update_task`. The Jira plugin is a stub. | `src/deda/core/_plugin.py`, `src/deda/plugins/jira/` |
| DCC execution | Maya, Houdini, ZBrush, Substance, and Photoshop plugins are stubs. No batch or headless execution, rendering, or playblasts. | `src/deda/plugins/*/` |
| Asset hierarchy and identity | Projects, collections, assets, sequences, shots, and elements exist. `AssetID` supports pinning with `#version` or `@changelist`. | `src/deda/core/types/` |
| Element metadata (status, owner, approved version) | Not implemented (`Element.metadata` is a `TODO`). | `src/deda/core/types/_element.py` |
| Director review | USD viewer with slate, camera reticle, and drawn annotations. Annotations save to `<asset rootdir>/notes/annotations_<timestamp>.json` with the camera transform and an optional description. | `src/deda/core/viewer/` |
| Command-line interface | `dedaverse run` and `dedaverse install` only. | `src/dedaverse/__main__.py` |
| Cost ledger | Documented process only; no API. | [09 Cost Tracking](09_COST_TRACKING.md) |

---

## 10.2 Inconsistencies in the current docs

These should be resolved regardless of tooling work:

1. **Local-filesystem file manager.** The pipeline README and shared skill conventions name "local filesystem" as a
   file manager option. Only Perforce is implemented.
2. **Two locations for review material.** The skills put review packages in `review/`. The viewer saves Director
   notes to `notes/`, which no skill reads. Agents would never see notes made in the viewer.
3. **Two versioning schemes.** File names carry `_v###` while Perforce keeps its own revisions. Pick one as
   authoritative. The natural choice is the file manager's revision, referenced as `AssetID#version` or
   `AssetID@changelist`, with `_v###` either dropped or kept only for exported review media.
4. **"Approved" has no home.** Every skill says to work only from approved inputs. No document or code defines
   where approval is stored or how an agent checks it.

---

## 10.3 Gap A — Status, approval, and publishing (foundation)

**Current.** Status and approvals exist only as prose and as task-manager states in a stub plugin. An agent cannot
ask "what is the approved version of this element?"

**Needed.** A stored, queryable state for each element.

Proposal:
- Implement `Element.metadata` (and the equivalent for assets and shots) with at least:
  - `status` (`assigned`, `in_progress`, `submitted`, `approved`, `published`, `notes`);
  - `owner_role` and `task_id`;
  - `latest_version`, `submitted_version`, and `approved_version` (as `AssetID#version` or `@changelist`);
  - `approved_by` and `approved_at`, plus a link to the review record.
- Store it in the entity's `.dedaverse` USDA (as custom data, consistent with
  [ASSET_METADATA_DESIGN.md](../ASSET_METADATA_DESIGN.md)) or in a sidecar record. Update that design document with
  whichever is chosen.
- Provide operations: `publish(element, files, note)`, `submit(element, version, review_package)`,
  `approve(element, version, notes)`, and `request_changes(element, version, notes)`. Approving is restricted to the
  Director.

**Unblocks.** Input resolution (B), review inbox (C), gates, dependency checks, and the Producer's status reporting.

---

## 10.4 Gap B — Agent tool interface (inputs, outputs, and reporting)

**Current.** The task brief is a text template in which the Producer hand-assembles paths. There is no
programmatic way for an agent to resolve inputs, publish, submit, read notes, or record costs. How the Producer
dispatches agents (spawning subagents, messaging long-running sessions, or a queue) is not defined.

**Needed.** One tool surface that every role agent uses, so the skills become executable instead of descriptive.

Proposal:
- A **Dedaverse MCP server** (preferred, since agents consume tools natively) and/or matching `dedaverse` CLI
  commands exposing:
  - `resolve_asset(name | asset_id)` → entity, content directory, elements;
  - `get_inputs(task_id)` → the pinned, approved input versions for the task, synced locally;
  - `get_task(task_id)` / `update_task_status(task_id, status)`;
  - `publish(...)`, `submit_for_review(...)` (from A);
  - `get_notes(task_id | element)` → Director notes addressed to the task (see C);
  - `record_cost(...)` → appends a validated ledger record ([09](09_COST_TRACKING.md));
  - `validate(element, version)` → runs the step's automated checks (see F).
- A **machine-readable task brief** (JSON or YAML) replacing the text template:

```yaml
task_id: KCIRC-142
role: rigger
entity: KCIRC:Assets:Characters:Hero::
element: rig
goal: Body and face rig hitting approved pose targets
inputs:                              # pinned; the agent refuses to start if any is not approved
  - KCIRC:Assets:Characters:Hero::model#12
  - KCIRC:Assets:Characters:Hero::concept/posetargets@48211
  - KCIRC:Assets:Characters:Hero::audio/HERO_SQ010_001#3
notes: [note-8812, note-8815]
deliverables:
  - element: rig
  - review: [pose_side_by_side, rom, moodtest, lipsync]
checks: [rig.joint_count, rig.influences_per_vertex, naming]
gate: rig_deformation
ledger: .dedaverse/cost-ledger/tasks/KCIRC-142.jsonl
```

- A **per-shot manifest** (the asset list recorded at layout) in the same form, so animation, FX, and lighting
  resolve the same pinned versions.
- A defined **dispatch model** for the Producer: how it starts a role agent with a brief, how it receives status,
  and where it keeps project state while no task manager is configured (see G).

---

## 10.5 Gap C — Director review

**Current.** The Director has no single place to see what is waiting for review, cannot compare work against its
reference side by side except in USD, and viewer annotations are not linked to a version or task.

**Needed.** A review workflow that takes minutes per item and produces notes an agent can act on.

Proposal:
- A **Review Inbox panel** in the Dedaverse app listing submissions by gate, oldest first, with the asset/shot,
  role, version, and a link to the review package. It is backed by the status data from A.
- A **side-by-side review view** that plays images, image sequences, and `.mov` files as well as USD. It needs
  A/B wipe, synchronized scrubbing, and version-to-version comparison. The existing slate and annotation overlays
  should work on every media type.
- **Approve / Request changes** actions that call the operations in A and record the decision.
- **Version-linked notes.** Extend the existing annotation JSON with `task_id`, `entity`, `element`, `version`,
  `frame`, `author`, and `status` (`open`/`addressed`/`closed`), stored where agents read them (resolving
  inconsistency 2). The Producer routes each note to the owning role; agents mark notes addressed in their next
  submission's change note.
- A **progress board** showing each asset and shot against its pipeline steps with status, time in status, and
  cost to date (from the ledger). This replaces text-only status reports as the Director's main overview.
- **Screenings in cut order** for sequences, using the editorial timeline (see D, Editor).

---

## 10.6 Gap D — Producing deliverables at each step

**Current.** The DCC plugins cannot run scripted work, and no generative tools are defined for the 2D and audio
roles. Several "standard" assets the docs depend on (turnaround rig, look-dev environment, pose-target cameras)
are described but do not exist.

**Needed.** Headless, scriptable execution per application, standard project rigs stored as assets, and defined
tools for 2D and audio generation.

### Shared infrastructure

- **Headless runners** per application plugin: `mayapy`, `hython`, Blender in background mode, the Substance
  automation toolkit, and an engine command line for games. Each runner takes a script and the pinned inputs, and
  returns output files, logs, and the job's compute time for the ledger.
- **Standard project rigs** stored under `/Reference/Rigs` and versioned: turnaround camera rig, look-dev lighting
  environment with shaderball and color charts, pose-target camera set, playblast/slate template.
- **Review media renderer**: turntables, slated playblasts, and side-by-side composites generated the same way for
  every role, so review packages are consistent.

### By step

| Step | What exists | Tool or process to define |
|---|---|---|
| Narrative | Text only; workable today. | Schemas for the beat sheet and dialogue list (line IDs, emotion, delivery) that Audio, Animation, and Editorial read. |
| Concept | Nothing. | An **image generation and editing tool** (generate, paint-over, inpaint, upscale); a **reference provenance record** (source, license, usage note) for every external image; turnaround-from-blockout using the turnaround rig. |
| Storyboard | Nothing. | The same image tool with panel templates; a shot-list schema; export in cut order for the Editor. |
| Previz / Layout | USD authoring in Python is possible. | Scripted scene assembly from the shot manifest; camera/lens authoring helpers; slated playblast via the review media renderer. |
| Modeller | Nothing. | Headless DCC runner; turnaround render from the standard rig; LOD generation; model checks (see F). |
| Surfacing / Lookdev | Nothing. | Scripted baking and texturing (e.g. Substance automation); the look-dev environment and material library as assets; value-range checks. |
| Rigger | Nothing. | Scripted skeleton and skinning tools; pose-target camera set; automated ROM, mood-test, and lip-sync renders. This is the hardest step to automate; expect more Director and human-expert involvement. |
| Animator | Nothing. | Scripted keying and playblast; mocap retargeting; **video-to-motion extraction** for body and face; lip-sync from dialogue audio. |
| VFX | Nothing. | Headless Houdini simulation and caching; engine effect profiling for games; the effects library as assets. |
| Lighting | Nothing. | Scripted lighting and render submission; **color-key comparison** (render vs. key, value and hue histograms); render budgets. |
| Audio | Nothing. | A voice source that satisfies the voice and rights rule; a dialogue-editing and mixing tool; loudness and format checks for delivery. |
| Editor | Nothing. | An editorial timeline in an open format (e.g. OpenTimelineIO) holding the cut, frame ranges, and version per shot; automatic replacement of each shot with its latest approved media; EDL export. |

---

## 10.7 Gap E — Render and compute execution

**Current.** No render submission or job tracking exists, yet `compute` cost records require job logs.

Proposal:
- A job runner abstraction (local first, render-farm plugin later) with job ID, resource type, start/end
  time, status, and log location.
- Every job writes its `compute` ledger record automatically, removing the dependency on agents recording it by
  hand.

---

## 10.8 Gap F — Automated acceptance checks

**Current.** Acceptance criteria in the skills are qualitative ("matches the art bible"), so every defect reaches the
Director.

Proposal: checks that run on `submit_for_review` and must pass (or be explicitly waived by the Producer with a
reason) before an item enters the Director's inbox.

| Area | Example checks |
|---|---|
| All | Naming convention; files published at the pinned versions; review package complete; cost records present since last submission. |
| Model | Polygon budget per part and LOD; non-manifold/n-gon report; scale and orientation; UV overlap; texel density within tolerance. |
| Surfacing | Texture resolution and channel set; albedo and roughness within library ranges; material names exist in the library. |
| Rig | Joint count and influences per vertex within engine limits; control names unchanged from the previous published rig; default pose unchanged. |
| Animation / FX / Lighting | Frame range matches the edit plus handles; camera matches the layout camera; render or cache complete for all frames. |
| Audio | Line IDs match the dialogue list; sample rate, format, and loudness to spec. |
| Editorial | Every shot in the cut resolves to a published version; frame ranges consistent with the published table. |

Creative judgement stays with the Director. The checks keep technical defects out of the review.

---

## 10.9 Gap G — Task management without Jira

**Current.** The Jira plugin is a stub, and the pipeline assumes a task manager for status, dispatch, and cost
mirroring.

Proposal: either implement the Jira plugin (`get_task`, `update_task`, worklogs, comments), or add a **local task
manager** plugin storing tasks as records in the project (alongside the cost ledger) so a production can run with
no external service. The Producer's state (plan, dependencies, assignments) lives there.

---

## 10.10 Roadmap

Ordered by dependency. Each item is a candidate issue or PR.

| # | Item | Depends on | Unblocks |
|---|---|---|---|
| 1 | Resolve the doc inconsistencies in §10.2 | — | Clear conventions for everything below |
| 2 | Element status, approval, and publish operations (Gap A) | — | 3, 4, 5, 8 |
| 3 | Agent tool interface: MCP server/CLI, structured task brief, shot manifest (Gap B) | 2 | Agents can resolve inputs and submit work |
| 4 | Review Inbox, side-by-side media review, version-linked notes (Gap C) | 2 | Director can review each step efficiently |
| 5 | Local task manager or Jira implementation (Gap G) | 2 | Producer state and dispatch without external services |
| 6 | Headless DCC runners, job runner, standard rigs, review media renderer (Gaps D, E) | 3 | 3D steps become executable by agents |
| 7 | Generative tools for concept, storyboard, and audio, with provenance and rights records (Gap D) | 3 | 2D and audio steps become executable by agents |
| 8 | Automated acceptance checks per step (Gap F) | 2, 3 | Fewer defects reach the Director |
| 9 | Cost ledger API writing records from the runtime and job runner automatically ([09](09_COST_TRACKING.md)) | 3, 6 | Accurate cost without relying on agents to self-report |

---

## 10.11 Decisions needed from the Director

1. **Tool surface**: MCP server, CLI, or both for the agent interface (item 3).
2. **Versioning authority**: file manager revisions (`AssetID#version`) vs. `_v###` file names (§10.2 item 3).
3. **Status storage**: `.dedaverse` USDA custom data vs. a sidecar record (item 2).
4. **Task manager**: implement Jira, add a local task manager, or both (item 5).
5. **First DCC targets**: which applications get headless runners first (e.g. Blender and Houdini for broad
   coverage, or Maya if it is the studio standard).
6. **Generative tool providers** for image and voice, subject to the rights rules in the Audio Artist and Concept
   Artist skills.
