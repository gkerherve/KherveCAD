"""Shared test setup: offscreen Qt, no background OpenSCAD renders.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# MainWindow fixtures must not spawn debounced OpenSCAD subprocesses:
# their finished-callbacks would fire inside later tests' event loops.
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
