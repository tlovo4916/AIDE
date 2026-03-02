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
                      │  5 Agents read/write shared Blackboard│
                      │  Director, Scientist, Librarian,      │
                      │  Writer, Critic                       │
                      └──────────────────────────────────────┘
                                              ↓
                                    PostgreSQL + ChromaDB + Filesystem
```

### Research Phases (`backend/types.py` - `ResearchPhase`)
`EXPLORE → HYPOTHESIZE → EVIDENCE → COMPOSE → COMPLETE`

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
- `board.py` - Filesystem-backed artifact store (JSON in `workspace/projects/{id}/`)；`get_state_summary()` 顶部始终注入研究课题
- `adapter.py` - `BoardAdapter` 存在但**目前 factory.py 直接使用 `Blackboard`，该文件可能是死代码**
- `levels.py` - L0 (50-token abstract) / L1 (500-token overview) / L2 (full content) for context budgeting
- `actions.py` - Action types and executor

**`backend/agents/`** - All extend `BaseAgent` (`base.py`)；构造时接收 `research_topic`，渲染 Jinja2 模板时传入

**`backend/agents/prompts/*.j2`** - 所有 5 个模板（director/scientist/librarian/writer/critic）都有：
- `{% if research_topic %}## ⚠️ RESEARCH TOPIC{% endif %}` 区块（优先于 context 展示）
- Language Requirement 区块（要求输出简体中文）

**`backend/llm/router.py`** - Unified LLM dispatch with `call()` and `generate()`; supports DeepSeek and OpenRouter providers with fallback

**`backend/api/projects.py`** - `start_project` launches `OrchestrationEngine.run()` as asyncio background task; `_running_tasks: dict[str, asyncio.Task]` tracks per-project engines

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
- `frontend/src/lib/ws-protocol.ts` - WebSocket frame types（含 `TopicDriftWarning` 事件）
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

---

## 已知未完成 / 待改进项

### 高优先级
- **`adapter.py` 可能是死代码**：`factory.py` 直接使用 `Blackboard` 而非 `BoardAdapter`，需确认 `BoardAdapter` 是否还有存在意义。
- **`dedup_check` 是空操作**：`board.py` 注释写明"dedup requires embedding service, skip when unavailable"，ChromaDB 虽然在跑但未集成到去重逻辑。
- **最终论文无法导出**：研究完成后用户无法下载/查看最终 draft artifact，前端缺少导出入口。
- **偏题检查是关键词匹配**：`_check_on_topic()` 用字符串匹配，不做语义理解；如果课题是纯中文而 artifacts 也是中文但用词不同则可能误报。

### 中优先级
- **Planner 是纯规则轮转**：`OrchestratorPlanner` 注释写明 `llm_router` "kept for interface compatibility but not used"，Agent 顺序固定，无法根据研究进展动态调整。
- **ChromaDB 未实际用于向量检索**：服务启动但 Librarian agent 没有真正调用向量搜索，所有"文献检索"都是 LLM 凭记忆生成。
- **Papers API**（`backend/api/papers.py`）：功能状态不明，未经过完整测试。
- **前端项目列表页**：缺乏运行中项目的进度预览，只有基本列表。
- **写回守卫（WriteBackGuard）**：存在但实际效果未经验证。

### 低优先级
- **Agent 超时 300s**：对慢速 LLM 调用可能仍不够，但太长会拖慢迭代。
- **LLM API 错误处理**：key 失效或限流时错误信息不够友好，无前端提示。
- **SubAgent 研究课题**：subagent 通过 context（board state summary）间接获得课题，未做独立验证。
- **暗色/亮色模式**：CSS 变量已完成，但部分 Badge / Modal 组件在亮色下视觉未精调。
