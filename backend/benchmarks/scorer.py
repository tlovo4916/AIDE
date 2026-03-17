"""Benchmark scorer -- compare results against gold standard expectations."""

from __future__ import annotations

from backend.config import settings
from backend.evaluation.metrics import jaccard_similarity
from backend.types import BenchmarkResult, BenchmarkTask, Contradiction


class BenchmarkScorer:
    """Score benchmark results against expected gold standard values."""

    def score_result(self, result: BenchmarkResult, task: BenchmarkTask) -> BenchmarkResult:
        """Compare a benchmark result against the task's expected values.

        Sets result.passed = True if all dimension scores fall within expected ranges.
        """
        if result.error:
            result.passed = False
            return result

        if not result.evaluation:
            result.passed = False
            return result

        expected = task.expected_evaluation
        if not expected:
            result.passed = True
            return result

        # Check each expected dimension range
        all_pass = True
        for dim_key, expected_range in expected.items():
            if dim_key == "subtopics":
                continue
            if not isinstance(expected_range, list) or len(expected_range) != 2:
                continue

            low, high = expected_range
            actual = result.evaluation.dimensions.get(dim_key)
            if actual is None:
                all_pass = False
                continue
            if not (low <= actual.combined <= high):
                all_pass = False

        # Check contradiction expectations if present
        if task.expected_contradictions:
            _, _, f1 = self.contradiction_f1(
                result.contradictions_found,
                task.expected_contradictions,
            )
            if f1 < 0.5:
                all_pass = False

        result.passed = all_pass
        return result

    @staticmethod
    def contradiction_f1(
        detected: list[Contradiction],
        expected: list[dict],
    ) -> tuple[float, float, float]:
        """Compute precision, recall, F1 for contradiction detection.

        Matches detected contradictions to expected ones using Jaccard similarity
        on claim text.
        """
        if not expected:
            return (1.0, 1.0, 1.0) if not detected else (0.0, 1.0, 0.0)
        if not detected:
            return (0.0, 0.0, 0.0)

        matched_expected: set[int] = set()
        matched_detected: set[int] = set()

        for i, det in enumerate(detected):
            det_text = f"{det.claim_a.text} {det.claim_b.text}"
            for j, exp in enumerate(expected):
                if j in matched_expected:
                    continue
                exp_text = f"{exp.get('claim_a', '')} {exp.get('claim_b', '')}"
                if jaccard_similarity(det_text, exp_text) > settings.eval_contradiction_threshold:
                    matched_expected.add(j)
                    matched_detected.add(i)
                    break

        precision = len(matched_detected) / len(detected) if detected else 0.0
        recall = len(matched_expected) / len(expected) if expected else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        return (precision, recall, f1)

    @staticmethod
    def score_accuracy(
        scores: dict[str, float],
        expected: dict[str, list[float]],
    ) -> dict[str, bool]:
        """Check each dimension score against expected [low, high] range."""
        results: dict[str, bool] = {}
        for dim, expected_range in expected.items():
            if not isinstance(expected_range, list) or len(expected_range) != 2:
                continue
            low, high = expected_range
            actual = scores.get(dim, 0.0)
            results[dim] = low <= actual <= high
        return results

    @staticmethod
    def generate_report(results: list[BenchmarkResult]) -> dict:
        """Generate aggregate report from benchmark results."""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        errors = [r for r in results if r.error]

        by_config: dict[str, dict] = {}
        for r in results:
            if r.config_name not in by_config:
                by_config[r.config_name] = {"total": 0, "passed": 0, "failed": 0}
            by_config[r.config_name]["total"] += 1
            if r.passed:
                by_config[r.config_name]["passed"] += 1
            else:
                by_config[r.config_name]["failed"] += 1

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / total if total > 0 else 0.0,
            "errors": len(errors),
            "by_config": by_config,
            "task_results": [
                {
                    "task_id": r.task_id,
                    "config": r.config_name,
                    "passed": r.passed,
                    "duration": r.duration_seconds,
                    "error": r.error,
                }
                for r in results
            ],
        }
