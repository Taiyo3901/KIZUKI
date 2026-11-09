"""Stage 4b: keep people and vehicles out of the comparison.

Crowds and cars move between two shots; if their difference reached the candidate stage, each one would cost a
Gemini call and some would come back as false alarms. Cloud Vision's object localisation finds them, and the
regions are masked out of the difference map. Boxes are found on the reference and on the target; the target's
boxes are warped into the reference's pixel space with the alignment homography.
"""
import logging
from typing import Protocol

import cv2
import numpy as np

from pipeline.face_blur import Region
from pipeline.settings import SETTINGS, Settings

log = logging.getLogger("analyzer.object_mask")

# Names Cloud Vision can return for things that move. Compared case-insensitively; names it never returns are
# harmless. Override with MASK_OBJECT_NAMES (comma separated).
DEFAULT_NAMES = (
    "person,man,woman,boy,girl,clothing,footwear,hat,bag,backpack,handbag,luggage & bags,umbrella,"
    "bicycle,car,van,truck,bus,motorcycle,vehicle,land vehicle,wheel,tire"
)


def mask_names(raw: str = DEFAULT_NAMES) -> frozenset[str]:
    return frozenset(n.strip().lower() for n in raw.split(",") if n.strip())


class ObjectDetector(Protocol):
    def detect(self, jpeg: bytes, width: int, height: int) -> list[Region]: ...


class MockObjectDetector:
    """Finds nothing (no paid call). Local development only."""

    def detect(self, jpeg: bytes, width: int, height: int) -> list[Region]:
        return []


class VisionObjectDetector:
    def __init__(self, names: frozenset[str], min_score: float):
        from google.cloud import vision
        self._vision = vision
        self._client = vision.ImageAnnotatorClient()
        self._names, self._min = names, min_score

    def detect(self, jpeg: bytes, width: int, height: int) -> list[Region]:
        resp = self._client.object_localization(image=self._vision.Image(content=jpeg))
        if resp.error.message:
            raise RuntimeError(f"Vision API error: {resp.error.message}")
        regions: list[Region] = []
        for o in resp.localized_object_annotations:
            if o.name.lower() not in self._names or o.score < self._min:
                continue
            xs = [v.x for v in o.bounding_poly.normalized_vertices]
            ys = [v.y for v in o.bounding_poly.normalized_vertices]
            x0, y0, x1, y1 = min(xs) * width, min(ys) * height, max(xs) * width, max(ys) * height
            regions.append((round(x0), round(y0), round(x1 - x0), round(y1 - y0)))
        return regions


def boxes_mask(shape: tuple[int, int], regions: list[Region], pad: float) -> np.ndarray:
    """255 inside every box (each grown by `pad` of its size), 0 elsewhere. `shape` is (height, width)."""
    mask = np.zeros(shape, np.uint8)
    h, w = shape
    for x, y, bw, bh in regions:
        px, py = int(bw * pad), int(bh * pad)
        cv2.rectangle(mask, (max(0, x - px), max(0, y - py)), (min(w - 1, x + bw + px), min(h - 1, y + bh + py)), 255, -1)
    return mask


def _detect(img: np.ndarray, detector: ObjectDetector) -> list[Region]:
    h, w = img.shape[:2]
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return detector.detect(buf.tobytes(), w, h)


def build_ignore_mask(reference: np.ndarray, target: np.ndarray, homography: np.ndarray, detector: ObjectDetector,
                      s: Settings = SETTINGS) -> tuple[np.ndarray, int]:
    """Mask (reference pixel space) of everything that moves in either photo, and how many objects it holds.

    A failure of the detector must never fail the analysis: without the mask there are only more candidates."""
    rh, rw = reference.shape[:2]
    th, tw = target.shape[:2]
    try:
        ref_regions = _detect(reference, detector)
        tgt_regions = _detect(target, detector)
    except Exception:  # noqa: BLE001  (network, quota, permissions...)
        log.warning("object detection failed; comparing without a mask", exc_info=True)
        return np.zeros((rh, rw), np.uint8), 0
    ref_mask = boxes_mask((rh, rw), ref_regions, s.mask_pad)
    tgt_mask = cv2.warpPerspective(boxes_mask((th, tw), tgt_regions, s.mask_pad), homography, (rw, rh), flags=cv2.INTER_NEAREST)
    return cv2.bitwise_or(ref_mask, tgt_mask), len(ref_regions) + len(tgt_regions)
