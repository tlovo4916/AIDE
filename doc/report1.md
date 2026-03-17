# Phase 1 (Foundation) + Phase 3 (Evaluation Engine) 审计报告

> 审计日期：2026-03-17 | 审计人：Claude Opus 4.6
>
> 范围：`backend/evaluation/`、`backend/benchmarks/`、`backend/models/{evaluation,iteration_metric,claim}.py`、`backend/tests/test_evaluation.py`、`backend/tests/test_improvements.py` 中评估相关部分

---

## 1. 总体评价

| 维度 | 评级 | 说明 |
|------|------|------|
| **架构符合度** | ✅ 良好 | 核心设计（多维评估、交叉模型、Claim提取、信息增益、Benchmark框架）均已实现 |
| **代码质量** | ✅ 良好 | 模块化清晰、类型完整、错误处理健壮 |
| **测试覆盖** | ✅ 优秀 | 50 个测试全部通过，覆盖 8 个模块、正常路径/边界/异常 |
| **Lint** | ✅ 通过 | `ruff check` 零错误零警告 |
| **集成状态** | ⚠️ 未集成 | 评估引擎已实现但未接入主循环，ORM 模型未使用 |
| **Ablation 有效性** | ❌ 失效 | 配置标志已定义但 runner 未检查，消融实验无效 |

---

## 2. 测试结果

```
backend/tests/test_evaluation.py ................ 50 passed (0.49s)
backend/tests/test_improvements.py (convergence) . 5 passed (0.65s)
ruff check backend/evaluation/ backend/benchmarks/ → All checks passed!
```

### 测试矩阵

| 测试类 | 用例数 | 覆盖范围 |
|--------|--------|----------|
| `TestComputableMetrics` | 16 | 6 个指标 + jaccard，含中英文 |
| `TestClaimExtractor` | 4 | 正常提取、中文、畸形响应、LLM异常 |
| `TestContradictionDetector` | 5 | 关键词(中/英)、LLM、去重、误报控制 |
| `TestInformationGainDetector` | 6 | 新内容、衰减、环路、窗口、重置、单次 |
| `TestEvaluatorService` | 6 | 模型选择、phase评估、保存、矛盾、信息增益 |
| `TestBenchmarkRunner` | 4 | 加载任务、执行、board搭建、消融配置 |
| `TestBenchmarkScorer` | 5 | 范围内/外评分、F1、报告结构 |
| `TestDimensions` | 4 | EXPLORE/COMPOSE/fallback、权重和 |
| `TestConvergence` (improvements) | 5 | per-phase 阈值、max-iter、artifact覆盖、EMA |

---

## 3. 架构符合度逐项对照

### 3.1 Phase 1: Foundation — 相关部分

| 架构要求 | 状态 | 详情 |
|----------|------|------|
| 新 ORM 表：`evaluation_results` | ✅ 已实现 | `backend/models/evaluation.py:EvaluationResult` |
| 新 ORM 表：`knowledge_state` | ✅ 已实现 | `backend/models/evaluation.py:KnowledgeState` |
| 新 ORM 表：`iteration_metrics` | ✅ 已实现 | `backend/models/iteration_metric.py:IterationMetric` |
| 新 ORM 表：`claims` + `contradictions` | ✅ 已实现 | `backend/models/claim.py` |
| 表注册到 `models/__init__.py` | ✅ 已注册 | 全部 import 并加入 `__all__` |
| Alembic 迁移覆盖 | ✅ 已有 | `002_phase1_tables.py` 包含这些表 |
| Feature flag `use_multi_eval` | ✅ 已定义 | `config.py` 中存在但默认 False |

### 3.2 Phase 3: Evaluation Engine

| 架构要求 | 状态 | 差异说明 |
|----------|------|----------|
| **多维质量评估** | ✅ 实现 | 5 phase × 4 维度，权重和=1.0 |
| **DimensionScore 数据模型** | ✅ 完全匹配 | `types.py:276-282`，含 computable/llm/combined/weight/evidence |
| **PhaseEvaluation 数据模型** | ✅ 完全匹配 | `types.py:285-292` |
| **Composite Score 公式** | ✅ 正确 | `Σ(combined×weight)/Σ(weight)` — `evaluator.py:135` |
| **Mixed 维度加权** | ✅ 正确 | `0.6×computable + 0.4×llm`，使用 config 中的 `eval_computable_weight/eval_llm_weight` |
| **EXPLORE 维度** | ✅ 匹配 | coverage_breadth(可计算), source_diversity(可计算), terminology_coverage(可计算), gap_identification(LLM) |
| **HYPOTHESIZE 维度** | ✅ 匹配 | specificity(混合), novelty(LLM), logical_coherence(LLM), coverage_breadth(可计算) |
| **EVIDENCE 维度** | ✅ 匹配 | citation_density(可计算), evidence_mapping(混合), methodological_rigor(LLM), source_diversity(可计算) |
| **COMPOSE 维度** | ✅ 匹配 | structural_completeness(可计算), argument_flow(LLM), citation_integration(混合), internal_consistency(可计算) |
| **SYNTHESIZE 维度** | ✅ 额外添加 | 架构未显式定义，实现添加了 SYNTHESIZE phase 的维度定义（合理扩展） |
| **交叉模型评估** | ✅ 实现 | `_CROSS_MODEL_MAP` + API key 可用性检查 + fallback |
| **交叉模型矩阵** | ⚠️ 部分 | 架构定义 4 条映射，实现只有 2 条（deepseek-reasoner→claude, deepseek-chat→reasoner）；claude→deepseek 通过 `startswith("claude-")` 分支处理 |
| **ClaimExtractor** | ✅ 实现 | 4000 char cap，JSON mode，safe_json_loads |
| **ContradictionDetector** | ✅ 实现 | keyword + LLM 双路径 + 去重 |
| **信息增益检测** | ⚠️ 简化 | 架构要求基于 embedding 余弦相似度；实现使用词集差异比率 |
| **环路检测** | ⚠️ 简化 | 架构要求 claim 指纹重复率；实现使用 Jaccard 文本相似度 |
| **收敛枯竭检测** | ✅ 实现 | 滑动窗口平均增益 < threshold |
| **Benchmark 框架** | ✅ 实现 | runner + scorer + 5 个 gold standard 任务 |
| **Ablation 配置** | ⚠️ 定义但失效 | 6 个 preset 已定义，但 `run_task()` 未根据配置标志调整评估行为 |
| **Gold standard 格式** | ⚠️ 简化 | 架构要求嵌套 `expected_score_range`/`expected_covered_subtopics`；实现使用扁平 `[low, high]` 数组 |
| **LLM 评估 Prompt** | ⚠️ 简化 | 架构要求结构化 prompt（含 criteria、finding/artifact_ref/impact、missing、score 阈值约束）；实现使用简单的 score+evidence prompt |
| **Claims 持久化到 DB** | ❌ 未实现 | Claim 仅存在于内存，未写入 `claims` 表 |
| **矛盾解决机制** | ❌ 未实现 | 架构要求 Agent 介入解决、3 次后标记 limitation、收敛阻断 |
| **评估结果写入 DB** | ❌ 未实现 | 仅写入文件系统 JSON，未写入 `evaluation_results` 表 |
| **信息增益基于 embedding** | ❌ 未实现 | 使用词集差异而非余弦相似度 |

---

## 4. 已发现缺陷

### P0 — 设计缺陷（影响功能正确性）

#### D01: Ablation 配置标志未生效
**位置**: `backend/benchmarks/runner.py:110-145`

`AblationConfig` 定义了 5 个控制开关（`use_cross_model`, `use_multi_dim`, `use_computable`, `use_llm_eval`, `use_info_gain`），但 `run_task()` 仅检查了 `use_info_gain`（第131行）。其余 4 个标志被完全忽略：
- `use_cross_model` → `evaluate_phase()` 总是启用交叉模型
- `use_multi_dim` → 总是使用多维评估
- `use_computable` → 总是运行可计算指标
- `use_llm_eval` → 总是运行 LLM 评估

**影响**: `run_ablation_suite()` 在 6 种配置下运行，但实际行为完全相同（除 info_gain 外），消融实验结论无效。

**建议修复**: `run_task()` 需要将 config 标志传递给 `EvaluatorService`，或在 `EvaluatorService` 增加开关参数。

---

#### D02: ORM 模型已定义但从未使用
**位置**: `backend/models/evaluation.py`, `backend/models/iteration_metric.py`, `backend/models/claim.py`

3 组 ORM 模型（`EvaluationResult`, `KnowledgeState`, `IterationMetric`, `Claim`, `Contradiction`）已定义并注册，对应的表结构通过 Alembic 创建，但：
- 没有任何代码向这些表写入数据
- `EvaluatorService.save_results()` 仅保存为文件系统 JSON
- `ClaimExtractor.extract()` 返回 Pydantic model，不是 ORM 实例
- `InformationGainDetector` 仅使用内存 list

**影响**: 评估结果不可持久化、不可跨运行查询、不可用于趋势分析。

---

### P1 — 与架构设计的偏差

#### D03: 信息增益使用词集差异而非 embedding 余弦相似度
**位置**: `backend/evaluation/convergence.py:34-41`

架构设计明确要求：
```
IG(iteration) = mean(1.0 - max_sim(a) for a in new_artifacts)
```
（基于 embedding 余弦相似度）

实现使用：
```python
new_words = current_words - prev_words
gain = len(new_words) / len(current_words)
```
（词集差异比率）

**影响**: 词集方法无法检测语义近似但措辞不同的重复内容。"apple" 和 "apples" 被视为不同词。

---

#### D04: 环路检测使用 Jaccard 而非 Claim 指纹
**位置**: `backend/evaluation/convergence.py:79-86`

架构要求基于归一化 claim 三元组的指纹重复率检测环路。实现仅使用原始文本的 Jaccard 相似度。

**影响**: 换用同义词/不同表述的循环内容无法被检测到。

---

#### D05: LLM 评估 Prompt 缺少结构化约束
**位置**: `backend/evaluation/evaluator.py:48-62`

架构设计要求：
- 包含 `dimension_specific_criteria`
- 输出格式含 `finding/artifact_ref/impact` 结构化证据
- `missing` 列表
- Score 阈值约束（>0.7 需 ≥3 正面证据，<0.3 需 ≥2 缺失项）

实现仅要求 `{"score": float, "evidence": ["..."]}` — 评分无外部锚定。

---

#### D06: 交叉模型矩阵不完整
**位置**: `backend/evaluation/evaluator.py:43-46`

架构定义了 4 条映射（含 claude-opus→deepseek-reasoner, claude-sonnet→deepseek-reasoner），实现只有 2 条显式映射。虽然 `startswith("claude-")` 分支覆盖了 claude→deepseek 路径，但缺少 `claude-opus-4-6` 的显式映射意味着所有 Claude 模型使用同一个 evaluator。

---

### P2 — 代码质量问题

#### D07: `EvaluationResult` ORM 字段与 `PhaseEvaluation` Pydantic 模型不匹配
**位置**: `backend/models/evaluation.py:30` vs `backend/types.py:288`

ORM `EvaluationResult` 有 `evaluator_role: str(50)` 字段（暗示 Agent 角色），但 `PhaseEvaluation` 没有 `evaluator_role`，只有 `evaluator_model`。ORM 也缺少 `evaluator_model` 字段。若未来集成时会导致映射困难。

| ORM `EvaluationResult` | Pydantic `PhaseEvaluation` | 匹配 |
|---|---|---|
| `evaluator_role` | — | ❌ |
| — | `evaluator_model` | ❌ |
| `scores` (JSON) | `dimensions` (dict) | ⚠️ 名称不同 |
| `overall_score` | `composite_score` | ⚠️ 名称不同 |
| `feedback` (Text) | `raw_evidence` (dict) | ⚠️ 类型不同 |

---

#### D08: `KnowledgeState` ORM 缺少架构要求的字段
**位置**: `backend/models/evaluation.py:39-55`

架构定义的 `knowledge_state` 表包含 `gap_count` 和 `gap_descriptions` 字段。ORM 模型缺少这两个字段，但有 `snapshot` (JSON) 可能用于存储。

---

#### D09: `IterationMetric` ORM 缺少 `information_gain` 字段
**位置**: `backend/models/iteration_metric.py`

架构的 `iteration_metrics` 表包含 `information_gain`, `artifact_count_delta`, `unique_claim_delta`, `eval_composite` 字段。ORM 模型有 `agent_role`, `duration_seconds`, `tokens_used`, `artifacts_produced`, `critic_score` — 完全不同的字段集。

| 架构定义 | ORM 实现 | 匹配 |
|---|---|---|
| `information_gain: FLOAT` | — | ❌ |
| `artifact_count_delta: INTEGER` | — | ❌ |
| `unique_claim_delta: INTEGER` | — | ❌ |
| `eval_composite: FLOAT` | — | ❌ |
| — | `agent_role: str(50)` | 额外 |
| — | `duration_seconds: float` | 额外 |
| — | `tokens_used: int` | 额外 |
| — | `artifacts_produced: int` | 额外 |
| — | `critic_score: float` | 额外 |

---

#### D10: `datetime.utcnow()` 弃用警告
**位置**: `backend/evaluation/evaluator.py:98`, `backend/types.py`（多处）

Python 3.12 中 `datetime.utcnow()` 已弃用。测试输出中有 16 个相关警告。应使用 `datetime.now(datetime.UTC)`。

---

#### D11: `_extract_subtopics()` 过于简陋
**位置**: `backend/evaluation/evaluator.py:291-308`

仅使用 `topic.split()` 分词。英文研究主题 "Transformer attention mechanisms in computer vision" 会产出无用子主题如 "in"、"for"。中文主题则几乎无法分词。

架构设计期望 TF-IDF 聚类或子主题分解。

---

### P3 — 轻微问题

#### D12: Benchmark runner 顺序执行
**位置**: `backend/benchmarks/runner.py:157-167, 169-174`

`run_all()` 和 `run_ablation_suite()` 使用顺序 for 循环。每个任务创建独立的临时 board，可以安全并行。6 个 ablation × 5 个 task = 30 次串行执行。

#### D13: Gold standard 格式简化
**位置**: `backend/benchmarks/tasks/*.json`

`expected_evaluation` 使用扁平 `[low, high]` 数组而非架构要求的嵌套结构（含 `expected_covered_subtopics`）。评分器可以工作，但丢失了对子主题覆盖的细粒度验证。

#### D14: 矛盾 F1 Jaccard 阈值硬编码
**位置**: `backend/benchmarks/scorer.py:82`

匹配阈值 0.3 硬编码，且偏低 — 即使 30% 的词重叠就认为匹配成功。

---

## 5. 测试覆盖差距分析

### 已覆盖

- 所有 6 个可计算指标（含中英文、边界值）
- Claim 提取（正常、异常、中文）
- 矛盾检测（关键词、LLM、去重）
- 信息增益（新内容、衰减、环路、窗口、重置）
- EvaluatorService（模型选择、phase 评估、保存、矛盾、信息增益）
- BenchmarkRunner（加载、执行、board 搭建、配置）
- BenchmarkScorer（范围评分、F1、报告）
- Dimensions（phase 维度、权重和、fallback）

### 未覆盖

| 场景 | 优先级 | 说明 |
|------|--------|------|
| Mixed 维度评估 | P1 | `evaluate_phase()` 中 mixed 路径（computable+LLM 加权合并）未被测试覆盖 |
| Ablation 配置实际生效 | P1 | 测试仅验证配置存在，未验证标志影响评估行为 |
| 大量 artifact 性能 | P2 | `_collect_artifacts()` 遍历所有 `ArtifactType` 枚举值 |
| 并发安全 | P2 | `InformationGainDetector` 使用内存 list，无锁 |
| `_extract_subtopics` 中文 | P2 | 中文 topic 的 `.split()` 行为未测试 |
| `contradiction_f1` 偏序匹配 | P3 | 当检测到的矛盾数 ≠ 预期数时的行为 |
| `save_results` 文件名冲突 | P3 | 同一秒内两次保存 |

---

## 6. Benchmark 任务质量评估

| 任务 ID | Phase | 语言 | 质量 | 备注 |
|---------|-------|------|------|------|
| `explore_coverage` | EXPLORE | 英文 | ✅ 好 | 3 篇真实论文引用，3 arxiv 域名提供 source diversity |
| `hypothesis_novelty` | HYPOTHESIZE | 中文 | ✅ 好 | 测试中文分词路径 |
| `evidence_mapping` | EVIDENCE | 英文 | ✅ 好 | 4 evidence + 2 hypotheses，含多种引用格式 |
| `compose_structure` | COMPOSE | 中文 | ✅ 好 | ~11KB 完整论文草稿，覆盖全部 section header |
| `contradiction_detection` | EVIDENCE | 英文 | ✅ 优 | 2 对精心设计的矛盾（关键词级 + 语义级） |

任务覆盖了 4 个 phase、中英双语、多种指标类型。`contradiction_detection` 的矛盾对设计尤其精巧。

**缺失**: 无 SYNTHESIZE phase 的 benchmark 任务。

---

## 7. 建议修复优先级

| 优先级 | 缺陷 | 建议行动 |
|--------|------|----------|
| **P0** | D01 Ablation 标志未生效 | `run_task()` 传递 config 给 `EvaluatorService`，或在 `EvaluatorService` 增加开关参数 |
| **P1** | D02 ORM 未使用 | 在 `EvaluatorService` 中增加 DB 写入，或标记为 Phase 2 集成任务 |
| **P1** | D03 信息增益非 embedding | 接入 `EmbeddingService`，使用余弦相似度替代词集差异 |
| **P1** | D05 LLM Prompt 缺约束 | 增加 dimension-specific criteria 和 score 阈值约束 |
| **P1** | D07/D08/D09 ORM 字段不匹配 | 对齐 ORM 和 Pydantic 模型字段 |
| **P2** | D10 datetime 警告 | 全局替换 `utcnow()` → `now(UTC)` |
| **P2** | D11 subtopic 分词 | 至少增加停用词过滤 + 中文 jieba 分词 |
| **P3** | D04 环路检测简化 | 未来 Phase 集成 claim 指纹时一并升级 |
| **P3** | D06 交叉模型矩阵 | 补全 claude-opus 显式映射 |
| **P3** | D12 串行执行 | `asyncio.gather()` 并行化 |
| **P3** | D13/D14 格式/阈值 | 丰富 gold standard 格式，阈值提取为参数 |

---

## 8. 总结

Phase 3 Evaluation Engine 的核心架构已正确实现：多维评估、交叉模型验证、Claim 提取与矛盾检测、信息增益收敛、Benchmark 框架与 Gold Standard 测试用例。代码质量良好，测试覆盖优秀（50 测试全部通过，Lint 零错误）。

**主要风险**在于：
1. **Ablation 实验无效**（P0）— 这是最关键的问题，6 种配置实际运行结果相同
2. **未与主循环集成** — 评估引擎独立可用但未接入 `OrchestrationEngine`
3. **ORM ↔ Pydantic 模型不对齐** — 未来集成时会引发额外的映射工作

建议优先修复 D01（Ablation 失效），然后统一 ORM/Pydantic 字段定义，最后在 Phase 4 实现时将评估引擎接入主循环。
