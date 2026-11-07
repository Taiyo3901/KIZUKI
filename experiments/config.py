"""Experiment settings. Everything is overridable by environment variables."""
import os
from dataclasses import dataclass


def _f(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


@dataclass(frozen=True)
class Settings:
    # --- Gemini (Vertex AI). Model names are NOT defaulted: set them after checking the official docs.
    judge_mode: str = os.environ.get("JUDGE_MODE", "mock")  # "mock" | "vertex"
    gemini_model_fast: str = os.environ.get("GEMINI_MODEL_FAST", "")
    gemini_model_pro: str = os.environ.get("GEMINI_MODEL_PRO", "")
    gcp_project: str = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    gcp_location: str = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-northeast1")

    # --- Thresholds (CLAUDE.md section 7)
    needs_review_threshold: float = _f("NEEDS_REVIEW_THRESHOLD", 0.6)
    recheck_low: float = _f("RECHECK_LOW", 0.4)    # RECHECK_RANGE = [low, high)
    recheck_high: float = _f("RECHECK_HIGH", 0.6)
    max_edge_px: int = int(os.environ.get("MAX_UPLOAD_EDGE_PX", 2048))

    # --- Alignment / diff (tuned in phase 1)
    min_inliers: int = int(os.environ.get("ALIGN_MIN_INLIERS", 30))
    dissim_threshold: float = _f("DIFF_DISSIM_THRESHOLD", 0.55)
    min_area_ratio: float = _f("DIFF_MIN_AREA_RATIO", 0.0002)  # of image area
    max_candidates: int = int(os.environ.get("DIFF_MAX_CANDIDATES", 5))
    crop_margin: float = _f("CROP_MARGIN", 0.5)  # extra context around a candidate box
    min_crop_px: int = int(os.environ.get("MIN_CROP_PX", 320))  # crops are grown to at least this size


SETTINGS = Settings()
