"""Stage 6: ask Gemini (Vertex AI) what changed inside each candidate region.

JUDGE_MODE=mock avoids all API calls (no cost) and returns a deterministic dummy answer.
"""
import json
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

from config import SETTINGS, Settings
from diff import Candidate

# Template for stone walls (CLAUDE.md section 2: template = observation items + prompt instruction).
STONE_WALL_TEMPLATE = {
    "name": "石垣",
    "observationItems": ["緩み", "割れ", "表面劣化", "孕み出し", "前倒れ", "崩れ", "樹木"],
    "promptInstruction": (
        "あなたは城の石垣を点検する専門家の補助をしています。"
        "同じ場所を撮った『前（基準写真）』と『後（投稿写真）』の切り抜きを比べ、"
        "石垣の状態が悪くなる方向の変化だけを報告してください。"
        "光の当たり方、影、天候、植物の季節による色の違いは『変化』に含めないでください。"
        "人や物が一時的に写り込んだだけのものも変化ではありません。"
        "変化が見つからなければ noChange を true にし、changes は空にしてください。"
    ),
}


def response_schema(observation_items: list[str]) -> dict:
    """JSON schema for structured output. `category` is limited to the template's items."""
    return {
        "type": "object",
        "properties": {
            "changes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "enum": observation_items},
                        "box_2d": {"type": "array", "items": {"type": "integer"},
                                   "minItems": 4, "maxItems": 4},
                        "confidence": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["category", "box_2d", "confidence", "reason"],
                },
            },
            "lightingDifference": {"type": "string"},
            "noChange": {"type": "boolean"},
        },
        "required": ["changes", "lightingDifference", "noChange"],
    }


@dataclass
class Judgement:
    changes: list[dict] = field(default_factory=list)  # box in reference pixel coords {x,y,width,height}
    lighting_difference: str = ""
    no_change: bool = True
    model: str = ""
    api_calls: int = 0

    @property
    def max_confidence(self) -> float:
        return max((c["confidence"] for c in self.changes), default=0.0)


def crop_with_margin(img: np.ndarray, c: Candidate, margin: float, min_px: int = 0) -> tuple[np.ndarray, tuple[int, int]]:
    """Crop around a candidate with a margin, grown to at least min_px per side (needs context to judge)."""
    h, w = img.shape[:2]
    mx, my = int(c.width * margin), int(c.height * margin)
    x0, y0 = c.x - mx, c.y - my
    x1, y1 = c.x + c.width + mx, c.y + c.height + my
    if x1 - x0 < min_px:
        cx = (x0 + x1) // 2
        x0, x1 = cx - min_px // 2, cx + min_px // 2
    if y1 - y0 < min_px:
        cy = (y0 + y1) // 2
        y0, y1 = cy - min_px // 2, cy + min_px // 2
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    return img[y0:y1, x0:x1], (x0, y0)


def gemini_box_to_pixels(box_2d: list[int], crop_origin: tuple[int, int], crop_size: tuple[int, int]) -> dict:
    """Gemini box_2d = [ymin, xmin, ymax, xmax] on a 0-1000 scale relative to the image sent.
    Convert to {x,y,width,height} in reference pixel coordinates (CLAUDE.md section 7)."""
    ymin, xmin, ymax, xmax = box_2d
    cw, ch = crop_size
    x0 = crop_origin[0] + round(xmin / 1000 * cw)
    y0 = crop_origin[1] + round(ymin / 1000 * ch)
    x1 = crop_origin[0] + round(xmax / 1000 * cw)
    y1 = crop_origin[1] + round(ymax / 1000 * ch)
    return {"x": x0, "y": y0, "width": max(0, x1 - x0), "height": max(0, y1 - y0)}


def _jpeg(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    assert ok
    return buf.tobytes()


class MockJudge:
    """Plumbing check only: reports every candidate as a change (confidence 0.7, first observation item).
    It cannot tell shadows from cracks, so its accuracy numbers mean nothing."""

    def judge(self, ref_crop, tgt_crop, origin, cand: Candidate, template: dict, model: str) -> dict:
        changes = [{"category": template["observationItems"][0], "box_2d": [100, 100, 900, 900],
                    "confidence": 0.7, "reason": "(mock) 候補をそのまま変化として返す"}]
        return {"changes": changes, "lightingDifference": "(mock)", "noChange": False}


class VertexJudge:
    def __init__(self, s: Settings):
        from google import genai
        from google.genai import types
        self._types = types
        if not s.gcp_project:
            raise RuntimeError("GOOGLE_CLOUD_PROJECT is not set")
        # Auth = application default credentials (gcloud auth application-default login). No API key.
        self._client = genai.Client(vertexai=True, project=s.gcp_project, location=s.gcp_location)

    def judge(self, ref_crop, tgt_crop, origin, cand: Candidate, template: dict, model: str) -> dict:
        t = self._types
        contents = [
            "1枚目が前（基準写真）、2枚目が後（投稿写真）です。",
            t.Part.from_bytes(data=_jpeg(ref_crop), mime_type="image/jpeg"),
            t.Part.from_bytes(data=_jpeg(tgt_crop), mime_type="image/jpeg"),
            "観察項目: " + "、".join(template["observationItems"]) +
            "\nbox_2d は 2枚目の画像に対する [ymin, xmin, ymax, xmax]（0〜1000）で返してください。",
        ]
        config = t.GenerateContentConfig(
            system_instruction=template["promptInstruction"],
            response_mime_type="application/json",
            response_json_schema=response_schema(template["observationItems"]),
            temperature=0.0,
        )
        from google.genai import errors
        delay = 10.0
        for attempt in range(7):  # rate limit (429) / transient server errors: wait and retry
            try:
                resp = self._client.models.generate_content(model=model, contents=contents, config=config)
                return json.loads(resp.text)
            except (errors.ClientError, errors.ServerError) as e:
                if getattr(e, "code", 0) not in (429, 500, 503) or attempt == 6:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 120)


def make_judge(s: Settings = SETTINGS):
    if s.judge_mode == "mock":
        return MockJudge()
    if s.judge_mode == "vertex":
        if not s.gemini_model_fast:
            raise RuntimeError("GEMINI_MODEL_FAST is not set (confirm the model name in the official docs)")
        return VertexJudge(s)
    raise ValueError(f"unknown JUDGE_MODE: {s.judge_mode}")


def judge_candidates(reference: np.ndarray, aligned: np.ndarray, cands: list[Candidate],
                     template: dict = STONE_WALL_TEMPLATE, s: Settings = SETTINGS, judge=None) -> Judgement:
    judge = judge or make_judge(s)
    result = Judgement(model=s.gemini_model_fast or "mock")
    lighting: list[str] = []
    for cand in cands:
        ref_crop, origin = crop_with_margin(reference, cand, s.crop_margin, s.min_crop_px)
        tgt_crop, _ = crop_with_margin(aligned, cand, s.crop_margin, s.min_crop_px)
        size = (tgt_crop.shape[1], tgt_crop.shape[0])

        out = judge.judge(ref_crop, tgt_crop, origin, cand, template, s.gemini_model_fast)
        result.api_calls += 1
        top = max((c["confidence"] for c in out["changes"]), default=0.0)
        # Ambiguous confidence -> re-judge once with the Pro model (only if configured).
        if s.recheck_low <= top < s.recheck_high and s.gemini_model_pro and s.judge_mode != "mock":
            out = judge.judge(ref_crop, tgt_crop, origin, cand, template, s.gemini_model_pro)
            result.api_calls += 1
            result.model = f"{s.gemini_model_fast}->{s.gemini_model_pro}"

        lighting.append(out.get("lightingDifference", ""))
        for ch in out["changes"]:
            if ch["category"] not in template["observationItems"]:
                continue  # schema should prevent this; guard anyway
            result.changes.append({
                "category": ch["category"],
                "box": gemini_box_to_pixels(ch["box_2d"], origin, size),
                "confidence": float(ch["confidence"]),
                "reason": ch["reason"],
            })
    result.lighting_difference = " / ".join(x for x in lighting if x)
    result.no_change = not result.changes
    return result
