# AIDE — 开发进度 WIP

> 最后更新：2026-03-11（Session 7）

---

## 总体进度概览

| 阶段 | 规划内容 | 完成度 | 状态 |
|------|----------|--------|------|
| Phase 1：基础架构 | Docker、FastAPI、DB、Blackboard、WS | ~90% | ✅ 基本完成 |
| Phase 2：多智能体核心 | 6 Agent + Orchestrator 主循环 + 并行 Lane | **~98%** | ✅ 核心稳定，Anthropic 接入，并行架构就绪 |
| Phase 3：高级研究能力 | 语义检索、真实 RAG、论文导出 | ~60% | 🔧 arXiv+S2+BM25 全链路打通，论文导出完善 |
| Phase 4：产品打磨 | 智能推荐、实验追踪、协作 | ~10% | 🔧 前端 concurrency 滑块、settings Anthropic 区 |

---

## Phase 1：基础架构（~90%）

### ✅ 已完成
- Docker Compose 4 服务（backend、frontend、postgres、chromadb）
- FastAPI 后端框架 + Alembic 数据库迁移
- PostgreSQL 数据模型：Project、Paper、TokenUsage
- Blackboard 文件系统存储（`workspace/projects/{id}/`）
- WebSocket 实时推送（`api/ws.py`）
- REST API：项目 CRUD、论文管理、检查点、设置
- Next.js 15 + Tailwind CSS 4 前端基础框架
- 项目创建/列表/详情页
- L0/L1/L2 上下文分级架构（数据结构 + LLM 生成逻辑已完整）
- 设置持久化（`workspace/settings_overrides.json`）
- **ContextBuilder**（`context_builder.py`）：L2→L1→L0 自动降级到 30K token 预算内

### ❌ 未完成
- 前端错误边界 / 全局错误处理 UI

---

## Phase 2：多智能体核心（~98%）

### ✅ 已完成
- **6 个 Agent**：Director、Scientist、Librarian、Writer、Critic、**Synthesizer**（Session 7 新增）
- OrchestrationEngine 主循环（plan → dispatch → validate → convergence → loop）
- OrchestratorPlanner（纯规则轮转，含 SYNTHESIZE 阶段序列）
- ConvergenceDetector（per-phase Critic 评分阈值 + max-iteration 保护）
- BacktrackController（矛盾时回退阶段）
- HeartbeatMonitor（崩溃恢复，stale 阈值可配置 360s）
- CheckpointManager（关键节点暂停等待用户审批，WS + REST 双路响应）
- SubAgentPool（并行子任务分发）
- WriteBackGuard（markdown fence 剥离 + 输入截断降噪）
- **LLM Router（DeepSeek + OpenRouter + Anthropic 三 provider + fallback）**（Session 7）
- **Anthropic/Claude Provider**（Session 7）：支持 claude-opus-4-6/sonnet-4-6，可配 base_url 代理
- **Per-role 模型分配**（Session 7）：推理角色→deepseek-reasoner，工具角色→deepseek-chat，用户可在 settings 覆盖为 Claude
- **并行 Lane 架构**（Session 7）：1-5 独立研究 lane，asyncio.gather 并行执行，合成阶段汇总
- **6 阶段研究流程**：EXPLORE → HYPOTHESIZE → EVIDENCE → COMPOSE → [SYNTHESIZE] → COMPLETE
- **Claude JSON 输出强制**（Session 7）：base.py 对 Claude 模型追加 JSON 格式指令，消除 non-JSON 问题
- TokenUsage 跟踪（`tracker.py`）
- 研究主题 6 层注入链（DB→Board→Planner→BaseAgent→Jinja2→Engine per-iter 检查）
- 主题漂移检测：`_check_on_topic()` + `TopicDriftWarning` WS 事件
- 前端运行状态指示器（ping 动画、iteration 计数、当前 agent、漂移 Toast）
- Challenge 自动 dismiss（`phase_iters > 2` 时自动解决）
- Phase COMPLETE 论文导出（`_on_research_complete()` → `exports/paper.md` + `ResearchCompleted` WS）
- Critic 分数提取链路：用 `agent_role == CRITIC` 替代不可靠的 artifact_type 字符串匹配
- L1 JSON 生成加固：markdown fence 剥离 + 强化 system prompt
- SPAWN_SUBAGENT handler：消除 "Unhandled action type" 警告

### ❌ 未完成
- **LLM 语义 Dedup**：`dedup_check()` 目前是直通（pass-through），非语义去重
- **Agent 输出 Pydantic schema 强校验**：仅靠 JSON parse
- **前端 ResearchCompleted 处理**：WS 事件已定义，前端未订阅/显示完成状态
- **并行 Lane 前端进度指示**：后端已支持，前端 lane 进度未可视化

---

## Phase 3：高级研究能力（~60%）

### ✅ 已完成
- ChromaDB + BM25 集成（服务运行，hybrid search 已实现）
- PDF 上传 → 解析（PyMuPDF/pdfplumber）→ 分块 → 嵌入（text-embedding-3-small）→ ChromaDB + BM25 入库（完整流水线）
- Librarian 真实 arXiv + Semantic Scholar 检索：`WebRetriever` 双源 fallback
- **S2 429 冷却期**（Session 7）：429 后 5 分钟内跳过 S2 直接走 arXiv，避免无效重试
- **Query 缓存归一化**（Session 7）：排序去重关键词作 cache key，翻译结果微差不再导致缓存未命中
- **Librarian 本地知识检索完善**（Session 7）：无 OpenAI key 时跳过 Hybrid search 避免 SSL 错误；BM25 fallback 现在返回 doc_texts 内容
- **论文导出增强**（Session 7）：`export_paper()` 除 DRAFT 外补充 HYPOTHESES/EVIDENCE/DIRECTIONS/OUTLINE，产出从 2 section→11 section、6.5KB→62KB

### ❌ 未完成
- **arXiv 检索结果未入 ChromaDB**：检索到的论文没有持久化到向量库
- **论文导出（PDF/LaTeX）**：目前只有 Markdown，无渲染引擎
- **前端论文编辑器 / 下载**：未实现
- **引用图谱构建**：`citation_graph.py` 存在但未集成

---

## Phase 4：产品打磨（~10%）

### ✅ 已完成
- 基础设置页面（LLM provider 选择、token 预算配置）
- **Anthropic 配置 UI**（Session 7）：API Key + Base URL 输入、Claude 模型选项
- **项目创建 concurrency 滑块**（Session 7）：1-5 并行 lane 选择
- **Synthesize 阶段标签**（Session 7）：前端 PHASES 显示 6 个阶段

### ❌ 未完成
- 智能研究方向推荐
- 实验追踪与可视化（假设演化树、证据网络图）
- 多用户协作
- 研究模板库

---

## Bug Fixes 历史（各 session 已修复）

| Session | 修复内容 |
|---------|----------|
| Session 2 | `tracker.py` ORM 双重定义冲突、`async_sessionmaker` 误用 `await`、列名错误 |
| Session 2 | `factory.py` CheckpointManager 注册表；`ws.py` checkpoint 响应用正确实例；`checkpoints.py` REST 实现 |
| Session 3 | 设置持久化：改为写 `/app/workspace/settings_overrides.json`，lifespan 恢复 |
| Session 4 | 研究主题 6 层注入链修复（topic 从未传给任何 agent） |
| Session 4 | 前端运行状态指示器（ping、iteration、TopicDriftWarning Toast） |
| Session 5 | Challenge 自动 dismiss（>2 iters 自动解决，解除收敛阻塞） |
| Session 5 | Phase COMPLETE 论文导出（`exports/paper.md` + `ResearchCompleted` WS） |
| Session 5 | Librarian 接入真实 arXiv API（5 篇论文注入 context） |
| Session 5 | ContextBuilder token 预算（L2→L1→L0 自动降级） |
| Session 6 | **Critic 分数链路修复**：`agent_role == CRITIC` 替代 artifact_type 字符串匹配（**P0**） |
| Session 6 | **L1 JSON 生成加固**：markdown fence 剥离 + 强化 prompt |
| Session 6 | **critic.j2 输出格式明确 artifact_type: review** |
| Session 6 | **WriteBackGuard 降噪**：fence 剥离 + 输入截断 3000 字符 |
| Session 6 | **Librarian 本地知识检索 SSL fallback**：Hybrid→BM25 graceful 降级 |
| Session 6 | **S2 限流优化**：重试 3 次 + Retry-After header + query 去重缓存 |
| Session 6 | **SPAWN_SUBAGENT handler**：消除 "Unhandled action type" 警告 |
| Session 6 | **Heartbeat stale 阈值**：180s→360s 可配置 |
| **Session 7** | **Anthropic/Claude Provider**：新增 `AnthropicProvider`，支持代理 base_url |
| **Session 7** | **Per-role 模型分配**：推理角色→reasoner，工具角色→chat |
| **Session 7** | **并行 Lane 架构**：concurrency 1-5，独立 workspace，asyncio.gather |
| **Session 7** | **SynthesizerAgent**：跨 lane 综合分析，SYNTHESIZE 阶段 |
| **Session 7** | **Claude non-JSON 修复**：base.py JSON 强制指令 + max_tokens 4096→8192 |
| **Session 7** | **Query 缓存归一化**：`_normalize_cache_key()` 排序去重关键词 |
| **Session 7** | **S2 429 冷却期**：5 分钟冷却后直接走 arXiv，省去无效重试 |
| **Session 7** | **Hybrid search 智能跳过**：无 OpenAI key 时直接 BM25，避免 SSL 错误 |
| **Session 7** | **BM25 fallback 返回内容**：从 `_doc_texts` 读取文本，不再返回空 |
| **Session 7** | **论文导出增强**：补充 hypotheses/evidence/directions，11 sections 62KB |

---

## 性能基线

### Session 6（纯 DeepSeek，2026-03-11）

| 指标 | 数据 |
|------|------|
| 总耗时 | 33 分 51 秒 |
| 总迭代数 | 14 轮 |
| 模型 | deepseek-chat + deepseek-reasoner |
| 论文产出 | ~6KB |

### Session 7 Run 1（DeepSeek + Claude 混合，修复前，2026-03-11）

| 指标 | 数据 |
|------|------|
| 总耗时 | 23 分 09 秒（**-32%**） |
| 总迭代数 | 14 轮 |
| Anthropic 调用 | 7 次 |
| non-JSON 警告 | **5 次** |
| S2 429 失败 | 8 次 |
| 论文产出 | 2 sections, 6.5KB |

### Session 7 Run 2（修复后验证，2026-03-11）

| 指标 | 数据 |
|------|------|
| 总耗时 | 27 分 25 秒 |
| 总迭代数 | 14 轮 |
| Anthropic 调用 | 7 次（全部成功） |
| non-JSON 警告 | **0 次** |
| S2 429 失败 | **0 次** |
| Query 缓存命中 | 3 次 |
| Critic 分数提取 | 10 次（6.0-9.0） |
| 论文产出 | **11 sections, 62KB** |

详细踩坑记录见 [doc/devrec.md](devrec.md)。

---

## 当前待办（Next Steps）

### P1 — 并行 Lane 实战验证
- [ ] 创建 concurrency=3 项目测试多 lane 并行 + 合成阶段
- [ ] 前端 Lane 进度可视化
- [ ] Synthesizer 输出质量评估

### P2 — 用户体验
- [ ] 前端 `ResearchCompleted` 处理：显示完成状态 + 论文下载链接
- [ ] 前端 Blackboard 详情视图：点击 artifact 卡片展开 L1/L2 完整内容
- [ ] 论文预览页：渲染 `exports/paper.md` 内容

### P2 — RAG 闭环
- [ ] arXiv/S2 检索结果入 ChromaDB 持久化
- [ ] 统一 `safe_json_loads()` 工具函数，集中处理 LLM 输出的 fence 剥离 + JSON 解析

### P3 — 长期完善
- [ ] LLM 语义去重（替换当前直通 dedup）
- [ ] Agent 输出 Pydantic schema 强校验
- [ ] 多用户 / 协作功能
- [ ] 研究可视化（假设演化、证据图）
- [ ] Magic numbers 收进 config.py 统一管理（300s 超时、3000 字符截断等）
- [ ] `invalid artifact_type` 模糊匹配（当前 fallback 工作但仍产生 warning）
