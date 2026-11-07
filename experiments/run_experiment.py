"""Run align -> diff -> judge for every case in a labels file and save JSON + overlay images.

Usage (from experiments/):  .venv\\Scripts\\python run_experiment.py [labels.json] [out_dir]
"""
import json
import sys
from pathlib import Path

import cv2

from align import align, resize_long_edge
from config import SETTINGS
from diff import find_candidates
from judge import judge_candidates, make_judge


def run_case(case: dict, base: Path, judge, s=SETTINGS) -> dict:
    ref = resize_long_edge(cv2.imread(str(base / case["reference"])), s.max_edge_px)
    tgt = resize_long_edge(cv2.imread(str(base / case["target"])), s.max_edge_px)
    res = {"id": case["id"], "image_size": {"width": ref.shape[1], "height": ref.shape[0]}}

    al = align(ref, tgt, s.min_inliers)
    res["alignment"] = {"ok": al.ok, "inliers": al.inliers, "reason": al.reason}
    if not al.ok:
        res.update(status="alignment_failed", candidates=[], changes=[], max_confidence=0.0, api_calls=0)
        return res

    cands, _ = find_candidates(ref, al.aligned, al.valid_mask, dissim_threshold=s.dissim_threshold,
                               min_area_ratio=s.min_area_ratio, max_candidates=s.max_candidates)
    jd = judge_candidates(ref, al.aligned, cands, s=s, judge=judge)
    res.update(
        candidates=[c.as_dict() for c in cands],
        changes=jd.changes, lighting_difference=jd.lighting_difference,
        max_confidence=jd.max_confidence, api_calls=jd.api_calls, model=jd.model,
        status="needs_review" if jd.max_confidence >= s.needs_review_threshold else "no_change",
    )
    res["_aligned"] = al.aligned
    res["_reference"] = ref
    return res


def draw_overlay(res: dict) -> "cv2.typing.MatLike":
    img = res["_aligned"].copy()
    for c in res["candidates"]:
        cv2.rectangle(img, (c["x"], c["y"]), (c["x"] + c["width"], c["y"] + c["height"]), (255, 160, 0), 2)
    for ch in res["changes"]:
        b = ch["box"]
        cv2.rectangle(img, (b["x"], b["y"]), (b["x"] + b["width"], b["y"] + b["height"]), (0, 0, 255), 3)
    return img


def main() -> None:
    labels_path = Path(sys.argv[1] if len(sys.argv) > 1 else "samples/labels.json")
    out_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "out")
    out_dir.mkdir(parents=True, exist_ok=True)
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    judge = make_judge()
    results = []
    for case in labels["cases"]:
        res = run_case(case, labels_path.parent, judge)
        if "_aligned" in res:
            cv2.imwrite(str(out_dir / f"{case['id']}_overlay.jpg"), draw_overlay(res))
            del res["_aligned"], res["_reference"]
        results.append(res)
        print(f"{case['id']}: {res['status']} (max_conf={res['max_confidence']:.2f}, api_calls={res['api_calls']})")
    (out_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved -> {out_dir / 'results.json'}")


if __name__ == "__main__":
    main()
