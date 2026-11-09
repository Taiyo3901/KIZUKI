"""Endpoints for tourists (no login screen; anonymous Firebase users + App Check)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.auth import Principal, get_principal, verify_app_check
from app.config import SETTINGS
from app.deps import State, get_state

router = APIRouter()


@router.get("/spots/{spot_id}")
def get_spot(spot_id: str, st: State = Depends(get_state)) -> dict:
    """Public info of a spot + time-limited URLs of its active reference photos."""
    spot = st.repo.get_spot(spot_id)
    if spot is None:
        raise HTTPException(404, "spot not found")
    refs = [{"referenceId": r.id, "season": r.data.season, "timeOfDay": r.data.timeOfDay,
             "url": st.storage.signed_download_url(r.data.storagePath, SETTINGS.download_url_expires_s)}
            for r in st.repo.list_references(spot_id)]
    # no `location`: tourists' phones neither need nor receive any position (the admin map reads it separately)
    return {"spotId": spot_id, "name": spot.name, "standingNote": spot.standingNote, "guideText": spot.guideText,
            "guideLayout": spot.guideLayout.model_dump() if spot.guideLayout else None,
            "guideLayoutPortrait": spot.guideLayoutPortrait.model_dump() if spot.guideLayoutPortrait else None,
            "references": refs}


@router.post("/spots/{spot_id}/upload-url", dependencies=[Depends(verify_app_check)])
def create_upload_url(spot_id: str, p: Principal = Depends(get_principal), st: State = Depends(get_state)) -> dict:
    """Issue a short-lived URL the phone PUTs the JPEG to. The uid travels as object metadata so the analyzer
    can record who uploaded without any extra database round trip."""
    if st.repo.get_spot(spot_id) is None:
        raise HTTPException(404, "spot not found")
    if st.repo.count_recent_uploads(p.uid, spot_id, SETTINGS.upload_window_s) >= SETTINGS.upload_limit:
        raise HTTPException(429, "too many uploads; try again later")
    st.repo.record_upload_request(p.uid, spot_id)
    path = f"uploads/{spot_id}/{uuid.uuid4().hex}.jpg"
    headers = {"x-goog-meta-uid": p.uid}
    url = st.storage.signed_upload_url(path, "image/jpeg", SETTINGS.upload_url_expires_s, headers)
    return {"uploadUrl": url, "path": path, "headers": {"Content-Type": "image/jpeg", **headers},
            "expiresInSeconds": SETTINGS.upload_url_expires_s}
