"""Endpoints for administrators / experts. Access is limited to the sites in the caller's `siteIds` claim."""
import json
import uuid
from datetime import datetime, timezone

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.auth import Principal, check_site_access, require_admin
from app.config import SETTINGS
from app.deps import State, get_state
from shared.schemas.models import REVIEW_DECISIONS, Group, GuideLayout, LatLng, Reference, Spot
from shared.schemas.templates import BUILTIN_TEMPLATES

router = APIRouter(prefix="/admin")


def _url(st: State, path: str) -> str:
    return st.storage.signed_download_url(path, SETTINGS.download_url_expires_s)


@router.get("/templates")
def list_templates() -> list[dict]:
    return [{"templateId": k, "name": t.name, "observationItems": t.observationItems}
            for k, t in BUILTIN_TEMPLATES.items()]


@router.get("/spots")
def list_spots(p: Principal = Depends(require_admin), st: State = Depends(get_state)) -> list[dict]:
    return [{"spotId": s.id, **s.data.model_dump(mode="json"), "captureUrl": f"{SETTINGS.capture_base_url}/capture/{s.id}"}
            for s in st.repo.list_spots(p.site_ids)]


@router.get("/groups")
def list_groups(p: Principal = Depends(require_admin), st: State = Depends(get_state)) -> list[dict]:
    return [{"groupId": g.id, "siteId": g.data.siteId, "name": g.data.name} for g in st.repo.list_groups(p.site_ids)]


class GroupIn(BaseModel):
    siteId: str
    name: str


@router.post("/groups", status_code=201)
def create_group(body: GroupIn, p: Principal = Depends(require_admin), st: State = Depends(get_state)) -> dict:
    check_site_access(p, body.siteId)
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "name is empty")
    if any(g.data.name == name for g in st.repo.list_groups([body.siteId])):
        raise HTTPException(409, "a group with this name already exists")
    return {"groupId": st.repo.add_group(Group(siteId=body.siteId, name=name)), "siteId": body.siteId, "name": name}


def _check_group(st: State, site_id: str, group_id: str | None) -> None:
    if group_id is None:
        return
    g = st.repo.get_group(group_id)
    if g is None or g.siteId != site_id:
        raise HTTPException(422, "unknown group for this site")


class SpotIn(BaseModel):
    siteId: str
    name: str
    location: LatLng
    standingNote: str = ""
    guideText: str = ""
    templateId: str = "stone_wall"
    groupId: str | None = None


@router.post("/spots", status_code=201)
def create_spot(body: SpotIn, p: Principal = Depends(require_admin), st: State = Depends(get_state)) -> dict:
    check_site_access(p, body.siteId)
    if body.templateId not in BUILTIN_TEMPLATES and st.repo.get_template(body.templateId) is None:
        raise HTTPException(422, "unknown templateId")
    _check_group(st, body.siteId, body.groupId)
    spot = Spot(**body.model_dump(), status="ok")
    spot_id = st.repo.add_spot(spot)
    return {"spotId": spot_id, "captureUrl": f"{SETTINGS.capture_base_url}/capture/{spot_id}"}


class SpotPatch(BaseModel):
    """Only the fields that are sent are changed (so groupId = null means "remove from the group")."""
    groupId: str | None = None
    guideText: str | None = None
    guideLayout: GuideLayout | None = None  # null resets to the default arrangement
    guideLayoutPortrait: GuideLayout | None = None


@router.patch("/spots/{spot_id}")
def update_spot(spot_id: str, body: SpotPatch, p: Principal = Depends(require_admin), st: State = Depends(get_state)) -> dict:
    """Moves a spot into a group (groupId = null leaves it) and/or sets its guide text."""
    spot = st.repo.get_spot(spot_id)
    if spot is None:
        raise HTTPException(404, "spot not found")
    check_site_access(p, spot.siteId)
    fields = body.model_dump(exclude_unset=True)
    if "guideText" in fields:
        fields["guideText"] = (fields["guideText"] or "").strip()
    if "groupId" in fields:
        _check_group(st, spot.siteId, fields["groupId"])
    # a Firestore document is limited to 1 MiB, shared by both layouts
    if len(json.dumps([fields.get("guideLayout"), fields.get("guideLayoutPortrait")])) > 900_000:
        raise HTTPException(413, "layout too large")
    for key, want in (("guideLayout", "landscape"), ("guideLayoutPortrait", "portrait")):
        if fields.get(key) is not None and fields[key].get("orientation", "landscape") != want:
            raise HTTPException(422, f"{key} must have orientation {want}")
    if fields:
        st.repo.update_spot(spot_id, fields)
    return {"spotId": spot_id, **fields}


@router.post("/spots/{spot_id}/references", status_code=201)
async def add_reference(spot_id: str, file: UploadFile = File(...), season: str | None = Form(None),
                        timeOfDay: str | None = Form(None), p: Principal = Depends(require_admin),
                        st: State = Depends(get_state)) -> dict:
    """Stores a reference photo, resized so its long edge is at most MAX_UPLOAD_EDGE_PX. The analyzer
    resizes uploads the same way, so change boxes are in this image's pixel coordinates."""
    spot = st.repo.get_spot(spot_id)
    if spot is None:
        raise HTTPException(404, "spot not found")
    check_site_access(p, spot.siteId)
    img = cv2.imdecode(np.frombuffer(await file.read(), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(422, "not an image")
    scale = SETTINGS.max_edge_px / max(img.shape[:2])
    if scale < 1:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    path = f"references/{spot_id}/{uuid.uuid4().hex}.jpg"
    st.storage.write(path, cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tobytes())
    try:
        ref = Reference(spotId=spot_id, storagePath=path, season=season or None, timeOfDay=timeOfDay or None)
    except ValueError:
        st.storage.delete(path)
        raise HTTPException(422, "bad season or timeOfDay")
    return {"referenceId": st.repo.add_reference(ref), "width": img.shape[1], "height": img.shape[0]}


def _own_spot(st: State, spot_id: str, p: Principal) -> Spot:
    spot = st.repo.get_spot(spot_id)
    if spot is None:
        raise HTTPException(404, "spot not found")
    check_site_access(p, spot.siteId)
    return spot


@router.get("/spots/{spot_id}/references")
def list_spot_references(spot_id: str, p: Principal = Depends(require_admin), st: State = Depends(get_state)) -> list[dict]:
    """All reference photos of a spot, active or not, for the season / time-of-day management screen."""
    _own_spot(st, spot_id, p)
    return [{"referenceId": r.id, "season": r.data.season, "timeOfDay": r.data.timeOfDay, "active": r.data.active,
             "url": _url(st, r.data.storagePath)} for r in st.repo.list_references(spot_id, active_only=False)]


class ReferenceIn(BaseModel):
    active: bool


@router.patch("/spots/{spot_id}/references/{reference_id}")
def set_reference_active(spot_id: str, reference_id: str, body: ReferenceIn, p: Principal = Depends(require_admin),
                         st: State = Depends(get_state)) -> dict:
    """Turns a reference photo on or off. The last active one cannot be turned off: tourists need a photo to match."""
    _own_spot(st, spot_id, p)
    ref = st.repo.get_reference(reference_id)
    if ref is None or ref.spotId != spot_id:
        raise HTTPException(404, "reference not found")
    active = [r.id for r in st.repo.list_references(spot_id)]
    if not body.active and active == [reference_id]:
        raise HTTPException(409, "at least one reference photo must stay active")
    st.repo.update_reference(reference_id, {"active": body.active})
    return {"referenceId": reference_id, "active": body.active}


def _summary(st: State, det_id: str, d) -> dict:
    spot = st.repo.get_spot(d.spotId)
    return {"id": det_id, "spotId": d.spotId, "spotName": spot.name if spot else "", "siteId": d.siteId,
            "status": d.status, "maxConfidence": d.maxConfidence,
            "categories": sorted({c.category for c in d.changes}),
            "createdAt": d.createdAt.isoformat() if d.createdAt else None}


@router.get("/detections")
def list_detections(status: str | None = None, sort: str = "newest", p: Principal = Depends(require_admin),
                    st: State = Depends(get_state)) -> list[dict]:
    """List for the review queue. sort = newest | confidence. Default shows everything the admin can see."""
    if sort not in ("newest", "confidence"):
        raise HTTPException(422, "sort must be newest or confidence")
    items = st.repo.list_detections(p.site_ids, status=status, order_by="confidence" if sort == "confidence" else "createdAt")
    return [_summary(st, i.id, i.data) for i in items]


def _get_visible(st: State, det_id: str, p: Principal):
    d = st.repo.get_detection(det_id)
    if d is None:
        raise HTTPException(404, "detection not found")
    check_site_access(p, d.siteId)
    return d


def spot_status_for(st: State, site_id: str, spot_id: str) -> str:
    """needs_review (something waits for a human) > confirmed_change (a human confirmed a change) > ok."""
    mine = [i.data.status for i in st.repo.list_detections([site_id]) if i.data.spotId == spot_id]
    if "needs_review" in mine:
        return "needs_review"
    return "confirmed_change" if "confirmed_change" in mine else "ok"


@router.get("/detections/{det_id}")
def get_detection(det_id: str, p: Principal = Depends(require_admin), st: State = Depends(get_state)) -> dict:
    """Detail for the comparison screen: reference vs submitted photo, with the changes (red boxes)."""
    d = _get_visible(st, det_id, p)
    photo, ref = st.repo.get_photo(d.photoId), st.repo.get_reference(d.referenceId)
    return {**_summary(st, det_id, d), "changes": [c.model_dump() for c in d.changes], "model": d.model,
            "reviewedBy": d.reviewedBy, "reviewedAt": d.reviewedAt.isoformat() if d.reviewedAt else None,
            "capturedAt": photo.capturedAt.isoformat() if photo else None,
            "photoUrl": _url(st, photo.storagePath) if photo else None,
            "referenceUrl": _url(st, ref.storagePath) if ref else None,
            "disclaimer": "AIの判定です。確定は管理者が行います"}


class DecisionIn(BaseModel):
    status: str


@router.patch("/detections/{det_id}")
def decide(det_id: str, body: DecisionIn, p: Principal = Depends(require_admin), st: State = Depends(get_state)) -> dict:
    """A human confirms: confirmed_change / false_positive / monitoring. The AI never does this."""
    if body.status not in REVIEW_DECISIONS:
        raise HTTPException(422, f"status must be one of {list(REVIEW_DECISIONS)}")
    d = _get_visible(st, det_id, p)
    if d.status == "no_change":
        raise HTTPException(409, "nothing to review: the AI found no change")
    st.repo.update_detection(det_id, {"status": body.status, "reviewedBy": p.uid,
                                      "reviewedAt": datetime.now(timezone.utc)})
    st.repo.set_spot_status(d.spotId, spot_status_for(st, d.siteId, d.spotId))
    return {"id": det_id, "status": body.status}
