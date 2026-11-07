"""Unit tests per stage (image in -> result out). No network."""
from datetime import datetime, timezone

import cv2
import numpy as np

from pipeline import face_blur, quality
from pipeline.candidates import Candidate, find_candidates
from pipeline.align import align
from pipeline.judge import MockJudge, gemini_box_to_pixels, judge_candidates, response_schema
from pipeline.select_reference import season_of, select_reference, time_of_day_of
from pipeline.settings import Settings
from shared.adapters.ports import Stored
from shared.schemas.models import Reference
from shared.schemas.templates import STONE_WALL
from tests.helpers import make_wall, reshoot, with_change


# --- stage 1
def test_quality_passes_sharp_bright_image():
    q = quality.run_quality(make_wall(), quality.MockSemanticQuality(), Settings())
    assert q.passed and q.reasons == []


def test_quality_flags_blur_and_darkness_with_reasons():
    wall = make_wall()
    blurred = cv2.GaussianBlur(wall, (0, 0), 12)
    dark = (wall * 0.1).astype(np.uint8)
    assert quality.REASON_BLUR in quality.check_numeric(blurred, Settings())
    assert quality.REASON_DARK in quality.check_numeric(dark, Settings())


def test_quality_skips_semantic_call_when_numbers_fail():
    class Boom:
        def check(self, img): raise AssertionError("should not be called")
    q = quality.run_quality(cv2.GaussianBlur(make_wall(), (0, 0), 12), Boom(), Settings())
    assert not q.passed


def test_quality_collects_semantic_reasons():
    class Occluded:
        def check(self, img): return [quality.REASON_OCCLUDED]
    q = quality.run_quality(make_wall(), Occluded(), Settings())
    assert not q.passed and q.reasons == [quality.REASON_OCCLUDED]


# --- stage 2
def test_blur_regions_changes_only_the_region():
    img = make_wall()
    out = face_blur.blur_regions(img, [(300, 200, 100, 100)], pad=0.0)
    assert not np.array_equal(out[200:300, 300:400], img[200:300, 300:400])
    assert np.array_equal(out[:150], img[:150])


def test_blur_faces_with_detector():
    class OneFace:
        def detect(self, jpeg, w, h): return [(100, 100, 80, 80)]
    img = make_wall()
    out, n = face_blur.blur_faces(img, OneFace())
    assert n == 1 and not np.array_equal(out, img)
    same, n0 = face_blur.blur_faces(img, face_blur.MockFaceDetector())
    assert n0 == 0 and np.array_equal(same, img)


# --- stage 4 + 5
def test_align_recovers_small_shift_and_candidates_find_the_change():
    ref = make_wall()
    tgt = reshoot(with_change(ref), gain=1.1, shift=(7, -5))
    al = align(ref, tgt, 30)
    assert al.ok
    cands, _ = find_candidates(ref, al.aligned, al.valid_mask, dissim_threshold=0.55,
                               min_area_ratio=0.0002, max_candidates=5)
    assert any(c.x - 30 <= 450 <= c.x + c.width + 30 and c.y - 30 <= 340 <= c.y + c.height + 30 for c in cands)


def test_no_candidates_for_lighting_change_only():
    ref = make_wall()
    al = align(ref, reshoot(ref, gain=1.15, shift=(5, 4)), 30)
    cands, _ = find_candidates(ref, al.aligned, al.valid_mask, dissim_threshold=0.55,
                               min_area_ratio=0.0002, max_candidates=5)
    assert cands == []


def test_align_fails_on_unrelated_images():
    assert not align(make_wall(1), np.full((700, 1000, 3), 128, np.uint8), 30).ok


# --- stage 6
def test_gemini_box_conversion_ymin_xmin_ymax_xmax_0_1000():
    # crop starts at (100, 50), is 200 px wide and 100 px high; box covers the right half of it
    b = gemini_box_to_pixels([0, 500, 1000, 1000], (100, 50), (200, 100))
    assert (b.x, b.y, b.width, b.height) == (200, 50, 100, 100)


def test_schema_limits_category_to_template_items():
    schema = response_schema(["割れ", "緩み"])
    assert schema["properties"]["changes"]["items"]["properties"]["category"]["enum"] == ["割れ", "緩み"]


class _Scripted:
    def __init__(self, *outs): self.outs, self.models = list(outs), []
    def judge(self, ref, tgt, cand, template, model):
        self.models.append(model)
        return self.outs.pop(0)


def _out(conf, cat="割れ"):
    return {"changes": [{"category": cat, "box_2d": [0, 0, 1000, 1000], "confidence": conf, "reason": "r"}],
            "lightingDifference": "light", "noChange": False}


def test_ambiguous_confidence_is_rechecked_with_pro_model():
    s = Settings(judge_mode="vertex", gemini_model_fast="fast", gemini_model_pro="pro")
    img = make_wall()
    j = _Scripted(_out(0.5), _out(0.8))
    r = judge_candidates(img, img, [Candidate(100, 100, 50, 50, 0.5)], STONE_WALL, j, s)
    assert j.models == ["fast", "pro"] and r.max_confidence == 0.8 and r.api_calls == 2


def test_confident_result_is_not_rechecked():
    s = Settings(judge_mode="vertex", gemini_model_fast="fast", gemini_model_pro="pro")
    img = make_wall()
    j = _Scripted(_out(0.9))
    judge_candidates(img, img, [Candidate(100, 100, 50, 50, 0.5)], STONE_WALL, j, s)
    assert j.models == ["fast"]


def test_category_outside_template_is_dropped():
    img = make_wall()
    r = judge_candidates(img, img, [Candidate(100, 100, 50, 50, 0.5)], STONE_WALL,
                         _Scripted(_out(0.9, cat="宇宙人")), Settings())
    assert r.changes == []


def test_mock_judge_reports_each_candidate():
    img = make_wall()
    r = judge_candidates(img, img, [Candidate(100, 100, 50, 50, 0.5)], STONE_WALL, MockJudge(), Settings())
    assert len(r.changes) == 1 and r.changes[0].category == STONE_WALL.observationItems[0]


# --- stage 7
def test_season_and_time_of_day_use_japan_time():
    dt = datetime(2026, 1, 15, 23, 0, tzinfo=timezone.utc)  # 08:00 JST on Jan 16
    assert season_of(dt) == "winter" and time_of_day_of(dt) == "morning"


def test_select_reference_prefers_matching_season_and_time():
    refs = [Stored("a", Reference(spotId="s", storagePath="a", season="summer", timeOfDay="day")),
            Stored("b", Reference(spotId="s", storagePath="b", season="winter", timeOfDay="morning")),
            Stored("c", Reference(spotId="s", storagePath="c"))]
    dt = datetime(2026, 1, 16, 8, 0, tzinfo=timezone(__import__("datetime").timedelta(hours=9)))
    assert select_reference(refs, dt).id == "b"
    assert select_reference([], dt) is None
