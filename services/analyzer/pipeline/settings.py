"""Analyzer settings, all overridable by environment variables (CLAUDE.md section 7)."""
import os
from dataclasses import dataclass


def _f(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def _i(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


@dataclass(frozen=True)
class Settings:
    # --- backends: "mock" avoids all paid calls / "local" avoids GCP storage + DB
    judge_mode: str = os.environ.get("JUDGE_MODE", "mock")        # mock | vertex
    face_mode: str = os.environ.get("FACE_MODE", "mock")          # mock | vision
    object_mode: str = os.environ.get("OBJECT_MODE", "mock")      # mock | vision (people / vehicles left out of the diff)
    backend: str = os.environ.get("BACKEND", "local")             # local | gcp
    bucket: str = os.environ.get("STORAGE_BUCKET", "")
    local_data_dir: str = os.environ.get("LOCAL_DATA_DIR", ".local_data")

    # --- Gemini via Vertex AI (no API key). Model names are NOT defaulted; set them from the official docs.
    gemini_model_fast: str = os.environ.get("GEMINI_MODEL_FAST", "")
    gemini_model_pro: str = os.environ.get("GEMINI_MODEL_PRO", "")
    gcp_project: str = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    gcp_location: str = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")

    # --- decision thresholds
    needs_review_threshold: float = _f("NEEDS_REVIEW_THRESHOLD", 0.6)
    recheck_low: float = _f("RECHECK_LOW", 0.4)
    recheck_high: float = _f("RECHECK_HIGH", 0.6)
    max_edge_px: int = _i("MAX_UPLOAD_EDGE_PX", 2048)

    # --- quality check (stage 1); values are first guesses, to be tuned on real photos
    blur_min_laplacian_var: float = _f("BLUR_MIN_LAPLACIAN_VAR", 40.0)
    dark_min_mean: float = _f("DARK_MIN_MEAN", 45.0)

    # --- alignment / candidates (stages 4-5)
    min_inliers: int = _i("ALIGN_MIN_INLIERS", 30)
    dissim_threshold: float = _f("DIFF_DISSIM_THRESHOLD", 0.55)
    min_area_ratio: float = _f("DIFF_MIN_AREA_RATIO", 0.0002)
    max_candidates: int = _i("DIFF_MAX_CANDIDATES", 5)
    mask_object_names: str = os.environ.get("MASK_OBJECT_NAMES", "")   # "" = the default list in object_mask.py
    object_min_score: float = _f("OBJECT_MIN_SCORE", 0.5)
    mask_pad: float = _f("MASK_PAD", 0.1)                         # grow each masked box by this share of its size
    crop_margin: float = _f("CROP_MARGIN", 0.5)
    min_crop_px: int = _i("MIN_CROP_PX", 320)


SETTINGS = Settings()
