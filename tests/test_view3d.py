"""Tests for 3D render styles and selection glow.

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
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad.view3d import RENDER_STYLES, View3D


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def test_every_style_paints_without_error(app):
    view = View3D()
    view.resize(200, 200)
    view.set_mesh([((0, 0, 0), (10, 0, 0), (0, 10, 0)),
                   ((0, 0, 0), (0, 10, 0), (0, 0, 10))], "test")
    view.set_highlight_mesh([((0, 0, 0), (10, 0, 0), (0, 10, 0))])
    for style in RENDER_STYLES:
        view.set_style(style)
        assert view.style == style
        view.grab()                    # exercises the paint path


def test_style_persists(app):
    view = View3D()
    view.set_style("Brushed metal")
    other = View3D()
    assert other.style == "Brushed metal"
    view.set_style("Shaded")           # restore default for other tests


def test_unknown_style_ignored(app):
    view = View3D()
    view.set_style("Shaded")
    view.set_style("Nonsense")
    assert view.style == "Shaded"
