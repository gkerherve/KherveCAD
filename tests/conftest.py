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
# My Library (user_library) must never read or write the user's real
# ~/Documents/KherveCAD Library from a test
import tempfile  # noqa: E402
os.environ["KHERVECAD_USER_LIBRARY"] = tempfile.mkdtemp(
    prefix="kcad-user-library-")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

#: persisted view options that change what a fresh View3D paints or how
#: fit() frames — a platform switched on in the real app made pixel and
#: framing tests fail on that machine only, and a saved Matte style
#: flattened the shading the contrast test measures. Neutral for the
#: session, then put back exactly as they were.
_NEUTRAL_SETTINGS = ("render_stage", "render_style", "render_bg",
                     "render_projection", "render_cavity", "render_edges",
                     "render_scale_bar",
                     # the Blueprint remembers the title block's material,
                     # company and author: a test choosing Aluminium once
                     # made every real sheet after it weigh aluminium
                     "blueprint/material", "blueprint/company",
                     "blueprint/drawn", "blueprint/dir")

#: looks that default to on, held off for the session instead of removed
_NEUTRAL_OFF = ("render_stage", "render_edges", "render_scale_bar")


@pytest.fixture(autouse=True)
def _fresh_blueprint_settings():
    """The Blueprint remembers the title block's material, company and
    author as the next sheet's defaults: a test that chose Steel made the
    next test's sheet weigh steel. Each test starts without them (the
    session fixture below puts the user's own back at the end)."""
    from PyQt5.QtCore import QSettings
    settings = QSettings("Kherve", "KherveCAD")
    for key in ("blueprint/material", "blueprint/company",
                "blueprint/drawn", "blueprint/dir"):
        settings.remove(key)
    yield


@pytest.fixture(autouse=True, scope="session")
def _neutral_view_settings():
    from PyQt5.QtCore import QSettings
    settings = QSettings("Kherve", "KherveCAD")
    saved = {key: settings.value(key) for key in _NEUTRAL_SETTINGS}
    for key in _NEUTRAL_SETTINGS:
        settings.remove(key)
    # the platform and edge lines are ON by default in the app; pixel and
    # framing tests were written for a bare view, so hold them off here
    for key in _NEUTRAL_OFF:
        settings.setValue(key, False)
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
