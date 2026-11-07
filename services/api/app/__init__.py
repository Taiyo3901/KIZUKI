"""Local convenience: make the repository root importable so `shared` is found without setting PYTHONPATH.
In the Docker image PYTHONPATH is already set and this does nothing."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]  # services/api/app/__init__.py -> repository root
if (_ROOT / "shared").is_dir() and str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))
