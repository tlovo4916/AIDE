# AIDE v1系统架构

> **定位**：系统设计文档 — 记录架构决策、模块职责与设计理由。
>
> **最后更新**：2026-03-18 | 遗留问题见 [q.md](./q.md)

---

## 目录

1. [问题诊断](#1-问题诊断)
2. [架构总览](#2-架构总览)
3. [Phase 1: Foundation](#3-phase-1-foundation)
4. [Phase 2: Semantic Knowledge Layer](#4-phase-2-semantic-knowledge-layer)
5. [Phase 3: Evaluation Engine](#5-phase-3-evaluation-engine)
6. [Phase 4: Intelligence Layer](#6-phase-4-intelligence-layer)
7. [前端影响](#7-前端影响)
8. [配置变更](#8-配置变更)
9. [测试策略](#9-测试策略)
10. [风险评估与排期](#10-风险评估与排期)
11. [附录：代码组织](#11-附录代码组织)

---

## 1. 问题诊断

详见 [review.md](./review.md)。14个缺陷归纳为3个根本性问题：

### A. 系统没有"认知"能力

| 该有的 | 实际的 |
|--------|--------|
| Agent 有专业化推理逻辑 | 6个Agent共享同一个 `render→call_llm→parse_json` 函数 |
| Planner 根据研究进展动态决策 | `sequence[(iteration-1) % len(sequence)]` 取模轮转 |
| Backtrack 基于语义矛盾检测 | `if "contradict" in text or "矛盾" in text` 关键词匹配 |
| Topic drift 基于语义理解 | `str.split()` + `in` 运算符 |

### B. 系统没有"评估"能力

| 该有的 | 实际的 |
|--------|--------|
| 独立的质量评估机制 | LLM给自己打分（方法论无效） |
| 收敛检测基于信息增益 | `critic_score >= 7.0 and file_count > 0` |
| Artifact去重基于语义 | Jaccard词集交集（换个同义词就绕过） |
| 研究进展可量化 | 没有任何 metric/benchmark/evaluation |

### C. 架构是"模拟形式"而非"实现功能"

| 声称的 | 实际的 |
|--------|--------|
| 黑板架构（响应式协作） | 文件夹 + JSON dump（被动读取） |
| 螺旋迭代（渐进深化） | for循环 + phase枚举 |
| 多Agent协作 | 串行调用同一函数 |
| Protocol-based依赖注入 | 管理1300行核心逻辑的过度抽象 |

---

## 2. 架构总览

### 2.1 四层架构

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: Intelligence (Adaptive Planner + Agent 深化)       │
│  ResearchStateAnalyzer → DispatchScorer → 动态选Agent        │
│  每个Agent有差异化execute()逻辑，Agent间InfoRequest通信       │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Evaluation Engine                                  │
│  多维质量评估（5维度/相）+ 交叉模型验证                        │
│  Claim提取 → 语义矛盾检测 → 信息增益收敛                      │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Semantic Knowledge Layer                           │
│  PostgreSQL+pgvector存artifact + 语义关系图                   │
│  相关性排序上下文构建（非截断），覆盖缺口检测                    │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Foundation                                         │
│  死代码清理，Settings迁移DB，Alembic迁移，嵌入管线              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 依赖关系

```
Phase 1: Foundation ──────→ Phase 2: Knowledge Layer
                                      │
                                      ▼
                            Phase 3: Evaluation Engine
                                      │
                                      ▼
                            Phase 4: Intelligence Layer
```

### 2.3 迁移策略

- **Feature flag 增量迁移**：每个新组件通过环境变量控制启停
- `AIDE_USE_SEMANTIC_BOARD=false` → 语义知识层
- `AIDE_USE_MULTI_EVAL=false` → 多维评估
- `AIDE_USE_ADAPTIVE_PLANNER=false` → 自适应规划
- 旧代码保留为默认路径，新代码验证通过后逐步切换
- Docker 唯一基础设施变更：`postgres:16-alpine` → `pgvector/pgvector:pg16`

### 2.4 关键设计决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 嵌入模型 | `qwen/qwen3-embedding-8b` via OpenRouter | 原生中英双语支持，已有 `EmbeddingService` 对接 |
| 向量存储 | pgvector (PostgreSQL) | 同库无网络跳转，ChromaDB仅保留给Librarian外部论文 |
| 评估方案 | 结构指标(60%) + 交叉模型LLM评估(40%) | 可计算指标为主确保可靠性，LLM评估捕捉语义质量 |
| 收敛方案 | 信息增益 + 质量达标 + 无矛盾 | 三条件AND，信息枯竭而非分数达标 |
| Agent深化 | 差异化 `execute()` 逻辑 | 不只换prompt，每个Agent有独立的前处理/后处理 |

---

## 3. Phase 1: Foundation

### 3.1 死代码清理

#### 删除

| 文件/代码 | 原因 |
|-----------|------|
| `backend/blackboard/adapter.py` | 确认死代码，`factory.py` 直接使用 `Blackboard`，`BoardAdapter` 无引用 |
| 6层 topic 注入中的4层 | 保留 board 存储 + engine 监控，删除 planner/base/j2/factory 中的重复注入 |
| `settings_overrides.json` 方案 | 用 `project_settings` DB表替代 |

#### 简化

| 目标 | 操作 |
|------|------|
| Protocol 抽象 | 只保留 `Board` Protocol（迁移期间有价值），删除其他单实现 Protocol |
| `WriteBackGuard` | 保留但从 `backend/memory/` 移到 `backend/agents/write_back_guard.py` |
| Challenge auto-dismiss | 后续用语义矛盾解决替代5轮后自动丢弃 |

#### Topic 注入精简

当前6层注入：
1. `factory.py`: 从DB读取 topic
2. `board.py`: 存入 meta.json，`get_state_summary()` 头部注入
3. `planner.py`: 每个 task description 前缀注入
4. `base.py`: 传入 Jinja2 模板变量
5. `*.j2`: 模板中 topic block
6. `engine.py`: `_check_on_topic()` 监控

精简为2层：
- **Layer A (存储+展示)**：`board.py` 存储 topic 并在 `get_state_summary()` 头部注入——这是所有 Agent 看到 topic 的唯一入口
- **Layer B (监控)**：`engine.py` 的 `_check_on_topic()` 监控漂移

删除 planner task prefix (Layer 3)、base.py 模板变量 (Layer 4)、j2 模板 block (Layer 5)。factory.py 读取 topic 仍需保留但不再传播给每个组件。

### 3.2 数据库迁移

#### 引入 Alembic

- 添加 `alembic` 到 `pyproject.toml` 依赖
- 配置 `backend/migrations/` 目录
- 替代当前 `init_db()` 中的手动 `ALTER TABLE` 逻辑

#### pgvector 启用

Docker Compose 变更：
```yaml
# docker-compose.yml
postgres:
  image: pgvector/pgvector:pg16    # 替代 postgres:16-alpine
  # 其余不变
```

初始化时：
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

#### 新增表

```sql
-- Artifact 存储（替代文件系统）
CREATE TABLE artifacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    artifact_type   VARCHAR(50) NOT NULL,
    artifact_id     VARCHAR(255) NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    content_l2      TEXT,                           -- 完整内容
    content_l1      JSONB,                          -- 结构化摘要
    content_l0      TEXT,                           -- 一句话摘要
    embedding       VECTOR(1536),                   -- pgvector, nullable
    created_by      VARCHAR(50),                    -- agent role
    superseded      BOOLEAN DEFAULT FALSE,
    phase_created   VARCHAR(50),
    quality_score   FLOAT,                          -- 来自多维评估
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, artifact_type, artifact_id, version)
);

-- Artifact 语义关系
CREATE TABLE artifact_relations (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_artifact  TEXT NOT NULL,                  -- "{type}/{id}"
    target_artifact  TEXT NOT NULL,
    relation_type    VARCHAR(30) NOT NULL,           -- supports|contradicts|refines|supersedes|cites|depends_on
    confidence       FLOAT DEFAULT 0.5,
    evidence         TEXT,
    created_by       VARCHAR(50),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, source_artifact, target_artifact, relation_type)
);

-- 多维评估结果
CREATE TABLE evaluation_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    artifact_id     UUID REFERENCES artifacts(id),  -- nullable, 可评估整个 phase
    phase           VARCHAR(50),
    evaluator_model VARCHAR(100),
    dimensions      JSONB NOT NULL,                 -- {coherence: 7, novelty: 5, ...}
    overall_score   FLOAT,
    raw_feedback    TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 知识状态快照
CREATE TABLE knowledge_state (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    phase            VARCHAR(50),
    iteration        INTEGER,
    coverage_score   FLOAT,
    density_score    FLOAT,
    coherence_score  FLOAT,
    gap_count        INTEGER,
    gap_descriptions JSONB,
    computed_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 消息存储（替代文件系统）
CREATE TABLE messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    from_agent  VARCHAR(50),
    to_agent    VARCHAR(50),
    content     TEXT,
    refs        JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Challenge 存储（替代文件系统）
CREATE TABLE challenges (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    challenge_id    VARCHAR(255),
    status          VARCHAR(20) DEFAULT 'open',
    challenger      VARCHAR(50),
    target_artifact VARCHAR(255),
    target_agent    VARCHAR(50),
    argument        TEXT,
    response        TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);

-- 项目设置（替代 settings_overrides.json）
CREATE TABLE project_settings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID REFERENCES projects(id),       -- null = 全局设置
    key         VARCHAR(100) NOT NULL,
    value       JSONB NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, key)
);

-- Claim 存储（矛盾检测基础）
CREATE TABLE claims (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_artifact  UUID NOT NULL REFERENCES artifacts(id),
    claim_text       TEXT NOT NULL,
    claim_type       VARCHAR(30),                   -- factual|causal|comparative|definitional
    confidence       VARCHAR(20),                   -- strong|moderate|tentative
    embedding        VECTOR(1536),
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Claim 矛盾记录
CREATE TABLE contradictions (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id           UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    claim_a_id           UUID NOT NULL REFERENCES claims(id),
    claim_b_id           UUID NOT NULL REFERENCES claims(id),
    relationship         VARCHAR(20) NOT NULL,      -- contradictory|nuanced
    explanation          TEXT,
    resolution_suggestion TEXT,
    status               VARCHAR(30) DEFAULT 'unresolved',
    resolution           TEXT,
    resolved_by_artifact UUID REFERENCES artifacts(id),
    created_at           TIMESTAMPTZ DEFAULT NOW()
);

-- InfoRequest 队列
CREATE TABLE info_requests (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id         UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    from_agent         VARCHAR(50) NOT NULL,
    to_agent           VARCHAR(50) NOT NULL,
    question           TEXT NOT NULL,
    context_refs       JSONB DEFAULT '[]',
    priority           VARCHAR(20) DEFAULT 'normal',
    parent_request_id  UUID REFERENCES info_requests(id),
    fulfilled          BOOLEAN DEFAULT FALSE,
    response_artifact  UUID REFERENCES artifacts(id),
    created_at         TIMESTAMPTZ DEFAULT NOW()
);

-- 迭代度量
CREATE TABLE iteration_metrics (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id        UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    phase             VARCHAR(50),
    iteration         INTEGER,
    information_gain  FLOAT,
    artifact_count_delta INTEGER,
    unique_claim_delta   INTEGER,
    eval_composite    FLOAT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.3 嵌入管线

现有 `backend/knowledge/embeddings.py` 的 `EmbeddingService` 已通过 OpenRouter 代理 embedding 调用。

**默认模型**：`qwen/qwen3-embedding-8b`（原生中英双语，通过 OpenRouter 代理）

**嵌入时机**：
- Artifact 写入时：异步嵌入 L2 内容，存入 `artifacts.embedding` 列
- 项目初始化时：对缺少嵌入的 artifact 补算（幂等）
- Research topic 设定时：嵌入 topic 文本并缓存

**缓存策略**：Artifact 不可变（新内容 = 新版本），嵌入只需计算一次。`artifacts.embedding` 列即缓存。embedding 调用失败则列为 NULL，查询回退到文本搜索。

**成本预估**：每个项目约 40 个 artifact → 40 次 embedding 调用。`qwen3-embedding-8b` 通过 OpenRouter 成本极低。

### 3.4 Settings 迁移

将 `backend/api/settings.py` 中的 `load_overrides()` / `_save_overrides()` 从读写 `/app/workspace/settings_overrides.json` 改为读写 `project_settings` 表。

```python
# 当前（删除）
def _save_overrides(overrides: dict):
    json.dump(overrides, open("/app/workspace/settings_overrides.json", "w"))

# 新方案
async def save_setting(session, project_id: str | None, key: str, value: Any):
    # upsert into project_settings table

async def load_settings(session, project_id: str | None) -> dict:
    # query project_settings table
```

---

## 4. Phase 2: Semantic Knowledge Layer

### 4.1 设计目标

将"文件夹 + JSON dump"的 Blackboard 升级为具备以下能力的语义知识层：
- Artifact 之间有语义关系（supports, contradicts, refines, supersedes, cites, depends_on）
- 上下文构建基于相关性排序而非全量截断
- 自动检测覆盖缺口
- 写入触发事件通知

### 4.2 SemanticBoard 实现

新文件 `backend/blackboard/semantic_board.py`，继承 `Blackboard`：

```python
class SemanticBoard(Blackboard):
    """PostgreSQL + pgvector backed board with semantic capabilities."""

    # --- 覆写 write_artifact ---
    async def write_artifact(self, artifact_type, artifact_id, content, ...):
        # 1. 写入 PostgreSQL artifacts 表
        # 2. 异步嵌入 L2 内容 (asyncio.create_task)
        # 3. 异步提取关系 (asyncio.create_task)
        # 4. 发布 ArtifactEvent 到事件总线

    # --- 语义关系图 ---
    async def get_relations(self, artifact_key, relation_type=None) -> list[ArtifactRelation]
    async def get_contradiction_pairs() -> list[tuple[str, str, float]]
    async def get_support_chain(artifact_key) -> list[str]

    # --- 语义搜索 ---
    async def find_relevant_artifacts(query, top_k=20, artifact_types=None) -> list[tuple]

    # --- 覆盖分析 ---
    async def compute_coverage() -> KnowledgeState
    async def get_coverage_gaps() -> list[CoverageGap]

    # --- 智能上下文 ---
    async def build_agent_context(role, task_description, budget=None) -> str

    # --- 事件总线 ---
    async def get_pending_events() -> list[ArtifactEvent]
```

在 `factory.py` 中通过 feature flag 切换：
```python
if settings.use_semantic_board:
    board = SemanticBoard(session_factory, embedding_service, project_id)
else:
    board = Blackboard(workspace_path, ...)  # 当前代码
```

### 4.3 关系提取算法

每次 `write_artifact` 后触发（fire-and-forget，非阻塞主循环）：

1. 获取新 artifact 的 L1 摘要
2. 获取最近 15 个同项目 artifact 的 L1 摘要（缓存）
3. 用轻量模型（`deepseek-chat`）提取关系：

```
Prompt: "Given this new artifact and these existing artifacts,
identify semantic relations. Output JSON array of
{source, target, relation_type, confidence, evidence}."

relation_type ∈ {supports, contradicts, refines, supersedes, cites, depends_on}
```

4. 存入 `artifact_relations` 表
5. 若 LLM 调用失败，artifact 照常写入，只是无关系数据

**成本**：每次约 2K token 输入，`deepseek-chat` 约 $0.001/次，整个项目约 $0.04。

### 4.4 相关性排序上下文构建

替代当前的 `build_budget_context()`（线性遍历所有 artifact → 截断到 token budget）：

```
Input:  agent_role, task_description, token_budget
Output: 在预算内的最相关上下文

算法：
1. 嵌入 task_description（使用 qwen/qwen3-embedding-8b）
2. 查询 pgvector 获取 top-K 最相似 artifact (K ≈ 20-40)
3. 计算复合相关性分数：
   relevance = (
       0.50 × cosine_similarity    +  # 语义相似度
       0.20 × role_affinity        +  # Agent 类型匹配度
       0.15 × recency_decay        +  # 时间衰减
       0.15 × graph_centrality        # 关系图中心度
   )
4. 按分数排序，贪心装箱：
   - 必选：research_topic, phase/iteration, open challenges
   - 高相关 artifact 用 L2 级别，占预算 60%
   - 中相关 artifact 用 L1 级别，占到 85%
   - 低相关 artifact 用 L0 级别，填满预算
5. 若 artifact 有 contradicts 关系，始终同时包含双方
```

**role_affinity**：使用已有的 `primary_artifact_types` 和 `dependency_artifact_types`（`base.py` 中每个 Agent 已定义）。

**graph_centrality**：简单 degree centrality，`artifact_relations` 表中 incoming `supports` 和 `cites` 关系数量。

### 4.5 覆盖缺口检测

每 N 轮迭代运行（N = `AIDE_COVERAGE_RECOMPUTE_INTERVAL`，默认 3）：

1. 用 LLM 分解 research topic 为子主题（缓存，仅首次调用）
2. 对每个子主题，查询 pgvector 最佳匹配
3. 若最佳匹配 cosine similarity < 0.5，标记为覆盖缺口
4. 存入 `knowledge_state` 表
5. 反馈给 Planner 用于优先调度

### 4.6 事件总线

轻量级进程内事件机制（非 Kafka/Redis 级别，适配当前单进程架构）：

```python
class ArtifactEvent:
    event_type: str          # "created" | "updated" | "challenged" | "superseded"
    artifact_type: ArtifactType
    artifact_id: str
    agent_role: AgentRole
    relations: list[ArtifactRelation]   # 写入时提取的关系

class EventBus:
    _pending: list[ArtifactEvent]

    async def publish(self, event: ArtifactEvent): ...
    async def drain(self) -> list[ArtifactEvent]: ...
```

Agent 不直接订阅。Planner 在每次决策前消费事件：
- 若检测到 `contradicts` 关系 → 提升 Critic 或被矛盾方 Agent 的调度优先级
- 若检测到 `depends_on` 指向缺失 artifact → 提升生产方 Agent 的优先级
- 事件同时转发到前端 WebSocket（enriched `ArtifactUpdated` 事件）

### 4.7 语义去重

替代当前 Jaccard 词集去重（只防复读机，不防换皮）：

```python
async def semantic_dedup_check(self, new_content: str, artifact_type: ArtifactType) -> bool:
    """返回 True 表示重复，应跳过。"""
    new_embedding = await self._embed(new_content)
    # 查询同类型最近 10 个非 superseded artifact
    similar = await self._query_pgvector(
        embedding=new_embedding,
        filter={"artifact_type": artifact_type, "superseded": False},
        top_k=10,
        threshold=0.85  # 余弦相似度 > 0.85 判定为语义重复
    )
    return len(similar) > 0
```

**阈值说明**：0.85 余弦相似度约等于"相同内容不同措辞"。远优于 Jaccard 0.6（只能防原文复制）。

---

## 5. Phase 3: Evaluation Engine

### 5.1 设计目标

从"LLM 自评 1-10 分"升级为：
- 多维度结构化评估（每个 phase 独立维度）
- 交叉模型验证（生成与评估用不同 provider）
- Claim 提取 + 语义矛盾检测
- 信息增益收敛检测

### 5.2 多维质量评估

#### 数据模型

```python
class DimensionScore(BaseModel):
    name: str
    computable_value: float | None    # 算法指标 (null if N/A)
    llm_value: float | None           # LLM 评估 (null if N/A)
    combined: float                   # 加权合并
    weight: float                     # 在 composite 中的权重
    evidence: list[str]               # 具体依据

class PhaseEvaluation(BaseModel):
    phase: ResearchPhase
    dimensions: dict[str, DimensionScore]
    composite_score: float            # 加权平均
    evaluator_model: str
    evaluator_provider: str
    raw_evidence: dict
    timestamp: datetime
```

#### 各 Phase 评估维度

**EXPLORE 阶段：**

| 维度 | 类型 | 算法 |
|------|------|------|
| `coverage_breadth` | 可计算 | TF-IDF 聚类计数 covered/expected 子主题 |
| `source_diversity` | 可计算 | 信息源 Shannon 熵 |
| `terminology_coverage` | 可计算 | 领域术语命中率 |
| `gap_identification` | LLM 评估 | 让评估器列出未识别的缺口 |

**HYPOTHESIZE 阶段：**

| 维度 | 类型 | 算法 |
|------|------|------|
| `specificity` | LLM 评估 | 可证伪性检查（变量/可测结果/范围） |
| `novelty_vs_literature` | 混合 | 余弦相似度 + LLM确认是否超越已有文献 |
| `logical_coherence` | LLM 评估 | 假设间一致性矩阵 |
| `coverage_of_topic` | 可计算 | 有假设的子主题占比 |

**EVIDENCE 阶段：**

| 维度 | 类型 | 算法 |
|------|------|------|
| `citation_density` | 可计算 | 引用数/内容长度，归一化 |
| `evidence_conclusion_mapping` | LLM 评估 | 证据-假设覆盖矩阵 |
| `conflicting_evidence_handling` | LLM 评估 | 矛盾证据是否被处理 |
| `methodological_rigor` | LLM 评估 | 引用源方法论局限性是否被标注 |

**COMPOSE 阶段：**

| 维度 | 类型 | 算法 |
|------|------|------|
| `structural_completeness` | 可计算 | 必需章节存在率 |
| `argument_flow` | LLM 评估 | 段落间逻辑连贯性 |
| `citation_integration` | 混合 | 内联引用数 + 引用恰当性 |
| `internal_consistency` | LLM 评估 | claim 间矛盾检测 |

#### Composite Score 计算

```
composite = Σ(dim.combined × dim.weight) / Σ(dim.weight)

其中 dim.combined =
  - 若两者都有: 0.6 × computable + 0.4 × llm   (信任可计算指标)
  - 若只有一个: 使用该值
  - 权重可配置，可通过环境变量调整
```

### 5.3 交叉模型评估

**核心原则**：生成内容的模型不能评估自己的产出。

#### EvaluatorService 接口

```python
class EvaluatorService:
    def __init__(self, llm_router: LLMRouter, token_tracker: TokenTracker): ...

    async def evaluate_phase(
        self,
        board: Board,
        phase: ResearchPhase,
        research_topic: str,
        generator_model: str,
    ) -> PhaseEvaluation
```

#### 模型分配矩阵（可配置）

| 生成模型 | 评估模型 |
|----------|----------|
| deepseek-reasoner | claude-sonnet-4-6 |
| deepseek-chat | deepseek-reasoner |
| claude-opus-4-6 | deepseek-reasoner |
| claude-sonnet-4-6 | deepseek-reasoner |

#### 结构化评估 Prompt 模式

```
You are evaluating research artifacts for: {dimension_name}

## Research Topic
{research_topic}

## Artifacts
{artifacts_formatted}

## Criteria
{dimension_specific_criteria}

## Required Output
{
  "score": <0.0-1.0>,
  "evidence": [
    {"finding": "...", "artifact_ref": "...", "impact": "positive|negative|neutral"}
  ],
  "missing": ["..."],
  "reasoning": "2-3 sentences"
}

IMPORTANT: Score above 0.7 requires ≥3 positive evidence items.
Score below 0.3 requires ≥2 specific missing items.
```

强制评估器将评分 grounded 在具体观察中，防止凭印象打分。

### 5.4 Claim 提取与矛盾检测

#### Claim 提取

每次 `write_artifact` 后运行 `ClaimExtractor`：

```python
class ClaimExtractor:
    async def extract(self, content: str, artifact_id: str) -> list[Claim]:
        """
        提取所有事实性声明，归一化为标准三元组。
        Prompt: "Extract all factual claims as normalized triples.
        Format: [{text, type (factual|causal|comparative|definitional),
                  confidence (strong|moderate|tentative), source_cited: bool}]
        Normalize: present tense, canonical nouns, remove hedging."
        """
```

Claims 存入 `claims` 表，嵌入存入 `claims.embedding`。

#### 矛盾检测算法

```
对每个新 claim:
  1. 快速过滤：pgvector 查询 embedding 相似度 > 0.3 的 existing claims
     （话题相关但可能矛盾的 claims 会有中等相似度）
  2. LLM 验证（使用交叉模型）：
     "Given Claim A and Claim B, are they:
      CONSISTENT | CONTRADICTORY | NUANCED?
      Output: {relationship, explanation, resolution_suggestion}"
  3. 若 contradictory 或 nuanced → 存入 contradictions 表
```

#### 矛盾解决（替代 auto-dismiss）

当前系统：5轮后自动丢弃 challenge（把异议扔进垃圾桶）。

新方案：
1. **Agent 介入解决**：Scientist 在 EVIDENCE 阶段收到未解决矛盾列表，必须产出明确回应（新证据/语境解释/证据强度评估）
2. **解决验证**：EvaluatorService 检查解决是否实质性地回应了矛盾
3. **不可解决矛盾**：3次解决尝试后标记为 `accepted_as_limitation`，必须出现在论文 Discussion 章节
4. **收敛阻断**：未解决矛盾（状态为 `unresolved`）阻止 phase 收敛

### 5.5 信息增益收敛

#### 信息增益计算

每次 Agent 执行后计算：

```python
# 对每个新 artifact，计算与已有同类型 artifact 的最大余弦相似度
max_sim = max(cosine_sim(embed(new), embed(existing)) for existing in same_type)

# 信息增益 = 1 - 最大相似度（越大越新颖）
IG(iteration) = mean(1.0 - max_sim(a) for a in new_artifacts)
# 范围: 0.0 (完全冗余) 到 1.0 (完全新颖)
```

#### 收敛枯竭检测

```python
def detect_diminishing_returns(metrics, window=5, threshold=0.05) -> bool:
    """连续 window 轮平均信息增益低于阈值 → 信息枯竭"""
    if len(metrics) < window:
        return False
    recent_gains = [m.information_gain for m in metrics[-window:]]
    avg_gain = mean(recent_gains)
    is_declining = all(recent_gains[i] >= recent_gains[i+1] for i in range(len-1))
    return avg_gain < threshold or (is_declining and recent_gains[-1] < threshold * 2)
```

#### 环路检测

```python
# 基于 claim 指纹重复率
for new_artifact in new_artifacts:
    new_claims = extract_claim_fingerprints(new_artifact)
    for existing in last_10_artifacts:
        existing_claims = get_claim_fingerprints(existing)
        overlap = |new_claims ∩ existing_claims| / |new_claims|
        if overlap > 0.8:
            loop_counter += 1

if loop_counter >= 3 in last 5 iterations:
    LOOP_DETECTED = True
    # → 触发策略变更（换 Agent/换方向），而非收敛
```

Claim 指纹归一化：LLM 将 "X causes Y" / "Y is caused by X" / "X leads to Y" 归一化为同一三元组。

#### 新收敛检测器

```python
class InformationTheoreticConvergence:
    async def check(self, board, phase) -> ConvergenceSignals:
        evaluation = await self._get_latest_evaluation(board, phase)
        metrics = await self._get_iteration_metrics(board, phase)

        # 三个独立收敛条件
        quality_ok = evaluation.composite_score >= self._phase_threshold(phase)
        exhausted = self._detect_diminishing_returns(metrics)
        no_contradictions = not await self._has_unresolved_contradictions(board)
        no_loops = not self._detect_loops(metrics)

        # 收敛 = 质量达标 AND (信息枯竭 OR 达到上限) AND 无矛盾 AND 无环路
        max_iter_reached = len(metrics) >= self._max_iterations
        converged = (
            quality_ok
            and (exhausted or max_iter_reached)
            and no_contradictions
            and no_loops
        )

        # 环路检测到 → 信号策略变更，不是收敛
        if not no_loops:
            await self._signal_strategy_change(board, phase)

        return ConvergenceSignals(
            is_converged=converged,
            critic_score=evaluation.composite_score * 10,  # 向后兼容
            information_gain=metrics[-1].information_gain if metrics else None,
            unresolved_contradictions=await board.get_unresolved_contradiction_count(),
            loop_detected=not no_loops,
            diminishing_returns=exhausted,
            evaluation=evaluation,
            ...
        )
```

**关键转变**：收敛 = "信息已充分提取"(diminishing returns) + "质量可接受"(multi-dim eval) + "无内部矛盾" + "不在原地打转"。

### 5.6 Benchmark 框架

目录：`backend/benchmarks/`

```
backend/benchmarks/
  tasks/                          # Gold standard 测试用例
    explore_coverage.json
    hypothesis_novelty.json
    evidence_mapping.json
    compose_structure.json
    contradiction_detection.json
  runner.py                       # 执行器
  scorer.py                       # 评分器
```

**Gold standard 格式**：

```json
{
  "task_id": "explore_coverage_001",
  "research_topic": "Transformer attention mechanisms in computer vision",
  "phase": "explore",
  "input_artifacts": [...],
  "expected_evaluation": {
    "coverage_breadth": {
      "expected_score_range": [0.6, 0.8],
      "expected_covered_subtopics": ["self-attention", "cross-attention", "spatial", "channel"]
    }
  },
  "expected_contradictions": [
    {"claim_a": "ViT outperforms CNN on ImageNet",
     "claim_b": "CNNs remain superior for small datasets",
     "expected_relationship": "nuanced"}
  ],
  "expected_convergence": false
}
```

**Ablation 支持**：

| 配置名 | 描述 |
|--------|------|
| `baseline` | 当前系统（单分 Critic, 关键词矛盾检测） |
| `cross_model_only` | 交叉模型评估，但单分 |
| `multi_dim_only` | 多维评估，但同模型 |
| `full_system` | 多维 + 交叉模型 + 信息论收敛 |
| `no_computable` | 仅 LLM 评估（消融可计算指标） |
| `no_llm_eval` | 仅可计算指标（消融 LLM 评估） |

---

## 6. Phase 4: Intelligence Layer

### 6.1 研究状态模型

新文件 `backend/orchestrator/research_state.py`：

```python
class ResearchState(BaseModel):
    """结构化研究进展快照，从 Board artifact 计算得出。"""

    # 覆盖度
    artifact_counts: dict[ArtifactType, int]
    missing_artifact_types: list[ArtifactType]

    # 假设追踪
    hypotheses: list[HypothesisStatus]
    unsupported_hypotheses: list[str]     # 无证据支持的假设 ID
    challenged_hypotheses: list[str]      # 有未解决挑战的假设 ID

    # 证据缺口
    evidence_gaps: list[EvidenceGap]
    evidence_contradictions: list[EvidenceContradiction]

    # 写作准备度
    sections_drafted: list[str]
    sections_needing_revision: list[str]
    uncited_claims: int

    # 质量信号
    phase_eval_scores: dict[ResearchPhase, float]
    latest_critic_weaknesses: list[str]
    open_challenge_count: int
    open_challenges_by_target: dict[AgentRole, int]

    # 信息请求
    pending_info_requests: list[InfoRequest]

    # 元信息
    current_phase: ResearchPhase
    iteration: int
    iterations_since_last_progress: int
    topic_drift_detected: bool
```

`ResearchStateAnalyzer` 读取 Board 计算 `ResearchState`。纯数据提取，无 LLM 调用，目标 < 100ms 完成。

### 6.2 调度评分器 (DispatchScorer)

新文件 `backend/orchestrator/dispatch_scorer.py`：

替代 `planner.py` 的 `sequence[(iteration-1) % len(sequence)]` 固定轮转。

#### 评分规则

| Agent | 高分信号 | 基础分 |
|-------|----------|--------|
| **Librarian** | `unsupported_hypotheses > 0`; 关键证据缺口; 目标 InfoRequest; EXPLORE/EVIDENCE 阶段 | 0.3 |
| **Scientist** | 缺少假设 artifact; 假设被挑战需回应; 证据矛盾需分析; HYPOTHESIZE 阶段 | 0.3 |
| **Director** | 多方向冲突; 停滞检测 (`iterations_since_progress > 3`); phase 转换临近 | 0.2 |
| **Writer** | `sections_needing_revision > 0`; critic 指出结构问题; COMPOSE 阶段; `uncited_claims > 阈值` | 0.3 |
| **Critic** | 距上次 critic ≥ N 轮; 有新 artifact 未审查; 草稿修订完成 | 0.2 |
| **Synthesizer** | 仅 SYNTHESIZE 阶段; 按 lane artifact 完成度评分 | 0.1 |

```python
class DispatchScorer:
    def score(self, state: ResearchState) -> dict[AgentRole, float]:
        scores = {}
        for agent in AgentRole:
            base = self._base_score(agent, state.current_phase)
            need = self._compute_need_signal(agent, state)
            phase_bonus = self._phase_bonus(agent, state.current_phase)
            request_bonus = self._pending_request_bonus(agent, state)
            scores[agent] = base + need + phase_bonus + request_bonus
        return scores
```

#### LLM Planner 降级为 tie-breaker

```python
# 在 planner.py 中
scores = self._scorer.score(research_state)
top_two = sorted(scores.items(), key=lambda x: -x[1])[:2]

if top_two[0][1] - top_two[1][1] < 0.1:
    # 分差太小，咨询 LLM 决断
    agent = await self._llm_tiebreak(top_two, research_state)
else:
    agent = top_two[0][0]
```

减少 LLM 调用：从每次迭代 → 约 10-20% 的迭代。

#### 任务描述动态生成

不再是静态 `_PHASE_TASKS` 字符串，而是引用具体缺口：

```
# 示例生成的任务描述
"Search for empirical evidence supporting hypothesis H-003
(currently 0 supporting findings, 1 contradicting).
Prioritize experimental studies from 2023-2025.
Also address InfoRequest IR-007 from Critic:
'Need papers comparing X and Y methodologies.'"
```

### 6.3 Agent 深化

每个 Agent 重写 `execute()` 添加差异化的前处理/后处理逻辑。

#### DirectorAgent — 研究地图维护

```python
class DirectorAgent(BaseAgent):
    async def execute(self, task, context):
        # 前处理：构建研究地图
        research_map = await self._build_research_map()
        # {research_questions: [{id, question, status, priority}],
        #  knowledge_frontier: [{area, known, unknown, importance}],
        #  strategic_priorities: [{priority, rationale, assigned_to}],
        #  blockers: [{description, resolution_path}]}

        enriched_context = context + self._format_research_map(research_map)
        response = await super().execute(task, enriched_context)

        # 后处理：验证产出引用了已有 RQ ID
        self._validate_map_update(response, research_map)
        return response
```

**停滞干预**：若因 `iterations_since_progress > 3` 被调度，注入特殊 prompt 迫使分析停滞原因并提出具体转向方案。

#### ScientistAgent — 假设生命周期

```python
class ScientistAgent(BaseAgent):
    async def execute(self, task, context):
        # 前处理：构建假设注册表
        registry = await self._build_hypothesis_registry()
        # [{id, text, status (proposed→supported→confirmed/rejected),
        #   confidence, supporting_evidence, contradicting_evidence,
        #   falsification_criteria, experiments_proposed}]

        # 注入注册表 + 指令：
        # - 新假设必须包含可证伪标准
        # - 已有假设根据新证据更新状态，不要重复提出
        # - 被挑战假设必须用证据回应或撤回

        response = await super().execute(task, enriched_context)

        # 后处理：验证假设有 falsification_criteria 和 confidence
        self._validate_hypothesis_fields(response)
        # 自动生成证据缺口 artifact
        self._generate_evidence_gaps(response, registry)
        return response
```

**假设状态流转**：
```
proposed → supported (有支持证据) → confirmed (充分证据+无矛盾)
                                  → challenged (有矛盾证据)
         → rejected (被证伪或撤回)
```

#### CriticAgent — 结构化对抗评审

```python
class CriticAgent(BaseAgent):
    async def execute(self, task, context):
        # 前处理：根据当前 phase 选择评审框架
        framework = self._select_framework(self._current_phase)
        # EXPLORE:     覆盖框架 (是否涵盖主要方面？遗漏关键文献？)
        # HYPOTHESIZE: 逻辑严谨性 (可证伪？有未说明假设？循环论证？)
        # EVIDENCE:    方法论批判 (来源可靠？证据代表性？有混淆变量？)
        # COMPOSE:     学术写作 (论证流、引用完整性、内部一致性)

        # 要求多维评分输出（非单一 1-10）：
        # {completeness, logical_coherence, evidence_quality,
        #  writing_quality, novelty, overall,
        #  critical_gaps: [...],
        #  actionable_suggestions: [{target_agent, action}]}

        response = await super().execute(task, enriched_context)

        # 后处理：解析 actionable_suggestions → 自动生成 InfoRequest
        for suggestion in response.actionable_suggestions:
            await self._create_info_request(suggestion)

        # 若任何维度 < 3 → 自动 RAISE_CHALLENGE
        for dim, score in response.dimension_scores.items():
            if score < 3:
                await self._raise_challenge(dim, score, response)

        return response
```

#### WriterAgent — 论证结构验证

```python
class WriterAgent(BaseAgent):
    async def execute(self, task, context):
        # 前处理：
        # - 读取现有草稿，解析章节名
        # - 构建 claim-证据映射 (哪些 claim 有引用支持)
        # - 识别无引用支持的声明 (含 "研究表明"/"evidence suggests" 但无 [ref])
        claim_evidence_map = await self._build_claim_evidence_map()
        enriched_context = context + self._format_claim_map(claim_evidence_map)

        response = await super().execute(task, enriched_context)

        # 后处理：
        # - 验证新 claim 引用了现有证据 artifact
        # - 检查草稿结构匹配学术论文模板
        # - 存储修订说明（diff summary + 原因）
        self._validate_citations(response)
        self._check_structure(response)
        return response
```

#### LibrarianAgent — 定向证据搜索

增强现有 `execute()`：

```python
# 当前：总是搜索 research_topic[:200]
# 新增：基于证据缺口构建定向查询
async def _build_targeted_queries(self, evidence_gaps, hypothesis_registry):
    queries = []
    for gap in evidence_gaps:
        if gap.related_hypothesis:
            queries.append(self._gap_to_query(gap))
            # e.g. "empirical study on [H-002 keywords] methodology comparison"
    return queries if queries else [self._default_topic_query()]
```

加入 citation chain 追踪：每条证据标注支持/反驳了哪些假设。

#### SynthesizerAgent — 跨视角整合

```python
class SynthesizerAgent(BaseAgent):
    async def execute(self, task, context):
        # 前处理：解析 lane artifact 为比较矩阵
        comparison = await self._build_comparison_matrix()
        # {agreement_areas: [{topic, lanes_agreeing, confidence}],
        #  disagreement_areas: [{topic, lane_positions, resolution_needed}],
        #  unique_contributions: [{lane, contribution}],
        #  quality_ranking: [{lane, avg_critic_score}]}

        # 注入比较矩阵，要求 LLM 裁决分歧（非简单拼接）
        response = await super().execute(task, enriched_context)
        return response
```

### 6.4 Agent 通信协议

#### InfoRequest 队列

存储在 `info_requests` 表。

```python
class InfoRequest(BaseModel):
    request_id: str
    from_agent: AgentRole
    to_agent: AgentRole
    question: str
    context_refs: list[str]          # 相关 artifact ID
    priority: TaskPriority
    parent_request_id: str | None    # 追踪请求链
    fulfilled: bool = False
    response_artifact_id: str | None
```

#### Critic 驱动反馈回路

```
Critic 审查假设 H-003 → evidence_quality = 3
  → 自动生成 InfoRequest(to=librarian, "Search for papers on X")
  → Planner 看到 pending request，提升 Librarian 调度分
  → Librarian 被调度，执行定向搜索
  → 产出 evidence_findings artifact
  → Critic 再次被调度，重新评估
```

#### 循环防护

```python
def _check_cycle(request: InfoRequest) -> bool:
    """防止 A→B→A 循环请求"""
    chain = []
    current = request
    while current.parent_request_id:
        chain.append(current.from_agent)
        current = get_request(current.parent_request_id)
        if len(chain) > 2:
            return True  # 循环检测
    return False
# 若检测到循环 → 改为调度 Critic 裁决
```

### 6.5 动态 Phase 管理

#### Phase 约束软化

当前：`_PHASE_SEQUENCES` 硬性限制每个 phase 可运行的 Agent。

新方案：序列变为调度分数加成（soft preference），而非硬约束。

```python
def _compute_phase_bonus(agent, phase) -> float:
    if agent in PREFERRED_AGENTS[phase]:
        return 0.2   # 加分
    elif agent in ALLOWED_AGENTS[phase]:
        return 0.0   # 不加不减
    else:
        return -0.3  # 减分但不禁止
```

**效果**：COMPOSE 阶段发现证据缺口时，可以直接调度 Librarian 定向搜索，无需正式回退到 EVIDENCE 阶段。

#### 选择性重探索

Critic 在 COMPOSE 阶段发现特定缺口时：
- 保持 phase = COMPOSE
- 任务描述明确标注"COMPOSE 阶段缺口定向检索"
- 收敛检测器不将此视为 phase 回退

#### Phase 阈值自适应

进入每个 phase 时评估初始状态：
- 若 topic 已有大量文献基础 → 降低 EXPLORE 收敛阈值
- 若 Director 的研究地图已包含成熟假设 → 降低 HYPOTHESIZE 迭代下限
- 不跳过 phase（会破坏收敛），只调整所需迭代量

---

## 7. 前端影响

### 7.1 新增 WebSocket 事件

```typescript
// ws-protocol.ts 新增类型

interface QualityMetricsPayload {
  artifact_id: string;
  dimensions: Record<string, number>;  // {coherence: 7, novelty: 5, ...}
  overall_score: number;
  evaluator_model: string;
}

interface PlannerDecisionPayload {
  iteration: number;
  chosen_agent: string;
  rationale: string;
  alternatives_considered: Array<{agent: string; score: number}>;
  board_state_signals: Record<string, number>;
}

// ArtifactUpdatedPayload 扩展（向后兼容）
interface ArtifactUpdatedPayload {
  // ... existing fields
  quality_score?: number;
  embedding_status?: "pending" | "computed" | "failed";
  relations?: Array<{target: string; type: string; confidence: number}>;
}
```

**不删除任何现有事件**，全部向后兼容。

### 7.2 Phase 5: 前端升级方案

#### 设计原则

后端从 Phase 1-4 已经具备了认知、评判、决策三大能力，但前端仍然是 v1 的"消息流 + artifact 卡片"展示。前端升级的核心目标：**让用户看到系统在"思考"什么，而不仅仅是"产出"了什么。**

#### 新增 Sidebar Section：Evaluation

在现有 5 个 section（Overview / Blackboard / Messages / Knowledge / Paper）基础上新增第 6 个：**Evaluation**。

修改文件：
- `frontend/src/app/projects/[id]/_components/sidebar.tsx` — `PROJECT_SECTIONS` 数组添加 `{ key: "evaluation", icon: Activity }`
- `frontend/src/contexts/ProjectSidebarContext.tsx` — `ProjectSection` 类型添加 `"evaluation"`
- `frontend/src/app/projects/[id]/page.tsx` — 添加 `activeSection === "evaluation"` 渲染条件

#### 新增 API Client 函数

在 `frontend/src/lib/api.ts` 中添加：

```typescript
export function getEvaluations(projectId: string, limit = 100) {
  return request(`/api/projects/${projectId}/evaluations?limit=${limit}`);
}
export function getIterationMetrics(projectId: string, limit = 100) {
  return request(`/api/projects/${projectId}/iteration-metrics?limit=${limit}`);
}
export function getClaims(projectId: string, limit = 100) {
  return request(`/api/projects/${projectId}/claims?limit=${limit}`);
}
export function getContradictions(projectId: string, limit = 100) {
  return request(`/api/projects/${projectId}/contradictions?limit=${limit}`);
}
```

#### 新增 WS 事件处理

在 `_hooks/useProjectState.ts` 中添加 `EvaluationCompleted` 和 `PhaseEvaluationCompleted` 事件处理，实时更新评估数据。

#### EvaluationSection 组件设计

新文件：`frontend/src/app/projects/[id]/_components/EvaluationSection.tsx`

包含 4 个子面板，按优先级排序：

##### P0: 研究质量仪表盘（Composite Score + 维度雷达图）

用 Recharts（已安装 v2.15.0）实现：

- **折线图**：每轮迭代的 `composite_score` 趋势，按 phase 分色
- **雷达图**：当前 phase 的 4-5 个维度评分（coverage_breadth, source_diversity, terminology_coverage, gap_identification 等）
- **信息增益面积图**：`information_gain` 随迭代递减的趋势，直观展示"信息枯竭→收敛"

数据源：`GET /api/projects/{id}/evaluations` + `GET /api/projects/{id}/iteration-metrics`

##### P1: Planner 决策日志（为什么选这个 Agent）

- **时间线列表**：每次迭代显示：选了哪个 Agent、评分多少、为什么（rationale）、其他候选的分数
- 让用户看到系统在"思考"而非"轮转"

数据源：WS 事件 `PlannerDecision`（或从 `iteration_metrics.metrics` JSON 字段读取）

##### P2: 矛盾追踪面板

- **矛盾卡片列表**：每个矛盾显示 Claim A vs Claim B、置信度、状态（unresolved / resolved / accepted_as_limitation）
- 状态用颜色区分：红色=未解决，绿色=已解决，灰色=接受为局限

数据源：`GET /api/projects/{id}/contradictions` + `GET /api/projects/{id}/claims`

##### P3: Claims 知识图谱（可选，复杂度最高）

- 展示提取的 claims 及其来源 artifact、置信度
- 可筛选：按 agent / 按置信度 / 按类型（factual/causal/comparative）

数据源：`GET /api/projects/{id}/claims`

#### OverviewSection 增强

在现有 OverviewSection 中嵌入轻量级评估摘要（不需要切到 Evaluation tab 就能看到核心指标）：

- **Mini 评分卡**：当前 phase 的 composite_score（大字号）+ 相比上次迭代的变化（↑↓）
- **收敛进度条**：质量达标（✓/✗）+ 信息枯竭（✓/✗）+ 无矛盾（✓/✗）→ 三条件可视化

#### 工作量估算

| 工作项 | Sessions | 优先级 |
|--------|----------|--------|
| Sidebar + 路由 + API client + 类型定义 | 1 | P0 |
| 质量仪表盘（折线图 + 雷达图 + 信息增益图） | 2-3 | P0 |
| OverviewSection mini 评分卡 + 收敛进度条 | 1 | P0 |
| Planner 决策日志时间线 | 1-2 | P1 |
| 矛盾追踪面板 | 1-2 | P2 |
| Claims 知识图谱 | 2-3 | P3 |
| WS 实时更新集成 | 1 | P1 |
| **合计** | **9-13 sessions** | |

#### 里程碑

**M5a（P0 完成）**：Evaluation tab 可用，折线图+雷达图+信息增益图渲染正常，OverviewSection 显示 mini 评分卡。约 4 sessions。

**M5b（P1 完成）**：Planner 决策日志可见，用户能看到"为什么选这个 Agent"。约 6 sessions 累计。

**M5c（全部完成）**：矛盾面板 + Claims 图谱上线。约 10-13 sessions 累计。

#### 设计规范

遵循现有 Indigo 设计系统：
- 颜色：`#818cf8`（dark）/ `#4f46e5`（light）
- 卡片：`rounded-xl border border-aide-border bg-aide-bg-tertiary`
- 图表主色：Indigo 渐变（`#818cf8` → `#6366f1` → `#4f46e5`）
- 深色/浅色模式：通过 CSS 变量自动适配
- 响应式：grid/flex + Tailwind，无固定宽度

### 7.3 可简化的前端

- Blackboard 数据来源从文件系统扫描改为 API 查询 → 简化轮询逻辑
- Pipeline 可视化可展示真实的调度决策历史（非固定序列）

---

## 8. 配置变更

### 8.1 新增环境变量

```bash
# Feature flags（增量迁移控制）
AIDE_USE_SEMANTIC_BOARD=false        # 启用语义知识层
AIDE_USE_MULTI_EVAL=false            # 启用多维评估
AIDE_USE_ADAPTIVE_PLANNER=false      # 启用自适应规划

# 评估
AIDE_EVAL_MODEL=deepseek-chat        # 交叉评估模型
AIDE_EVAL_DIMENSIONS=coherence,novelty,evidence,structure,relevance
AIDE_EVAL_CROSS_MODEL=true           # 强制交叉模型评估

# 嵌入
AIDE_EMBEDDING_MODEL=qwen/qwen3-embedding-8b   # 默认嵌入模型
AIDE_EMBEDDING_DIMENSIONS=1536

# pgvector
AIDE_PGVECTOR_ENABLED=true

# 语义层
AIDE_RELATION_EXTRACTION_MODEL=deepseek-chat
AIDE_COVERAGE_RECOMPUTE_INTERVAL=3   # 每 N 轮重算覆盖度
AIDE_CONTEXT_SEMANTIC_WEIGHT=0.50
AIDE_CONTEXT_GRAPH_WEIGHT=0.15
AIDE_CONTEXT_RECENCY_WEIGHT=0.15
AIDE_CONTEXT_AFFINITY_WEIGHT=0.20
AIDE_CONTRADICTION_CONFIDENCE_THRESHOLD=0.6
AIDE_SEMANTIC_DEDUP_THRESHOLD=0.85

# 收敛（信息论）
AIDE_CONVERGENCE_INFO_GAIN_THRESHOLD=0.05
AIDE_CONVERGENCE_GAIN_WINDOW=5
AIDE_CONVERGENCE_LOOP_THRESHOLD=0.8

# 迁移
AIDE_MIGRATE_ON_START=false          # 启动时自动迁移文件系统 artifact 到 DB
```

### 8.2 config.py 新增字段

```python
# Feature flags
use_semantic_board: bool = False
use_multi_eval: bool = False
use_adaptive_planner: bool = False

# Evaluation
eval_model: str = "deepseek-chat"
eval_dimensions: list[str] = ["coherence", "novelty", "evidence", "structure", "relevance"]
eval_cross_model: bool = True

# Embedding
embedding_model: str = "qwen/qwen3-embedding-8b"
embedding_dimensions: int = 1536

# pgvector
pgvector_enabled: bool = True

# Semantic layer
relation_extraction_model: str = "deepseek-chat"
coverage_recompute_interval: int = 3
context_semantic_weight: float = 0.50
context_graph_weight: float = 0.15
context_recency_weight: float = 0.15
context_affinity_weight: float = 0.20
contradiction_confidence_threshold: float = 0.6
semantic_dedup_threshold: float = 0.85

# Convergence
convergence_info_gain_threshold: float = 0.05
convergence_gain_window: int = 5
convergence_loop_threshold: float = 0.8

# Migration
migrate_on_start: bool = False
```

### 8.3 Docker Compose 变更

唯一变更：

```yaml
postgres:
  image: pgvector/pgvector:pg16    # 替代 postgres:16-alpine
```

`pgvector/pgvector:pg16` 是 `postgres:16-alpine` 的 drop-in 替换，预装 pgvector 扩展。无新服务。

---

## 9. 测试策略

### 9.1 集成测试（真实 LLM 调用）

目录：`backend/tests/integration/`

- 标记 `@pytest.mark.integration`（默认跳过，手动/nightly 运行）
- 使用最便宜模型（`deepseek-chat`）
- 松散断言（检查结构，不检查内容）

| 测试场景 | 验证内容 |
|----------|----------|
| `test_agent_output_parseable` | 每个 Agent 真实调用，输出可解析为 `AgentResponse` |
| `test_critic_multi_dimensional` | Critic 真实评审，输出含多维评分结构 |
| `test_full_phase_2_iterations` | 完整 phase 跑 2 轮，artifact 产出正常 |
| `test_semantic_dedup` | 2 个语义相似 artifact，去重正确 |
| `test_claim_extraction` | 真实 artifact 内容，提取 claims 结构正确 |
| `test_contradiction_detection` | 2 个矛盾 claim，检测到矛盾 |

**成本预算**：每次集成测试运行 < $0.10 USD。

### 9.2 单元测试（Mock LLM）

保留现有 mock 测试策略，但覆盖新增逻辑：
- `DispatchScorer` 给定 `ResearchState` → 验证分数正确
- `InformationTheoreticConvergence` 给定 metrics → 验证收敛判断
- `ResearchStateAnalyzer` 给定 board 数据 → 验证状态提取
- 循环防护逻辑
- Phase 软约束评分

### 9.3 可重复性策略

- **结构断言**：检查 key 存在、分数在范围内、type 合法
- **统计断言**：跑 3 次取中位数（integration tests）
- **Snapshot 录制**：首次运行录制 LLM 响应到文件，后续可回放（unit test mode）

---

## 10. 风险评估与排期

### 10.1 各阶段风险

| Phase | 风险等级 | 主要风险 | 缓解措施 |
|-------|----------|----------|----------|
| Phase 1 | 低 | 纯增量变更 | 现有测试必须全部通过 |
| Phase 2 | 中 | 核心数据通路变更 | Feature flag + dual-write（同时写文件系统和DB） |
| Phase 3 | 低-中 | 新增到 engine 循环 | 评估结果与旧 critic_score 并行输出 |
| Phase 4 | 中-高 | 改变 Agent 调度行为 | A/B 对比：新旧 planner 并行记录，验证新方案更优 |

### 10.2 回滚策略

每个 Phase 通过 feature flag 独立控制：
1. 设置 `AIDE_USE_SEMANTIC_BOARD=false`（或对应 flag）
2. 系统立即回退到旧路径
3. 无需代码部署，只需改环境变量

### 10.3 验证标准

**Phase 1 完成标准**：
- [ ] 所有现有测试通过
- [ ] 新 DB 表创建成功（Alembic 迁移）
- [ ] Settings 从 JSON 文件迁移到 DB 正常工作
- [ ] pgvector 扩展启用
- [ ] 死代码已清除

**Phase 2 完成标准**：
- [ ] `SemanticBoard` 通过 `Board` Protocol 所有接口测试
- [ ] 语义去重优于 Jaccard（相同测试集上准确率更高）
- [ ] 上下文构建延迟 < 500ms（100 artifact 量级）
- [ ] 关系提取正确率 > 80%（人工抽查 20 个 artifact）

**Phase 3 完成标准**：
- [ ] 交叉模型评估产出可解析的多维评分
- [ ] 信息增益检测能区分"有效新内容"和"换皮重复"
- [ ] 矛盾检测在 benchmark 上 F1 > 0.7
- [ ] 收敛检测在 3 个测试 topic 上表现合理

**Phase 4 完成标准**：
- [ ] 自适应 planner 在 3 个测试 topic 上优于固定轮转（更少迭代/更高质量）
- [ ] Agent 深化不影响输出可解析性
- [ ] InfoRequest 通信不产生循环
- [ ] Critic 反馈回路正常驱动后续 Agent 调度

---

## 11. 附录：代码组织

### 新增文件

```
backend/
  blackboard/
    semantic_board.py              # SemanticBoard 实现
  orchestrator/
    research_state.py              # ResearchState + Analyzer
    dispatch_scorer.py             # Agent 调度评分器
  evaluation/
    __init__.py
    evaluator.py                   # EvaluatorService (交叉模型评估)
    dimensions.py                  # 维度定义与评分逻辑
    metrics.py                     # 可计算结构指标
    claims.py                      # Claim 提取与矛盾检测
  benchmarks/
    __init__.py
    runner.py                      # Benchmark 执行器
    scorer.py                      # 评分器
    tasks/                         # Gold standard 测试用例
  migrations/                     # Alembic
    env.py
    versions/
  models/
    artifact.py                    # Artifact ORM
    evaluation.py                  # EvaluationResult ORM
    message.py                     # Message ORM
    challenge.py                   # Challenge ORM
    project_settings.py            # ProjectSettings ORM
    claim.py                       # Claim + Contradiction ORM
    info_request.py                # InfoRequest ORM
    iteration_metric.py            # IterationMetric ORM
```

### 删除文件

```
backend/blackboard/adapter.py     # 确认死代码
backend/memory/                    # WriteBackGuard 移到 agents/ 后删除目录
```

### 修改文件

```
backend/orchestrator/planner.py    # 调度评分器替代轮转
backend/orchestrator/convergence.py # 信息论收敛替代数字比较
backend/orchestrator/engine.py     # 集成评估+事件+状态分析
backend/orchestrator/factory.py    # Feature flag 分支 + 新依赖注入
backend/orchestrator/backtrack.py  # 语义矛盾替代关键词匹配
backend/agents/base.py             # 添加 pre/post 处理钩子
backend/agents/director.py         # 研究地图维护
backend/agents/scientist.py        # 假设生命周期
backend/agents/critic.py           # 结构化多维评审
backend/agents/writer.py           # 论证结构验证
backend/agents/librarian.py        # 定向证据搜索
backend/agents/synthesizer.py      # 比较矩阵裁决
backend/api/settings.py            # DB-backed settings
backend/config.py                  # 新配置字段
backend/types.py                   # 新类型定义
docker-compose.yml                 # pgvector 镜像
```
