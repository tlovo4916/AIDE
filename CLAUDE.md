# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Start/Stop
```bash
./start.sh          # Build and start all 4 services (first run creates .env from .env.example)
./stop.sh           # Stop all services
docker compose down -v  # Stop and remove data volumes
```

### Logs & Debugging
```bash
docker compose logs -f backend
docker compose logs -f frontend
# 从容器内测试 API（宿主机 localhost:8000 可能被代理拦截返回 502）
docker compose exec backend python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read())"
open http://localhost:8000/docs   # FastAPI Swagger UI
```

### Linting & Tests (run inside container)
```bash
docker compose exec backend ruff check backend/
docker compose exec backend ruff format backend/
docker compose exec backend pytest
docker compose exec frontend npm run lint
```

### Service Ports
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- ChromaDB: http://localhost:8100
- PostgreSQL: localhost:5433

---

## Architecture

AIDE is a **blackboard-based multi-agent research assistant**. Agents share a persistent filesystem state rather than passing data in a pipeline. The orchestrator runs a spiral loop: plan → dispatch agent → validate → check convergence → repeat.

### Core Data Flow
```
Frontend (Next.js) ↔ WebSocket/REST ↔ FastAPI Backend
                                              ↓
                                    OrchestrationEngine
                                    (factory.py wires all deps)
                                              ↓
                      ┌──────────────────────────────────────┐
                      │  6 Agents read/write shared Blackboard│
                      │  Director, Scientist, Librarian,      │
                      │  Writer, Critic, Synthesizer          │
                      └──────────────────────────────────────┘
                                              ↓
                                    PostgreSQL + ChromaDB + Filesystem
```

### Research Phases (`backend/types.py` - `ResearchPhase`)
`EXPLORE → HYPOTHESIZE → EVIDENCE → COMPOSE → [SYNTHESIZE] → COMPLETE`

The orchestrator detects convergence (via `CriticAgent` score threshold + stable rounds) to advance phases, or backtracks on contradictions.

### Key Components

**`backend/orchestrator/`**
- `engine.py` - Main loop; uses `Board`, `Planner`, `ConvergenceDetector` Protocols
- `factory.py` - 组合根，所有依赖在此装配；每次启动时从 DB 读取 `research_topic` 并注入全链路
- `planner.py` - **规则驱动**的 Agent 轮转（非 LLM），每阶段有固定 sequence；任务描述中注入研究课题
- `convergence.py` - Phase completion detection (score threshold + stable rounds)；使用 per-phase critic score
- `backtrack.py` - Reverts phase on contradictions
- `heartbeat.py` - Crash recovery

**`backend/blackboard/`**
- `board.py` - Filesystem-backed artifact store；`get_state_summary()` 顶部始终注入研究课题；`resolve_challenge()` 支持自动 dismiss；`export_paper()` 导出最终 draft 到 `exports/paper.md`
- `context_builder.py` - **Token 预算 ContextBuilder**：L2→L1→L0 自动降级，确保 context 不超 30K tokens
- `levels.py` - L0/L1/L2 generation via LLM with truncation fallback
- `actions.py` - Action executor（含 write_artifact/post_message/raise_challenge/resolve_challenge）

**`backend/agents/`** - All extend `BaseAgent` (`base.py`)；构造时接收 `research_topic` 和 `project_id`，`execute()` 将两者传给 `llm_router.generate()` 实现 token 追踪

**`backend/agents/prompts/*.j2`** - 所有 6 个模板（director/scientist/librarian/writer/critic/synthesizer）都有：
- `{% if research_topic %}## ⚠️ RESEARCH TOPIC{% endif %}` 区块（优先于 context 展示）
- Language Requirement 区块（要求输出简体中文）

**`backend/llm/router.py`** - Unified LLM dispatch with `call()` and `generate()`; supports DeepSeek, OpenRouter and Anthropic providers with fallback。`generate()` 接收 `project_id`/`agent_role` 用于 token 追踪

**`backend/llm/tracker.py`** - Token 用量持久化（PostgreSQL `token_usage` 表）；`get_project_usage()` 返回分模型统计（token 数、USD/RMB 费用）；`COST_PER_1K` 定义各模型单价（含 DeepSeek/Claude/GPT/Gemini）

**`backend/api/projects.py`** - `start_project` launches `OrchestrationEngine.run()` as asyncio background task; `_running_tasks: dict[str, asyncio.Task]` tracks per-project engines；含 `GET /usage`（token 费用）、`GET /citation-graph`（引用图谱）、`PUT /export/paper`（保存编辑）、`GET /export/paper/html`（HTML 导出）

**`backend/checkpoint/`** - Halts orchestrator at critical moments, notifies frontend via WebSocket, waits for user approval (30-min timeout)

**`backend/api/settings.py`** - `load_overrides()` / `_save_overrides()` 将设置写入 `/app/workspace/settings_overrides.json`，跨重启持久化（因容器内无 .env 可写）

### Protocol-Based Design
Components communicate through Python `Protocol` classes (structural subtyping), enabling loose coupling:
- `Board` protocol → implemented by `Blackboard` (直接) 或 `BoardAdapter`
- `LLMRouter` protocol → implemented by `LLMRouter` class
- All orchestrator dependencies are injected via `factory.py`

### Context Budget System (L0/L1/L2)
Agents receive context at different detail levels based on token budget (default 30,000 tokens). Ratios are configured via `AIDE_*_RATIO` env vars.

### Frontend
- Next.js 15 App Router, React 19, TypeScript, Tailwind CSS 4
- `frontend/src/lib/api.ts` - HTTP client functions
- `frontend/src/lib/ws-protocol.ts` - WebSocket frame types（含 `TopicDriftWarning`、`ResearchCompleted` 事件）
- `frontend/src/components/ui/markdown.tsx` - 自定义 Markdown 渲染组件（替代 react-markdown，因其 v9 纯 ESM 与 Next.js webpack 不兼容）
- Real-time blackboard state updates via WebSocket (`api/ws.py`)

## Configuration
All backend settings are Pydantic `BaseSettings` in `backend/config.py`, overridable via `AIDE_*` environment variables. Key tunables: `AIDE_MAX_ITERATIONS_PER_PHASE`, `AIDE_CONVERGENCE_MIN_CRITIC_SCORE`, `AIDE_CONVERGENCE_STABLE_ROUNDS`, `AIDE_CHECKPOINT_TIMEOUT_MINUTES`, `AIDE_CONTEXT_BUDGET_TOKENS`.

## Python Stack
- Python 3.12, FastAPI, SQLAlchemy (async), AsyncPG, ChromaDB, Ruff (linter, line-length=100, target py312)
- `pyproject.toml` at repo root defines all deps and tool config

---

## 已完成工作复盘（按 Session）

### Session 2（2026-02-28）— 核心运行时修复
1. **`backend/llm/tracker.py`**：删除重复 ORM 定义（与 `models/token_usage.py` 冲突）；修复 `async with await session_factory()` → `async with session_factory()`；修正列名 `model`→`model_name`、`cost`→`cost_usd`。
2. **`backend/orchestrator/factory.py`**：新增 `_checkpoint_managers` 注册表；`get_checkpoint_manager(project_id)` 函数供 API 层获取正在运行的实例。
3. **`backend/api/ws.py`**：修复 `_handle_checkpoint_response` 错误地创建新 `CheckpointManager` 实例（`_pending` 为空导致永远等不到响应），改为从注册表取运行中实例。
4. **`backend/api/checkpoints.py`**：实现 checkpoint REST 响应接口的 TODO，调用 `mgr.apply_user_response()`。

### Session 3（2026-02-28）— 设置持久化
5. **`backend/api/settings.py`** + **`backend/main.py`**：设置写入 `/app/workspace/settings_overrides.json`（Docker volume 内），lifespan 启动时自动恢复，解决容器重启后设置丢失问题。

### Session 5（2026-03-02）— P0/P1 功能补全

#### P0 — 阻塞核心功能修复
16. **Challenge 自动解决**：`engine.py` `_handle_challenges()` 新增自动 dismiss 逻辑——当 `phase_iters > 2` 时，对未解决 challenge 调用 `board.resolve_challenge()` 并广播 `ChallengeResolved` WS 事件，防止收敛条件永久阻塞。
17. **Phase COMPLETE 论文导出**：`engine.run()` 退出后若 `phase == COMPLETE`，调用 `_on_research_complete()` → `board.export_paper()` 将最新 DRAFT 写入 `exports/paper.md`，广播 `ResearchCompleted` WS 事件。

#### P1 — 真实研究能力
18. **Librarian 真实 arXiv 检索**：`LibrarianAgent` 覆写 `execute()`，在调用 LLM 前先 `_enrich_context_with_literature()`——通过 `WebRetriever.search_arxiv()` 拉取真实论文摘要并注入 context（受 `AIDE_ENABLE_WEB_RETRIEVAL` 开关控制，`.env` 已设为 `true`）。
19. **ContextBuilder Token 预算**：新建 `backend/blackboard/context_builder.py`，`build_budget_context()` 按 L2→L1→L0 顺序降级，直到 context token 数 ≤ `AIDE_CONTEXT_BUDGET_TOKENS`（默认 30K），最终兜底硬截断。`engine._build_state_summary()` 改用此函数。
20. **`settings_overrides.json` 管理**：`enable_web_retrieval` 持久化覆盖问题：`.env` / `.env.example` 均改为 `true`，并需在设置页手动打开或通过 API 更新（`POST /api/settings`）。

#### P1.2（已验证存在）
- PDF 处理流水线（`papers.py` + `PDFProcessor` + `EmbeddingService` + `VectorStore` + `BM25Store`）已完整实现，用户上传 PDF 后自动入库 ChromaDB + BM25。

### Session 4（2026-03-02）— 前端体验 + 引擎稳定性 + 研究课题修复

#### 前端改造
6. **Artifact 卡片**：移除所有 `.slice()` 截断；超 300 字符的卡片显示 "Show more / Collapse" 折叠按钮。
7. **深浅模式**：`layout.tsx` 加入 Sun/Moon 切换，`localStorage` 持久化，`globals.css` 加 `[data-theme="light"]` 变量。
8. **UTC 时间修复**：`parseTS()` helper 补 `Z` 后缀，防止浏览器时区误判。
9. **Markdown 渲染**：自定义 `frontend/src/components/ui/markdown.tsx`（支持 bold/italic/code/heading/list/blockquote），替代纯 ESM 的 react-markdown v9。
10. **运行状态可视化**：
    - 顶部 ping 动画横幅：`研究进行中 · Explore 阶段 · 第 N 轮 · [agent] 执行中`
    - 左侧栏：迭代计数 + "等待下一个 Agent…" 过渡态
    - 右下角 Toast：`TopicDriftWarning` 偏题警告，8 秒自动消失
    - 每 30s 轮询项目状态（刷新 phase/status）

#### Agent 输出语言
11. **所有 5 个 `.j2` 提示词**：加入 Language Requirement 区块，强制所有内容字段输出简体中文。

#### 引擎稳定性（Compose 阶段卡死 bug）
12. **per-phase critic score**：`board.py` 新增 `get_phase_critic_score(phase)` / `set_phase_critic_score(phase, score)`；`convergence.py` 改用 per-phase score，防止旧阶段高分导致新阶段秒收敛。
13. **Agent 超时不跳过计数**：`engine.py` 超时 `continue` 前补调 `increment_phase_iteration()`，防止同阶段无限轮转。
14. **Phase 立即持久化**：`_advance_phase()` 切换后立即 `update_meta("phase", ...)` 写入 meta.json，防止重启后 phase 回退。

#### 研究课题跑偏（最严重 bug）
15. **6 层注入链**：
    - `factory.py`：从 DB 读 `project.research_topic`
    - `board.py`：`init_workspace(research_topic)` 存入 meta.json；`get_state_summary()` 顶部注入 `## ⚠️ RESEARCH TOPIC`
    - `planner.py`：每条任务描述以 `[RESEARCH TOPIC]: ...` 开头
    - `base.py`：`research_topic` 作为 Jinja2 模板变量传入
    - 5 个 `.j2` 模板：专门的课题强调区块
    - `engine.py`：`_check_on_topic()` 每轮关键词匹配检查（<20% 触发 `TopicDriftWarning` WS 事件）

### Session 6（2026-03-11）— 核心质量链路修复 + 性能实测

#### P0 — Critic 分数链路（修复前分数始终 0.0，阶段只能靠 max_iterations 超时推进）
21. **`engine.py:293-296`**：分数提取条件从 `art_type == "review"`（依赖 LLM 输出正确 artifact_type）改为 `action.agent_role == AgentRole.CRITIC`（直接判断角色）。`_extract_critic_score()` 新增 dict 类型嵌套 content 的直接遍历。
22. **`levels.py`**：`generate_l1()` 在 `json.loads()` 前增加 `_strip_markdown_fences()` 剥离 markdown fence（DeepSeek 常返回 ` ```json ``` ` 包裹内容）。强化 system prompt 为 `"Output raw JSON only. No markdown fences, no comments, no explanation."`。
23. **`critic.j2`**：输出格式示例中补上 `"artifact_type": "review"` 和 `"action_type": "write_artifact"`，IMPORTANT 中明确强调。

#### P1 — 降噪 + 检索修复
24. **`write_back_guard.py`**：加 `_strip_markdown_fences()` + 输入截断到 3000 字符 + 强化 system prompt，减少 JSON 解析失败。
25. **`librarian.py:_search_local_knowledge()`**：重构为先尝试 Hybrid search（vector+BM25），SSL 失败时 graceful fallback 到纯 BM25（`bm25_store.query()`）。修复了 `search()` → `query()` 方法名不匹配的 bug。
26. **`web_retriever.py`**：`_MAX_RETRIES` 2→3，`_RATE_LIMIT_BACKOFF` 10→15s，新增 `Retry-After` header 读取动态 backoff。
27. **`librarian.py:_search_with_fallback()`**：新增 `_query_cache: set[str]` 去重缓存，同一 query 不重复请求 S2/arXiv API。

#### P2 — 清理
28. **`actions.py`**：补上 `SPAWN_SUBAGENT` handler（`_exec_spawn_subagent`），记录为 blackboard message，消除 "Unhandled action type" 警告。
29. **`heartbeat.py` + `config.py`**：stale 阈值从硬编码 `interval*3`（180s）改为可配置 `heartbeat_stale_threshold_seconds=360`（`AIDE_HEARTBEAT_STALE_THRESHOLD_SECONDS`），消除 agent 执行期间的误报。

#### 性能实测数据（英文课题 "LLM inference optimization"，deepseek-chat + deepseek-reasoner 混合）
- **总耗时 33 分 51 秒**，14 轮迭代，4 个阶段全部通过 critic 质量评判收敛推进
- EXPLORE: 4 轮 10m39s（含 S2 首次 429 重试 97s）| critic=7.0
- HYPOTHESIZE: 4 轮 8m36s | critic=7.0→8.0→6.0
- EVIDENCE: 4 轮 11m10s | critic=8.0→7.0
- COMPOSE: 2 轮 3m26s（含 SubAgent 并行撰写）| critic=7.0→8.0
- S2 首次请求因 429 需 ~97s（15+30+45s backoff），后续 ~1s
- Agent 单次调用：Librarian 2-4min，Scientist ~3min，Director ~1.75min，Critic ~2.5min，Writer ~2.25min

### Session 8（2026-03-11）— Token 计费修复 + Phase 2/3 收尾

#### P0 — Token 计费链路（修复前所有项目费用显示 0）
30. **`backend/agents/base.py`**：`execute()` 调用 `generate()` 时未传 `project_id`/`agent_role`，导致 `router.py` 的 `record_usage()` 从未被调用。修复：传递 `project_id=self._project_id, agent_role=self.role`。Protocol 定义同步更新。
31. **`backend/orchestrator/factory.py`**：6 个 agent 中仅 Librarian 传了 `project_id`，其余 5 个为空字符串。修复：所有 agent 构造时传入 `project_id=str(project_id)`。
32. **`backend/agents/subagent.py`**：Protocol 定义同步更新，增加 `project_id`/`agent_role` 可选参数。

#### P1 — Token 费用展示
33. **`backend/llm/tracker.py`**：`COST_PER_1K` 增加 Claude 模型族（opus/sonnet/haiku）定价；`_resolve_cost_key()` 智能识别模型族；`get_project_usage()` 返回 `total_cost_rmb`（USD*7.24）、分模型明细。
34. **`backend/orchestrator/engine.py`**：`_on_research_complete()` 收集 token usage 并通过 `ResearchCompleted` WS 事件广播。
35. **`backend/api/projects.py`**：新增 `GET /{id}/usage` 端点返回 token 费用。
36. **前端项目详情页**：完成 banner 显示总 token/USD/RMB；论文弹窗显示分模型明细表。

#### P1 — Artifact 去重
37. **`backend/blackboard/board.py`**：`dedup_check()` 从直通空操作改为 Jaccard 词集相似度（阈值 0.6），对比最近 10 条同类 artifact，重复则跳过写入。

#### P1 — 引用图谱
38. **`backend/agents/librarian.py`**：`_persist_web_papers()` 将检索论文入库 BM25 索引；`_update_citation_graph()` 构建 NetworkX DiGraph。
39. **`backend/api/projects.py`**：新增 `GET /{id}/citation-graph` 端点。

#### P1 — 论文编辑与导出
40. **`backend/api/projects.py`**：新增 `PUT /{id}/export/paper`（保存编辑内容）、`GET /{id}/export/paper/html`（HTML 可打印导出），含 `_markdown_to_html()` 转换。
41. **前端项目详情页**：论文编辑模式（edit/save/cancel）+ PDF 导出（浏览器 window.print）。

#### P1 — Agent 输出容错
42. **`backend/agents/base.py`**：`_parse_response()` 增加 `_fuzzy_match_action_type()` 模糊匹配（处理 LLM 输出的非标准 action_type）+ target 自动填充。

#### P2 — 前端 WS 事件处理
43. **前端项目详情页**：处理 `ResearchCompleted`（完成 banner + 自动加载 token）、`LanesStarted`/`LaneCompleted`/`SynthesisStarted`（lane 进度可视化）。

#### 性能实测数据（2 次完整运行）
- **Run 1**（课题 "RAG optimization"）：14 轮 ~30min，115,842 tokens，$0.82 / 5.94 RMB
- **Run 2**（课题 "Knowledge distillation"）：14 轮 ~37min，104,719 tokens，$0.77 / 5.58 RMB
- 两次运行均 4 阶段全部 critic 收敛通过，token 数据完整写入 DB，项目间完全隔离

### Session 9（2026-03-11）— 前端重构 + Phase 3 收尾

#### Phase 3 后端收尾
43. **统一 `safe_json_loads()`**：新建 `backend/utils/json_utils.py`，集中 markdown fence 剥离 + 前缀文字剥离 + JSON 解析 + fallback。替换 `levels.py`/`base.py`/`write_back_guard.py` 中的重复 `_strip_markdown_fences()` + `json.loads()` 逻辑。
44. **arXiv/S2 检索结果入 ChromaDB**：`librarian.py` 新增 `_persist_to_chromadb()`，在 OpenAI API key 可用时自动将检索论文嵌入并存入 ChromaDB 向量库（含去重检查），不可用时 graceful skip 仅走 BM25。

#### 前端重构（Indigo 主题 + 研究流水线可视化）
45. **设计系统**：`globals.css` 从蓝色系迁移到 Indigo 系（dark: `#818cf8`，light: `#4f46e5`）。新增 CSS 变量（shadow-card/shadow-card-hover/shadow-btn-glow/primary-50~900）、动画（scale-in/slide-in-left）、工具类（card-hover/btn-primary-glow/page-title/sidebar-item/input-focus-ring/::selection）。
46. **UI 组件升级**：Button（新增 outline/success variant + hover glow + rounded-lg）、Card（rounded-xl + shadow-sm + hoverable prop）、Badge（rounded-full 药丸形 + indigo agent variant）、Modal（size prop sm/md/lg/xl/full + scale-in 动画 + bg-black/80）、Input（h-10 + rounded-lg + input-focus-ring）。
47. **Sidebar 重写**：240px↔64px 收起展开 + `data-sidebar` 属性驱动主内容区 margin + 项目内 5 section 导航（Overview/Blackboard/Messages/Knowledge/Paper）。
48. **ProjectSidebarContext**：`frontend/src/contexts/ProjectSidebarContext.tsx`，跨组件共享项目导航状态。
49. **项目详情页分解**（1298 行 → ~200 行容器 + 5 section + 1 hook + 1 utils）：
    - `_utils/formatters.ts`：PHASES/ARTIFACT_SECTIONS/parseTS/formatElapsed/formatDateTime/getArtifactDisplay
    - `_hooks/useProjectState.ts`：全部 useState + WS 订阅 + 30s 轮询 + action handlers
    - `_components/OverviewSection.tsx`：研究流水线节点图（6 色阶段 + 展开产出 + timeline + lane 进度 + token/time 卡）
    - `_components/BlackboardSection.tsx`：全宽 3 列 artifact 网格（按类型分组 + 折叠 + hoverable）
    - `_components/MessagesSection.tsx`：双栏（消息流含角色过滤 + Challenge 面板含状态过滤）
    - `_components/KnowledgeSection.tsx`：双栏（PapersPanel + 引用图谱内联展示）
    - `_components/PaperSection.tsx`：论文编辑/预览 + token 统计 + 导出
50. **Dashboard 改版**：page-title 渐变下划线 + stagger 进入动画 + hoverable 卡片 + Modal 子组件提取。
51. **Settings 改版**：page-title + hoverable Card + colored 分组标签 + sticky 保存按钮 + stagger 动画。
52. **PaperEditor 颜色适配**：全部 `slate-*` 硬编码颜色替换为 `aide-*` CSS 变量。
53. **清理 10 个废弃组件**：BoardView/ChallengePanel/MessageStream/PhaseIndicator/SpiralVisualizer/PDFUploader/SearchTester/CitationGraph/CheckpointModal/AdjustEditor + 3 个空目录。

### Session 10（2026-03-13）— 全面质量验证

#### 测试执行（4 并行团队 + 1 全链路）
54. **后端单元测试**：Ruff Lint 0 issues；Pytest 17/17 PASS（test_json_utils）；Ruff Format 6 files 需格式化（非阻塞）
55. **REST API 集成测试**：10 个端点全部通过（health/projects CRUD/settings GET+PUT/usage/citation-graph/export paper html/DELETE）
56. **WebSocket 连通测试**：`ws://localhost:8000/ws/projects/{id}` 连接成功并稳定保持
57. **并发压力测试**：120 请求 / 0.35s = 341 req/s，0 错误（health p50=4.7ms, projects p50=196ms, create p50=112ms）
58. **前端渲染测试**：Dashboard/Settings/项目详情页全部 HTTP 200；7 个 JS chunk + CSS + 字体正常加载
59. **全链路 E2E 测试**：创建项目 → 启动研究 → Planner 分配 Agent（Librarian/Director）→ arXiv 检索 5 篇论文 → 3 个 Artifact 产出（L0/L1/L2 三级）→ Token 计费正常（8,923 tokens / $0.059）→ 引用图谱 5 节点 → 暂停/恢复正常 → 前端渲染正常
60. **测试清理**：删除 29 个测试/压力测试项目

---

## 已知未完成 / 待改进项

### 中优先级
- **Planner 是纯规则轮转**：Agent 顺序固定，无法根据研究进展动态调整（`llm_router` 仅保留接口兼容性）。
- **偏题检查是关键词匹配**：`_check_on_topic()` 用字符串匹配，不做语义理解。
- **前端 Blackboard 详情视图**：当前只展示 L0 摘要卡片，未实现点击展开 L1/L2 完整内容。
- **WriteBackGuard 效果待验证**：降噪已做（fence 剥离 + 截断），但实际是否产生有价值的 write-back artifact 未确认。
### 低优先级
- **Challenge 处理**：自动 dismiss（>2 iters）已实现，但未测试完整 raise→respond→resolve 流程。
- **`adapter.py` 可能是死代码**：`factory.py` 直接使用 `Blackboard`，`BoardAdapter` 可能无存在意义。
- **Agent 超时 300s**：实测中未触发超时，但 Librarian 含 S2 重试时理论可达 ~4min，接近阈值。
