# 6. VFX, Lighting and Audio

These departments work in parallel once shots are laid out and animated. Their creative direction is defined
early in the [Visual Bible](01_VISUAL_DEVELOPMENT.md#13-the-project-visual-bible) (effects and lighting
language) and in story development (audio), and is realized in 3D during shot production.

---

## 6.1 Visual effects (VFX)

VFX artists create effects that are impractical to animate by hand: dust, smoke, fire, sparks, explosions,
destruction, water, weather, magic, and crowds.

### Linear media (film / series)

- Effects are typically authored in **Houdini** or other high-end simulation software.
- Inputs: published animation (character motion, contacts), layout cameras, and environment geometry.
- Process: effect look development (turntables and test simulations reviewed against the effects language) →
  per-shot simulation → caching → rendering or hand-off to lighting.
- Effects follow the Visual Bible's stylization rules (realistic vs. stylized shapes, timing, and color).
- Simulations are expensive; they begin in earnest after animation is approved to avoid re-simulation.

### Games

- Effects are authored **inside the game engine** (particle systems, shaders, flipbooks, mesh effects) so they
  respond to gameplay at runtime.
- **Texture authoring happens outside the engine**: flipbook sheets, noise and gradient textures, and simulated
  elements are created in tools such as Houdini, EmberGen, Substance Designer, or Photoshop, then imported.
- Performance budgets (overdraw, particle counts, texture memory) are part of the design constraints.

### Reusable effects library

Like the material library, a project maintains a library of approved effects (a standard fire, dust impact,
water splash) that shots or levels reuse and adapt.

---

## 6.2 Lighting

### Lighting language (early, in visual development)

The lighting language is discussed and defined early in the development process and becomes part of the
Visual Bible. It specifies:

- Mood by story beat, location, and time of day.
- Key-to-fill ratios and contrast.
- Color temperature and palette of light.
- Hard vs. soft light, use of practical (motivated) sources.
- How characters are separated from backgrounds (rim light, value separation).
- Signature lighting setups for key moments.

It is illustrated with color keys, painted lighting keys, and references.

### Shot lighting (production)

Later in production — while VFX are being authored — lighting artists replicate those designed moods as 3D
lighting in the scenes:

1. **Sequence lighting / master lights.** A lead lights key shots in a sequence to establish the look, matching
   the color keys.
2. **Shot lighting.** Remaining shots inherit the sequence setup and are adjusted per shot for camera and
   continuity.
3. **Character lighting.** Dedicated rims, kickers, and eye lights to keep characters readable.
4. **Render passes / AOVs** for compositing flexibility.
5. **Review** side by side with the color key and neighboring shots in the edit.

For games, lighting is authored per level in the engine: dynamic and baked lighting, light probes, post-process
volumes, and time-of-day systems, following the same lighting language.

### Compositing (film)

Compositing combines render passes, FX, and any plates into the final image, with color grading applied to
match the color script.

---

## 6.3 Audio

Audio is recorded and produced for character dialogue, ambient sound, sound effects, and music.

### Dialogue

- **Scratch dialogue** recorded early (often by the crew) for story reels and previz.
- **Final voice recording** with voice actors. **Character lines must be captured before facial animation can
  proceed**, because lip-sync and facial performance are built on the recording.
- The recorded performance is also used to **adjust the posing and timing of the body animation** to better
  align with the voice actor's delivery.
- Video of the recording session is valuable facial and gesture reference for animators.

### Ambient and sound effects

- Ambience beds (environments, weather, crowds) and specific effects (footsteps, impacts, cloth, props) are
  recorded (field recording, Foley) or designed.
- For games, sounds are implemented with middleware or the engine's audio system with variations and
  parameters tied to gameplay.

### Music

- Temp music in early edits; composed score and licensed music later.
- Music cues are spotted against the edit (film) or tied to game states.

### Mix

The final mix balances dialogue, effects, and music, delivered in the required formats.

---

## 6.4 Skills involved

- FX Artist / FX Technical Director
- Real-time VFX Artist (games)
- Lighting Artist / Lighting TD
- Lighting Lead / Key Lighter
- Compositor
- Colorist
- Voice Director, Voice Actor
- Dialogue Editor
- Sound Designer, Foley Artist
- Composer, Music Editor
- Re-recording Mixer / Audio Implementer (games)

See [Roles and Art Skills](07_ROLES_AND_SKILLS.md).
