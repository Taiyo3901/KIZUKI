"""False-alarm check with the PRODUCTION pipeline (alignment, people mask, difference, Gemini with the stone-wall template).

  python experiments/regress_prod.py <labels.json> [--objects] [--prompt old|new] [--repeat N] [--pairs]

Every case in labels.json is a pair of photos that should show no change (`"expected": []`). The script reports,
per pair, how many candidates reached Gemini and what Gemini answered. `--prompt` picks the wording (old = before "落書き・汚損"), `--repeat` judges each pair N times, `--pairs` is for
real before/after pairs whose truth is not "no change" (it only lists what Gemini says). `--objects` also uses Cloud Vision's object
detection like the deployed analyzer does. Paid calls (Gemini, and Vision with --objects); same environment as
miss_check.py: JUDGE_MODE=vertex, GOOGLE_CLOUD_PROJECT, GEMINI_MODEL_FAST and application default credentials.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "services" / "analyzer"))
sys.path.insert(0, str(ROOT))
from pipeline import align, candidates, judge as judge_stage, object_mask  # noqa: E402
from pipeline.gemini_client import GeminiClient  # noqa: E402
from pipeline.settings import SETTINGS  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402
from prompts import template_for  # noqa: E402


def read(path: Path) -> np.ndarray:
    img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    return align.resize_long_edge(img, SETTINGS.max_edge_px)


def opt(name: str, default: str) -> str:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main() -> None:
    args = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and sys.argv[i - 1] not in ("--repeat", "--prompt")]
    labels = Path(args[0])
    base = labels.parent
    cases = json.loads(labels.read_text(encoding="utf-8"))["cases"]
    template = template_for(opt("--prompt", "new"))
    n = int(opt("--repeat", "1"))
    pairs = "--pairs" in sys.argv
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
        ignore, m = (object_mask.build_ignore_mask(ref, tgt, al.homography, detector, SETTINGS) if detector else (None, 0))
        cands, _ = candidates.find_candidates(ref, al.aligned, al.valid_mask, dissim_threshold=SETTINGS.dissim_threshold,
                                              min_area_ratio=SETTINGS.min_area_ratio, max_candidates=SETTINGS.max_candidates,
                                              ignore_mask=ignore)
        with ThreadPoolExecutor(max_workers=5) as ex:
            runs = list(ex.map(lambda _: judge_stage.judge_candidates(ref, al.aligned, cands, template, judge, SETTINGS), range(n)))
        calls += sum(r.api_calls for r in runs)
        hits = sum(r.max_confidence >= SETTINGS.needs_review_threshold for r in runs)
        alarms += hits > 0
        cats = {}
        for r in runs:
            for c in r.changes:
                cats[c.category] = cats.get(c.category, 0) + 1
        verdict = f"needs review in {hits}/{n} runs" if pairs else (f"FALSE ALARM in {hits}/{n} runs" if hits else "no change")
        print(f"{case['id']}: masked {m}, candidates {len(cands)}, alignment inliers {al.inliers}; {verdict}; categories {cats}; "
              f"max confidences {[round(r.max_confidence, 2) for r in runs]}")
        if pairs:
            for c in runs[0].changes[:3]:
                print(f"     - {c.category} {c.confidence:.2f}: {c.reason[:110]}")
    if not pairs:
        print(f"\nfalse alarms: {alarms} of {len(cases)} pairs; Gemini calls: {calls}")
    else:
        print(f"\nGemini calls: {calls}")


if __name__ == "__main__":
    main()
