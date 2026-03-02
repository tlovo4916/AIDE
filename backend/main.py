from __future__ import annotations

import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.models import init_db
from backend.api.settings import load_overrides

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("chromadb").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    settings.projects_dir.mkdir(parents=True, exist_ok=True)
    load_overrides()
    await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.api.projects import router as projects_router  # noqa: E402
from backend.api.papers import router as papers_router  # noqa: E402
from backend.api.checkpoints import router as checkpoints_router  # noqa: E402
from backend.api.settings import router as settings_router  # noqa: E402
from backend.api.ws import router as ws_router  # noqa: E402

app.include_router(projects_router, prefix="/api")
app.include_router(papers_router, prefix="/api")
app.include_router(checkpoints_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(ws_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
