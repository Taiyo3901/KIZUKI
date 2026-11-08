"""Local convenience: make the repository root importable so `shared` is found without setting PYTHONPATH.
In the Docker image PYTHONPATH is already set and this does nothing."""
import sys
from pathlib import Path

_PARENTS = Path(__file__).resolve().parents  # [app, api, services, <repository root>] in the repository; shorter in the image
if len(_PARENTS) > 3 and (_PARENTS[3] / "shared").is_dir() and str(_PARENTS[3]) not in sys.path:
    sys.path.append(str(_PARENTS[3]))
