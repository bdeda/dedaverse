# Production Pipeline Guide

This folder describes how a team builds a visual media project — a film, series, or game — from 2D concept art
through finished 3D shots or in-engine content. It is written for artists, leads, producers, and pipeline
engineers, and describes the *creative process* that Dedaverse is designed to support.

The documents are ordered roughly the way work flows through a production, but most phases overlap and loop
back on each other. The guiding idea across all of them is the same: **establish the artistic intent early,
make it visible to everyone, and verify every downstream step against it.**

## Documents

| # | Document | Covers |
|---|----------|--------|
| 1 | [Visual Development](01_VISUAL_DEVELOPMENT.md) | Concept development, per-asset art bibles, the project Visual Bible, the lighting language, and how reference material is published and grows over the project. |
| 2 | [Asset Construction](02_ASSET_CONSTRUCTION.md) | Turnarounds, modeling from 2D reference, modular part breakdown, UV layout, texturing, and the project material library. |
| 3 | [Rigging and Deformation](03_RIGGING_AND_DEFORMATION.md) | Body and facial skeletons, skinning, deformation targets, extreme poses, FACS, lip-sync and mood tests, iterative rig validation. |
| 4 | [Animation](04_ANIMATION.md) | Performance definition, blocking, refinement, motion capture (high-end and video-based), facial animation. |
| 5 | [Story, Editorial, Previz and Layout](05_STORY_EDITORIAL_PREVIZ_LAYOUT.md) | Storyboards, the editorial cut, previsualization, and shot layout for linear media. |
| 6 | [VFX, Lighting and Audio](06_VFX_LIGHTING_AUDIO.md) | Simulation and effects (offline and in-engine), shot lighting, dialogue, ambience and music. |
| 7 | [Roles and Art Skills](07_ROLES_AND_SKILLS.md) | The disciplines required at each step, the skills each needs, and a pipeline-step × skill matrix. |
| 8 | [Project Roles](08_PROJECT_ROLES.md) | High-level role definitions for a team with a human Director/Cinematographer and agent roles orchestrated by a Producer agent; review gates; how roles map to skills. |
| 9 | [Cost Tracking](09_COST_TRACKING.md) | The project cost ledger: what counts as cost, how each cost is recorded when it is incurred, rates, Jira mirroring, and how the Producer answers "what has this asset cost?" |
| 10 | [Tooling and Process Gaps](10_TOOLING_GAPS.md) | Review of the pipeline against the current codebase: what agents and the Director need to fetch inputs, produce deliverables, submit, and review each step; proposed tools and roadmap. |

## Pipeline at a glance

```
                     ┌──────────────────────────────────────────────────────────┐
                     │            VISUAL BIBLE  (living reference)              │
                     │  tone · mood · shape · color · lighting · materials      │
                     └───────▲───────────────────────┬──────────────────────────┘
          new approved work  │                       │  targets & constraints
          feeds back in      │                       ▼
 Story ─► Storyboards ─► Editorial cut ─► Previz ─► Layout ─► Shot animation ─► FX ─► Lighting ─► Comp/Final
   │                                                  ▲            ▲             ▲        ▲
   │                                                  │            │             │        │
 Concept ─► Asset art bible ─► Turnarounds ─► Model ─► UV ─► Texture/Material ─► Rig ─► Deformation tests
                                                                                   │
 Voice / performance capture ──────────────────────────────────────────────────────┘
```

For games, the story/editorial/previz column is replaced (or supplemented) by gameplay design, level blockout,
and in-engine cinematics, but the asset, rigging, animation, FX, lighting and audio phases follow the same
principles.

## Principles shared by every phase

1. **Intent before execution.** Every asset or shot starts with an approved visual target (concept, board, previz,
   pose sheet, lighting key). Work is reviewed *against that target*, not against personal taste.
2. **Small, reviewable pieces.** Assets are split into parts, shots into passes, performances into beats. Small
   pieces get higher fidelity and faster, cheaper iteration.
3. **Compare side by side.** Reviews place the reference (concept, pose target, video reference, lighting key)
   next to the current render from the same angle and framing.
4. **Lock decisions at the right time.** Changes are cheap early (concept, boards, performance planning) and
   expensive late (final animation, simulation, lighting). Each document calls out where decisions should be
   locked.
5. **Publish, version, and link.** Every approved deliverable is versioned and linked to the asset or shot it
   belongs to, so any artist can find the current target and the history behind it.

## How Dedaverse fits in

Dedaverse organizes a project as a hierarchy of collections and assets (see
[ASSET_METADATA_DESIGN.md](../ASSET_METADATA_DESIGN.md)). The processes in this guide map onto that structure:

- Reference material (concepts, art bibles, the Visual Bible, lighting keys) can be tracked as assets or
  elements in their own collections so they are versioned and discoverable like any production file.
- Production assets (characters, props, environments) and shots (sequences, shots) are collections/assets whose
  elements — model, textures, rig, animation, FX, lighting — are versioned through the configured file manager
  plugin (e.g. Perforce or local filesystem) and tracked through the task manager plugin (e.g. Jira).
- DCC launcher plugins (Maya, Houdini, ZBrush, Substance, Photoshop, Blender, Godot, etc.) open the right
  application for each step.
- Tracking time per element (e.g. "the animation elements of character X") gives producers the per-phase cost
  data described in the [Project Brief](../PROJECT_BRIEF.md). The cost ledger that records it is defined in
  [Cost Tracking](09_COST_TRACKING.md).
