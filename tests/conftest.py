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

# The tests' OWN settings file. KherveCAD keeps its options in
# QSettings("Kherve", "KherveCAD") — on macOS the user's real
# com.kherve.KherveCAD.plist — and the suite used to write there: the
# scale bar switched off for the run, every style test leaving
# "KherveCAD" as the interface style. A KherveCAD opened during a run
# came up classic, without its scale bar (the user, 2026-10-20). Every
# QSettings(organisation, application) of the run now opens an INI file
# in a temporary folder instead, so the user's settings are never read
# or written by a test.
from PyQt5 import QtCore  # noqa: E402

_REAL_QSETTINGS = QtCore.QSettings
_REAL_QSETTINGS.setPath(_REAL_QSETTINGS.IniFormat, _REAL_QSETTINGS.UserScope,
                        tempfile.mkdtemp(prefix="kcad-test-settings-"))


class _TestSettings(_REAL_QSETTINGS):
    def __init__(self, *args, **kwargs):
        if len(args) >= 2 and isinstance(args[0], str) \
                and isinstance(args[1], str):
            super().__init__(_REAL_QSETTINGS.IniFormat,
                             _REAL_QSETTINGS.UserScope, args[0], args[1],
                             *args[2:], **kwargs)
        else:
            super().__init__(*args, **kwargs)


QtCore.QSettings = _TestSettings

import pytest

# Fusion is the app's default; the tests were written for the classic
# bars. Asked through the environment, NOT the settings: those are the
# user's own, and writing "KherveCAD" there switched their app back to
# the classic look every time the suite ran
os.environ.setdefault("KHERVECAD_INTERFACE_STYLE", "KherveCAD")  # noqa: E402

#: persisted view options that change what a fresh View3D paints or how
#: fit() frames — a platform switched on in the real app made pixel and
#: framing tests fail on that machine only, and a saved Matte style
#: flattened the shading the contrast test measures. Neutral for the
#: session, then put back exactly as they were.
_NEUTRAL_SETTINGS = ("render_stage", "render_style", "render_bg",
                     "render_projection", "render_cavity", "render_edges",
                     "render_scale_bar", "render_grid", "render_axes",
                     "code_wrap",
                     # the Blueprint remembers the title block's material,
                     # company and author: a test choosing Aluminium once
                     # made every real sheet after it weigh aluminium
                     "blueprint/material", "blueprint/company",
                     "blueprint/drawn", "blueprint/dir",
                     # the developer's own chosen UI language: left as
                     # "zh"/"fr"/"es" it silently switched
                     # userguide._chapters_module()'s selection (which
                     # reads this key directly, unlike language.tr()'s
                     # calls, which need install() too) while no
                     # DictTranslator was installed, so a User Guide test
                     # compared an English search term against a Chinese
                     # manual and only passed by the accident of the Tool
                     # reference chapter staying English
                     "language",
                     # Fusion / SolidWorks toolbars and the ribbon tab
                     "interface_style", "ribbon/tab", "tree/history",
                     "browser/hidden")

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
                "blueprint/drawn", "blueprint/dir",
                # the Interface Style too, per test: the user's own
                # KherveCAD, running beside a long test run, shares these
                # settings, and switching it to Fusion mid-run opened
                # later test windows with Fusion's menus and toolbars
                "interface_style", "ribbon/tab", "tree/history",
                "sketch/inset_size", "sketch/mini2d_size"):
        settings.remove(key)
    # every tab shown in tests (users start with Variables / Code hidden)
    settings.setValue("browser/hidden", "none")
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


@pytest.fixture(autouse=True)
def _delete_asks_nothing(monkeypatch):
    """Deleting a container asks keep-or-all in a modal box, which would
    hang an offscreen test: answer 'delete everything', the old
    behaviour (tests of the question set their own answer)."""
    from khervecad import delete_ui
    monkeypatch.setattr(delete_ui, "ask_hook", lambda nodes: delete_ui.ALL)
