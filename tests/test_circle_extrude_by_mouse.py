"""A circle drawn in Sketch Mode, clicked (selected), the sketch left,
Extruded Boss pressed: a normal extrude of that circle in the right
place (filmed Exercise 7, 2026-11-15: it came out 0.01 mm thick,
wrapped, misplaced).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

from test_lever_by_mouse import (_at, _drag_arrow, _drag, _extruded_boss, _move,
                                 _open_top_sketch, _wait, win)  # noqa
from test_clevis_by_mouse import _circle, _tab
from khervecad import analysis, mesh
from khervecad.mcp_tools import McpToolExecutor


def _volume(win):
    return analysis.mass_properties(mesh.tessellate(win.model.root))


@pytest.mark.parametrize("base", [False, True])
def test_a_clicked_circle_extrudes_normally(win, base):
    if base:
        McpToolExecutor(win).execute(
            "apply_code", {"code": "cube([60, 40, 10]); // Plate\n"})
        QTest.qWait(100)
    _tab(win, "Sketch")
    QTest.mouseClick(win.view3d.nav_bar.buttons["fit"], Qt.LeftButton)
    QTest.qWait(50)
    _open_top_sketch(win)
    _circle(win, (30, 20), 8)
    v2 = win.view2d
    v2.set_tool("select")
    p = _at(win, 38, 20)                      # on the circle's rim
    _move(v2.viewport(), p)
    QTest.mouseClick(v2.viewport(), Qt.LeftButton, Qt.NoModifier, p)
    QTest.qWait(50)
    _extruded_boss(win)
    QTest.qWait(200)
    ext = [n for n in win.model.root.walk() if n.type == "linear_extrude"]
    assert len(ext) == 1
    _drag_arrow(win, 10.0)
    assert float(ext[0].params["height"]) == pytest.approx(10)
    size = _volume(win)["size"]
    assert size[0] == pytest.approx(60 if base else 16, abs=0.3)
    assert size[1] == pytest.approx(40 if base else 16, abs=0.3)
    assert size[2] == pytest.approx(10, abs=0.3)


def test_a_clicked_circle_on_a_face_sketch_extrudes_normally(win,
                                                            monkeypatch):
    """The same on a face sketch of a part (Sketch Mode, a face click),
    the circle clicked before leaving."""
    from khervecad import (feature_pick, normal_to, sketch_choice,
                           sketch_mode)
    monkeypatch.setattr(sketch_choice, "ask_hook", None)
    from khervecad.model import SHAPE_2D
    McpToolExecutor(win).execute(
        "apply_code", {"code": "cube([60, 40, 10]); // Plate\n"})
    QTest.qWait(100)
    _tab(win, "Sketch")
    QTest.mouseClick(win.view3d.nav_bar.buttons["fit"], Qt.LeftButton)
    QTest.qWait(50)
    win.builder.active_tree().clearSelection()
    normal_to.create(win)
    top = next(f for f in win._choice_preview["faces"]
               if f["dir"][2] > 0.99)
    feature_pick.picked(win, dict(kind="face", pos=top["pos"],
                                  dir=top["dir"], tris=[]),
                        ("part", win._feature_pick["parts"][0][0]))
    QTest.qWait(300)
    assert sketch_mode.sketching(win)
    _circle(win, (30, 20), 8)
    v2 = win.view2d
    v2.set_tool("select")
    p = _at(win, 38, 20)
    _move(v2.viewport(), p)
    QTest.mouseClick(v2.viewport(), Qt.LeftButton, Qt.NoModifier, p)
    QTest.qWait(50)
    _extruded_boss(win)
    QTest.qWait(200)
    ext = [n for n in win.model.root.walk() if n.type == "linear_extrude"]
    assert len(ext) == 1
    _drag_arrow(win, 10.0)
    size = _volume(win)["size"]
    assert size[0] == pytest.approx(60, abs=0.3)
    assert size[1] == pytest.approx(40, abs=0.3)
    assert size[2] == pytest.approx(20, abs=0.3)
