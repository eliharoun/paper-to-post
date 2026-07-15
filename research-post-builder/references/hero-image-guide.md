# Hero Image Guide

The front (title) card shows an AI-generated hero image behind the headline.
During the Write step, author a single `hero_image_prompt` string in the post
JSON that a Google Gemini image model (`gemini-3.1-flash-image-preview`, aka
Nano Banana) will render. This guide defines the house rules; the topic's own
look comes from `hero_style.style` in `config/brand.<account>.yml`.

## The one rule that matters most: show the thing, not a symbol of the thing

**Depict the paper's actual subject or scenario as a concrete, literal scene
caught mid-action — NOT an abstract metaphor.** The headline already carries the
idea in words; the image's job is to give the eye something *real and specific*
to lock onto. Eyetracking research is blunt: readers **study** concrete,
information-carrying images (real objects, people, the actual subject matter)
and **skip** decorative/abstract ones. A glowing crystal, a floating orb of
light, an abstract "corruption spreading" motif reads as interchangeable stock —
it says "science" without saying *this* science.

Ask: **"What does this finding literally look like as a photographed moment?"**
Then show *that*.

- Data-poisoning paper → **show a tampered document being fed into a machine and
  a visibly wrong output coming out**, not dye bleeding into a crystal.
- Moon-skipping / proprioception paper → **show an astronaut skipping across the
  lunar surface, one leg cut away to reveal the working muscles**, not glowing
  filaments on a floating body.
- CRISPR gene-edit → **a single glowing thread being pulled from a densely woven
  textile with tweezers**, not a blue double helix with scissors.

The metaphor can still be *staged as* a scene — but stage it as a tangible
physical moment you could photograph, with a real subject, a real action, and a
real setting. "Mechanism-or-consequence as a moment," never "field as a symbol."

### When the subject is intangible, anchor on the human or the consequence

"Depict the object of study" works when that object is tangible (a device, a
model being compressed, an agent picking a tool). But when the paper's subject is
**intangible** — memory, an algorithm, a statistical effect, a policy, a
behaviour — do **NOT** build a device to represent it. Inventing an apparatus
(e.g. "a core whose face is glowing memory modules") forces the viewer through a
decoding chain and reads as abstract. Instead:

- **Anchor on the human interaction or the real-world consequence**, using a real,
  relatable object and **one single legible action** the viewer reads without
  decoding. When the finding is about how a system behaves *toward a person*,
  prefer a **relational/human anchor** (a person + the thing happening to them) so
  the stakes stay visible.
- **Litmus test:** if explaining the image needs more than one "which stands
  for…" clause, it's too abstract — collapse it to one real action.
- **Worked example (from a real run):** *"AI agents remember what you tell them"*
  → a device etching speech-bubbles into memory cells was three stacked metaphors
  (bubble = user speech, module = memory, fusing = permanence) and read as an
  unrecognizable gadget. The fix: **a person telling an assistant something and
  that sentence being filed into a labeled personal dossier the assistant keeps** —
  one action, human stakes visible, nothing to decode.

## Build in a reason to swipe

A hero that stops the scroll almost always has these. Work at least two into every prompt:

- **One dominant focal subject**, large, filling the upper half — decided
  in under a second. If a viewer can't instantly name what they're looking at,
  it's a diagram, not a hero.
- **A frozen action / moment** — a verb in progress (feeding, cracking, skipping,
  colliding, forming, escaping). A still that implies story beats a static pose.
- **A curiosity gap / anomaly** — one incongruous or "impossible-looking" element
  that makes the missing explanation feel like an itch ("wait, why is *that*
  happening?"). This is what the swipe resolves.
- **A human or relatable anchor when honest** — a hand, a face, a body, an
  astronaut. Gives scale and stakes; a face's gaze can point the eye at the key
  object. (Don't force a human where the paper has none.)
- **Drama in the light** — one strong key light, high contrast between subject and
  a near-black background, shallow depth of field, a saturated accent only on the
  focal subject. Prompt *against* the model's default of flat, balanced, evenly
  lit, "tidy product shot" renders.

## Hard house rules (every prompt)

- **No text, words, letters, numbers, labels, logos, charts, diagrams, flowcharts,
  or UI.** Pure imagery. State this explicitly at the end of the prompt.
- **Composition for a 4:5 vertical card:** subject in the UPPER HALF,
  filling the frame generously. The **entire bottom ~40% must be empty, dark,
  low-detail negative space** for the headline overlay — describe that region as a
  *concrete surface* ("the whole bottom half fading into a smooth, deep-shadowed
  floor of calm empty negative space"), which reserves the space far more reliably
  than saying "leave room for text." **No bright objects, glows, highlights, or
  focal detail below the midline** — the headline is white and the account label is
  the topic accent colour, so anything bright or accent-coloured low in the frame
  fights the text. The subject must NOT extend into the bottom of the frame.
  - **Worked negative example (why this rule exists):** a "brass balance scale with
    two glowing food plates" prompt put the bright plates and a mint-green rim glow
    in the *lower third* — exactly where the green "DAILY BIO BITS" label sits — so
    the label washed out. The fix was pushing the whole scale into the upper half
    and forcing the bottom half to empty dark counter. Bright + low = clash.
- **Legibility is enforced downstream, but don't rely on it.** The compositor draws
  a soft dark halo behind the text and runs a **contrast QC check**: if the area
  behind the headline or label is too light/similar, `research-hero` fails and the
  post falls back to the motif front card (a *worse* outcome than a good hero). So a
  prompt that ignores the "dark lower third" rule doesn't ship a broken card — it
  silently loses its hero image. Keep the lower third dark to keep the hero.
- **Fold in the topic house style** from `hero_style.style` (palette, medium,
  mood) so every post in a topic feels like a set.
- **Honor the topic's `hero_style.concept_guidance` if present** (in
  `config/brand.<account>.yml`). Unlike `style` (which governs *how the image
  looks* and is pasted into the prompt), `concept_guidance` governs *what to
  depict* and is **writer-facing only — never paste it into the image prompt**.
  Use it when choosing the subject/scene so the hero is *representative of this
  paper*: a scroller should grasp what the paper is about from the image alone,
  and the scene should be specific enough that it couldn't be swapped onto a
  different paper in the topic. (This does not relax the house style or the "show
  the thing, not a symbol" rule — it sharpens subject choice within them.)
- **Honesty firewall applies to imagery too.** For animal studies, don't depict a
  human as the subject of the finding. Don't visually imply a result stronger than
  the paper shows. The image must be as honest as the headline.

## Banned clichés (auto-reject these — they read as generic stock "science")

Double helixes, glowing floating brains, circuit boards / chips as "AI",
binary-number rain, hexagon/node network overlays, generic humanoid robots,
floating holographic globes or dashboards, abstract glowing crystals/orbs, and
undifferentiated particle/energy clouds. Litmus test: **"Could this exact image
sit on any other paper in the field?"** If yes, it's a cliché — make it specific
to *this* paper's actual subject.

## How to write the prompt (for Gemini image models)

Write **flowing prose sentences that describe one scene** — not a comma-separated
keyword salad. Gemini image models are language-grounded and reward a narrative
"a [subject] [doing an action] in [a setting], lit [a way], shot [a way]" far
more than tag lists (which produce the averaged, generic look we're avoiding).

Fill this order (order matters — concrete subject + action first anchors it):

1. **Medium/style** — "A photorealistic photograph of…" or "An editorial 3D
   render of…" (pick ONE lane; don't mix three).
2. **Concrete subject** with 1–2 material/attribute details, performing an
   **active, present-tense moment** (the verb is what kills the vague mood-piece).
3. **Specific setting/context** with one grounding detail.
4. **Composition + negative space** — "Vertical 4:5 composition: the subject sits
   in the upper half; the entire bottom ~40% (everything below the midline) fades
   into a calm, dark, empty [surface] forming deep negative space."
5. **Camera + lighting** — real photographic terms: shot type, angle, lens
   (macro 60–105mm for objects, 24–35mm for a figure), light direction/quality,
   shallow depth of field with sharp focus on the focal detail.
6. **House-style clause** from `hero_style.style` (keep it fixed across the topic).
7. **Exclusions** — "Clean composition, no text, no words, no letters, no numbers,
   no logos, no charts or diagrams, no watermark."

Keep it to ~3–5 sentences. Be specific; specificity is what buys quality and
concreteness. (`research-hero` sets aspect ratio `4:5` via config — you don't set
it in the prompt, but you may echo "vertical 4:5" as reinforcement.)

## Example (CS, data-poisoning / scientific-fraud paper)

> A photorealistic close-up of a single subtly-forged research page sliding off a
> conveyor into the glowing intake slot of a sleek matte-black machine, while the
> card it prints out the other side comes out visibly warped and wrong; the one
> tampered page glows faintly red among clean white ones. Set on a dark studio
> surface. Vertical 4:5 composition: the machine and the feeding page fill the
> upper half, the entire bottom ~40% (below the midline) fading into a smooth,
> deep-shadowed floor that forms calm negative space. Low three-quarter angle, shot on an 85mm lens,
> dramatic single warm key light against a near-black background, shallow depth of
> field with sharp focus on the forged page entering the slot. Premium editorial
> 3D render, sleek modern tech aesthetic, single cyan (#38BDF8) accent. Clean
> composition, no text, no words, no letters, no numbers, no logos, no diagrams,
> no watermark.

## Example (bio, Moon-skipping / proprioception paper)

> A photorealistic image of an astronaut mid-skip across the grey lunar surface,
> caught at the top of the bounce with one leg trailing, where a clean anatomical
> cutaway of that thigh and calf reveals the working muscles glowing faint
> mint-green as they fire. Black space and a low Earth on the dark horizon behind.
> Vertical 4:5 composition: the skipping figure fills the upper half, the entire
> bottom ~40% (below the midline) fading into the dark shadowed lunar ground as calm negative space.
> Dynamic low angle catching the leap, shot on a 35mm lens, hard low-angle sunlight
> raking across the suit with deep shadow behind, shallow depth of field with sharp
> focus on the exposed leg muscles. Premium editorial render, subsurface scattering
> on the muscle, single mint-green bioluminescent accent against deep charcoal
> shadow. Clean composition, no text, no words, no letters, no numbers, no logos,
> no diagrams, no watermark.
