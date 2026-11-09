"""Where does a change get lost? Adds known changes to a photo and measures each stage before Gemini.

  python experiments/miss_check.py <reference.jpg> [out_dir] [--judge]

--repeat N   judge every candidate N times (Gemini answers vary a little from call to call) and print the detection rate
--prompt old|new   the stone-wall wording before / after "落書き・汚損" was added (default new)
--judge also sends each candidate to Gemini (a paid call; needs JUDGE_MODE=vertex, GOOGLE_CLOUD_PROJECT,
GEMINI_MODEL_FAST and application default credentials) and prints what it answers.

For every synthetic change it reports: did the alignment hold, how different the difference map is inside the
changed region, and whether a candidate covers the region at several difference thresholds. It makes no paid call.
Needs the analyzer's requirements (OpenCV, scikit-image); run from the repository root.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "analyzer"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import align, candidates, judge as judge_stage  # noqa: E402
from pipeline.settings import SETTINGS  # noqa: E402
from shared.schemas.templates import BUILTIN_TEMPLATES  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402
from collections import Counter  # noqa: E402
from prompts import template_for  # noqa: E402


def read(path: Path) -> np.ndarray:
    return cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)  # non-ASCII paths on Windows


def reshoot(img: np.ndarray, seed: int = 1) -> np.ndarray:
    """A second visit: a slightly different standing point, a different exposure, sensor noise, JPEG."""
    rng = np.random.default_rng(seed)
    h, w = img.shape[:2]
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = src + rng.uniform(-14, 14, src.shape).astype(np.float32)
    out = cv2.warpPerspective(img, cv2.getPerspectiveTransform(src, dst), (w, h), borderMode=cv2.BORDER_REFLECT)
    out = np.clip(out.astype(np.float32) * 0.93 - 4 + rng.normal(0, 3, out.shape), 0, 255).astype(np.uint8)
    return cv2.imdecode(cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 88])[1], 1)


def changes(img: np.ndarray) -> dict[str, tuple[np.ndarray, tuple[int, int, int, int]]]:
    """name -> (photo with the change, region x, y, w, h). Placed on the stone wall, clear of people."""
    out = {}
    a = img.copy()
    cv2.line(a, (850, 1000), (905, 1095), (25, 25, 25), 4)
    cv2.line(a, (905, 1095), (880, 1150), (25, 25, 25), 3)
    out["thin crack (4px line)"] = (a, (840, 995, 75, 160))
    b = img.copy()
    cv2.rectangle(b, (1000, 1020), (1090, 1080), (205, 205, 210), -1)
    out["small light block (90x60)"] = (b, (1000, 1020, 90, 60))
    c = img.copy()
    cv2.rectangle(c, (1150, 1010), (1310, 1120), (35, 38, 42), -1)
    out["large dark patch (160x110)"] = (c, (1150, 1010, 160, 110))
    d = img.copy()
    d[1042:1122, 790:910] = img[1030:1110, 760:880]       # a stone-sized area pushed 30px right and 12px down
    out["shifted stones (120x80)"] = (d, (790, 1042, 120, 80))
    return out


def iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax0, ay0, ax1, ay1 = a[0], a[1], a[0] + a[2], a[1] + a[3]
    bx0, by0, bx1, by1 = b[0], b[1], b[0] + b[2], b[1] + b[3]
    iw, ih = max(0, min(ax1, bx1) - max(ax0, bx0)), max(0, min(ay1, by1) - max(ay0, by0))
    inter = iw * ih
    return inter / (a[2] * a[3] + b[2] * b[3] - inter)


def opt(name: str, default: str) -> str:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def _judge_and_print(judge, template, ref, aligned, cands, region=None) -> None:
    n = int(opt("--repeat", "1"))
    if n > 1:
        with ThreadPoolExecutor(max_workers=5) as ex:
            runs = list(ex.map(lambda _: judge_stage.judge_candidates(ref, aligned, cands, template, judge, SETTINGS), range(n)))
        hits = [r.max_confidence >= SETTINGS.needs_review_threshold for r in runs]
        cats = Counter(c.category for r in runs for c in r.changes)
        print(f"   Gemini x{n}: detected {sum(hits)}/{n}; categories {dict(cats)}; max confidences {[round(r.max_confidence, 2) for r in runs]}")
        return
    j = judge_stage.judge_candidates(ref, aligned, cands, template, judge, SETTINGS)
    print(f"   Gemini: {j.api_calls} call(s), max confidence {j.max_confidence:.2f}, {len(j.changes)} change(s)")
    for c in j.changes:
        near = ""
        if region:
            near = f" [overlap with the real change: {iou(region, (c.box.x, c.box.y, c.box.width, c.box.height)):.2f}]"
        print(f"     - {c.category} conf {c.confidence:.2f}{near}: {c.reason[:90]}")
    if not j.changes:
        print(f"     (no change reported; lighting note: {j.lighting_difference[:90]})")


def main() -> None:
    args = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and sys.argv[i - 1] not in ("--repeat", "--prompt")]
    use_judge = "--judge" in sys.argv
    ref = read(Path(args[0]))
    out_dir = Path(args[1]) if len(args) > 1 else None
    judge = None
    if use_judge:
        from pipeline.gemini_client import GeminiClient
        judge = judge_stage.GeminiJudge(GeminiClient(SETTINGS))
        template = template_for(opt("--prompt", "new"))
    h, w = ref.shape[:2]
    print(f"reference {w}x{h}")
    # the same re-shoot for every change, so the only difference between rows is the change itself
    cases = {"CONTROL: no change (re-shoot only)": (ref, (0, 0, 1, 1)), **changes(ref)}
    for name, (img, region) in cases.items():
        tgt = reshoot(img)
        al = align.align(ref, tgt, 30)
        print(f"\n== {name}   region x={region[0]} y={region[1]} w={region[2]} h={region[3]}")
        if not al.ok:
            print(f"   alignment FAILED: {al.reason}")
            continue
        if name.startswith("CONTROL"):
            cands, _ = candidates.find_candidates(ref, al.aligned, al.valid_mask, dissim_threshold=SETTINGS.dissim_threshold,
                                                  min_area_ratio=SETTINGS.min_area_ratio, max_candidates=SETTINGS.max_candidates)
            print(f"   alignment ok (inliers {al.inliers}); candidates found with no change: {len(cands)}")
            if judge:
                _judge_and_print(judge, template, ref, al.aligned, cands)
            continue
        dis = candidates.dissimilarity_map(ref, al.aligned)
        x, y, rw, rh = region
        inside = dis[y:y + rh, x:x + rw]
        print(f"   alignment ok (inliers {al.inliers}); difference inside region: mean {inside.mean():.2f}, p90 {np.percentile(inside, 90):.2f}, max {inside.max():.2f}"
              f"; whole-photo mean {dis.mean():.2f}, p99 {np.percentile(dis, 99):.2f}")
        for thr in (0.55, 0.45, 0.35, 0.25):
            cands, _ = candidates.find_candidates(ref, al.aligned, al.valid_mask, dissim_threshold=thr, min_area_ratio=0.0002, max_candidates=5)
            best = max((iou(region, (c.x, c.y, c.width, c.height)) for c in cands), default=0.0)
            hit = any(iou(region, (c.x, c.y, c.width, c.height)) > 0.05 for c in cands)
            print(f"   threshold {thr:.2f}: {len(cands)} candidates; region {'COVERED' if hit else 'missed '} (best IoU {best:.2f})")
        if judge:
            cands, _ = candidates.find_candidates(ref, al.aligned, al.valid_mask, dissim_threshold=SETTINGS.dissim_threshold,
                                                  min_area_ratio=SETTINGS.min_area_ratio, max_candidates=SETTINGS.max_candidates)
            _judge_and_print(judge, template, ref, al.aligned, cands, region)
        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)
            vis = cv2.applyColorMap((dis * 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
            cv2.rectangle(vis, (x, y), (x + rw, y + rh), (255, 255, 255), 3)
            cv2.imencode(".jpg", vis)[1].tofile(str(out_dir / (name.split(" (")[0].replace(" ", "_") + "_diff.jpg")))


if __name__ == "__main__":
    main()
