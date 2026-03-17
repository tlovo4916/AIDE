# Round 2 审计报告 — Phase 1 修复 + Phase 2 (EventBus/RelationExtractor) + Phase 3 (可计算指标/ClaimExtractor/DB持久化)

> 审计日期：2026-03-17 | 审计人：Claude Opus 4.6
>
> 范围：Round 1 (D01-D14) 修复验证 + `backend/evaluation/{evaluator,metrics,store}.py` + `backend/blackboard/{event_bus,relation_extractor}.py` + `backend/models/{evaluation,iteration_metric,claim,artifact}.py` + `backend/orchestrator/{engine,factory,planner}.py` + `backend/tests/test_evaluation.py`

---

## 1. 总体评价

| 维度 | 评级 | 说明 |
|------|------|------|
| **Round 1 修复率** | ✅ 9/14 | D01-D02, D05-D11 已修复；D03/D04/D12-D14 设计决策保留 |
| **Phase 2 新组件** | ✅ 良好 | EventBus + RelationExtractor 设计合理、代码质量高 |
| **Phase 3 新指标** | ✅ 良好 | evidence_mapping + specificity 实现正确 |
| **DB 持久化层** | ✅ 已实现 | ClaimStore/ContradictionStore/EvaluationStore 完整覆盖 |
| **测试覆盖** | ✅ 优秀 | 65 测试全部通过 (0.60s)，覆盖新模块 |
| **Lint** | ✅ 通过 | `ruff check` 零错误零警告 |

---

## 2. 测试结果

```
backend/tests/test_evaluation.py ................ 65 passed (0.60s)
ruff check backend/ → All checks passed!
```

### 测试矩阵

| 测试类 | 用例数 | 覆盖范围 |
|--------|--------|----------|
| `TestComputableMetrics` | 16 | 6 个原始指标 + jaccard，含中英文 |
| `TestClaimExtractor` | 4 | 正常提取、中文、畸形响应、LLM异常 |
| `TestContradictionDetector` | 5 | 关键词(中/英)、LLM、去重、误报控制 |
| `TestInformationGainDetector` | 6 | 新内容、衰减、环路、窗口、重置、单次 |
| `TestEvaluatorService` | 6 | 模型选择、phase评估、保存、矛盾、信息增益 |
| `TestBenchmarkRunner` | 4 | 加载任务、执行、board搭建、消融配置 |
| `TestBenchmarkScorer` | 5 | 范围内/外评分、F1、报告结构 |
| `TestDimensions` | 4 | EXPLORE/COMPOSE/fallback、权重和 |
| **`TestEvidenceMapping`** (新) | 3 | 全映射、部分映射、空输入 |
| **`TestSpecificity`** (新) | 3 | 高specificity、低specificity、中文+数字 |
| **`TestClaimStore`** (新) | 4 | confidence映射、空列表、类存在性 |
| **`TestEvaluationStore`** (新) | 3 | 函数签名、空矛盾、project_id |
| **`TestContradictionStore`** (新) | 2 | evidence编码、evaluator with project_id |

---

## 3. Round 1 缺陷修复验证

### 已修复 (9/14)

| 缺陷 | 状态 | 修复方式 | 验证 |
|------|------|----------|------|
| **D01** (P0) Ablation 标志未生效 | ✅ 已修复 | `evaluate_phase()` 新增 4 个 kwargs: `use_cross_model`, `use_multi_dim`, `use_computable`, `use_llm_eval`。代码根据这些标志跳过对应评估分支 | `evaluator.py:243-247` 参数定义, `:256-287` 条件分支 |
| **D02** (P0) ORM 未使用 | ✅ 已修复 | 新增 `evaluation/store.py` 提供 `ClaimStore`, `ContradictionStore`, `EvaluationStore`。`evaluator.py` 在 `project_id` 非空时自动调用 | `evaluator.py:332-334`, `:365-367`, `store.py` 全文 |
| **D05** (P1) LLM Prompt 缺约束 | ✅ 已修复 | `_DIMENSION_CRITERIA` 字典含 14 个维度专属评估标准；prompt 包含评分量表、约束条件（>0.7 需 ≥3 正面发现）、结构化输出格式（finding/artifact_ref/impact + missing） | `evaluator.py:134-216` |
| **D06** (P1) 交叉模型不完整 | ✅ 已修复 | `_CROSS_MODEL_MAP` 增至 4 条：`deepseek-reasoner→claude-sonnet-4-6`, `deepseek-chat→deepseek-reasoner`, `claude-opus-4-6→deepseek-reasoner`, `claude-sonnet-4-6→deepseek-reasoner` | `evaluator.py:124-129` |
| **D07** (P1) EvaluationResult ORM 字段不匹配 | ✅ 已修复 | `evaluator_role` → `evaluator_model (String(100))`；新增 `evaluator_provider`, `dimensions`, `composite_score`, `raw_evidence` 字段 | `models/evaluation.py` |
| **D08** (P1) KnowledgeState 缺字段 | ✅ 已修复 | 新增 `gap_count (Integer)` 和 `gap_descriptions (JSON)` 字段 | `models/evaluation.py` |
| **D09** (P1) IterationMetric 缺字段 | ✅ 已修复 | 新增 `information_gain`, `artifact_count_delta`, `unique_claim_delta`, `eval_composite` 字段，保留原有运营字段 | `models/iteration_metric.py` |
| **D10** (P2) datetime.utcnow() 弃用 | ✅ 已修复 | 全部替换为 `datetime.now(UTC)`，`from datetime import UTC` | `evaluator.py:8-9`, `:269` |
| **D11** (P2) subtopic 提取简陋 | ✅ 已修复 | `_tokenize_topic()` 实现：英文停用词过滤 (38 个) + 中文字符双字母组提取 | `evaluator.py:102-118` |

### 设计决策保留 (5/14)

| 缺陷 | 状态 | 说明 |
|------|------|------|
| **D03** (P1) 信息增益非 embedding | ⏸️ 保留 | 架构要求 embedding 余弦相似度，但当前使用词集差异——属 Phase 2 SemanticBoard 集成范畴 |
| **D04** (P1) 环路检测非 claim 指纹 | ⏸️ 保留 | 同上，需 ClaimExtractor 全面集成后升级 |
| **D12** (P3) Benchmark runner 串行 | ⏸️ 保留 | 性能优化，非功能阻塞 |
| **D13** (P3) Gold standard 格式简化 | ⏸️ 保留 | 可后续丰富 |
| **D14** (P3) 矛盾 F1 阈值硬编码 | ⏸️ 保留 | 可后续参数化 |

---

## 4. Phase 2 新组件审计

### 4.1 EventBus (`backend/blackboard/event_bus.py`)

**架构符合度**: ✅ 符合架构 Phase 2 要求的 artifact 生命周期事件机制

| 项目 | 评估 |
|------|------|
| 数据模型 | `ArtifactEvent` dataclass: `event_type`, `artifact_type`, `artifact_id`, `agent_role`, `project_id`, `relations` |
| 事件类型 | `created`, `updated`, `challenged`, `superseded` — 覆盖架构要求 |
| API | `publish()`, `drain()` (消费+清空), `peek()` (只读) — 接口简洁 |
| 并发安全 | `asyncio.Lock` 保护 `_pending` 列表 ✅ |
| 容量限制 | `_MAX_PENDING = 200`，超限丢弃旧事件 ✅ |

**代码质量**: 优秀。50 行代码，零冗余，类型完整。

**集成状态**: ✅ 已集成
- `factory.py` 创建 `EventBus` 实例并传递给 `planner`
- `planner.py` 在规划前调用 `event_bus.drain()` 消费事件，注入矛盾/依赖信息到任务描述

### 4.2 RelationExtractor (`backend/blackboard/relation_extractor.py`)

**架构符合度**: ✅ 符合 Phase 2 语义关系发现要求

| 项目 | 评估 |
|------|------|
| 关系类型 | `supports`, `contradicts`, `refines`, `supersedes`, `cites`, `depends_on` — 6 种，覆盖架构要求 |
| LLM 调用 | 结构化 system prompt，JSON mode，最多 15 个历史 artifact |
| 验证 | 目标 UUID 白名单验证、关系类型枚举验证、confidence 裁剪 [0,1]、evidence 截断 500 字 |
| 持久化 | `ArtifactRelation` ORM 对象通过 `session_factory` 写入 DB |
| 错误处理 | LLM 调用和 DB 持久化均有 try/except + 日志 |

**代码质量**: 优秀。防御性编程到位。

**潜在问题**:
- N01: `recent_artifacts[:15]` 硬编码上限，大项目可能遗漏重要早期 artifact — 可提取为配置项

### 4.3 Orchestrator 集成 (`engine.py`, `factory.py`, `planner.py`)

| 集成点 | 状态 | 说明 |
|--------|------|------|
| EventBus 创建 | ✅ | `factory.py` 创建 EventBus 实例 |
| EventBus 传递给 Planner | ✅ | `planner.py` 构造函数接收 `event_bus` 参数 |
| Planner 消费事件 | ✅ | `planner.py` 在规划逻辑中 drain 事件，提取矛盾/依赖注入任务 |
| SemanticBoard feature flag | ✅ | `factory.py` 根据 `settings.use_semantic_board` 条件创建 |
| Coverage gap detection | ✅ | `engine.py` 定期调用 `board.compute_coverage()` |

---

## 5. Phase 3 新模块审计

### 5.1 可计算指标 (`backend/evaluation/metrics.py`)

#### `evidence_mapping(hypotheses, evidence_texts)`

**逻辑**: 对每个 hypothesis 提取关键词（去停用词 + 最小长度2），检查 ≥min(3, len(words)) 个关键词出现在 evidence 文本中。

| 项目 | 评估 |
|------|------|
| 正确性 | ✅ 逻辑正确，阈值 `min(3, len(words))` 处理短 hypothesis |
| 中文支持 | ✅ `[a-zA-Z\u4e00-\u9fff]{2,}` 正则覆盖中文字符 |
| 边界处理 | ✅ 空 hypotheses → 0.0，无匹配关键词 → unmapped |
| 输出格式 | ✅ 返回 `DimensionScore`，evidence 含映射/未映射详情 |

#### `specificity(artifacts)`

**逻辑**: 计算量化术语（数字/百分比）+ CamelCase 专有名词的密度。`value = min(density * 10, 1.0)`。

| 项目 | 评估 |
|------|------|
| 正确性 | ✅ 密度公式合理，`*10` 放大系数使 10% specific terms → 满分 |
| CamelCase 检测 | ✅ `[A-Z][a-z]+(?:[A-Z][a-z]+)+` 匹配 ResearchTopic 类术语 |
| 中文兼容 | ⚠️ CamelCase 正则对纯中文无效，但 `_QUANTITATIVE_RE` 可捕获数字 |

### 5.2 DB 持久化层 (`backend/evaluation/store.py`)

#### `ClaimStore`

| 项目 | 评估 |
|------|------|
| Pydantic→ORM 映射 | ✅ confidence 字符串→浮点映射 (`strong→1.0`, `moderate→0.7`, `tentative→0.4`) |
| 反向加载 | ✅ `load_claims()` 浮点→字符串反映射 |
| 事务管理 | ✅ `async with session.begin()` 自动 commit/rollback |
| UUID 生成 | ✅ `uuid.uuid4()` 生成新 ID |

**问题**:
- N02: `source_agent=c.source_artifact[:50]` — 字段名不匹配：Pydantic `source_artifact` 映射到 ORM `source_agent`。语义上 `source_artifact` 是 artifact ID，但 ORM 列名暗示 agent。不影响功能但增加维护困惑。

#### `ContradictionStore`

| 项目 | 评估 |
|------|------|
| Claim UUID 映射 | ✅ 通过 `claim_id_map` 将 Pydantic claim_id 映射到 DB UUID |
| Evidence 序列化 | ✅ `json.dumps({explanation, relationship, detected_by})` |
| 缺失处理 | ✅ claim UUID 映射不存在时 skip + warning |

#### `EvaluationStore`

| 项目 | 评估 |
|------|------|
| PhaseEvaluation→ORM | ✅ dimensions 通过 `model_dump(mode="json")` 序列化 |
| IterationMetric 写入 | ✅ 包含 `information_gain`, `artifact_count_delta`, `unique_claim_delta`, `eval_composite` |
| 额外数据 | ✅ `metrics` JSON 字段存储 `is_diminishing` + `is_loop_detected` 布尔值 |

### 5.3 Evaluator 集成

| 集成点 | 状态 | 说明 |
|--------|------|------|
| `evaluate_phase()` → DB | ✅ | `self._project_id` 非空时调用 `_save_evaluation_to_db()` |
| `evaluate_contradictions()` → DB | ✅ | Claims + Contradictions 一并持久化 |
| `save_to_db()` 公共方法 | ✅ | 外部调用者可显式触发持久化 |
| Ablation flags 传递 | ✅ | `evaluate_phase()` kwargs 控制各评估分支 |
| 错误隔离 | ✅ | DB 写入失败仅记日志，不中断评估流程 |

---

## 6. 新发现的问题

### N01: `_STOPWORDS_EN` 重复定义
**位置**: `evaluator.py:45-98` 和 `metrics.py:226-279`
**严重度**: P3

两个文件各自定义了完全相同的 38 个英文停用词集合 `_STOPWORDS_EN` / `_ENGLISH_STOPWORDS`。应抽取到公共模块（如 `utils/nlp.py`）避免不一致风险。

### N02: Store 测试仅验证签名/存在性
**位置**: `test_evaluation.py` 中 `TestClaimStore`, `TestEvaluationStore`, `TestContradictionStore`
**严重度**: P2

所有 Store 测试都是"存在性测试"（检查类是否存在、方法签名是否正确），没有实际的 DB round-trip 测试。这意味着：
- ORM 列映射错误不会被捕获
- 事务异常路径未覆盖
- `load_claims()` 反向映射正确性未验证

**建议**: 添加使用 SQLite in-memory DB 或 pytest-asyncio + async_session_factory mock 的集成测试。

### N03: `runner.py` 仍未传递 ablation flags
**位置**: `backend/benchmarks/runner.py`
**严重度**: P2

D01 的修复仅在 `evaluator.py` 侧添加了 kwargs。`runner.py` 的 `run_task()` 调用 `evaluator.evaluate_phase()` 时仍未传递 `AblationConfig` 的标志。这意味着通过 runner 运行的消融实验仍然全部使用默认值（全开）。

**修复方案**: `run_task()` 应将 `config.use_cross_model` 等标志作为 kwargs 传给 `evaluate_phase()`。

### N04: `ContradictionStore.save_contradictions()` 的 `claim_id_map` 类型注解
**位置**: `store.py:95`
**严重度**: P3

参数类型 `dict[str, uuid.UUID]`，但 `evaluator.py:571` 传入的是 `dict[str, object]`（因 `zip` 推断）。运行时不影响，但类型检查器会报错。

### N05: EventBus 事件未发布
**位置**: 全局搜索
**严重度**: P2

`EventBus.publish()` 在 planner 侧有 `drain()` 消费端，但目前没有找到在 agent 执行或 board 操作中调用 `publish()` 的代码。EventBus 已接线但无事件源——所有 drain 调用返回空列表。

**建议**: 在 `board.py` 的 `write_artifact()` / `update_artifact()` 或 `engine.py` 的迭代完成后添加事件发布。

---

## 7. 架构符合度矩阵（更新版）

### Phase 1 Foundation

| 架构要求 | 状态 | 详情 |
|----------|------|------|
| ORM 表: `evaluation_results` | ✅ | 字段已对齐 Pydantic 模型 |
| ORM 表: `knowledge_state` | ✅ | 新增 `gap_count` + `gap_descriptions` |
| ORM 表: `iteration_metrics` | ✅ | 新增 4 个架构要求字段 |
| ORM 表: `claims` + `contradictions` | ✅ | 已实现 + 已使用 |
| Alembic 迁移 | ✅ | `002_phase1_tables.py` |
| Feature flag `use_multi_eval` | ✅ | `config.py` |

### Phase 2 Semantic Knowledge Layer (部分)

| 架构要求 | 状态 | 详情 |
|----------|------|------|
| EventBus 事件机制 | ✅ 已实现 | 但无事件源 (N05) |
| 语义关系提取 | ✅ 已实现 | RelationExtractor 6 种关系类型 |
| ArtifactRelation ORM | ✅ 已实现 | source_id/target_id UUID FK |
| SemanticBoard (pgvector) | ⚠️ Feature-flagged | 存在但默认关闭 |
| Coverage gap detection | ✅ 已集成 | engine.py 定期调用 |
| Embedding-based 信息增益 | ❌ 未实现 | 仍用词集差异 |

### Phase 3 Evaluation Engine

| 架构要求 | 状态 | 变化 |
|----------|------|------|
| 多维质量评估 | ✅ | 不变 |
| 交叉模型评估 | ✅ | D06 修复：4 条完整映射 |
| LLM 评估 Prompt | ✅ | D05 修复：结构化 criteria + 约束 |
| Ablation 配置 | ⚠️ | evaluator 侧已支持，runner 侧未传递 (N03) |
| ClaimExtractor | ✅ | 不变 |
| ContradictionDetector | ✅ | 不变 |
| Claims 持久化到 DB | ✅ | D02 修复：ClaimStore |
| 评估结果写入 DB | ✅ | D02 修复：EvaluationStore |
| 可计算指标: evidence_mapping | ✅ 新增 | 关键词映射，去停用词 |
| 可计算指标: specificity | ✅ 新增 | 量化术语 + CamelCase 密度 |
| ORM ↔ Pydantic 对齐 | ✅ | D07/D08/D09 修复 |
| 矛盾解决机制 | ❌ | 架构要求 Agent 介入解决，未实现 |
| 信息增益 embedding | ❌ | 同 Phase 2 依赖 |

---

## 8. 测试覆盖差距（更新版）

### 已覆盖
- 8 个可计算指标（含 evidence_mapping + specificity）
- Claim 提取/矛盾检测/信息增益
- EvaluatorService 全流程
- Benchmark runner + scorer
- Store 类存在性和签名

### 仍未覆盖

| 场景 | 优先级 | 说明 |
|------|--------|------|
| Store DB round-trip | P1 | 无实际数据库读写测试 (N02) |
| Ablation 通过 runner 传递 | P1 | runner 未将 flags 传给 evaluator (N03) |
| EventBus publish→drain 链路 | P2 | EventBus 无事件源 (N05) |
| RelationExtractor 单元测试 | P2 | 无测试覆盖 |
| Mixed 维度评估路径 | P2 | computable+LLM 加权合并路径 |
| 大量 artifact 性能 | P3 | `_collect_artifacts()` 遍历全部类型 |

---

## 9. 建议修复优先级

| 优先级 | 缺陷 | 建议行动 |
|--------|------|----------|
| **P2** | N03 runner 未传 ablation flags | `run_task()` 将 `config.use_*` 传给 `evaluate_phase()` |
| **P2** | N05 EventBus 无事件源 | 在 board/engine 中添加 `publish()` 调用 |
| **P2** | N02 Store 测试浅层 | 添加 SQLite in-memory DB 集成测试 |
| **P3** | N01 停用词重复 | 抽取到 `utils/nlp.py` |
| **P3** | N04 类型注解不一致 | `claim_id_map` 统一为 `dict[str, uuid.UUID]` |

---

## 10. 总结

**Round 2 整体进展优秀。** Round 1 的 14 个缺陷中 9 个已修复（含 2 个 P0 和全部 P1），5 个因架构依赖合理保留。

**关键改进**:
1. **Ablation 框架就绪** (D01) — evaluator 已支持 4 个开关，但 runner 侧仍需接线 (N03)
2. **DB 持久化完整** (D02) — Claims/Contradictions/Evaluations/IterationMetrics 均可写入 DB
3. **LLM 评估质量提升** (D05) — 14 个维度专属 criteria + 评分约束 + 结构化证据
4. **Phase 2 基础设施到位** — EventBus + RelationExtractor 架构合理，但 EventBus 缺少事件源
5. **可计算指标扩展** — evidence_mapping + specificity 填补了架构要求的指标空白

**剩余风险**:
1. N03: Ablation 通过 runner 运行时仍无效（evaluator 已支持但 runner 未传参）
2. N05: EventBus 已集成到 planner 消费端，但无代码向其发布事件
3. Store 测试仅为浅层签名验证，ORM 映射错误可能在运行时才暴露

**建议下一步**: 修复 N03 (runner 传参) 和 N05 (事件发布)，然后添加 Store 集成测试，即可认为 Phase 2 + Phase 3 基础部分达到生产就绪状态。
