# 4. Animation

Animation brings a character to life by authoring its behavior and movement. Animation follows a staged
process — performance definition, blocking, refinement, polish — and may use motion capture as a starting point
for both body and face.

```
Performance definition ─► Voice recording ─► Blocking ─► [Performance lock] ─► Refinement / mocap integration ─► Facial ─► Polish ─► Final
       ▲                        │                                                   ▲
       └──── reference video, previz, storyboards, direction ──────────────────────┘
```

---

## 4.1 Inputs

- **Approved rig** ([Rigging](03_RIGGING_AND_DEFORMATION.md)) with validated body and facial deformation.
- **Storyboards and previz** for linear media ([Story, Editorial, Previz and Layout](05_STORY_EDITORIAL_PREVIZ_LAYOUT.md)),
  or gameplay design specs and move lists for games.
- **Layout** (film): the shot's cameras, stubbed assets, and rough character blocking.
- **Recorded dialogue** ([Audio](06_VFX_LIGHTING_AUDIO.md#63-audio)) — required before facial animation.
- **Reference video**: actors or animators performing the action, shot by the animation team.
- **Character art bible**: attitude poses, expression sheet, and personality notes.

---

## 4.2 Performance definition (before animation begins)

Changes to mood, speed, timing, and overall acting are **difficult and expensive to make once animation is
underway**. The nuances of the performance should be worked out before the second (refinement) phase begins.

- **Acting brief** per shot or action: intent, emotional state, subtext, how the character's mood changes over
  the shot.
- **Reference performances**: the animator (or an actor) records video of the performance, often several
  options, and reviews them with the director or animation supervisor.
- **Voice performance**: when dialogue exists, the recording defines rhythm and emotional beats. The body
  performance may be adjusted to follow the voice actor's delivery.
- **Timing and pacing**: agreed with editorial (film) or design (games).
- **Approval**: the director / animation supervisor approves the performance direction.

---

## 4.3 Phase 1 — Blocking

Blocking establishes the performance with the minimum number of poses.

- **Key poses** that tell the story of the shot, in stepped (non-interpolated) playback.
- **Breakdowns** that define how the character moves between key poses (arcs, weight shifts).
- **Timing** of each pose relative to dialogue and the edit.
- **Camera-aware posing**: poses are designed for the shot camera, favoring clear silhouettes.

Blocking is reviewed for storytelling, acting choices, and timing. **This is the last inexpensive point to
change the performance.** When blocking is approved, the performance is considered locked.

---

## 4.4 Phase 2 — Refinement (and motion capture)

Refinement converts blocking into full motion:

- Spline interpolation, overlapping action, follow-through, and weight.
- Arcs, spacing, and contact points (feet, hands on props) are cleaned up.
- Poses are pushed to match the character's attitude sheet and the Visual Bible's stylization level.

### Motion capture

Mocap data may replace or supplement hand-keyed animation.

- **High-end optical or inertial capture.** Actors in suits perform on a capture stage. Data is solved to a
  skeleton, cleaned (marker swaps, jitter, foot sliding), and **retargeted** to the character rig.
- **Video-based capture.** Motion is extracted from ordinary video using pose-estimation tools, then
  retargeted. Lower cost and flexible (animators can capture their own reference), but typically requires more
  cleanup.
- **Integration.** Mocap is treated as a performance layer. Animators edit on top of it (layered animation) to
  fix contacts, push poses toward the character's stylization, adjust timing to the edit, and correct
  proportional differences between the actor and the character.

Mocap captures the actor's choices; if the performance direction was not locked before the shoot, re-shooting or
heavy editing is usually required.

---

## 4.5 Facial animation

Facial animation follows the same staged process and depends on final or near-final dialogue.

- **Facial capture**: head-mounted camera or video-based solving produces FACS or blend-shape curves from the
  actor's performance. Data is retargeted to the character's facial rig.
- **Hand-keyed / hybrid**: animators key visemes for lip-sync, then layer emotion (brows, eyes, cheeks), eye darts
  and blinks.
- **Lip-sync check**: mouth shapes, tongue, and teeth positions are reviewed against the viseme targets defined
  in [Rigging §3.2](03_RIGGING_AND_DEFORMATION.md#32-defining-pose-targets).
- **Eyes**: eye direction, focus changes, and blink timing are key to readable thought and emotion.
- **Body alignment**: the audio recording and facial performance may be used to adjust the timing and posing of
  the body to better match the voice actor's delivery.

---

## 4.6 Phase 3 — Polish

- Final detail: finger animation, small secondary motion, eye micro-movements, breathing.
- Check against cameras for intersections and contact issues.
- Hand-off to cloth/hair simulation, FX, and lighting.

---

## 4.7 Games-specific notes

- Animation is often authored as **cycles and clips** (idle, walk, run, jumps, attacks, reactions) with defined
  start/end poses for blending.
- Clips are assembled into **state machines / blend trees** in the engine and tested in gameplay.
- Root motion, foot planting, and additive layers (breathing, aim offsets) are defined per project.
- In-engine cinematics follow the linear-media process in this document and in
  [Story, Editorial, Previz and Layout](05_STORY_EDITORIAL_PREVIZ_LAYOUT.md).

---

## 4.8 Skills involved

- Animation Supervisor / Director
- Character Animator (body)
- Facial Animator
- Motion Capture Technician / Mocap Solver
- Mocap Cleanup and Retargeting Artist
- Performance Actor / Voice Actor (performance source)
- Gameplay Animator / Animation Technical Artist (games)

See [Roles and Art Skills](07_ROLES_AND_SKILLS.md).
