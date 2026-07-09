"""Abstract, on-brand concept backdrops for the front/title card.

Each motif is an SVG tinted with the account accent at low opacity, rendered
behind the title with a radial scrim so the headline stays legible. These are
decorative brand texture, not paper-specific illustration.
"""
from __future__ import annotations

import base64

_NEURAL = """
<svg width="1080" height="1350" viewBox="0 0 1080 1350" xmlns="http://www.w3.org/2000/svg">
  <g stroke="{accent}" stroke-width="2" opacity="0.16" fill="none">
    <line x1="120" y1="200" x2="380" y2="420"/><line x1="380" y1="420" x2="680" y2="300"/>
    <line x1="680" y1="300" x2="900" y2="520"/><line x1="380" y1="420" x2="520" y2="740"/>
    <line x1="520" y1="740" x2="820" y2="880"/><line x1="900" y1="520" x2="820" y2="880"/>
    <line x1="200" y1="980" x2="520" y2="740"/><line x1="200" y1="980" x2="480" y2="1180"/>
    <line x1="820" y1="880" x2="720" y2="1180"/><line x1="480" y1="1180" x2="720" y2="1180"/>
  </g>
  <g fill="{accent}" opacity="0.30">
    <circle cx="120" cy="200" r="12"/><circle cx="380" cy="420" r="16"/>
    <circle cx="680" cy="300" r="12"/><circle cx="900" cy="520" r="14"/>
    <circle cx="520" cy="740" r="18"/><circle cx="820" cy="880" r="14"/>
    <circle cx="200" cy="980" r="12"/><circle cx="480" cy="1180" r="16"/>
    <circle cx="720" cy="1180" r="12"/>
  </g>
</svg>
"""

_HELIX = """
<svg width="1080" height="1350" viewBox="0 0 1080 1350" xmlns="http://www.w3.org/2000/svg">
  <g stroke="{accent}" stroke-width="4" fill="none" opacity="0.18">
    <path d="M300 120 C 620 320, 460 520, 780 720 C 460 920, 620 1120, 300 1320"/>
    <path d="M780 120 C 460 320, 620 520, 300 720 C 620 920, 460 1120, 780 1320"/>
  </g>
  <g stroke="{accent}" stroke-width="3" opacity="0.14">
    <line x1="360" y1="200" x2="720" y2="200"/><line x1="440" y1="320" x2="640" y2="320"/>
    <line x1="620" y1="440" x2="460" y2="440"/><line x1="360" y1="560" x2="720" y2="560"/>
    <line x1="440" y1="680" x2="640" y2="680"/><line x1="620" y1="800" x2="460" y2="800"/>
    <line x1="360" y1="920" x2="720" y2="920"/><line x1="440" y1="1040" x2="640" y2="1040"/>
    <line x1="620" y1="1160" x2="460" y2="1160"/>
  </g>
</svg>
"""

# --- more backdrops ---

_CIRCUIT = """
<svg width="1080" height="1350" viewBox="0 0 1080 1350" xmlns="http://www.w3.org/2000/svg">
  <g stroke="{accent}" stroke-width="3" fill="none" opacity="0.15">
    <path d="M80 260 H 360 V 120"/><path d="M360 260 H 620 V 460 H 900"/>
    <path d="M80 620 H 300 V 900 H 560"/><path d="M560 900 V 1180 H 980"/>
    <path d="M700 120 V 360 H 980"/><path d="M420 1180 V 820 H 240"/>
  </g>
  <g fill="{accent}" opacity="0.32">
    <circle cx="360" cy="120" r="10"/><circle cx="900" cy="460" r="10"/>
    <circle cx="560" cy="900" r="10"/><circle cx="980" cy="1180" r="10"/>
    <circle cx="700" cy="120" r="10"/><circle cx="240" cy="820" r="10"/>
    <rect x="600" y="440" width="40" height="40" rx="6"/>
    <rect x="280" y="880" width="40" height="40" rx="6"/>
  </g>
</svg>
"""

_WAVEFORM = """
<svg width="1080" height="1350" viewBox="0 0 1080 1350" xmlns="http://www.w3.org/2000/svg">
  <g stroke="{accent}" fill="none" opacity="0.18" stroke-width="3">
    <path d="M0 700 Q 90 500 180 700 T 360 700 T 540 700 T 720 700 T 900 700 T 1080 700"/>
    <path d="M0 820 Q 135 560 270 820 T 540 820 T 810 820 T 1080 820" opacity="0.6"/>
    <path d="M0 580 Q 60 460 120 580 T 240 580 T 360 580 T 480 580 T 600 580 T 720 580 T 840 580 T 960 580 T 1080 580" opacity="0.5"/>
  </g>
</svg>
"""

_ORBITS = """
<svg width="1080" height="1350" viewBox="0 0 1080 1350" xmlns="http://www.w3.org/2000/svg">
  <g stroke="{accent}" fill="none" opacity="0.16" stroke-width="3">
    <ellipse cx="540" cy="675" rx="420" ry="180"/>
    <ellipse cx="540" cy="675" rx="180" ry="420"/>
    <ellipse cx="540" cy="675" rx="330" ry="330"/>
  </g>
  <g fill="{accent}" opacity="0.34">
    <circle cx="540" cy="675" r="22"/><circle cx="960" cy="675" r="12"/>
    <circle cx="540" cy="255" r="12"/><circle cx="305" cy="440" r="9"/>
    <circle cx="775" cy="910" r="9"/>
  </g>
</svg>
"""

_HEXGRID = """
<svg width="1080" height="1350" viewBox="0 0 1080 1350" xmlns="http://www.w3.org/2000/svg">
  <defs><pattern id="h" width="150" height="130" patternUnits="userSpaceOnUse">
    <path d="M37 0 L112 0 L150 65 L112 130 L37 130 L0 65 Z"
      fill="none" stroke="{accent}" stroke-width="2.5" opacity="0.14"/>
  </pattern></defs>
  <rect width="1080" height="1350" fill="url(#h)"/>
</svg>
"""

_PARTICLES = """
<svg width="1080" height="1350" viewBox="0 0 1080 1350" xmlns="http://www.w3.org/2000/svg">
  <g fill="{accent}">
    <circle cx="140" cy="180" r="6" opacity="0.5"/><circle cx="380" cy="120" r="10" opacity="0.3"/>
    <circle cx="640" cy="240" r="5" opacity="0.5"/><circle cx="880" cy="160" r="8" opacity="0.35"/>
    <circle cx="240" cy="420" r="9" opacity="0.3"/><circle cx="520" cy="500" r="5" opacity="0.5"/>
    <circle cx="780" cy="440" r="11" opacity="0.28"/><circle cx="960" cy="560" r="6" opacity="0.45"/>
    <circle cx="120" cy="700" r="10" opacity="0.3"/><circle cx="420" cy="760" r="6" opacity="0.5"/>
    <circle cx="700" cy="720" r="8" opacity="0.35"/><circle cx="900" cy="840" r="5" opacity="0.5"/>
    <circle cx="200" cy="980" r="7" opacity="0.4"/><circle cx="520" cy="1040" r="10" opacity="0.3"/>
    <circle cx="820" cy="1020" r="6" opacity="0.5"/><circle cx="340" cy="1200" r="9" opacity="0.32"/>
    <circle cx="680" cy="1240" r="5" opacity="0.5"/><circle cx="960" cy="1180" r="8" opacity="0.35"/>
  </g>
</svg>
"""

_TOPO = """
<svg width="1080" height="1350" viewBox="0 0 1080 1350" xmlns="http://www.w3.org/2000/svg">
  <g stroke="{accent}" fill="none" opacity="0.15" stroke-width="2.5">
    <path d="M-40 300 C 240 220, 480 380, 760 280 S 1120 240, 1120 240"/>
    <path d="M-40 440 C 280 360, 520 520, 800 420 S 1120 380, 1120 380"/>
    <path d="M-40 620 C 240 540, 560 700, 820 600 S 1120 560, 1120 560"/>
    <path d="M-40 820 C 300 740, 540 900, 840 800 S 1120 760, 1120 760"/>
    <path d="M-40 1020 C 260 940, 520 1100, 800 1000 S 1120 960, 1120 960"/>
    <path d="M-40 1200 C 300 1120, 560 1260, 860 1180 S 1120 1140, 1120 1140"/>
  </g>
</svg>
"""

_GRID = """
<svg width="1080" height="1350" viewBox="0 0 1080 1350" xmlns="http://www.w3.org/2000/svg">
  <defs><pattern id="g" width="90" height="90" patternUnits="userSpaceOnUse">
    <path d="M90 0 H0 V90" fill="none" stroke="{accent}" stroke-width="1.5" opacity="0.12"/>
  </pattern></defs>
  <rect width="1080" height="1350" fill="url(#g)"/>
  <g fill="{accent}" opacity="0.3">
    <circle cx="180" cy="270" r="7"/><circle cx="540" cy="540" r="7"/>
    <circle cx="810" cy="360" r="7"/><circle cx="360" cy="900" r="7"/>
    <circle cx="720" cy="1080" r="7"/>
  </g>
</svg>
"""

_MOLECULE = """
<svg width="1080" height="1350" viewBox="0 0 1080 1350" xmlns="http://www.w3.org/2000/svg">
  <g stroke="{accent}" stroke-width="3" opacity="0.18">
    <line x1="360" y1="420" x2="540" y2="560"/><line x1="540" y1="560" x2="720" y2="440"/>
    <line x1="540" y1="560" x2="560" y2="800"/><line x1="560" y1="800" x2="380" y2="920"/>
    <line x1="560" y1="800" x2="760" y2="900"/><line x1="360" y1="420" x2="220" y2="300"/>
    <line x1="720" y1="440" x2="880" y2="360"/>
  </g>
  <g fill="{accent}" opacity="0.34">
    <circle cx="360" cy="420" r="20"/><circle cx="540" cy="560" r="26"/>
    <circle cx="720" cy="440" r="20"/><circle cx="560" cy="800" r="24"/>
    <circle cx="380" cy="920" r="16"/><circle cx="760" cy="900" r="16"/>
    <circle cx="220" cy="300" r="13"/><circle cx="880" cy="360" r="13"/>
  </g>
</svg>
"""

_MOTIFS = {
    "neural": _NEURAL,
    "helix": _HELIX,
    "circuit": _CIRCUIT,
    "waveform": _WAVEFORM,
    "orbits": _ORBITS,
    "hexgrid": _HEXGRID,
    "particles": _PARTICLES,
    "topo": _TOPO,
    "grid": _GRID,
    "molecule": _MOLECULE,
}


def available_motifs() -> list[str]:
    return list(_MOTIFS)


def motif_data_uri(name: str, accent: str) -> str | None:
    """Return a base64 SVG data URI for the named motif tinted with accent, or None."""
    svg = _MOTIFS.get(name)
    if not svg:
        return None
    filled = svg.replace("{accent}", accent).strip()
    b64 = base64.b64encode(filled.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"
