"""SolidWorks' Fill Pattern (2026-11-15, the "Deform feature" video): the
ribbon button, the window, a click on the face, the 181 squares of the
video's Ø80 fan-cover face, margin / direction / seed settings, OK and
Cancel — all with real mouse events — and the MCP tool.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QToolButton

from khervecad import analysis, fill_pattern, mesh, toolbar_style
from khervecad.mcp_tools import McpToolExecutor

_APP = QApplication.instance() or QApplication([])

# the fan cover's plate: Ø90 x 3 with the Ø80 recess 1 mm deep (floor z=2)
PLATE = ("difference(){ cylinder(h=3,d=90,$fn=120); "
         "translate([0,0,2]) cylinder(h=2,d=80,$fn=120);}")


@pytest.fixture
def win():
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.resize(1500, 950)
    toolbar_style.apply(w, "SolidWorks", remember=False)
    w.show()
    McpToolExecutor(w).execute("apply_code", {"code": PLATE})
    QTest.qWait(50)
    yield w
    toolbar_style.apply(w, "KherveCAD", remember=False)
    w._dirty = False
    w.close()


def _button(win, data):
    win.ribbon.show_tab("features")
    QTest.qWait(30)
    return next(b for b in win.findChildren(QToolButton)
                if b.isVisible() and b.defaultAction() is not None
                and b.defaultAction().data() == data)


def _click_face_at(win, point):
    view = win.view3d
    eye, r, u, f = view._camera()
    x, y, _z = view._project(eye, r, u, f, point)
    from PyQt5.QtCore import QPoint
    QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier,
                     QPoint(int(x), int(y)))
    QTest.qWait(60)


def _features(win):
    return [n for n in win.model.root.walk()
            if isinstance(n.params.get(fill_pattern.KEY), dict)]


def _volume(win):
    return analysis.mass_properties(mesh.tessellate(win.model.root))[
        "volume"]


def _open_and_click(win):
    # the ribbon button sits in the Features tab's pattern panel
    QTest.mouseClick(_button(win, "fill_pattern"), Qt.LeftButton)
    QTest.qWait(50)
    assert win._fill_panel is not None and win._fill_panel.isVisible()
    _click_face_at(win, [14.0, 9.0, 2.0])


def test_the_video_face_gets_181_squares_by_mouse(win):
    """Ø80 face, loop 5, instance 5, margin 1, 2 mm squares: the 181 of
    the video, and the volume of 181 square pockets 2 deep."""
    base = _volume(win)
    _open_and_click(win)
    feats = _features(win)
    assert len(feats) == 1, "the face click made no Fill Pattern"
    assert "181" in feats[0].name
    assert win._fill_panel.count.text().startswith("181")
    assert base - _volume(win) == pytest.approx(181 * 4 * 2, rel=0.01)
    win._fill_panel.ok.click()
    QTest.qWait(30)
    assert win._fill_panel is None and len(_features(win)) == 1


def test_settings_refill_and_cancel_takes_it_away(win):
    base = _volume(win)
    n0 = len(list(win.model.root.walk()))
    _open_and_click(win)
    panel = win._fill_panel
    panel.fields["spacing"].setValue(8.0)        # a typed value
    QTest.qWait(30)
    n8 = int(panel.count.text().split()[0])
    assert 0 < n8 < 181
    panel.fields["margin"].setValue(10.0)
    QTest.qWait(30)
    assert int(panel.count.text().split()[0]) < n8
    panel.fields["margin"].setValue(1.0)
    panel.fields["layout"].setCurrentIndex(1)    # Square grid
    QTest.qWait(30)
    assert int(panel.count.text().split()[0]) > 100
    panel.cancel.click()
    QTest.qWait(30)
    assert win._fill_panel is None and not _features(win)
    assert _volume(win) == pytest.approx(base, rel=1e-6)
    assert len(list(win.model.root.walk())) == n0


def test_the_fill_is_plain_openscad_and_not_red(win):
    _open_and_click(win)
    win._fill_panel.ok.click()
    code = win.model.to_scad()
    assert "linear_extrude" in code and "polygon" in code
    from khervecad import model as M
    errors = M.validate(win.model.root)
    assert not errors, errors


def test_direction_from_a_sketch_line_in_the_tree(win):
    """A sketch line clicked in the tree is the pattern direction: on a
    square grid with pitches 5 (along) and 3 (across) a line along X and
    one along Y fill differently."""
    import math
    line = win.model.add_node("line", dict(x1=0, y1=0, x2=0, y2=10,
                                           width=0.2))
    line.name = "Direction line"
    _open_and_click(win)
    panel = win._fill_panel
    panel.fields["layout"].setCurrentIndex(1)            # Square grid
    panel.fields["loop_spacing"].setValue(3.0)
    QTest.qWait(30)
    feat = _features(win)[0]

    def xs():
        poly = next(n for n in feat.walk() if n.type == "polygon")
        return sorted({round(p[0], 3) for p in poly.params["points"]})
    along_x = xs()
    # the line (a Y line) is clicked in the tree: real selection
    win.builder.active_tree().select_nodes([line])
    QTest.qWait(30)
    assert win._fill_state["dir_node"] is line
    assert feat.params[fill_pattern.KEY]["direction"] == \
        pytest.approx([0, 1, 0], abs=1e-6)
    along_y = xs()
    assert along_x != along_y
    # reversing a symmetric grid keeps the count
    n = int(panel.count.text().split()[0])
    panel.fields["reverse"].setChecked(True)
    QTest.qWait(30)
    assert abs(int(panel.count.text().split()[0]) - n) <= 4
    panel.ok.click()


def test_mcp_fill_pattern(win):
    ex = McpToolExecutor(win)
    body = [c for c in win.model.root.children if c.visible][0]
    r = ex.execute("fill_pattern", dict(node_id=body.id, point=[14, 9, 2],
                                        normal=[0, 0, 1]))
    assert r.get("count") == 181, r
    r2 = ex.execute("fill_pattern", dict(
        node_id=r["feature_id"], action="update", layout="perforation",
        shape="circle", size=2.5))
    assert r2["count"] > 100 and "error" not in r2
    from khervecad import model as M
    assert not M.validate(win.model.root)
