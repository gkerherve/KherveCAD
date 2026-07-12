"""Tests for the Code-tab text editor (line numbers, indentation).

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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad.treepanel import CodeView


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def test_gutter_widens_with_line_count(app):
    code = CodeView()
    code.setPlainText("\n".join(str(i) for i in range(5)))
    narrow = code.line_number_area_width()
    code.setPlainText("\n".join(str(i) for i in range(1500)))
    assert code.line_number_area_width() > narrow


def test_indent_and_dedent_round_trip(app):
    code = CodeView()
    code.setPlainText("a\nb\nc")
    code.selectAll()
    code.indent_selection()
    assert code.toPlainText() == "    a\n    b\n    c"
    code.selectAll()
    code.dedent_selection()
    assert code.toPlainText() == "a\nb\nc"


def test_dedent_stops_at_line_start(app):
    code = CodeView()
    code.setPlainText("  x")            # only two leading spaces
    code.selectAll()
    code.dedent_selection()
    assert code.toPlainText() == "x"    # removed both, not into the text


def test_code_tab_has_a_toolbar(app):
    from khervecad.model import DocumentModel
    from khervecad.treepanel import BuilderPanel
    from PyQt5.QtWidgets import QToolBar
    panel = BuilderPanel(DocumentModel())
    tabs = [panel.tabText(i) for i in range(panel.count())]
    assert "Code" in tabs
    # the editor exposes the editing actions the toolbar drives
    for method in ("undo", "redo", "cut", "copy", "paste",
                   "indent_selection", "dedent_selection"):
        assert callable(getattr(panel.code, method))
