"""KIZUKI API (Cloud Run).  Local:  uvicorn app.main:app --port 8080  (dev auth, in-memory data, demo seed)."""
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app import admin, public
from app.config import SETTINGS, assert_safe_for_cloud
from app.deps import get_state

assert_safe_for_cloud(SETTINGS)
log = logging.getLogger("api")
app = FastAPI(title="KIZUKI API")
app.add_middleware(CORSMiddleware, allow_origins=[o for o in SETTINGS.cors_origins.split(",") if o],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(public.router)
app.include_router(admin.router)


@app.get("/")
def root() -> dict:
    return {"service": "KIZUKI API", "health": "/healthz", "docs": "/docs"}


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


# ---------------------------------------------------------------- local development only
# Stands in for Cloud Storage + Eventarc: the phone PUTs the photo here and, if the analyzer code is
# importable, it is analyzed in-process with the same stores (mock Gemini unless JUDGE_MODE=vertex).
if SETTINGS.backend == "local":
    from app.dev_storage import CURRENT_BASE

    @app.middleware("http")
    async def remember_caller_base(request: Request, call_next):
        token = CURRENT_BASE.set(request.headers.get("x-dev-public-base") or str(request.base_url).rstrip("/"))
        try:
            return await call_next(request)
        finally:
            CURRENT_BASE.reset(token)

    def _analyze(path: str, uid: str) -> None:
        sys.path.append(str(Path(__file__).resolve().parents[2] / "analyzer"))  # `pipeline` lives there
        from pipeline.face_blur import MockFaceDetector
        from pipeline.gemini_client import GeminiClient
        from pipeline.judge import GeminiJudge, MockJudge
        from pipeline.quality import GeminiSemanticQuality, MockSemanticQuality
        from pipeline.run import Deps, analyze_upload
        from pipeline.settings import Settings
        s, st = Settings(), get_state()
        client = GeminiClient(s) if s.judge_mode == "vertex" else None
        deps = Deps(st.storage, st.repo, MockFaceDetector(),
                    GeminiSemanticQuality(client, s.gemini_model_fast) if client else MockSemanticQuality(),
                    GeminiJudge(client) if client else MockJudge(), s)
        try:
            res = analyze_upload(path, uid, datetime.now(timezone.utc), deps)
            log.warning("dev analysis of %s -> %s", path, res.outcome)
        except Exception:
            log.exception("dev analysis failed for %s", path)

    @app.put("/dev-files/{path:path}", status_code=200)
    async def dev_put(path: str, request: Request, background: BackgroundTasks) -> dict:
        if not path.startswith(("uploads/", "references/")):
            raise HTTPException(403, "not allowed")
        get_state().storage.write(path, await request.body())
        if path.startswith("uploads/") and SETTINGS.dev_analyze_on_upload:
            background.add_task(_analyze, path, request.headers.get("x-goog-meta-uid", "anonymous"))
        return {"stored": path}

    @app.get("/dev-files/{path:path}")
    def dev_get(path: str) -> Response:
        try:
            return Response(get_state().storage.read(path), media_type="image/jpeg")
        except FileNotFoundError:
            raise HTTPException(404, "not found")
