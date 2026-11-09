"""Builds the analyzer's dependencies from settings: local (in-memory, mocks) or GCP."""
from pathlib import Path

from pipeline.face_blur import MockFaceDetector, VisionFaceDetector
from pipeline.gemini_client import GeminiClient
from pipeline.judge import GeminiJudge, MockJudge
from pipeline.object_mask import DEFAULT_NAMES, MockObjectDetector, VisionObjectDetector, mask_names
from pipeline.quality import GeminiSemanticQuality, MockSemanticQuality
from pipeline.run import Deps
from pipeline.settings import SETTINGS, Settings
from shared.adapters.memory import MemoryRepository, MemoryStorage


def build_deps(s: Settings = SETTINGS) -> Deps:
    if s.backend == "gcp":
        from shared.adapters.gcp import FirestoreRepository, GcsStorage
        if not s.bucket:
            raise RuntimeError("STORAGE_BUCKET is not set")
        storage, repo = GcsStorage(s.bucket), FirestoreRepository(s.gcp_project or None)
    elif s.backend == "local":
        storage, repo = MemoryStorage(Path(s.local_data_dir)), MemoryRepository()
    else:
        raise ValueError(f"unknown BACKEND: {s.backend}")

    client = None
    if s.judge_mode == "vertex":
        if not s.gemini_model_fast:
            raise RuntimeError("GEMINI_MODEL_FAST is not set (confirm the model name in the official docs)")
        client = GeminiClient(s)
    judge = GeminiJudge(client) if client else MockJudge()
    semantic = GeminiSemanticQuality(client, s.gemini_model_fast) if client else MockSemanticQuality()
    faces = VisionFaceDetector() if s.face_mode == "vision" else MockFaceDetector()
    objects = VisionObjectDetector(mask_names(s.mask_object_names or DEFAULT_NAMES), s.object_min_score) if s.object_mode == "vision" else MockObjectDetector()
    return Deps(storage=storage, repo=repo, faces=faces, semantic=semantic, judge=judge, settings=s, objects=objects)
