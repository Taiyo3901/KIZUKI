"""Stage 1: quality check. Blur / darkness by numbers; occlusion / backlight by Gemini.

A failed check stops the pipeline and the reasons are stored (CLAUDE.md section 4).
"""
from typing import Protocol

import cv2
import numpy as np

from pipeline.gemini_client import GeminiClient
from pipeline.settings import SETTINGS, Settings
from shared.schemas.models import Quality

REASON_BLUR = "ブレ"
REASON_DARK = "暗さ"
REASON_OCCLUDED = "対象が隠れている"
REASON_BACKLIT = "逆光"


def check_numeric(img: np.ndarray, s: Settings = SETTINGS) -> list[str]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    reasons = []
    if cv2.Laplacian(gray, cv2.CV_64F).var() < s.blur_min_laplacian_var:
        reasons.append(REASON_BLUR)
    if float(gray.mean()) < s.dark_min_mean:
        reasons.append(REASON_DARK)
    return reasons


class SemanticQuality(Protocol):
    def check(self, img: np.ndarray) -> list[str]: ...


class MockSemanticQuality:
    """Always passes (no paid call)."""

    def check(self, img: np.ndarray) -> list[str]:
        return []


_SCHEMA = {
    "type": "object",
    "properties": {"occluded": {"type": "boolean"}, "backlit": {"type": "boolean"}, "note": {"type": "string"}},
    "required": ["occluded", "backlit", "note"],
}
_SYSTEM = ("文化財の点検用に撮られた写真が、比較に使えるかを判定します。"
           "occluded: 撮影対象（石垣など）が人・物・手などで大きく隠れている。"
           "backlit: 強い逆光で対象が黒くつぶれている、または白飛びしている。")


class GeminiSemanticQuality:
    def __init__(self, client: GeminiClient, model: str):
        self._client, self._model = client, model

    def check(self, img: np.ndarray) -> list[str]:
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        out = self._client.generate_json(self._model, [(buf.tobytes(), "image/jpeg")], _SCHEMA, _SYSTEM)
        return ([REASON_OCCLUDED] if out["occluded"] else []) + ([REASON_BACKLIT] if out["backlit"] else [])


def run_quality(img: np.ndarray, semantic: SemanticQuality, s: Settings = SETTINGS) -> Quality:
    reasons = check_numeric(img, s)
    if not reasons:  # skip the paid call when the numbers already fail
        reasons += semantic.check(img)
    return Quality(passed=not reasons, reasons=reasons)
