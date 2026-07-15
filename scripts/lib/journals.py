"""Flagship-journal knowledge, shared by the `journals` source and the scorer.

One place owns the mapping from a short journal name (as written in topics.yml)
to its OpenAlex source id, plus the set of flagship venue display-names used to
give those journals a ranking boost no matter which source surfaced the paper.

Adding a journal = one line here. Both `scripts/fetch_journals.py` (fetch by
source id) and `scripts/lib/filtering.py` (venue-prestige bonus) read from this.
"""
from __future__ import annotations

# name -> (OpenAlex source id, canonical display name). The source ids are the
# `S...` ids from https://api.openalex.org/sources; display names are matched
# (normalized) against a paper's `venue` for the prestige bonus.
JOURNAL_SOURCES: dict[str, tuple[str, str]] = {
    # Multidisciplinary flagships
    "nature": ("S137773608", "Nature"),
    "science": ("S3880285", "Science"),
    "cell": ("S110447773", "Cell"),
    # The Lancet family (clinical)
    "lancet": ("S49861241", "The Lancet"),
    "lancet-oncology": ("S116900674", "The Lancet Oncology"),
    "lancet-neurology": ("S70053155", "The Lancet Neurology"),
    "lancet-infectious-diseases": ("S23772524", "The Lancet Infectious Diseases"),
    # Nature family (high-volume, bio-relevant)
    "nature-medicine": ("S203256638", "Nature Medicine"),
    "nature-genetics": ("S137905309", "Nature Genetics"),
    "nature-communications": ("S64187185", "Nature Communications"),
    "nature-neuroscience": ("S2298632", "Nature Neuroscience"),
}


def resolve_source_ids(names: list[str]) -> list[str]:
    """Map journal names to OpenAlex source ids, preserving order, de-duped."""
    ids: list[str] = []
    for name in names:
        key = name.strip().lower()
        if key not in JOURNAL_SOURCES:
            known = ", ".join(sorted(JOURNAL_SOURCES))
            raise ValueError(f"unknown journal {name!r}; known journals: {known}")
        sid = JOURNAL_SOURCES[key][0]
        if sid not in ids:
            ids.append(sid)
    return ids


def _normalize_venue(venue: str) -> str:
    """Lowercase, drop a leading 'the ', strip parenthetical suffixes, collapse
    whitespace. So 'The Lancet', 'Lancet (London, England)' and 'lancet' all
    normalize to the same key that PubMed/Crossref/OpenAlex can then match."""
    v = venue.strip().lower()
    if "(" in v:  # PubMed venues like "Lancet (London, England)"
        v = v.split("(", 1)[0]
    v = " ".join(v.split())
    if v.startswith("the "):
        v = v[4:]
    return v


# Normalized flagship display names, matched against a paper's venue.
FLAGSHIP_VENUES: frozenset[str] = frozenset(
    _normalize_venue(display) for _, display in JOURNAL_SOURCES.values()
)


def is_flagship_venue(venue: str | None) -> bool:
    """True if `venue` names one of the flagship journals above (any source).

    Matches on the normalized display name so a Nature/Lancet paper earns the
    prestige bonus whether it arrived via the journals source, OpenAlex,
    Crossref or PubMed (each spells the venue a little differently)."""
    if not venue:
        return False
    return _normalize_venue(venue) in FLAGSHIP_VENUES
