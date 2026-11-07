"""Analyzer service (Cloud Run). Eventarc posts a Cloud Storage "object finalized" event here.

Run locally:  uvicorn app.main:app --port 8081   (BACKEND=local uses in-memory stores; nothing is persisted)
"""
import logging
from datetime import datetime

from fastapi import FastAPI, Request

from app.deps import build_deps
from pipeline.run import UPLOAD_RE, analyze_upload

log = logging.getLogger("analyzer")
app = FastAPI(title="KIZUKI analyzer")
_deps = None


def deps():
    global _deps
    if _deps is None:
        _deps = build_deps()
    return _deps


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/")
async def on_storage_event(request: Request) -> dict:
    """Body = Cloud Storage object resource (bucket, name, metadata, timeCreated, ...)."""
    obj = await request.json()
    name = obj.get("name", "")
    if not UPLOAD_RE.match(name):  # only uploads/{spotId}/{uuid}.jpg triggers analysis
        return {"ignored": name}
    meta = obj.get("metadata") or {}
    created = obj.get("timeCreated")
    captured_at = datetime.fromisoformat(created.replace("Z", "+00:00")) if created else None
    try:
        res = analyze_upload(name, meta.get("uid", "anonymous"), captured_at, deps())
    except FileNotFoundError:
        # Already processed (the original is deleted after blurring) -> a redelivered event; nothing to do.
        log.info("upload already processed: %s", name)
        return {"ignored": name, "reason": "already processed"}
    log.info("analyzed %s -> %s", name, res.outcome)
    return {"outcome": res.outcome, "photoId": res.photo_id, "detectionId": res.detection_id}
