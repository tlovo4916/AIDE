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
| Service    | Container Port | Host Port              |
|------------|---------------|------------------------|
| Frontend   | 3000          | http://localhost:30000 |
| Backend    | 8000          | http://localhost:30001 |
| ChromaDB   | 8100          | http://localhost:30002 |
| PostgreSQL | 5433          | localhost:30003        |

Hot-reload enabled for both backend and frontend via Docker volume mounts.

### Database
PostgreSQL: user=`aide`, password=`aide`, db=`aide`. Persistent data in `workspace_data` Docker volume at `/app/workspace`.

---

## File Layout

```
backend/
  orchestrator/   engine.py, factory.py, planner.py, convergence.py, backtrack.py, heartbeat.py
  agents/         base.py, director.py, scientist.py, librarian.py, writer.py, critic.py, synthesizer.py, subagent.py
  agents/prompts/ *.j2 templates (one per agent)
  blackboard/     board.py, context_builder.py, levels.py, actions.py
  llm/            router.py, tracker.py, providers/{deepseek,openrouter,anthropic}.py
  api/            projects.py, ws.py, settings.py, papers.py, checkpoints.py
  utils/          json_utils.py
  config.py       Pydantic BaseSettings, all AIDE_* env vars
  types.py        enums (AgentRole, ResearchPhase, ArtifactType) + Pydantic models
frontend/
  src/app/                    pages (dashboard, settings, project detail)
  src/app/projects/[id]/      _components/ (5 sections), _hooks/, _utils/
  src/components/ui/          button, card, badge, modal, input, markdown
  src/hooks/                  useBlackboard, useTypedWebSocket
  src/lib/                    api.ts, ws-protocol.ts
  src/contexts/               ProjectSidebarContext
```

## Configuration

All backend settings in `backend/config.py`, overridable via `AIDE_*` env vars.

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
- **DeepSeek**: `AIDE_DEEPSEEK_API_KEY` (default)
- **OpenRouter**: `AIDE_OPENROUTER_API_KEY`
- **Anthropic**: `AIDE_ANTHROPIC_API_KEY` + `AIDE_ANTHROPIC_BASE_URL`

## Tech Stack
- **Backend**: Python 3.12, FastAPI, SQLAlchemy (async), AsyncPG, ChromaDB
- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS 4
- **Lint**: Ruff (line-length=100, target py312, rules: E, F, I, N, W, UP)
- **Deps**: `pyproject.toml` (backend), `package.json` (frontend)

## Known Defects

See `doc/review.md` for full architectural review. Key issues:
- 5/6 agents are empty classes, all logic lives in .j2 templates
- Planner is fixed-sequence rotation (`iteration % len(sequence)`), not dynamic scheduling
- Backtrack detection uses English keywords but agents output Chinese — never triggers
- Convergence relies on LLM self-evaluation scores with no external anchor
- No evaluation framework to measure whether the system produces useful output
- Settings persistence uses raw JSON file instead of database
- ~15KB of implemented but never-integrated code (compressor.py, retriever.py, active_tracker.py)
- Heartbeat module ~40% dead code (snapshot, recover, ws_connected)
