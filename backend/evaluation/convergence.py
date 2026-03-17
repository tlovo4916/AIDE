"""Information gain detection for convergence monitoring."""

from __future__ import annotations

from backend.config import settings
from backend.evaluation.metrics import jaccard_similarity
from backend.types import InformationGainMetric


class InformationGainDetector:
    """Track information novelty across iterations to detect diminishing returns."""

    def __init__(self) -> None:
        self._history: list[str] = []
        self._word_sets: list[set[str]] = []

    def add_iteration(self, content: str) -> None:
        """Record content from one iteration."""
        self._history.append(content)
        self._word_sets.append(set(content.lower().split()))

    def compute(self) -> InformationGainMetric:
        """Compute information gain for the latest iteration."""
        n = len(self._history)
        if n == 0:
            return InformationGainMetric(iteration=0)
        if n == 1:
            return InformationGainMetric(
                iteration=1,
                information_gain=1.0,
                artifact_count_delta=1,
                unique_claim_delta=len(self._word_sets[0]),
            )

        # New words not seen in any previous iteration
        prev_words: set[str] = set()
        for ws in self._word_sets[:-1]:
            prev_words |= ws

        current_words = self._word_sets[-1]
        new_words = current_words - prev_words
        gain = len(new_words) / len(current_words) if current_words else 0.0

        return InformationGainMetric(
            iteration=n,
            information_gain=gain,
            unique_claim_delta=len(new_words),
            is_diminishing=self.detect_diminishing_returns(),
            is_loop_detected=self.detect_loop(),
        )

    def detect_diminishing_returns(
        self,
        window: int | None = None,
        threshold: float | None = None,
    ) -> bool:
        """Check if recent iterations show diminishing information gain.

        Uses a sliding window to compute average novelty ratio.
        """
        window = window if window is not None else settings.eval_info_gain_window
        threshold = threshold if threshold is not None else settings.eval_info_gain_threshold
        n = len(self._word_sets)
        if n < 2:
            return False

        effective_window = min(window, n - 1)
        gains: list[float] = []

        for i in range(n - effective_window, n):
            if i <= 0:
                continue
            prev_all: set[str] = set()
            for ws in self._word_sets[:i]:
                prev_all |= ws
            current = self._word_sets[i]
            new = current - prev_all
            gain = len(new) / len(current) if current else 0.0
            gains.append(gain)

        if not gains:
            return False
        avg_gain = sum(gains) / len(gains)
        return avg_gain < threshold

    def detect_loop(self, threshold: float | None = None) -> bool:
        """Detect if recent iterations are repeating (high Jaccard between consecutive)."""
        threshold = threshold if threshold is not None else settings.eval_loop_jaccard_threshold
        n = len(self._history)
        if n < 2:
            return False

        sim = jaccard_similarity(self._history[-1], self._history[-2])
        return sim >= threshold

    def reset(self) -> None:
        """Clear history on phase transition."""
        self._history.clear()
        self._word_sets.clear()
