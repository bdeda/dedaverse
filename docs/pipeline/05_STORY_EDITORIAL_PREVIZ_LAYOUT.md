# 5. Story, Editorial, Previz and Layout

For linear media (films, series, trailers, in-game cinematics), the sequence of shots is designed before the
shots are produced. Each stage increases the fidelity of communication about the shot so every downstream
department can align with the artistic vision.

```
Script / story ─► Storyboards ─► Story reel (editorial cut) ─► Previz ─► Layout ─► Shot production
      ▲                 │                  │                     │          │
      └──── story revisions ◄──────────────┴─────────────────────┘          │
                                             editorial updates timing ◄─────┘ (continuously)
```

---

## 5.1 Storyboards

Storyboarding is an **iterative process alongside story development**. Boards are drawn, cut together, reviewed,
and redrawn as the story changes.

Storyboards establish:

- **The sequence of shots**, their order, and the story beat each one serves.
- **Mood** of each moment, often with value or color notes tied to the color script.
- **Action** — what characters do, key poses and acting beats.
- **Cuts and transitions** — hard cuts, match cuts, dissolves, and the editorial style of the sequence.
- **Broad camera movement** — pans, tilts, dollies, cranes, handheld feel, zooms, indicated with arrows and
  framing boxes.
- **Composition and staging** — screen direction, eyelines, foreground/background relationships.
- **Design notes** — sound cues, dialogue, FX moments, lighting ideas, and anything downstream teams must know.

Boards are numbered by sequence and shot (e.g. `SQ010_SH0040`) and these identifiers become the shot
collections and assets tracked in Dedaverse.

---

## 5.2 Editorial

The editorial department is involved from the storyboard phase until final delivery.

- **Story reel / animatic.** Editorial cuts storyboards together with scratch dialogue, temporary music, and
  sound effects to establish pacing and running time. This is the first watchable version of the film.
- **Iteration with story.** Every board revision is cut in, and the reel is re-screened. The reel is the primary
  tool for evaluating story changes.
- **Shot timing as the contract.** The cut defines each shot's frame range. Previz, layout, and animation work to
  these ranges (plus handles).
- **Progressive replacement.** As production produces previz, layout, animation, and final renders, editorial
  swaps them into the cut, so the film progressively gains fidelity.
- **Minor timing adjustments.** Editorial typically makes small adjustments to shot lengths as rendered shots
  arrive. Larger changes are coordinated with production because they affect animation and FX ranges.

---

## 5.3 Previsualization (previz)

Previz takes the storyboards and adds detail by staging the shot in 3D space.

- **3D staging** of characters, props, and sets using simple proxy geometry or early blockouts at correct scale.
- **Camera design** with real lenses, heights, and more granular camera animation than the boards can express.
- **Blocking** of character movement and timing with simple animation.
- **Spatial continuity** — checking that screen direction, eyelines, and geography work across cuts.
- **Technical planning** — identifying shots that need complex FX, crowds, set extensions, or special rigs.

Previz is iterative: each pass improves the fidelity of communication about the shot. Previz renders replace
boards in the editorial cut, and **animators use the previz as reference when doing shot work**.

---

## 5.4 Layout

Layout turns the approved previz into a production-ready shot scene.

- **Stub in assets.** The shot scene references the current published versions of characters, props, and sets
  (proxies if final assets are not ready). The shot's asset list is recorded so updates propagate
  automatically.
- **Author cameras.** Final camera placement, lens, and animation are authored to the edit's frame range.
- **Rough blocking.** Characters are placed and roughly animated following the previz, giving animators a
  starting point with correct staging.
- **Set dressing** as needed for the camera view.
- **Continuity checks** across neighboring shots.

Layout output is published per shot and becomes the starting point for animation, FX, and lighting. In
Dedaverse, sequences and shots are collections/assets, and the shot's layout, animation, FX, and lighting
elements are versioned independently beneath each shot.

---

## 5.5 Games-specific notes

- Gameplay equivalents: level design blockouts (greybox), gameplay camera design, and encounter layouts serve
  the role of previz and layout.
- In-engine cinematics follow the full storyboard → editorial → previz → layout process, often authored
  directly in the engine's sequencer.

---

## 5.6 Skills involved

- Director / Story Supervisor
- Story Artist / Storyboard Artist
- Editor and Assistant Editor
- Previz Artist / Previz Supervisor
- Layout Artist (camera and staging)
- Set Dresser
- Cinematographer / Director of Photography (camera language)

See [Roles and Art Skills](07_ROLES_AND_SKILLS.md).
