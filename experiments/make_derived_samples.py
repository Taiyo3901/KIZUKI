"""Build before/after pairs from REAL wall photos (ishigaki_samples) by adding known synthetic changes.

Reference = a real photo. Target = the same photo with
  - no change   : lighting / color / noise / tiny camera shift (+ optional soft shadow)
  - crack       : a dark jagged line is drawn  (expected category 割れ)
  - shift       : one rectangular patch is displaced by ~12-20 px (expected 孕み出し/緩み/前倒れ)
Only hand-checked references (CURATED) are used, and changes are placed on the stone area only,
so the location of every change is known. Real accuracy on real damage is NOT measured by this.
Photos with ShareAlike licenses are skipped. Output stays local (gitignored).

Usage: .venv\\Scripts\\python make_derived_samples.py [num_refs=20]
"""
import csv
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "ishigaki_samples"
OUT = Path(__file__).resolve().parent / "samples_derived"
rng = np.random.default_rng(42)

# References checked by eye (contact sheet) where stone fills much of the frame.
# Value = normalized (x, y, w, h) of the stone area; changes are only placed inside it.
# Keys are the "rNN" ids from pick_references(20) order.
CURATED = {
    "r11": (0.10, 0.10, 0.80, 0.60),
    "r12": (0.10, 0.55, 0.80, 0.35),
    "r15": (0.40, 0.30, 0.50, 0.50),
    "r16": (0.50, 0.10, 0.45, 0.75),
    "r18": (0.05, 0.40, 0.55, 0.50),
}


def place(region, w, h, margin_px):
    rx, ry, rw, rh = region
    x = rng.uniform(rx * w, max(rx * w + 1, (rx + rw) * w - margin_px))
    y = rng.uniform(ry * h, max(ry * h + 1, (ry + rh) * h - margin_px))
    return x, y


def pick_references(n: int) -> list[dict]:
    rows = list(csv.DictReader(open(SRC / "licenses.csv", encoding="utf-8-sig")))
    ok = [r for r in rows if r["wall_main_subject"] == "yes" and r["is_photo"] == "yes"
          and r["share_alike"] != "yes" and not r["damage_hint"] and r["file"].endswith(".jpg")]
    step = max(1, len(ok) // n)
    return ok[::step][:n]


def perturb(img: np.ndarray, strong_light: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """Lighting/color/noise change + tiny homography. Returns (image, 3x3 matrix used)."""
    h, w = img.shape[:2]
    f = img.astype(np.float32) / 255
    f = f ** rng.uniform(0.8, 1.25)
    f *= rng.uniform(0.75, 1.25) if strong_light else 1.0
    f *= rng.uniform(0.94, 1.06, size=3)
    f += rng.normal(0, rng.uniform(0.01, 0.025), f.shape)
    out = (np.clip(f, 0, 1) * 255).astype(np.uint8)
    j = 0.006 * np.array([w, h])
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = (src + rng.uniform(-1, 1, src.shape) * j).astype(np.float32)
    H = cv2.getPerspectiveTransform(src, dst)
    out = cv2.warpPerspective(out, H, (w, h), borderMode=cv2.BORDER_REFLECT)
    return out, H


def soft_shadow(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    mask = np.zeros((h, w), np.float32)
    p = rng.uniform(0.25, 0.75, 2) * [w, h]
    ang = rng.uniform(0, np.pi)
    poly = np.array([p + 3000 * np.array([np.cos(ang), np.sin(ang)]),
                     p - 3000 * np.array([np.cos(ang), np.sin(ang)]),
                     p - 3000 * np.array([np.cos(ang), np.sin(ang)]) + 3000 * np.array([-np.sin(ang), np.cos(ang)]),
                     p + 3000 * np.array([np.cos(ang), np.sin(ang)]) + 3000 * np.array([-np.sin(ang), np.cos(ang)])], np.int32)
    cv2.fillPoly(mask, [poly], 1.0)
    mask = cv2.GaussianBlur(mask, (0, 0), 35)
    factor = 1.0 - mask * rng.uniform(0.25, 0.45)
    return np.clip(img.astype(np.float32) * factor[..., None], 0, 255).astype(np.uint8)


def add_crack(img: np.ndarray, region) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    h, w = img.shape[:2]
    x, y = place(region, w, h, 120)
    ang = rng.uniform(0, 2 * np.pi)
    pts = [(x, y)]
    for _ in range(int(rng.integers(8, 14))):
        ang += rng.uniform(-0.7, 0.7)
        step = rng.uniform(12, 24)
        x, y = x + np.cos(ang) * step, y + np.sin(ang) * step
        pts.append((x, y))
    P = np.array(pts, np.int32)
    layer = np.zeros((h, w), np.float32)
    cv2.polylines(layer, [P], False, 1.0, int(rng.integers(2, 4)))
    layer = cv2.GaussianBlur(layer, (0, 0), 0.8)
    out = img.astype(np.float32) * (1 - 0.85 * layer[..., None]) + 25 * 0.85 * layer[..., None]
    x0, y0 = P.min(0) - 6
    x1, y1 = P.max(0) + 6
    return np.clip(out, 0, 255).astype(np.uint8), (int(x0), int(y0), int(x1 - x0), int(y1 - y0))


def add_shift(img: np.ndarray, region) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    h, w = img.shape[:2]
    pw, ph = int(rng.integers(90, 140)), int(rng.integers(60, 100))
    x, y = place(region, w, h, pw + 40)
    x, y = int(x), int(y)
    dx = int(rng.choice([-1, 1]) * rng.integers(12, 21))
    out = img.copy()
    patch = img[y:y + ph, x:x + pw].copy()
    out[y:y + ph, x + dx:x + dx + pw] = patch
    gx = x if dx > 0 else x + pw          # side where a gap opens: darken it a little
    gap = np.zeros((h, w), np.float32)
    cv2.line(gap, (gx, y), (gx, y + ph), 1.0, abs(dx) // 2 + 2)
    gap = cv2.GaussianBlur(gap, (0, 0), 2)
    out = np.clip(out.astype(np.float32) * (1 - 0.5 * gap[..., None]), 0, 255).astype(np.uint8)
    x0, x1 = min(x, x + dx), max(x + pw, x + dx + pw)
    return out, (x0, y, x1 - x0, ph)


def map_box(box: tuple[int, int, int, int], H: np.ndarray, w: int, h: int) -> dict:
    x, y, bw, bh = box
    c = np.float32([[[x, y]], [[x + bw, y]], [[x + bw, y + bh]], [[x, y + bh]]])
    t = cv2.perspectiveTransform(c, H).reshape(-1, 2)
    x0, y0 = t.min(0)
    x1, y1 = t.max(0)
    return {"x": float(x0 / w), "y": float(y0 / h), "width": float((x1 - x0) / w), "height": float((y1 - y0) / h)}


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    cases, sources = [], []
    for i, r in enumerate(pick_references(n), 1):
        ref = cv2.imread(str(SRC / r["file"]))
        if ref is None:
            continue
        h, w = ref.shape[:2]
        rid = f"r{i:02d}"
        if rid not in CURATED:
            continue
        region = CURATED[rid]
        cv2.imwrite(str(OUT / f"{rid}_ref.jpg"), ref)
        sources.append({"id": rid, "file": r["file"], "license": r["license"], "attribution": r["attribution_text"],
                        "page": r["commons_page"]})

        def add(kind, img, expected):
            tgt, H = perturb(img)
            if kind == "shadow":
                tgt = soft_shadow(tgt)
            exp = []
            for e in expected:
                exp.append({**e["meta"], "box": map_box(e["box"], H, w, h)})
            cv2.imwrite(str(OUT / f"{rid}_{kind}.jpg"), tgt)
            cases.append({"id": f"{rid}_{kind}", "reference": f"{rid}_ref.jpg", "target": f"{rid}_{kind}.jpg", "expected": exp})

        add("light", ref, [])
        add("shadow", ref, [])
        for k in (1, 2):
            cr, cb = add_crack(ref, region)
            add(f"crack{k}", cr, [{"meta": {"category": "割れ"}, "box": cb}])
            sh, sb = add_shift(ref, region)
            add(f"shift{k}", sh, [{"meta": {"category": "孕み出し", "acceptable_categories": ["孕み出し", "緩み", "前倒れ"]}, "box": sb}])

    (OUT / "labels.json").write_text(json.dumps({"cases": cases}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "sources.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(sources)} references, {len(cases)} cases -> {OUT}")


if __name__ == "__main__":
    main()
