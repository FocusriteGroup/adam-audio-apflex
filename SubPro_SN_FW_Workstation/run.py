"""Entry point — Sub-Pro SN/FW Workstation."""
import sys
from pathlib import Path

# Make the Audio-Precision repo root importable so we can reach
# oca/, services/, etc. without installing anything as a package.
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from app.main import SubProApp

if __name__ == '__main__':
    SubProApp().run()
