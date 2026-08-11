"""Resolution uniforme des ressources en source, wheel et PyInstaller."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def resource_directory(name):
    module_root = Path(__file__).resolve().parent
    candidates = [
        module_root / name,
        Path(getattr(sys, "_MEIPASS", module_root)) / name,
        Path(sys.prefix) / "share" / "call-of-python" / name,
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return os.fspath(candidate)
    # Le mode source peut generer un fallback dans ce chemin.
    return os.fspath(candidates[0])
