#!/usr/bin/env python3
"""Launcher. Run this file, or `python -m gcats` from the same folder."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from gcats.app import run

if __name__ == "__main__":
    sys.exit(run())
