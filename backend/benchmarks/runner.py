"""Benchmark runner with ablation configuration."""

from __future__ import annotations

import json
import logging
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

from backend.blackboard.board import Blackboard
from backend.types import (
    AgentRole,
    ArtifactMeta,
    ArtifactType,
    BenchmarkResult,
    BenchmarkTask,
    ResearchPhase,
)

if TYPE_CHECKING:
    from backend.evaluation.evaluator import EvaluatorService

logger = logging.getLogger(__name__)


class AblationConfig(BaseModel):
    """Configuration for ablation experiments."""

    name: str = "baseline"
    use_cross_model: bool = False
    use_multi_dim: bool = False
    use_info_gain: bool = False
    use_computable: bool = True
    use_llm_eval: bool = True


# Preset ablation configurations
ABLATION_PRESETS: dict[str, AblationConfig] = {
    "baseline": AblationConfig(
        name="baseline",
        use_cross_model=False,
        use_multi_dim=False,
        use_info_gain=False,
    ),
    "cross_model_only": AblationConfig(
        name="cross_model_only",
        use_cross_model=True,
        use_multi_dim=False,
        use_info_gain=False,
    ),
    "multi_dim_only": AblationConfig(
        name="multi_dim_only",
        use_cross_model=False,
        use_multi_dim=True,
        use_info_gain=False,
    ),
    "full_system": AblationConfig(
        name="full_system",
        use_cross_model=True,
        use_multi_dim=True,
        use_info_gain=True,
    ),
    "no_computable": AblationConfig(
        name="no_computable",
        use_cross_model=True,
        use_multi_dim=True,
        use_info_gain=True,
        use_computable=False,
    ),
    "no_llm_eval": AblationConfig(
        name="no_llm_eval",
        use_cross_model=False,
        use_multi_dim=True,
        use_info_gain=True,
        use_llm_eval=False,
    ),
}


class BenchmarkRunner:
    """Load and execute benchmark tasks against the evaluation engine."""

    def __init__(
        self,
        evaluator: EvaluatorService,
        tasks_dir: Path | None = None,
    ) -> None:
        self._evaluator = evaluator
        self._tasks_dir = tasks_dir or Path(__file__).parent / "tasks"

    def load_tasks(self) -> list[BenchmarkTask]:
        """Load all benchmark tasks from JSON files in tasks_dir."""
        tasks: list[BenchmarkTask] = []
        if not self._tasks_dir.exists():
            logger.warning("Benchmark tasks directory not found: %s", self._tasks_dir)
            return tasks

        for f in sorted(self._tasks_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                tasks.append(BenchmarkTask(**data))
            except Exception:
                logger.exception("Failed to load benchmark task: %s", f)
        return tasks

    async def run_task(
        self,
        task: BenchmarkTask,
        config: AblationConfig | None = None,
    ) -> BenchmarkResult:
        """Run a single benchmark task and return the result."""
        config = config or ABLATION_PRESETS["baseline"]
        start = time.monotonic()

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                board = await self._setup_temp_board(task, Path(tmp_dir))
                phase = ResearchPhase(task.phase)

                evaluation = await self._evaluator.evaluate_phase(
                    board,
                    phase,
                    generator_model="deepseek-chat",
                    use_cross_model=config.use_cross_model,
                    use_multi_dim=config.use_multi_dim,
                    use_computable=config.use_computable,
                    use_llm_eval=config.use_llm_eval,
                )
                contradictions = await self._evaluator.evaluate_contradictions(board)

                # Check information gain if enabled
                convergence_metric = None
                if config.use_info_gain:
                    for art in task.input_artifacts:
                        content = art.get("content", "")
                        if content:
                            convergence_metric = self._evaluator.check_information_gain(content)

                duration = time.monotonic() - start
                return BenchmarkResult(
                    task_id=task.task_id,
                    config_name=config.name,
                    evaluation=evaluation,
                    contradictions_found=contradictions,
                    convergence_metric=convergence_metric,
                    duration_seconds=duration,
                )

        except Exception as exc:
            duration = time.monotonic() - start
            logger.exception("Benchmark task %s failed", task.task_id)
            return BenchmarkResult(
                task_id=task.task_id,
                config_name=config.name,
                duration_seconds=duration,
                error=str(exc),
            )

    async def run_all(
        self,
        config: AblationConfig | None = None,
    ) -> list[BenchmarkResult]:
        """Run all benchmark tasks with the given config."""
        tasks = self.load_tasks()
        results: list[BenchmarkResult] = []
        for task in tasks:
            result = await self.run_task(task, config)
            results.append(result)
        return results

    async def run_ablation_suite(self) -> dict[str, list[BenchmarkResult]]:
        """Run all tasks under each ablation preset."""
        suite_results: dict[str, list[BenchmarkResult]] = {}
        for name, config in ABLATION_PRESETS.items():
            suite_results[name] = await self.run_all(config)
        return suite_results

    async def _setup_temp_board(self, task: BenchmarkTask, tmp_dir: Path) -> Blackboard:
        """Create a temporary blackboard with task artifacts."""
        board = Blackboard(tmp_dir)
        await board.init_workspace(research_topic=task.research_topic)

        for i, art_data in enumerate(task.input_artifacts):
            art_type_str = art_data.get("artifact_type", "evidence_findings")
            try:
                art_type = ArtifactType(art_type_str)
            except ValueError:
                art_type = ArtifactType.EVIDENCE_FINDINGS

            artifact_id = art_data.get("artifact_id", f"bench-{i:03d}")
            content = art_data.get("content", "")
            if isinstance(content, dict):
                content = json.dumps(content, ensure_ascii=False)

            meta = ArtifactMeta(
                artifact_type=art_type,
                artifact_id=artifact_id,
                version=1,
                created_by=AgentRole(art_data.get("created_by", "scientist")),
            )
            await board.write_artifact(art_type, artifact_id, 1, content, meta)

        return board
