"""Orchestrates the analysis of one uploaded photo (stages 1-8).

Order (decided with the user): face blur FIRST, then everything else, so an unblurred image is never sent
to Gemini. The original upload is deleted as soon as the blurred copy is saved (CLAUDE.md section 9).
Each stage lives in its own module and can be tested on its own (image in -> JSON-like result out).
"""
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import cv2
import numpy as np

from pipeline import align as align_stage
from pipeline import candidates as candidates_stage
from pipeline import face_blur, judge as judge_stage, quality as quality_stage
from pipeline.select_reference import select_reference
from pipeline.settings import SETTINGS, Settings
from shared.adapters.ports import Repository, Storage
from shared.schemas.models import Detection, DetectionStatus, Photo, Quality
from shared.schemas.templates import BUILTIN_TEMPLATES

UPLOAD_RE = re.compile(r"^uploads/(?P<spot>[^/]+)/(?P<name>[^/]+)\.jpe?g$")
REASON_ALIGN = "基準写真と位置が合わない"


@dataclass
class Deps:
    storage: Storage
    repo: Repository
    faces: face_blur.FaceDetector
    semantic: quality_stage.SemanticQuality
    judge: judge_stage.Judge
    settings: Settings = SETTINGS


@dataclass
class AnalysisResult:
    outcome: str  # unknown_spot | quality_failed | no_reference | no_change | needs_review
    spot_id: str = ""
    photo_id: str | None = None
    detection_id: str | None = None
    faces_blurred: int = 0
    quality: Quality | None = None
    max_confidence: float = 0.0
    api_calls: int = 0


def decide_status(max_confidence: float, threshold: float) -> DetectionStatus:
    """Stage 8 rule: AI only goes as far as 'needs_review'; a human confirms (CLAUDE.md section 1)."""
    return "needs_review" if max_confidence >= threshold else "no_change"


def _decode(data: bytes, max_edge: int) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("not a decodable image")
    return align_stage.resize_long_edge(img, max_edge)


def _jpeg(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return buf.tobytes()


def analyze_upload(upload_path: str, uploader_uid: str, captured_at: datetime | None, d: Deps) -> AnalysisResult:
    s = d.settings
    m = UPLOAD_RE.match(upload_path)
    if not m:
        raise ValueError(f"unexpected upload path: {upload_path}")
    spot_id, name = m["spot"], m["name"]
    captured_at = captured_at or datetime.now(timezone.utc)

    spot = d.repo.get_spot(spot_id)
    if spot is None:
        d.storage.delete(upload_path)  # nothing to attach it to
        return AnalysisResult("unknown_spot", spot_id)

    # --- stage 2: blur faces, keep only the blurred image, delete the original
    img = _decode(d.storage.read(upload_path), s.max_edge_px)
    img, n_faces = face_blur.blur_faces(img, d.faces)
    photo_path = f"photos/{spot_id}/{name}.jpg"
    d.storage.write(photo_path, _jpeg(img))
    d.storage.delete(upload_path)

    # --- stage 1: quality
    quality = quality_stage.run_quality(img, d.semantic, s)

    # --- stage 7 (+ 4): choose a reference and align to it
    chosen = select_reference(d.repo.list_references(spot_id), captured_at)
    aligned = None
    if quality.passed and chosen is not None:
        ref_img = _decode(d.storage.read(chosen.data.storagePath), s.max_edge_px)
        al = align_stage.align(ref_img, img, s.min_inliers)
        if al.ok:
            aligned = al
        else:
            quality = Quality(passed=False, reasons=[REASON_ALIGN])

    photo_id = d.repo.add_photo(Photo(siteId=spot.siteId, spotId=spot_id, storagePath=photo_path,
                                      capturedAt=captured_at, quality=quality, uploaderUid=uploader_uid))
    res = AnalysisResult("quality_failed", spot_id, photo_id, faces_blurred=n_faces, quality=quality)
    if not quality.passed:
        return res
    if chosen is None:
        res.outcome = "no_reference"
        return res

    # --- stage 5: candidates
    cands, _ = candidates_stage.find_candidates(
        ref_img, aligned.aligned, aligned.valid_mask, dissim_threshold=s.dissim_threshold,
        min_area_ratio=s.min_area_ratio, max_candidates=s.max_candidates)

    # --- stage 6: judge
    template = d.repo.get_template(spot.templateId) or BUILTIN_TEMPLATES.get(spot.templateId)
    if template is None:
        raise ValueError(f"unknown template: {spot.templateId}")
    jd = judge_stage.judge_candidates(ref_img, aligned.aligned, cands, template, d.judge, s)

    # --- stage 8: save
    status = decide_status(jd.max_confidence, s.needs_review_threshold)
    det_id = d.repo.add_detection(Detection(
        siteId=spot.siteId, photoId=photo_id, spotId=spot_id, referenceId=chosen.id, changes=jd.changes,
        maxConfidence=jd.max_confidence, status=status, model=jd.model))
    if status == "needs_review":
        d.repo.set_spot_status(spot_id, "needs_review")
    res.outcome, res.detection_id = status, det_id
    res.max_confidence, res.api_calls = jd.max_confidence, jd.api_calls
    return res


def new_upload_name() -> str:
    return uuid.uuid4().hex
