"""Make SYNTHETIC test images to check that the code runs end to end.

These are NOT real wall photos, so they say nothing about real accuracy.
Usage: .venv\\Scripts\\python make_synthetic_samples.py   (writes samples_synthetic/)
"""
import json
from pathlib import Path

import cv2
import numpy as np

OUT = Path("samples_synthetic")
W, H = 1600, 1200
rng = np.random.default_rng(0)


def base_wall() -> np.ndarray:
    img = np.full((H, W, 3), 140, np.uint8)
    for y in range(0, H, 100):          # rough "stone" blocks
        off = 0 if (y // 100) % 2 == 0 else 80
        for x in range(-off, W, 160):
            shade = int(rng.integers(100, 180))
            cv2.rectangle(img, (x + 3, y + 3), (x + 157, y + 97), (shade, shade - 5, shade - 15), -1)
    noise = rng.normal(0, 12, img.shape).astype(np.float32)
    return np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def reshoot(img: np.ndarray, gain=1.0, shift=(0, 0), shadow=False) -> np.ndarray:
    M = np.float32([[1, 0, shift[0]], [0, 1, shift[1]]])
    out = cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REFLECT)
    out = np.clip(out.astype(np.float32) * gain, 0, 255)
    if shadow:
        out[:, W // 2:] *= 0.7
    return out.astype(np.uint8)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    ref = base_wall()
    cv2.imwrite(str(OUT / "ref.jpg"), ref)
    cases = []

    def add(name, img, expected):
        cv2.imwrite(str(OUT / f"{name}.jpg"), img)
        cases.append({"id": name, "reference": "ref.jpg", "target": f"{name}.jpg", "expected": expected})

    add("same_bright", reshoot(ref, gain=1.15, shift=(6, -4)), [])
    add("same_shadow", reshoot(ref, shadow=True, shift=(-5, 3)), [])

    crack = reshoot(ref, shift=(4, 4))
    cv2.polylines(crack, [np.array([[800, 500], [840, 560], [820, 620], [870, 700]])], False, (20, 20, 20), 6)
    add("crack", crack, [{"category": "割れ", "box": {"x": 790 / W, "y": 490 / H, "width": 90 / W, "height": 220 / H}}])

    sticker = reshoot(ref, gain=0.95)
    cv2.rectangle(sticker, (300, 300), (400, 380), (30, 30, 220), -1)
    add("sticker", sticker, [{"category": "孕み出し", "box": {"x": 300 / W, "y": 300 / H, "width": 100 / W, "height": 80 / H}}])

    (OUT / "labels.json").write_text(json.dumps({"cases": cases}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(cases)} cases to {OUT}")


if __name__ == "__main__":
    main()
