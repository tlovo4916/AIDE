"""Computable structural metrics -- pure Python, no LLM calls."""

from __future__ import annotations

import math
import re
from collections import Counter

from backend.types import DimensionScore
from backend.utils.nlp import ENGLISH_STOPWORDS as _STOPWORDS_EN

# Section headers expected in a complete research paper (English + Chinese)
_SECTION_HEADERS_EN = [
    "abstract",
    "introduction",
    "background",
    "method",
    "result",
    "discussion",
    "conclusion",
    "reference",
]
_SECTION_HEADERS_ZH = [
    "摘要",
    "引言",
    "背景",
    "方法",
    "结果",
    "讨论",
    "结论",
    "参考",
]

# Contradiction keywords (reused from board.has_contradictory_evidence pattern)
_CONTRADICT_EN = {"contradict", "inconsistent", "conflict", "disagree", "oppose", "however not"}
_CONTRADICT_ZH = {"矛盾", "冲突", "不一致", "相悖", "反驳", "否定"}
_NEGATION_EN = {"not", "no", "never", "neither", "cannot", "doesn't", "don't", "isn't", "aren't"}
_NEGATION_ZH = {"不", "没有", "否", "非", "未", "无"}


def jaccard_similarity(a: str, b: str) -> float:
    """Word-set Jaccard similarity between two texts."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0


def _tokenize(text: str) -> list[str]:
    """Tokenize text using whitespace + jieba for Chinese."""
    # Split on whitespace first
    tokens = text.lower().split()
    # Check if text contains Chinese characters
    if re.search(r"[\u4e00-\u9fff]", text):
        try:
            import jieba

            tokens.extend(jieba.lcut(text))
        except ImportError:
            pass
    return tokens


def coverage_breadth(
    artifacts: list[str],
    subtopics: list[str],
) -> DimensionScore:
    """Compute subtopic hit rate across artifacts.

    Args:
        artifacts: List of artifact text content.
        subtopics: Expected subtopics to cover.

    Returns:
        DimensionScore with computable_value = fraction of subtopics covered.
    """
    if not subtopics:
        return DimensionScore(name="coverage_breadth", computable_value=0.0)

    combined = " ".join(artifacts).lower()
    combined_tokens = set(_tokenize(combined))
    hits = []
    for topic in subtopics:
        topic_tokens = set(_tokenize(topic))
        if topic.lower() in combined or topic_tokens & combined_tokens:
            hits.append(topic)

    value = len(hits) / len(subtopics)
    evidence = [f"Covered {len(hits)}/{len(subtopics)} subtopics"]
    if hits:
        evidence.append(f"Found: {', '.join(hits[:5])}")
    return DimensionScore(
        name="coverage_breadth",
        computable_value=value,
        combined=value,
        evidence=evidence,
    )


def source_diversity(artifacts: list[str]) -> DimensionScore:
    """Shannon entropy of source URLs/DOIs across artifacts."""
    # Extract URLs and DOIs
    url_pattern = re.compile(r"https?://[^\s\)]+|doi:\S+|arxiv:\S+", re.IGNORECASE)
    sources: list[str] = []
    for text in artifacts:
        sources.extend(url_pattern.findall(text))

    if not sources:
        return DimensionScore(
            name="source_diversity",
            computable_value=0.0,
            combined=0.0,
            evidence=["No sources found"],
        )

    # Normalize to domains
    domains: list[str] = []
    for s in sources:
        if "://" in s:
            domain = s.split("://")[1].split("/")[0]
        else:
            domain = s.split(":")[0]
        domains.append(domain)

    counts = Counter(domains)
    total = sum(counts.values())
    entropy = -sum((c / total) * math.log2(c / total) for c in counts.values() if c > 0)
    # Normalize: max entropy = log2(n_unique)
    max_entropy = math.log2(len(counts)) if len(counts) > 1 else 1.0
    value = min(entropy / max_entropy, 1.0) if max_entropy > 0 else 0.0

    return DimensionScore(
        name="source_diversity",
        computable_value=value,
        combined=value,
        evidence=[
            f"{len(set(domains))} unique domains from {total} sources",
            f"Shannon entropy: {entropy:.2f}",
        ],
    )


def terminology_coverage(
    artifacts: list[str],
    domain_terms: list[str],
) -> DimensionScore:
    """Domain term hit rate across artifacts."""
    if not domain_terms:
        return DimensionScore(name="terminology_coverage", computable_value=0.0)

    combined = " ".join(artifacts).lower()
    hits = [t for t in domain_terms if t.lower() in combined]
    value = len(hits) / len(domain_terms)
    return DimensionScore(
        name="terminology_coverage",
        computable_value=value,
        combined=value,
        evidence=[f"Covered {len(hits)}/{len(domain_terms)} domain terms"],
    )


def citation_density(artifacts: list[str]) -> DimensionScore:
    """Reference count / content length ratio."""
    combined = " ".join(artifacts)
    if not combined.strip():
        return DimensionScore(
            name="citation_density",
            computable_value=0.0,
            combined=0.0,
            evidence=["No content"],
        )

    # Count citation patterns: [N], (Author, Year), doi:, arxiv:, http(s)://
    patterns = [
        r"\[\d+\]",
        r"\([A-Z][a-z]+(?:\s+et\s+al\.?)?,?\s*\d{4}\)",
        r"doi:\S+",
        r"arxiv:\S+",
    ]
    total_refs = 0
    for pat in patterns:
        total_refs += len(re.findall(pat, combined))

    content_len = len(combined)
    # Normalize: ~1 ref per 500 chars is "dense" (value=1.0)
    value = min(total_refs / (content_len / 500), 1.0) if content_len > 0 else 0.0

    return DimensionScore(
        name="citation_density",
        computable_value=value,
        combined=value,
        evidence=[f"{total_refs} references in {content_len} chars"],
    )


def structural_completeness(draft_text: str) -> DimensionScore:
    """Section header checklist — checks for expected paper sections."""
    if not draft_text.strip():
        return DimensionScore(
            name="structural_completeness",
            computable_value=0.0,
            combined=0.0,
            evidence=["Empty draft"],
        )

    lower = draft_text.lower()
    found_en = [h for h in _SECTION_HEADERS_EN if h in lower]
    found_zh = [h for h in _SECTION_HEADERS_ZH if h in lower]
    found = set(found_en + found_zh)

    # Use the maximum of EN or ZH coverage
    en_ratio = len(found_en) / len(_SECTION_HEADERS_EN) if _SECTION_HEADERS_EN else 0
    zh_ratio = len(found_zh) / len(_SECTION_HEADERS_ZH) if _SECTION_HEADERS_ZH else 0
    value = max(en_ratio, zh_ratio)

    return DimensionScore(
        name="structural_completeness",
        computable_value=value,
        combined=value,
        evidence=[f"Found sections: {', '.join(sorted(found))}"],
    )


# Regex patterns for specificity metric
_QUANTITATIVE_RE = re.compile(r"\d+\.?\d*%?")
_CAMEL_CASE_RE = re.compile(r"[A-Z][a-z]+(?:[A-Z][a-z]+)+")


def evidence_mapping(
    hypotheses: list[str],
    evidence_texts: list[str],
) -> DimensionScore:
    """Compute how many hypotheses have supporting evidence.

    For each hypothesis, extract keywords (minus stopwords) and check
    whether ≥3 keywords appear in any evidence text.

    Args:
        hypotheses: Hypothesis texts.
        evidence_texts: Evidence artifact texts.

    Returns:
        DimensionScore with value = fraction of hypotheses with evidence mapping.
    """
    if not hypotheses:
        return DimensionScore(
            name="evidence_mapping",
            computable_value=0.0,
            combined=0.0,
            evidence=["No hypotheses to map"],
        )

    combined_evidence = " ".join(evidence_texts).lower()
    mapped: list[str] = []
    unmapped: list[str] = []

    for hyp in hypotheses:
        # Extract keywords: split on whitespace, remove stopwords and short tokens
        words = [
            w
            for w in re.findall(r"[a-zA-Z\u4e00-\u9fff]{2,}", hyp.lower())
            if w not in _STOPWORDS_EN
        ]
        if not words:
            unmapped.append(hyp[:50])
            continue

        hits = sum(1 for w in words if w in combined_evidence)
        if hits >= min(3, len(words)):
            mapped.append(hyp[:50])
        else:
            unmapped.append(hyp[:50])

    value = len(mapped) / len(hypotheses)
    evidence_info: list[str] = [f"Mapped {len(mapped)}/{len(hypotheses)} hypotheses"]
    if unmapped:
        evidence_info.append(f"Unmapped: {', '.join(unmapped[:3])}")

    return DimensionScore(
        name="evidence_mapping",
        computable_value=value,
        combined=value,
        evidence=evidence_info,
    )


def specificity(artifacts: list[str]) -> DimensionScore:
    """Compute specificity score based on quantitative terms and proper nouns.

    Quantitative density = count of numeric/percentage tokens / total word count.
    Specificity = min(quantitative_density * 10, 1.0).

    Args:
        artifacts: List of artifact text content.

    Returns:
        DimensionScore with computable_value reflecting content specificity.
    """
    combined = " ".join(artifacts)
    if not combined.strip():
        return DimensionScore(
            name="specificity",
            computable_value=0.0,
            combined=0.0,
            evidence=["No content"],
        )

    words = combined.split()
    total_words = len(words)
    if total_words == 0:
        return DimensionScore(
            name="specificity", computable_value=0.0, combined=0.0, evidence=["No words"]
        )

    # Count quantitative tokens (numbers, percentages)
    quant_count = len(_QUANTITATIVE_RE.findall(combined))
    # Count proper nouns / CamelCase terms
    camel_count = len(_CAMEL_CASE_RE.findall(combined))

    specific_count = quant_count + camel_count
    density = specific_count / total_words
    value = min(density * 10, 1.0)

    return DimensionScore(
        name="specificity",
        computable_value=value,
        combined=value,
        evidence=[
            f"{quant_count} quantitative terms, {camel_count} proper nouns in {total_words} words",
            f"Density: {density:.4f}, Score: {value:.2f}",
        ],
    )


def internal_consistency_keyword(artifacts: list[str]) -> DimensionScore:
    """Keyword-based contradiction scan across artifacts.

    Returns a score where 1.0 = no contradictions found, 0.0 = many contradictions.
    """
    if len(artifacts) < 2:
        return DimensionScore(
            name="internal_consistency",
            computable_value=1.0,
            combined=1.0,
            evidence=["Too few artifacts to check"],
        )

    contradiction_count = 0
    evidence: list[str] = []
    all_keywords = _CONTRADICT_EN | _CONTRADICT_ZH

    for i, a in enumerate(artifacts):
        lower_a = a.lower()
        for kw in all_keywords:
            if kw in lower_a:
                contradiction_count += 1
                evidence.append(f"Artifact {i}: contains '{kw}'")
                break

    # Also check for negation-based contradictions between artifact pairs
    for i in range(len(artifacts)):
        for j in range(i + 1, min(i + 5, len(artifacts))):
            words_i = set(artifacts[i].lower().split())
            words_j = set(artifacts[j].lower().split())
            overlap = words_i & words_j
            if len(overlap) < 3:
                continue
            neg_i = words_i & (_NEGATION_EN | _NEGATION_ZH)
            neg_j = words_j & (_NEGATION_EN | _NEGATION_ZH)
            if neg_i != neg_j and len(overlap) > 5:
                contradiction_count += 1
                evidence.append(f"Artifacts {i},{j}: negation mismatch with shared content")

    # More contradictions → lower score
    value = max(0.0, 1.0 - (contradiction_count * 0.2))
    return DimensionScore(
        name="internal_consistency",
        computable_value=value,
        combined=value,
        evidence=evidence or ["No contradictions detected"],
    )
