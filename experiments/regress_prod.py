"""False-alarm check with the PRODUCTION pipeline (alignment, people mask, difference, Gemini with the stone-wall template).

  python experiments/regress_prod.py <labels.json> [--objects]

Every case in labels.json is a pair of photos that should show no change (`"expected": []`). The script reports,
per pair, how many candidates reached Gemini and what Gemini answered. `--objects` also uses Cloud Vision's object
detection like the deployed analyzer does. Paid calls (Gemini, and Vision with --objects); same environment as
miss_check.py: JUDGE_MODE=vertex, GOOGLE_CLOUD_PROJECT, GEMINI_MODEL_FAST and application default credentials.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "analyzer"))
sys.path.insert(0, str(ROOT))
from pipeline import align, candidates, judge as judge_stage, object_mask  # noqa: E402
from pipeline.gemini_client import GeminiClient  # noqa: E402
from pipeline.settings import SETTINGS  # noqa: E402
from shared.schemas.templates import BUILTIN_TEMPLATES  # noqa: E402


def read(path: Path) -> np.ndarray:
    img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    return align.resize_long_edge(img, SETTINGS.max_edge_px)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    labels = Path(args[0])
    base = labels.parent
    cases = json.loads(labels.read_text(encoding="utf-8"))["cases"]
    template = BUILTIN_TEMPLATES["stone_wall"]
    judge = judge_stage.GeminiJudge(GeminiClient(SETTINGS))
    detector = (object_mask.VisionObjectDetector(object_mask.mask_names(object_mask.DEFAULT_NAMES), SETTINGS.object_min_score)
                if "--objects" in sys.argv else None)
    alarms = calls = 0
    for case in cases:
        ref, tgt = read(base / case["reference"]), read(base / case["target"])
        al = align.align(ref, tgt, SETTINGS.min_inliers)
        if not al.ok:
            print(f"{case['id']}: alignment failed ({al.reason})")
            continue
        ignore, n = (object_mask.build_ignore_mask(ref, tgt, al.homography, detector, SETTINGS) if detector else (None, 0))
        cands, _ = candidates.find_candidates(ref, al.aligned, al.valid_mask, dissim_threshold=SETTINGS.dissim_threshold,
                                              min_area_ratio=SETTINGS.min_area_ratio, max_candidates=SETTINGS.max_candidates,
                                              ignore_mask=ignore)
        j = judge_stage.judge_candidates(ref, al.aligned, cands, template, judge, SETTINGS)
        calls += j.api_calls
        alarm = j.max_confidence >= SETTINGS.needs_review_threshold
        alarms += alarm
        print(f"{case['id']}: masked {n}, candidates {len(cands)}, gemini calls {j.api_calls}, max confidence {j.max_confidence:.2f}"
              f" -> {'NEEDS REVIEW (false alarm)' if alarm else 'no change'}")
        for c in j.changes:
            print(f"     - {c.category} {c.confidence:.2f}: {c.reason[:100]}")
    print(f"\nfalse alarms: {alarms} of {len(cases)} pairs; Gemini calls: {calls}")


if __name__ == "__main__":
    main()
