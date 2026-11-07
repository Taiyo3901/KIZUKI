"""Stage 6: ask Gemini what changed inside each candidate region (structured JSON output).

Ambiguous confidence (RECHECK range) is re-judged once with the Pro model.
"""
from dataclasses import dataclass, field
from typing import Protocol

import cv2
import numpy as np

from pipeline.candidates import Candidate
from pipeline.gemini_client import GeminiClient
from pipeline.settings import SETTINGS, Settings
from shared.schemas.models import Box, Change, Template


def response_schema(observation_items: list[str]) -> dict:
    """`category` is limited to the template's items with an enum; no free-text parsing."""
    return {
        "type": "object",
        "properties": {
            "changes": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": observation_items},
                    "box_2d": {"type": "array", "items": {"type": "integer"}, "minItems": 4, "maxItems": 4},
                    "confidence": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["category", "box_2d", "confidence", "reason"]}},
            "lightingDifference": {"type": "string"},
            "noChange": {"type": "boolean"},
        },
        "required": ["changes", "lightingDifference", "noChange"],
    }


@dataclass
class Judgement:
    changes: list[Change] = field(default_factory=list)
    lighting_difference: str = ""
    model: str = ""
    api_calls: int = 0

    @property
    def max_confidence(self) -> float:
        return max((c.confidence for c in self.changes), default=0.0)


def crop_with_margin(img: np.ndarray, c: Candidate, margin: float, min_px: int = 0) -> tuple[np.ndarray, tuple[int, int]]:
    """Crop around a candidate with a margin, grown to at least min_px per side (Gemini needs context)."""
    h, w = img.shape[:2]
    mx, my = int(c.width * margin), int(c.height * margin)
    x0, y0, x1, y1 = c.x - mx, c.y - my, c.x + c.width + mx, c.y + c.height + my
    if x1 - x0 < min_px:
        cx = (x0 + x1) // 2
        x0, x1 = cx - min_px // 2, cx + min_px // 2
    if y1 - y0 < min_px:
        cy = (y0 + y1) // 2
        y0, y1 = cy - min_px // 2, cy + min_px // 2
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    return img[y0:y1, x0:x1], (x0, y0)


def gemini_box_to_pixels(box_2d: list[int], origin: tuple[int, int], size: tuple[int, int]) -> Box:
    """Gemini box_2d = [ymin, xmin, ymax, xmax] on a 0-1000 scale of the image sent.
    Convert to pixels in the (aligned) reference photo."""
    ymin, xmin, ymax, xmax = box_2d
    cw, ch = size
    x0, y0 = origin[0] + round(xmin / 1000 * cw), origin[1] + round(ymin / 1000 * ch)
    x1, y1 = origin[0] + round(xmax / 1000 * cw), origin[1] + round(ymax / 1000 * ch)
    return Box(x=x0, y=y0, width=max(0, x1 - x0), height=max(0, y1 - y0))


def _jpeg(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return buf.tobytes()


class Judge(Protocol):
    def judge(self, ref_crop: np.ndarray, tgt_crop: np.ndarray, cand: Candidate, template: Template, model: str) -> dict: ...


class MockJudge:
    """Plumbing only: reports every candidate as a change (confidence 0.7). It cannot tell shadows from cracks."""

    def judge(self, ref_crop, tgt_crop, cand, template, model):
        return {"changes": [{"category": template.observationItems[0], "box_2d": [100, 100, 900, 900],
                             "confidence": 0.7, "reason": "(mock) 候補をそのまま変化として返す"}],
                "lightingDifference": "(mock)", "noChange": False}


class GeminiJudge:
    def __init__(self, client: GeminiClient):
        self._client = client

    def judge(self, ref_crop, tgt_crop, cand, template, model):
        parts = ["1枚目が前（基準写真）、2枚目が後（投稿写真）です。",
                 (_jpeg(ref_crop), "image/jpeg"), (_jpeg(tgt_crop), "image/jpeg"),
                 "観察項目: " + "、".join(template.observationItems) +
                 "\nbox_2d は 2枚目の画像に対する [ymin, xmin, ymax, xmax]（0〜1000）で返してください。"]
        return self._client.generate_json(model, parts, response_schema(template.observationItems),
                                          template.promptInstruction)


def judge_candidates(reference: np.ndarray, aligned: np.ndarray, cands: list[Candidate], template: Template,
                     judge: Judge, s: Settings = SETTINGS) -> Judgement:
    result = Judgement(model=s.gemini_model_fast or "mock")
    lighting: list[str] = []
    for cand in cands:
        ref_crop, origin = crop_with_margin(reference, cand, s.crop_margin, s.min_crop_px)
        tgt_crop, _ = crop_with_margin(aligned, cand, s.crop_margin, s.min_crop_px)
        size = (tgt_crop.shape[1], tgt_crop.shape[0])

        out = judge.judge(ref_crop, tgt_crop, cand, template, s.gemini_model_fast)
        result.api_calls += 1
        top = max((c["confidence"] for c in out["changes"]), default=0.0)
        if s.recheck_low <= top < s.recheck_high and s.gemini_model_pro and s.judge_mode != "mock":
            out = judge.judge(ref_crop, tgt_crop, cand, template, s.gemini_model_pro)
            result.api_calls += 1
            result.model = f"{s.gemini_model_fast}->{s.gemini_model_pro}"

        lighting.append(out.get("lightingDifference", ""))
        for ch in out["changes"]:
            if ch["category"] not in template.observationItems:
                continue  # the schema enum should prevent this; guard anyway
            result.changes.append(Change(
                category=ch["category"], box=gemini_box_to_pixels(ch["box_2d"], origin, size),
                confidence=min(1.0, max(0.0, float(ch["confidence"]))), reason=ch["reason"]))
    result.lighting_difference = " / ".join(x for x in lighting if x)
    return result
