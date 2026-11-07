"""pytest setup: make `app` (this folder) and `shared` (repository root) importable."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for p in (HERE, HERE.parent.parent):
    sys.path.insert(0, str(p))
