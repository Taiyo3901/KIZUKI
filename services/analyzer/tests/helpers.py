"""Synthetic images for tests (stone-like texture + known changes)."""
import cv2
import numpy as np


def make_wall(seed: int = 0, w: int = 1000, h: int = 700) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.full((h, w, 3), 140, np.uint8)
    for y in range(0, h, 70):
        off = 0 if (y // 70) % 2 == 0 else 55
        for x in range(-off, w, 110):
            c = int(rng.integers(100, 180))
            cv2.rectangle(img, (x + 3, y + 3), (x + 107, y + 67), (c, c - 5, c - 15), -1)
    noise = rng.normal(0, 12, img.shape)
    return np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def reshoot(img: np.ndarray, gain: float = 1.0, shift: tuple[int, int] = (0, 0)) -> np.ndarray:
    h, w = img.shape[:2]
    out = cv2.warpAffine(img, np.float32([[1, 0, shift[0]], [0, 1, shift[1]]]), (w, h), borderMode=cv2.BORDER_REFLECT)
    return np.clip(out.astype(np.float32) * gain, 0, 255).astype(np.uint8)


def with_change(img: np.ndarray) -> np.ndarray:
    out = img.copy()
    cv2.rectangle(out, (400, 300), (500, 380), (30, 30, 220), -1)  # a clear red patch
    return out


def jpeg(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return buf.tobytes()
