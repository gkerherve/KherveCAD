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

import pytest  # noqa: E402

#: persisted view options that change what a fresh View3D paints or how
#: fit() frames — a platform switched on in the real app made pixel and
#: framing tests fail on that machine only, and a saved Matte style
#: flattened the shading the contrast test measures. Neutral for the
#: session, then put back exactly as they were.
_NEUTRAL_SETTINGS = ("render_stage", "render_style", "render_bg",
                     "render_projection", "render_cavity", "render_edges")


@pytest.fixture(autouse=True, scope="session")
def _neutral_view_settings():
    from PyQt5.QtCore import QSettings
    settings = QSettings("Kherve", "KherveCAD")
    saved = {key: settings.value(key) for key in _NEUTRAL_SETTINGS}
    for key in _NEUTRAL_SETTINGS:
        settings.remove(key)
    settings.sync()
    del settings
    yield
    # a fresh object: the one above would be gone if the module that
    # created the QApplication has been torn down by now
    settings = QSettings("Kherve", "KherveCAD")
    for key, value in saved.items():
        if value is None:
            settings.remove(key)
        else:
            settings.setValue(key, value)
