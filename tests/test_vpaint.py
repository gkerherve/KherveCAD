"""vpaint.py / paint_ui.py: hand painting — dabs and lines over a part's
own colour, the code round trip, the drag brush and paint_stroke.

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

from khervecad import mesh, scadparse
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _doc(strokes):
    doc = DocumentModel()
    col = doc.add_node("color", dict(color="#00ff00"))
    doc.add_node("sphere", dict(radius=20.0), parent=col)
    node = doc.wrap_nodes([col], "vertex_paint")
    node.params["strokes"] = strokes
    return doc, node


def _colour_near(doc, point):
    best = None
    for tri, c in mesh.tessellate_colored(doc.root):
        centre = [sum(v[k] for v in tri) / 3 for k in range(3)]
        d = sum((centre[k] - point[k]) ** 2 for k in range(3))
        if best is None or d < best[0]:
            best = (d, c[0])
    return best[1]


def test_a_dab_paints_round_its_centre_only(app):
    doc, node = _doc([[0, 0, 20, 6, 255, 0, 0, 1, 1]])
    assert node.id not in validate(doc.root)
    assert _colour_near(doc, [0, 0, 20]) == "#ff0000"
    assert _colour_near(doc, [0, 0, -20]) == "#00ff00"


def test_later_strokes_paint_over_and_lines_run_end_to_end(app):
    doc, _node = _doc([[0, 0, 20, 6, 255, 0, 0, 1, 1],
                       [0, 0, 20, 3, 0, 0, 255, 1, 1],
                       [-20, 0, 0, 7, 255, 255, 0, 1, 1, 0, -20, 0]])
    assert _colour_near(doc, [0, 0, 20]) == "#0000ff"
    assert _colour_near(doc, [-14, -14, 0]) == "#ffff00"
    assert _colour_near(doc, [14, 14, 0]) == "#00ff00"


def test_strength_mixes_and_the_code_round_trips(app):
    doc, node = _doc([[0, 0, 20, 6, 255, 0, 0, 0.5, 1]])
    c = _colour_near(doc, [0, 0, 20])
    assert c == "#808000"
    root, warnings = scadparse.parse_scad(doc.to_scad())
    assert not warnings
    back = next(n for n in root.walk() if n.type == "vertex_paint")
    assert back.params["strokes"] == [[0, 0, 20, 6, 255, 0, 0, 0.5, 1]]
    node.params["strokes"] = [[1, 2, 3]]
    assert "stroke 0" in validate(doc.root)[node.id]


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    return win


def test_a_drag_paints_and_paint_stroke_maps_world_points(window):
    from PyQt5.QtCore import QEvent, QPoint, Qt
    from PyQt5.QtGui import QMouseEvent
    from khervecad import paint_ui
    from khervecad.mcp_tools import McpToolExecutor
    doc = window.model
    move = doc.add_node("translate", dict(x=100.0))
    ball = doc.add_node("sphere", dict(radius=20.0), parent=move)
    node = doc.wrap_nodes([ball], "vertex_paint")
    view = window.view3d
    view.yaw, view.pitch, view.distance = 0.0, 89.0, 150.0
    view.target = [100.0, 0.0, 0.0]
    view.projection = "Orthographic"
    panel = paint_ui.start(window, node)
    assert view.edit_tool is panel.tool
    eye, right, up, fwd = view._camera()
    a = view._project(eye, right, up, fwd, [95.0, 0.0, 20.0])
    b = view._project(eye, right, up, fwd, [105.0, 0.0, 20.0])
    view.mousePressEvent(QMouseEvent(
        QEvent.MouseButtonPress, QPoint(int(a[0]), int(a[1])),
        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    for t in range(1, 11):
        p = QPoint(int(a[0] + (b[0] - a[0]) * t / 10),
                   int(a[1] + (b[1] - a[1]) * t / 10))
        view.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, p, Qt.NoButton,
                                        Qt.LeftButton, Qt.NoModifier))
    view.mouseReleaseEvent(QMouseEvent(
        QEvent.MouseButtonRelease, QPoint(int(b[0]), int(b[1])),
        Qt.LeftButton, Qt.NoButton, Qt.NoModifier))
    rows = node.params["strokes"]
    assert len(rows) >= 3
    assert min(r[0] for r in rows) < -3 and max(r[0] for r in rows) > 3
    panel.close()
    assert view.edit_tool is None
    ex = McpToolExecutor(window)
    out = ex.execute("paint_stroke", {
        "node_id": node.id, "clear": True,
        "strokes": [{"at": [100, 0, 20], "radius": 5, "color": "white"},
                    {"at": [80, 0, 0], "to": [120, 0, 0], "radius": 2,
                     "color": "#000000"}]})
    assert "error" not in out, out
    assert node.params["strokes"][0][:3] == pytest.approx([0, 0, 20])
    assert len(node.params["strokes"][1]) == 12
    assert "error" in ex.execute("paint_stroke", {
        "node_id": node.id, "at": [0, 0, 0], "color": "notacolour"})
