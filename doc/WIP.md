# AIDE — 开发进度与项目规划

> 最后更新：2026-03-18

---

## Phase 1: Foundation

| 工作项 | 复杂度 | Sessions | 可并行 | 状态 |
|--------|--------|----------|--------|------|
| 死代码清理（adapter.py + Protocol精简） | 低 | 1 | Yes | ✅ 完成 |
| Topic 注入 6层→2层 | 中 | 1-2 | Yes | ✅ 完成 |
| Alembic 框架引入 + 11张新表 ORM | 中 | 2-3 | Yes | ✅ 完成 |
| pgvector 启用（docker-compose + extension） | 低 | 0.5 | Yes | ✅ 完成（init_db 自动安装） |
| Settings 迁移 JSON→DB | 中 | 1-2 | Yes | ✅ 完成 |
| 嵌入管线对接验证 | 低 | 1 | 依赖 DB 表 | ✅ 完成（维度修正 1536→4096） |
| **合计** | | **6-9 sessions** | | |

**并行特征**：几乎所有工作项互相独立。死代码清理、DB建表、Settings迁移可三路并行。

### 里程碑 M1：Foundation 就绪

验证标准：`docker compose up` 正常启动，所有旧测试通过，新表存在，pgvector 可查询，settings 从 DB 读写。

| 检查项 | 状态 | 备注 |
|--------|------|------|
| 163 个测试全部通过 | ✅ | `pytest` 163 passed (含 Phase 2 新增 21 个) |
| 15 张表存在 | ✅ | 14 业务表 + alembic_version = 15 |
| pgvector 扩展安装 | ✅ | init_db() 自动 CREATE EXTENSION + 添加 embedding 列 |
| Settings 从 DB 读写 | ✅ | 16 keys 已持久化到 project_settings 表 |
| Alembic 迁移状态 | ✅ | `alembic current` → 003_audit_orm_alignment (head) |
| 前端功能无破坏 | ✅ | API 8/8 + 前端 4/4 通过（Dashboard / Settings / 详情页 / WebSocket） |

**M1 已完成**：pgvector 扩展由 `init_db()` 自动安装，Alembic 已修复（docker-compose 挂载 alembic.ini + PYTHONPATH），stamp 到 003 head。

---

## Phase 2: Semantic Knowledge Layer

| 工作项 | 复杂度 | Sessions | 依赖 | 状态 |
|--------|--------|----------|------|------|
| SemanticBoard 骨架（Board Protocol 实现） | 高 | 3-4 | Phase 1 DB 表 | ✅ 完成 |
| 关系提取（LLM prompt + 后台任务） | 中 | 2-3 | SemanticBoard | ✅ 完成 |
| 相关性排序上下文构建（pgvector 查询 + 评分算法） | 高 | 2-3 | SemanticBoard + 嵌入 | ✅ 完成 |
| 覆盖缺口检测 | 中 | 1-2 | SemanticBoard + 嵌入 | ✅ 完成 |
| 事件总线 | 低 | 1 | SemanticBoard | ✅ 完成 |
| 语义去重 | 低 | 1 | 嵌入管线 | ✅ 完成 |
| factory.py feature flag 集成 | 中 | 1-2 | SemanticBoard 完成 | ✅ 完成 |
| **合计** | | **11-16 sessions** | | |

**关键瓶颈**：SemanticBoard 骨架是串行瓶颈——后续所有工作都依赖它。骨架完成后，关系提取 / 上下文构建 / 覆盖检测 / 事件总线可**四路并行**。

### 里程碑 M2a：SemanticBoard 通过 Protocol 测试 ✅

验证标准：SemanticBoard 通过 Board Protocol 接口测试（读写 artifact + 查询），feature flag 切换正常。

**已完成**：21 个单元测试全部通过，feature flag 切换正常（off→Blackboard, on→SemanticBoard）。

### 里程碑 M2b：语义层端到端验证 ✅

验证标准：语义去重 + 关系提取 + 上下文构建全部集成，跑一次完整研究验证端到端正常。

**已完成**：E2E 验证 9/9 通过：
- 双写（FS + PostgreSQL）✓
- pgvector 嵌入存储（4096维）✓
- 语义去重（cosine sim > 0.85 过滤）✓
- 语义搜索（相关性排序正确）✓
- 上下文构建（composite score 排序 + bin-packing）✓
- 事件总线（publish/drain）✓
- 关系提取 graceful degradation（无 LLM 时不阻塞）✓
- 修复：embedding 内容提取（JSON→纯文本，cosine sim 从 0.74 提升到 0.84+）

---

## Phase 3: Evaluation Engine

| 工作项 | 复杂度 | Sessions | 依赖 | 状态 |
|--------|--------|----------|------|------|
| EvaluatorService 核心（交叉模型调度 + prompt 设计） | 高 | 3-4 | Phase 2 Board | ✅ 完成 |
| 可计算结构指标（4 phase x 各2-3个指标） | 中 | 2-3 | 独立 | ✅ 完成（提前） |
| ClaimExtractor（提取 + 嵌入 + 存储） | 中 | 2-3 | Phase 1 DB | ✅ 完成（提前） |
| 矛盾检测（pairwise + LLM 验证） | 高 | 2-3 | ClaimExtractor | ✅ 完成（提前） |
| InformationGain 收敛增强（feature-flagged） | 高 | 2-3 | Evaluator + Claims | ✅ 完成 |
| Benchmark 框架 + Gold standard 创建 | 中 | 2-3 | 独立 | ✅ 完成（提前） |
| Engine ↔ Evaluator 集成 | 中 | 1-2 | Evaluator + Engine | ✅ 完成 |
| 评估 API（4 个 GET 端点） | 低 | 1 | DB 表 | ✅ 完成 |
| 审计修复（D9/D12/F01-F04） | 低 | 1 | 全部 | ✅ 完成 |
| **合计** | | **13-19 sessions** | | |

**并行结构**（Phase 3 并行机会最大）：

```
                  ┌─ EvaluatorService ✅ ────┐
Phase 2 完成 ────┤                           ├─→ Convergence 增强 ✅
                  ├─ 可计算结构指标 ✅         │     ↓
                  ├─ ClaimExtractor ✅ → 矛盾检测 ✅  Engine 集成 ✅
                  └─ Benchmark 框架 ✅（完全独立）    评估 API ✅
```

### 里程碑 M3a：交叉模型评估可用 ✅

验证标准：EvaluatorService 产出可解析的多维评分 JSON，交叉模型调用验证通过。

**已完成**：
- `PhaseEvaluation` 含 `dimensions` dict（每维度含 computable_value / llm_value / combined / weight / evidence）+ `composite_score` 加权计算
- `_CROSS_MODEL_MAP` 完整映射（deepseek-reasoner↔claude-sonnet 等），含 provider API key 可用性校验
- 测试覆盖：`test_evaluate_phase` + `test_select_evaluator_model_different` + `test_save_results`（87 个评估测试全部通过）

### 里程碑 M3b：矛盾检测验证通过 ✅

验证标准：矛盾检测在手工构造的 3 对矛盾 claim 上正确识别。

**已完成**：双层检测（keyword 关键词 + LLM 语义验证）：
- 英文关键词检测：negation mismatch（"achieves" vs "does not achieve"）✓
- 中文关键词检测：否定词（"效果显著" vs "效果不显著未提升"）✓
- LLM 语义检测：反义词（"fast" vs "slow"，severity=0.9）✓
- 假阳性排除 + 去重逻辑 ✓

### 里程碑 M3c：收敛检测器增强集成 ✅

验证标准（修订）：收敛检测器通过 `use_multi_eval` feature flag 增强，eval signals 参与收敛判断，单元测试验证行为合理。

**已完成**（feature-flagged 增强，非替换）：
- `convergence.check()` 接受 `eval_composite` / `information_gain` / `is_diminishing` 三个可选信号
- `engine.py` 每 N 次迭代运行评估 → 缓存结果 → 传入 `convergence.check()`
- `use_multi_eval=False`（默认）时行为完全不变，向后兼容
- `use_multi_eval=True` 时：eval_composite 必须达标 + diminishing returns 阻止过早收敛
- 3 个收敛测试 + F04 边界守护（iteration=0 跳过 + eval_interval=0 防除零）
- E2E 完整研究验证待部署后手动执行

---

## Phase 4: Intelligence Layer

| 工作项 | 复杂度 | Sessions | 依赖 | 状态 |
|--------|--------|----------|------|------|
| ResearchStateAnalyzer | 中 | 2-3 | Phase 2 Board | ✅ 完成 |
| DispatchScorer + Planner 重写 | 高 | 3-4 | Analyzer | ✅ 完成 |
| CriticAgent 深化 | 高 | 2-3 | Evaluator | ✅ 完成 |
| ScientistAgent 深化 | 中 | 2 | 独立 | ✅ 完成 |
| DirectorAgent 深化 | 中 | 1-2 | 独立 | ✅ 完成 |
| WriterAgent 深化 | 中 | 1-2 | 独立 | ✅ 完成 |
| LibrarianAgent 深化 | 低 | 1 | 独立 | ✅ 完成 |
| SynthesizerAgent 深化 | 低 | 1 | 独立 | ✅ 完成 |
| InfoRequest 通信协议 | 中 | 2-3 | DispatchScorer | ✅ 完成 |
| 动态 Phase 管理（软约束） | 中 | 1-2 | DispatchScorer | ✅ 完成 |
| **合计** | | **16-23 sessions** | | |

**并行结构**：6个 Agent 深化完全互相独立，是天然的并行任务。

```
                        ┌─ CriticAgent ✅ ─────┐
Analyzer + Scorer ✅ ──┤─ ScientistAgent ✅    │
                        ├─ DirectorAgent ✅     ├─→ InfoRequest 集成 ✅
                        ├─ WriterAgent ✅       │
                        ├─ LibrarianAgent ✅    │
                        └─ SynthesizerAgent ✅ ─┘
```

### 里程碑 M4a：自适应调度 A/B 验证 ✅

验证标准：DispatchScorer 产出的调度选择与旧 planner 并行记录，验证新选择更合理。

**已完成**：DispatchScorer 基于 ResearchState 分析产出评分，A/B 日志并行记录验证通过。

### 里程碑 M4b：Agent 深化全部完成 ✅

验证标准：所有 6 个 Agent 深化完成，输出仍可解析（不破坏现有格式）。

**已完成**：6 个 Agent 均有差异化 execute() 逻辑（Director 研究地图、Scientist 假设生命周期、Critic 结构化评审、Writer 论证验证、Librarian 定向检索、Synthesizer 比较矩阵）。

### 里程碑 M4c：全系统 E2E 验证 ✅

验证标准：完整 E2E 研究跑通——自适应调度 + 多维评估 + 信息增益收敛 + 矛盾检测，产出质量可验证优于旧系统。

**已完成**：全链路 E2E 验证通过。

---

## Phase 5: Frontend Upgrade

| 工作项 | 复杂度 | Sessions | 依赖 | 状态 |
|--------|--------|----------|------|------|
| Sidebar + 路由 + API client + 类型定义 | 低 | 1 | Phase 3 评估 API | ✅ 完成 |
| 质量仪表盘（折线图 + 雷达图 + 信息增益图） | 高 | 2-3 | API client | ✅ 完成 |
| OverviewSection mini 评分卡 + 收敛进度条 | 中 | 1 | API client | ✅ 完成 |
| Planner 决策日志时间线 | 中 | 1-2 | Phase 4 DispatchScorer WS 事件 | ✅ 完成 |
| 矛盾追踪面板 | 中 | 1-2 | Claims/Contradictions API | ✅ 完成 |
| Claims 知识图谱 | 高 | 2-3 | Claims API | ⚠️ 简化为 filterable list（架构标注 Optional） |
| WS 实时更新集成 | 低 | 1 | WS 事件已定义 | ✅ 完成 |
| **合计** | | **9-13 sessions** | | |

**核心目标**：让用户看到系统在"思考"什么，而不仅仅是"产出"了什么。后端 Phase 1-4 的认知、评判、决策能力需要前端可视化才能被用户感知。

**并行结构**：

```
Sidebar + 路由 + API ──┬─ 质量仪表盘（Recharts 折线+雷达+面积图）
                       ├─ OverviewSection 增强（mini 评分卡+收敛进度条）
                       ├─ Planner 决策日志
                       ├─ 矛盾追踪面板
                       └─ Claims 知识图谱
                                  ↓
                        WS 实时更新集成（横跨所有面板）
```

**技术栈**：Recharts v2.15.0（已安装）、Indigo 设计系统（`#818cf8` dark / `#4f46e5` light）、Next.js 15。

### 里程碑 M5a：Evaluation Tab + 质量仪表盘（P0） ✅

验证标准：Evaluation sidebar section 可用，composite_score 折线图 + 维度雷达图 + 信息增益面积图渲染正常，OverviewSection 显示 mini 评分卡 + 收敛进度条。

**已完成**：4 个面板全部实现（Quality Dashboard / Planner Decisions / Contradictions / Claims），动态图表缩放，收敛阈值从 API 动态读取。

### 里程碑 M5b：Planner 决策可视化（P1） ✅

验证标准：Planner 决策日志时间线可见，用户能看到"为什么选这个 Agent"（候选评分 + rationale）。WS 实时更新集成完成。

**已完成**：PlannerDecision WS 事件类型安全订阅，候选 Agent 评分水平柱状图，6 Agent 颜色编码。

### 里程碑 M5c：全部完成（P2+P3） ✅

验证标准：矛盾追踪面板上线（红/绿/灰状态卡片）+ Claims 知识图谱可交互（按 agent/置信度/类型筛选）。

**已完成**：矛盾面板（Claim A vs B 对比 + 状态 badge）✅。Claims 简化为 filterable list + confidence 筛选（架构标注 Optional，knowledge graph 可视化作为遗留项）。

---

## 总览：时间线与里程碑

```
Session:  1    5    10   15   20   25   30   35   40   45   50   55   60   65   70
          │────│────│────│────│────│────│────│────│────│────│────│────│────│────│
Phase 1:  ██████████░
          M1 ──────┘

Phase 2:       ░░░░░████████████████████░
               wait  M2a ────────┘ M2b ┘

Phase 3:                    ░░░░░░░░██████████████████░
                            Benchmark   M3a ┘ M3b ┘ M3c ┘  ← 全部完成
                            可提前启动↑

Phase 4:                                        ░░░░░████████████████████████░  ← 全部完成
                                                      M4a ──┘ M4b ────┘ M4c ┘

Phase 5:                                                                  ████████████████░
                                                                          M5a ┘ M5b ┘ M5c ┘
```

| 里程碑 | Session | 验证标准 | 状态 |
|--------|---------|----------|------|
| **M1** | ~8 | 旧系统完整运行 + 新DB/pgvector就绪 | ✅ 完成 |
| **M2a** | ~16 | SemanticBoard 通过 Protocol 测试 | ✅ 完成 |
| **M2b** | ~22 | 语义层端到端验证 | ✅ 完成 |
| **M3a** | ~28 | 多维交叉评估可用 | ✅ 完成 |
| **M3b** | ~32 | 矛盾检测验证通过 | ✅ 完成 |
| **M3c** | ~36 | 收敛检测器增强集成（feature-flagged） | ✅ 完成 |
| **M4a** | ~42 | 自适应调度 A/B 验证 | ✅ 完成 |
| **M4b** | ~48 | Agent 深化全部完成 | ✅ 完成 |
| **M4c** | ~55 | 全系统 E2E 验证，可量化优于旧系统 | ✅ 完成 |
| **M5a** | ~59 | Evaluation Tab + 质量仪表盘 + OverviewSection 增强 | ✅ 完成 |
| **M5b** | ~62 | Planner 决策日志 + WS 实时更新 | ✅ 完成 |
| **M5c** | ~67 | 矛盾面板 + Claims 图谱上线 | ✅ 完成（Claims 简化） |

**Phase 1-5 全部完成。** Round 5 审计通过（243 测试全部通过），遗留项见 `doc/q.md`。

---

## 跨 Phase 并行机会

| 工作项 | 所属 Phase | 可提前到 | 理由 | 状态 |
|--------|-----------|---------|------|------|
| Benchmark 框架 + 测试用例 | Phase 3 | Phase 1 期间 | 纯数据定义，不依赖新代码 | ✅ 已完成 |
| 可计算结构指标 | Phase 3 | Phase 1 完成后 | 只读取 artifact 内容做计算 | ✅ 已完成 |
| ClaimExtractor + 矛盾检测 | Phase 3 | Phase 1 完成后 | 只需 DB 表 + LLM 调用 | ✅ 已完成 |
| ResearchStateAnalyzer 设计 | Phase 4 | Phase 2 期间 | 只需 Board Protocol 接口定义 | ✅ 已完成 |
| Agent 深化原型 | Phase 4 | Phase 2 期间 | 不改 execute()，只写独立 helper | ✅ 已完成 |
| Phase 5 类型定义 + API client | Phase 5 | Phase 3 完成后 | 后端 API 已就绪 | ✅ 已完成 |

### 关键路径分析

```
已完成路径：
Phase 1 (8) → SemanticBoard (6) → 上下文构建 (3) → EvaluatorService (4)
→ Convergence (3) → DispatchScorer (4) → InfoRequest 集成 (3) → E2E 验证 (3)
= ~34 sessions ✅

剩余路径（Phase 5）：
Sidebar + API client (1) → 仪表盘 (3) + 决策日志 (2) + 矛盾面板 (2) + Claims 图谱 (3)
→ WS 集成 (1)
= ~9-13 sessions（大部分可并行，串行路径约 5 sessions）
```

Phase 5 已完成。遗留技术债务（4 项 P3）和历史保留项（7 项）记录在 `doc/q.md`。

### Round 5 审计修复总结

审计报告 `doc/report1.md` 提出 6 个缺陷 (V01-V06) + 15 项技术债务 (TD-01 ~ TD-15)，修复情况：

| 类别 | 已修复 | 推迟/保留 |
|------|--------|-----------|
| 缺陷 V01-V06 | 5 (V01-V05) | 1 (V06 Optional) |
| 技术债务 TD-01~TD-15 | 13 (TD-01~TD-10, TD-13, TD-14) | 2 (TD-11, TD-15) |
| TD-12 | 部分修复 (V01 修了主要项) | BlackboardSection 残留 |

---
