# 3. Rigging and Deformation

Rigging makes a static mesh animatable. The mesh is bound (skinned) to an armature skeleton, controls are
built for animators, and the deformation is refined until the character moves the way the design intends.

The central idea of this document is **target-driven rigging**: before the skeleton is finalized, the team
defines *what the deformations should look like*, then iterates on joints, skin weights, and correctives until
rendered poses match those targets.

```
Deformation intent (art bible) ──┐
Conceptual motion videos ────────┤
Real-world reference video ──────┼─► Pose targets (body, hands, feet, face/FACS)
                                 │            │
                                 │            ▼
                                 │   Skeleton authoring ─► Skinning ─► Render poses
                                 │            ▲                            │
                                 │            └──── adjust ◄── compare ◄───┘
                                 │
                                 └─► Mood tests & lip-sync tests ─► Rig approval ─► Publish to animation
```

---

## 3.1 Inputs

- **Approved 3D model**, split into parts ([Asset Construction §2.2](02_ASSET_CONSTRUCTION.md#22-part-breakdown-build-in-smaller-pieces)),
  with deformation-friendly topology.
- **Deformation intent** from the art bible: how cloth, armor, soft tissue, hair, and accessories should move.
- **Conceptual motion videos.** Short animatics or motion studies built from the original concept art and
  early 3D mesh renders (e.g. paint-overs, puppet-style 2D animation, or simple 3D camera moves around posed
  renders). They communicate *how the character is meant to move*: weight, attitude, squash and stretch,
  stylization level.
- **Reference video.** Real-world footage of people or animals performing relevant actions (walks, runs,
  reaching, crouching, facial expressions, speech), shot or sourced by the rigging and animation teams.
- **Project rig standards.** Joint naming, orientation conventions, control shapes and colors, required
  attributes, and engine/renderer constraints (joint count limits and influences per vertex for games).

---

## 3.2 Defining pose targets

Before skeleton construction is finalized, the team defines and renders a set of **pose targets** — images
showing exactly how the mesh should look in key poses. These are painted over 3D renders or sculpted directly
on the mesh.

### Body extremes

- Full range of motion for each major joint: shoulder raise/forward/back, elbow full bend, wrist bend and twist,
  spine bend and twist, hip flex/extension, knee full bend, deep crouch, extreme reach overhead.
- Signature poses from the pose and attitude sheet.
- Areas of known difficulty: shoulders, armpits, elbows, hips/groin, knees, and neck.

### Hand poses

- Fist, flat spread hand, relaxed curl, pointing, grip on a prop, pinch, thumb extremes, and any gestures that
  define the character.

### Foot poses

- Flat stance, toe raise, heel raise, extreme toe bend, ankle roll, and footwear-specific behavior (stiff boots
  vs. soft shoes vs. bare feet).

### Face poses

- **FACS action units.** Poses for each Facial Action Coding System action unit the character needs (brow
  raisers, lid tighteners, cheek raiser, nose wrinkler, lip corner pullers/depressors, jaw drop, lip pucker,
  lip funneler, etc.).
- **Combination shapes** that are known to conflict (e.g. smile + jaw open, brow raise + squint).
- **Visemes / phonemes.** Mouth shapes for speech: lip, **tongue, and teeth placement** for each sound group
  (e.g. M/B/P closed lips; F/V lower lip to upper teeth; TH tongue between teeth; L tongue tip to upper
  palate; O/U rounded lips; E/I wide lips; open vowels with visible lower teeth).
- **Expression extremes.** The strongest versions of joy, anger, sadness, fear, surprise, disgust, and
  contempt, plus character-specific expressions from the expression sheet.

Each pose target records the camera angle and lighting used, so the rig render can be produced from the same
view for comparison.

---

## 3.3 Body skeleton authoring and skinning

1. **Place joints** against the model and the pose targets, not just anatomy charts. Joint placement determines
   pivot points; misplaced joints cannot be fixed by skin weights alone.
2. **Orient joints** consistently per project standards so animation and mocap retargeting behave predictably.
3. **Add helper and twist joints** where the pose targets demand volume preservation (forearm twist, upper arm
   twist, thigh twist, shoulder and hip helpers, and corrective joints at the elbows and knees).
4. **Bind and paint skin weights.** Start with automatic binding, then paint weights by hand. Use smooth, even
   falloff; limit influences per vertex to the project's budget.
5. **Add correctives.** Pose-space corrective blend shapes or driven helper joints fix remaining problems in
   specific poses (e.g. shoulder raised, elbow fully bent).
6. **Secondary deformation.** Muscle/jiggle systems, cloth and hair simulation setups, or rigid attachments for
   accessories, depending on the part.

---

## 3.4 Iterative deformation review

The rig is validated by rendering each pose target and comparing it against the conceptual reference.

1. Pose the rig to match each target pose.
2. Render from the target's camera and lighting.
3. Review side by side (or overlaid/flipbooked) with the target image and the reference video frame.
4. Note discrepancies: volume loss, candy-wrapper twisting, collapsing joints, intersecting geometry, pinching,
   unreadable silhouettes, off-model shapes.
5. Adjust **skeleton placement**, **skin weights**, or **correctives**, and repeat.

A **range-of-motion (ROM) animation** — a clip that moves every joint through its full range — is played on the
rig after each iteration to catch regressions. The ROM is also used to validate the rig in the target
renderer or game engine.

The rig passes when every pose target is hit within agreed tolerance and the ROM shows no deformation
artifacts at the project's camera distances.

---

## 3.5 Facial rig authoring

Face pose extremes drive a dedicated facial iteration.

1. **Choose the approach**: joint-based (common in games), blend-shape-based (common in film), or hybrid.
   Many productions use FACS-based blend shapes driven by a joint or control layer.
2. **Author the face skeleton / shape set** from the FACS and viseme targets — jaw, lips (upper/lower,
   corners), cheeks, nose, eyelids, brows, tongue, and eyes.
3. **Build the control layer** animators will use: on-face controls, a GUI panel, and higher-level pose
   sliders (phonemes, expressions) that combine the underlying shapes.
4. **Iterate against targets** exactly as with the body: render each FACS shape, viseme, and combination from
   the target camera and compare.

### Talking faces: lip, tongue, and teeth

Speech readability depends on the inside of the mouth as much as the lips.

- Upper teeth move with the skull; lower teeth and tongue move with the jaw.
- Tongue controls must reach the upper teeth and palate (L, T, D, N), rest between teeth (TH), and pull back
  (K, G).
- Lip rolls, lip compression for plosives (P, B, M), and lower lip to upper teeth contact (F, V) must be
  achievable without intersection.
- Lip corners must hold volume through wide and rounded shapes.

---

## 3.6 Mood tests and lip-sync tests

Before the rig is released to animation, it is exercised with short performance tests:

- **Mood tests.** Short animated clips of the character shifting between expressions (e.g. neutral → suspicious
  → angry → resigned). Reviewers without prior context should be able to name the mood correctly.
- **Lip-sync tests.** The face is animated to recorded lines of dialogue — ideally the actual voice actor's
  recordings, or scratch audio if final lines are not yet available. The test must visually read as the spoken
  words, with lip, tongue, and teeth positions matching the viseme targets.
- **Combined tests.** Dialogue delivered with emotion (e.g. an angry line, a whispered line) to test
  combination shapes.
- **Body mood tests.** Idle and posture clips expressing mood through the body (slumped, proud, nervous) to
  verify spine, shoulders, and neck deformation.

Each test is rendered and reviewed against the concept expression sheets and reference video. Issues feed back
into skeleton placement, skin weights, and blend shapes. Iterate until the rig reliably hits the designed
intent and is human-readable.

---

## 3.7 Rig approval and publishing

- The rig is approved by the rigging lead, animation lead, and art director (for appearance).
- The published rig includes the skinned mesh parts, skeleton, controls, correctives, and any simulation setups,
  plus the rendered pose targets, ROM, and test clips as validation records.
- Rigs are versioned. Updates must preserve control names and default poses so existing animation continues to
  work; breaking changes require coordination with animation.

---

## 3.8 Skills involved

- Character Technical Director (TD) / Rigger
- Facial Rigger / Facial TD
- Deformation / Creature TD (muscle, skin, cloth, hair setups)
- Modeler / Sculptor (corrective and blend-shape sculpting)
- Concept Artist / Paint-over Artist (pose targets)
- Animator (testing and feedback)

See [Roles and Art Skills](07_ROLES_AND_SKILLS.md).
