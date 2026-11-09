"""Whole pipeline (stages 1-8) with in-memory storage/DB and mock judge. No network."""
from datetime import datetime, timezone

import cv2
import pytest
from fastapi.testclient import TestClient

from pipeline.face_blur import MockFaceDetector
from pipeline.judge import MockJudge
from pipeline.quality import MockSemanticQuality
from pipeline.run import Deps, analyze_upload
from pipeline.settings import Settings
from shared.adapters.memory import MemoryRepository, MemoryStorage
from shared.schemas.models import LatLng, Reference, Spot
from tests.helpers import jpeg, make_wall, reshoot, with_change

NOW = datetime(2026, 11, 7, 3, 0, tzinfo=timezone.utc)


class OneFace:
    def detect(self, jpeg_bytes, w, h):
        return [(100, 100, 80, 80)]


def setup(faces=None, objects=None):
    storage, repo = MemoryStorage(), MemoryRepository()
    spot_id = repo.add_spot(Spot(siteId="site1", name="s", location=LatLng(lat=0, lng=0), templateId="stone_wall"))
    storage.write("references/r1.jpg", jpeg(make_wall()))
    repo.add_reference(Reference(spotId=spot_id, storagePath="references/r1.jpg"))
    deps = Deps(storage, repo, faces or MockFaceDetector(), MockSemanticQuality(), MockJudge(), Settings(),
                **({"objects": objects} if objects else {}))
    return deps, spot_id


def upload(deps, spot_id, img, name="u1"):
    path = f"uploads/{spot_id}/{name}.jpg"
    deps.storage.write(path, jpeg(img))
    return path


def test_unchanged_photo_is_no_change_and_original_is_deleted():
    deps, spot = setup()
    path = upload(deps, spot, reshoot(make_wall(), gain=1.1, shift=(5, 4)))
    r = analyze_upload(path, "uid1", NOW, deps)
    assert r.outcome == "no_change" and r.quality.passed
    assert not deps.storage.exists(path)                       # original removed
    assert deps.storage.exists(f"photos/{spot}/u1.jpg")        # blurred copy kept
    det = deps.repo.get_detection(r.detection_id)
    assert det.status == "no_change" and det.siteId == "site1" and det.changes == []
    assert deps.repo.get_spot(spot).status == "ok"


def test_changed_photo_becomes_needs_review_and_marks_the_spot():
    deps, spot = setup()
    r = analyze_upload(upload(deps, spot, reshoot(with_change(make_wall()), shift=(4, 3))), "uid1", NOW, deps)
    assert r.outcome == "needs_review" and r.max_confidence >= 0.6
    det = deps.repo.get_detection(r.detection_id)
    assert det.status == "needs_review" and det.changes and det.referenceId
    assert deps.repo.get_spot(spot).status == "needs_review"
    assert det.reviewedBy is None  # AI never confirms a change


def test_blurry_photo_stops_with_reason_and_no_detection():
    deps, spot = setup()
    path = upload(deps, spot, cv2.GaussianBlur(make_wall(), (0, 0), 12))
    r = analyze_upload(path, "uid1", NOW, deps)
    assert r.outcome == "quality_failed" and r.detection_id is None
    assert "ブレ" in r.quality.reasons
    rec = deps.repo.photos[r.photo_id]
    assert rec.quality.passed is False and rec.storagePath == ""          # reasons kept, picture not stored
    assert not deps.storage.exists(path) and not deps.storage.exists(f"photos/{spot}/u1.jpg")


def test_unrelated_photo_is_recorded_as_alignment_failure():
    deps, spot = setup()
    r = analyze_upload(upload(deps, spot, make_wall(seed=99)), "uid1", NOW, deps)
    assert r.outcome == "quality_failed" and r.detection_id is None
    assert "基準写真と位置が合わない" in r.quality.reasons
    assert not deps.storage.exists(f"photos/{spot}/u1.jpg")


def test_faces_are_blurred_before_saving():
    deps, spot = setup(faces=OneFace())
    src = make_wall()
    path = upload(deps, spot, src)
    r = analyze_upload(path, "uid1", NOW, deps)
    assert r.faces_blurred == 1
    saved = cv2.imdecode(__import__("numpy").frombuffer(deps.storage.read(f"photos/{spot}/u1.jpg"), "uint8"), 1)
    assert abs(float(saved[110:170, 110:170].std()) - float(src[110:170, 110:170].std())) > 1  # region changed


def test_no_reference_is_reported():
    deps, spot = setup()
    deps.repo.references.clear()
    r = analyze_upload(upload(deps, spot, make_wall()), "uid1", NOW, deps)
    assert r.outcome == "no_reference" and r.detection_id is None


def test_unknown_spot_deletes_the_upload():
    deps, _ = setup()
    deps.storage.write("uploads/nope/x.jpg", jpeg(make_wall()))
    assert analyze_upload("uploads/nope/x.jpg", "u", NOW, deps).outcome == "unknown_spot"
    assert not deps.storage.exists("uploads/nope/x.jpg")


def test_bad_path_is_rejected():
    deps, _ = setup()
    with pytest.raises(ValueError):
        analyze_upload("photos/a/b.jpg", "u", NOW, deps)


# --- Eventarc entry point
def test_event_endpoint(monkeypatch):
    import app.main as main
    deps, spot = setup()
    path = upload(deps, spot, reshoot(make_wall(), shift=(3, 3)))
    monkeypatch.setattr(main, "_deps", deps)
    c = TestClient(main.app)
    body = {"bucket": "b", "name": path, "metadata": {"uid": "anon1"}, "timeCreated": "2026-11-07T03:00:00Z"}
    assert c.post("/", json=body).json()["outcome"] == "no_change"
    # redelivery of the same event (original already deleted) is harmless
    assert c.post("/", json=body).json()["reason"] == "already processed"
    # other prefixes never trigger analysis
    assert "ignored" in c.post("/", json={"bucket": "b", "name": "photos/a/b.jpg"}).json()
    assert c.get("/healthz").json() == {"ok": True}


class PersonOverTheChange:
    """Reports a person standing right where the red patch is (the patch is at x 400-500, y 300-380)."""

    def detect(self, jpeg_bytes, w, h):
        return [(390, 290, 130, 110)]


class BrokenDetector:
    def detect(self, jpeg_bytes, w, h):
        raise RuntimeError("Vision unavailable")


def test_difference_under_a_detected_person_is_left_out():
    deps, spot = setup(objects=PersonOverTheChange())
    r = analyze_upload(upload(deps, spot, with_change(make_wall())), "uid1", NOW, deps)
    assert r.outcome == "no_change" and r.objects_masked >= 1 and r.api_calls == 0   # no paid call either


def test_the_same_difference_is_reported_when_nothing_is_detected():
    deps, spot = setup()
    r = analyze_upload(upload(deps, spot, with_change(make_wall())), "uid1", NOW, deps)
    assert r.outcome == "needs_review" and r.objects_masked == 0


def test_a_failing_object_detector_does_not_fail_the_analysis():
    deps, spot = setup(objects=BrokenDetector())
    r = analyze_upload(upload(deps, spot, with_change(make_wall())), "uid1", NOW, deps)
    assert r.outcome == "needs_review"     # compared without a mask


class FlakySemantic:
    """Fails the first time (a dropped connection), works afterwards."""

    def __init__(self):
        self.calls = 0

    def check(self, img):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("connection dropped")
        return []


def test_a_crash_after_the_original_is_deleted_is_resumed_from_the_blurred_copy():
    deps, spot = setup()
    deps.semantic = FlakySemantic()
    path = upload(deps, spot, reshoot(make_wall(), gain=1.1, shift=(5, 4)))
    with pytest.raises(RuntimeError):
        analyze_upload(path, "uid1", NOW, deps)
    assert not deps.storage.exists(path) and deps.storage.exists(f"photos/{spot}/u1.jpg")   # nothing was lost
    r = analyze_upload(path, "uid1", NOW, deps)                                             # the redelivered event
    assert r.outcome == "no_change" and r.photo_id
    with pytest.raises(FileNotFoundError):                                                   # and a third delivery is a no-op
        analyze_upload(path, "uid1", NOW, deps)
    assert len(deps.repo.photos) == 1
