"""Project folders, shared by every script so they work from any working directory.

Links stored in data/*.json (e.g. "assets/camera/pan.svg") are relative to ROOT.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ASSETS = ROOT / "assets"
REPORTS = ROOT / "reports"
DOCS = ROOT / "docs"
ENV_PATH = ROOT / ".env"
