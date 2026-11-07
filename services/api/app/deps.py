"""Shared state of the API process: the storage and the repository (swapped in tests)."""
from dataclasses import dataclass

from app.config import SETTINGS
from shared.adapters.ports import Repository, Storage


@dataclass
class State:
    storage: Storage
    repo: Repository


_state: State | None = None


def build_state() -> State:
    if SETTINGS.backend == "gcp":
        from shared.adapters.gcp import FirestoreRepository, GcsStorage
        if not SETTINGS.bucket:
            raise RuntimeError("STORAGE_BUCKET is not set")
        return State(GcsStorage(SETTINGS.bucket), FirestoreRepository(SETTINGS.gcp_project or None))
    from app.dev_seed import seed
    from app.dev_storage import DevHttpStorage
    from shared.adapters.memory import MemoryRepository
    state = State(DevHttpStorage(), MemoryRepository())
    seed(state.repo, state.storage)
    return state


def get_state() -> State:
    global _state
    if _state is None:
        _state = build_state()
    return _state


def set_state(state: State | None) -> None:
    global _state
    _state = state
