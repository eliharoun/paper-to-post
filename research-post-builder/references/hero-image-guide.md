# Hero Image Guide

The front (title) card shows an AI-generated hero image behind the headline.
During the Write step, author a single `hero_image_prompt` string in the post
JSON that a text-to-image model will render. This guide defines the house rules;
the topic's own look comes from `hero_style.style` in `config/brand.<account>.yml`.

## Rules for every hero prompt

- **Conceptual and metaphorical.** Evoke the paper's specific idea, not generic
  "science". A reader should sense the topic before reading the headline.
- **No text, words, labels, numbers, diagrams, flowcharts, or UI.** Pure imagery.
- **Composition for a 4:5 vertical card:** place the main subject in the UPPER
  two-thirds, filling the frame generously. Reserve the BOTTOM third as calm,
  dark negative space (a smooth gradient into shadow) for the headline overlay.
  The subject must NOT extend into the very bottom of the frame.
- **One clear focal subject** with depth and cinematic lighting. Scroll-stopping,
  premium, editorial.
- **Fold in the topic house style** from `hero_style.style` (palette, medium,
  mood) so every post in a topic feels like a set.

## How to write the prompt

Write 2-4 sentences: (1) the focal subject as a metaphor for this paper,
(2) composition + lighting, (3) the house-style descriptor, (4) an explicit
"no text, no words, no diagrams; reserve calm dark space in the lower third".

## Example (CS, IoT security paper)

> A sleek matte-black smart-home device floating in a dark studio void, its
> casing cracking open to reveal an exposed glowing circuit interior, with fluid
> ribbons of brilliant cyan light threading through the breach like intruding
> agents. Cinematic volumetric lighting, sharp macro detail, premium editorial
> 3D render. Subject anchored in the upper two-thirds; smooth gradient into deep
> shadow across the lower third. No text, no words, no diagrams.

## Example (bio, cell-biology paper)

> A translucent cluster of luminous alveolar cells suspended in a dark
> microscopic void, a small pocket of scarred, charcoal-toned mutated cells
> persisting deep in the core while the surrounding tissue glows with healthy
> mint-green bioluminescence. Subsurface scattering, shallow depth of field,
> premium editorial macro 3D render. Subject anchored in the upper two-thirds;
> smooth gradient into deep shadow across the lower third. No text, no words,
> no diagrams.
