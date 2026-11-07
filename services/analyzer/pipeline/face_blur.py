"""Stage 2: detect faces (Cloud Vision) and blur them. Only the blurred image is kept (CLAUDE.md section 9)."""
from typing import Protocol

import cv2
import numpy as np

Region = tuple[int, int, int, int]  # x, y, width, height in pixels


def blur_regions(img: np.ndarray, regions: list[Region], pad: float = 0.3) -> np.ndarray:
    """Return a copy with each region (grown by `pad`) heavily blurred."""
    out = img.copy()
    h, w = img.shape[:2]
    for x, y, bw, bh in regions:
        px, py = int(bw * pad), int(bh * pad)
        x0, y0, x1, y1 = max(0, x - px), max(0, y - py), min(w, x + bw + px), min(h, y + bh + py)
        if x1 <= x0 or y1 <= y0:
            continue
        k = max(15, ((x1 - x0) // 3) | 1)  # odd kernel proportional to the face size
        out[y0:y1, x0:x1] = cv2.GaussianBlur(out[y0:y1, x0:x1], (k, k), 0)
    return out


class FaceDetector(Protocol):
    def detect(self, jpeg: bytes, width: int, height: int) -> list[Region]: ...


class MockFaceDetector:
    """Finds no faces (no paid call). Use only for local development."""

    def detect(self, jpeg: bytes, width: int, height: int) -> list[Region]:
        return []


class VisionFaceDetector:
    def __init__(self):
        from google.cloud import vision
        self._vision = vision
        self._client = vision.ImageAnnotatorClient()

    def detect(self, jpeg: bytes, width: int, height: int) -> list[Region]:
        resp = self._client.face_detection(image=self._vision.Image(content=jpeg))
        if resp.error.message:
            raise RuntimeError(f"Vision API error: {resp.error.message}")
        regions = []
        for f in resp.face_annotations:
            xs = [v.x for v in f.bounding_poly.vertices]
            ys = [v.y for v in f.bounding_poly.vertices]
            regions.append((min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)))
        return regions


def blur_faces(img: np.ndarray, detector: FaceDetector) -> tuple[np.ndarray, int]:
    h, w = img.shape[:2]
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    regions = detector.detect(buf.tobytes(), w, h)
    return (blur_regions(img, regions) if regions else img), len(regions)
