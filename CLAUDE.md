# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Start/Stop
```bash
./start.sh          # Build and start all 4 services (first run creates .env from .env.example)
./stop.sh           # Stop all services (keeps data volumes)
docker compose down -v  # Stop and remove data volumes
```

### Logs & Debugging
```bash
docker compose logs -f backend
docker compose logs -f frontend
# Test API from inside container (host localhost:30001 may be intercepted by proxy → 502)
docker compose exec backend python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read())"
open http://localhost:30001/docs   # FastAPI Swagger UI
```

### Linting & Tests (run inside container)
```bash
docker compose exec backend ruff check backend/
docker compose exec backend ruff format backend/
docker compose exec backend pytest
docker compose exec backend pytest backend/tests/test_json_utils.py -k test_name  # single test
docker compose exec frontend npm run lint
```

### Service Ports
| Service    | Container Port | Host Port                  |
|------------|---------------|----------------------------|
| Frontend   | 3000          | http://localhost:30000     |
| Backend    | 8000          | http://localhost:30001     |
| ChromaDB   | 8100          | http://localhost:30002     |
| PostgreSQL | 5433          | localhost:30003            |

Hot-reload is enabled for both backend and frontend via Docker volume mounts.

### Database
PostgreSQL credentials: user=`aide`, password=`aide`, db=`aide`. Persistent data lives in the `workspace_data` Docker volume mounted at `/app/workspace`.

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

### Research Phases (`backend/types.py` — `ResearchPhase`)
`EXPLORE → HYPOTHESIZE → EVIDENCE → COMPOSE → [SYNTHESIZE] → COMPLETE`

The orchestrator detects convergence (via `CriticAgent` score threshold + stable rounds) to advance phases, or backtracks on contradictions. SYNTHESIZE only runs when `concurrency > 1` (parallel lanes).

### Key Components

**`backend/orchestrator/`**
- `engine.py` — Main loop; uses `Board`, `Planner`, `ConvergenceDetector` Protocols
- `factory.py` — Composition root: all dependencies wired here; reads `research_topic` from DB and injects it into the full chain
- `planner.py` — **Rule-driven** agent rotation (not LLM), fixed sequence per phase; injects research topic into task descriptions
- `convergence.py` — Phase completion detection (score threshold + stable rounds); uses per-phase critic score
- `backtrack.py` — Reverts phase on contradictions
- `heartbeat.py` — Crash recovery

**`backend/blackboard/`**
- `board.py` — Filesystem-backed artifact store; `get_state_summary()` always prepends research topic; `resolve_challenge()` supports auto-dismiss; `export_paper()` exports final draft to `exports/paper.md`; `dedup_check()` uses Jaccard similarity (threshold 0.6)
- `context_builder.py` — **Token budget ContextBuilder**: L2→L1→L0 auto-downgrade, ensures context ≤ 30K tokens
- `levels.py` — L0/L1/L2 summary generation via LLM with truncation fallback
- `actions.py` — Action executor (write_artifact/post_message/raise_challenge/resolve_challenge/spawn_subagent)

**`backend/agents/`** — All extend `BaseAgent` (`base.py`); receive `research_topic` and `project_id` at construction; `execute()` passes both to `llm_router.generate()` for token tracking. `_parse_response()` includes fuzzy action_type matching for LLM output robustness.

**`backend/agents/prompts/*.j2`** — All 6 templates (director/scientist/librarian/writer/critic/synthesizer) have:
- `{% if research_topic %}## ⚠️ RESEARCH TOPIC{% endif %}` block (shown before context)
- Language Requirement block (requires Simplified Chinese output)

**`backend/llm/router.py`** — Unified LLM dispatch with `call()` and `generate()`; supports DeepSeek, OpenRouter, and Anthropic providers with fallback. `generate()` accepts `project_id`/`agent_role` for token tracking.

**`backend/llm/tracker.py`** — Token usage persistence (PostgreSQL `token_usage` table); `get_project_usage()` returns per-model stats (tokens, USD/RMB costs); `COST_PER_1K` defines per-model pricing.

**`backend/api/projects.py`** — `start_project` launches `OrchestrationEngine.run()` as asyncio background task; `_running_tasks: dict[str, asyncio.Task]` tracks per-project engines. Endpoints: `GET /usage`, `GET /citation-graph`, `PUT /export/paper`, `GET /export/paper/html`.

**`backend/checkpoint/`** — Halts orchestrator at critical moments, notifies frontend via WebSocket, waits for user approval (30-min timeout).

**`backend/api/settings.py`** — `load_overrides()` / `_save_overrides()` persist settings to `/app/workspace/settings_overrides.json` (survives container restarts since .env is not writable inside containers).

**`backend/utils/json_utils.py`** — `safe_json_loads()`: strips markdown fences, prefix text, then parses JSON with fallback. Used throughout agents and blackboard.

### Research Topic Injection (6-layer chain)
This was a critical bug fix — the research topic must flow through the entire system:
1. `factory.py`: reads `project.research_topic` from DB
2. `board.py`: stores in meta.json; `get_state_summary()` prepends `## ⚠️ RESEARCH TOPIC`
3. `planner.py`: prefixes every task description with `[RESEARCH TOPIC]: ...`
4. `base.py`: passes as Jinja2 template variable
5. All `.j2` templates: dedicated topic emphasis block
6. `engine.py`: `_check_on_topic()` keyword-match check each iteration, broadcasts `TopicDriftWarning` via WS if <20% keywords found

### Protocol-Based Design
Components communicate through Python `Protocol` classes (structural subtyping), enabling loose coupling:
- `Board` protocol → implemented by `Blackboard` (directly) or `BoardAdapter`
- `LLMRouter` protocol → implemented by `LLMRouter` class
- All orchestrator dependencies are injected via `factory.py`

### Context Budget System (L0/L1/L2)
Agents receive context at different detail levels based on token budget (default 30,000 tokens). Ratios are configured via `AIDE_*_RATIO` env vars (core=5%, task=17%, cross=10%, literature=43%, history=7%).

### Parallel Research Lanes
When `project.concurrency > 1`, `factory.py` creates N lane engines with isolated workspaces under `lanes/{idx}/`. All lanes run via `asyncio.gather()`, then `SynthesizerAgent` reads all lane artifacts. Single-lane (concurrency=1) skips the SYNTHESIZE phase.

### Frontend
- Next.js 15 App Router, React 19, TypeScript, Tailwind CSS 4
- Indigo design system (`#818cf8` dark, `#4f46e5` light) with dark/light mode toggle
- `frontend/src/lib/api.ts` — HTTP client functions
- `frontend/src/lib/ws-protocol.ts` — WebSocket frame types (TopicDriftWarning, ResearchCompleted, LanesStarted, etc.)
- `frontend/src/components/ui/markdown.tsx` — Custom Markdown renderer (replaces react-markdown v9, which is pure ESM and incompatible with Next.js webpack)
- Project detail page decomposed into 5 sections: Overview (pipeline visualization), Blackboard, Messages, Knowledge, Paper
- Key files: `_hooks/useProjectState.ts` (all state + WS + polling), `_utils/formatters.ts`, `contexts/ProjectSidebarContext.tsx`

---

## Configuration

All backend settings are Pydantic `BaseSettings` in `backend/config.py`, overridable via `AIDE_*` environment variables.

### Key Tunables
| Variable | Default | Purpose |
|----------|---------|---------|
| `AIDE_DEFAULT_MODEL` | `deepseek-reasoner` | Default LLM model |
| `AIDE_MAX_ITERATIONS_PER_PHASE` | 20 | Max iterations before forced phase advance |
| `AIDE_CONVERGENCE_MIN_CRITIC_SCORE` | 7.0 | Critic score threshold for phase convergence |
| `AIDE_CONVERGENCE_STABLE_ROUNDS` | 3 | Consecutive rounds above threshold to converge |
| `AIDE_CONTEXT_BUDGET_TOKENS` | 30000 | Max tokens in agent context |
| `AIDE_CHECKPOINT_TIMEOUT_MINUTES` | 30 | User approval timeout |
| `AIDE_ENABLE_WEB_RETRIEVAL` | true | Enable arXiv/S2 paper search |
| `AIDE_HEARTBEAT_STALE_THRESHOLD_SECONDS` | 360 | Crash detection threshold |

### LLM Providers
- **DeepSeek**: `AIDE_DEEPSEEK_API_KEY` (default provider)
- **OpenRouter**: `AIDE_OPENROUTER_API_KEY`
- **Anthropic**: `AIDE_ANTHROPIC_API_KEY` + `AIDE_ANTHROPIC_BASE_URL` (models prefixed `claude-`)
- Per-role model defaults: Director/Scientist/Critic/Synthesizer → `deepseek-reasoner`; Librarian/Writer/SubAgents → `deepseek-chat`

## Python Stack
- Python 3.12, FastAPI, SQLAlchemy (async), AsyncPG, ChromaDB, Ruff
- Ruff config: line-length=100, target py312, rules: E, F, I, N, W, UP
- `pyproject.toml` at repo root defines all deps and tool config

---

## Known Issues / TODO

### Medium Priority
- **Planner is pure rule rotation**: Agent sequence is fixed per phase, cannot dynamically adjust based on research progress.
- **Topic drift check is keyword matching**: `_check_on_topic()` uses string matching, no semantic understanding.
- **Frontend Blackboard detail view**: Currently only shows L0 summary cards, no click-to-expand for L1/L2 content.
- **WriteBackGuard effectiveness unverified**: Noise reduction done (fence stripping + truncation), but actual value of write-back artifacts not confirmed.

### Low Priority
- **Challenge handling**: Auto-dismiss (>2 iters) implemented, but full raise→respond→resolve flow untested.
- **`adapter.py` may be dead code**: `factory.py` uses `Blackboard` directly, `BoardAdapter` may be unnecessary.
- **Agent timeout 300s**: Not triggered in testing, but Librarian with S2 retries can theoretically reach ~4min, close to threshold.

---

## Session History
Detailed session-by-session changelog is in [CHANGELOG.md](./CHANGELOG.md).
