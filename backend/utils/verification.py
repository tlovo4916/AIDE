"""Citation and claim verification utilities for hallucination mitigation."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Patterns that capture typical citation forms:
#   [1], [23], [Smith et al., 2024], [Smith 2024], [Smith & Jones, 2023]
_CITATION_RE = re.compile(
    r"\[("
    r"\d+"                                          # numeric: [1], [23]
    r"|[A-Z][a-z]+(?:\s+(?:et\s+al\.?|&\s+[A-Z][a-z]+))?,?\s*\d{4}"  # author-year
    r")\]"
)

# Patterns for inline author mentions: "Smith et al. (2024)", "Smith (2024)"
_INLINE_CITE_RE = re.compile(
    r"([A-Z][a-z]+(?:\s+et\s+al\.?)?)\s*\(\d{4}\)"
)


def verify_citations(
    text: str,
    known_titles: list[str],
    known_ids: list[str] | None = None,
) -> list[str]:
    """Check citation references in *text* against known papers.

    Args:
        text: The text to scan for citation references.
        known_titles: List of paper titles available on the board.
        known_ids: Optional list of artifact IDs (e.g. paper DOIs, board IDs).

    Returns:
        A list of citation strings that could NOT be matched to any known
        paper title or ID.  An empty list means all citations are verifiable.
    """
    if not text:
        return []

    known_ids = known_ids or []

    # Build a lowered lookup set from titles and IDs for cheap matching
    title_words: dict[str, str] = {}  # lowered-title -> original
    for t in known_titles:
        title_words[t.lower().strip()] = t
    id_set = {kid.lower().strip() for kid in known_ids}

    unverified: list[str] = []

    # --- Bracket citations [N] or [Author, Year] ---
    for match in _CITATION_RE.finditer(text):
        ref = match.group(1).strip()
        if _ref_matches_known(ref, title_words, id_set):
            continue
        unverified.append(match.group(0))

    # --- Inline citations: Author (Year) ---
    for match in _INLINE_CITE_RE.finditer(text):
        author = match.group(1).strip()
        full = match.group(0).strip()
        if _inline_matches_known(author, title_words, id_set):
            continue
        unverified.append(full)

    return unverified


def _ref_matches_known(
    ref: str,
    title_words: dict[str, str],
    id_set: set[str],
) -> bool:
    """Return True if a bracket citation reference matches a known source."""
    ref_lower = ref.lower()

    # Numeric references (e.g. "1") -- match against IDs
    if ref.isdigit():
        return ref in id_set or ref_lower in id_set

    # Author-year references: extract the author surname portion
    author_part = re.split(r"[,\s]+\d{4}", ref)[0].strip().lower()
    if not author_part:
        return False

    # Check if the author surname appears in any known title
    for title_lower in title_words:
        if author_part in title_lower:
            return True

    # Check IDs
    if ref_lower in id_set or author_part in id_set:
        return True

    return False


def _inline_matches_known(
    author: str,
    title_words: dict[str, str],
    id_set: set[str],
) -> bool:
    """Return True if an inline author mention matches a known source."""
    author_lower = author.lower().replace(" et al.", "").replace(" et al", "").strip()
    if not author_lower:
        return False

    for title_lower in title_words:
        if author_lower in title_lower:
            return True

    if author_lower in id_set:
        return True

    return False
