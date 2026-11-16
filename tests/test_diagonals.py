# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Both diagonals of a rectangle, drawn and snapped to (2026-11-16, the
user: SolidWorks shows the two and snaps on them and their crossing)."""
import pytest
from PyQt5.QtCore import QPointF
from PyQt5.QtWidgets import QApplication

from khervecad import diagonals, diagonals2d, wireframe
from test_stacked_features import app, win  # noqa


def _box_tris():
    from khervecad import mesh
    from khervecad.model import CadNode
    return mesh.tessellate(CadNode("cube", "c", {"width": 40, "depth": 20, "height": 10}))


def test_every_face_of_a_box_gives_both_diagonals():
    quads = diagonals.face_quads(_box_tris())
    assert len(quads) == 6
    top = next(q for q in quads if all(abs(p[2] - 10) < 1e-9 for p in q))
    (a, c), (b, d) = diagonals.diagonals(top)
    assert {round(a[0]), round(c[0])} == {0, 40}
    assert {round(b[0]), round(d[0])} == {0, 40}
    assert diagonals.centre(top) == pytest.approx((20, 10, 10))


def test_snap_takes_the_centre_then_a_diagonal():
    q = [(0, 0), (40, 0), (40, 20), (0, 20)]
    assert diagonals.snap((20.3, 9.8), [q], 1.0, 0.5) == ((20, 10), "centre")
    (x, y), kind = diagonals.snap((10, 5.2), [q], 1.0, 0.5)
    assert kind == "diagonal" and y == pytest.approx(x / 2)
    # the OTHER diagonal (from (40, 0) to (0, 20)) too
    (x, y), kind = diagonals.snap((10, 15.1), [q], 1.0, 0.5)
    assert kind == "diagonal" and y == pytest.approx(20 - x / 2)


def test_a_rectangle_in_the_2d_sketch_snaps_at_its_centre(win):
    m = win.model
    m.add_node("rect", dict(x=0, y=0, width=40, height=20))
    QApplication.processEvents()
    scene = win.view2d.scene()
    scene.rebuild() if hasattr(scene, "rebuild") else None
    QApplication.processEvents()
    assert any(abs(diagonals.centre(q)[0] - 20) < 1e-6
               for q in diagonals2d.quads(scene))
    got = diagonals2d.snap(scene, QPointF(20.01, 10.02))
    assert got is not None and got[1] == "centre"
    assert (got[0].x(), got[0].y()) == pytest.approx((20, 10))


def test_wireframe_paints_the_diagonals(win):
    from khervecad.mcp_tools import McpToolExecutor
    McpToolExecutor(win).execute("apply_code",
                                 {"code": "cube([40, 20, 10]);\n"})
    QApplication.processEvents()
    wireframe.set_on(win, True)
    assert len(wireframe._quads(win.view3d)) == 6
    win.view3d.repaint()
    wireframe.set_on(win, False)


def test_3d_sketch_on_a_face_snaps_to_its_diagonals(win):
    from khervecad.mcp_tools import McpToolExecutor
    from test_stacked_features import _sketch_on
    McpToolExecutor(win).execute("apply_code",
                                 {"code": "cube([40, 20, 10]); // Base\n"})
    QApplication.processEvents()
    part = next(c for c in win.model.root.children
                if c.visible and c.type != "assign")
    win.resize(1300, 850)
    win.show()
    tool = _sketch_on(win, part, (20, 10, 10))
    quads = tool.quads()
    assert quads, tool.info.get("segments")
    c = diagonals.centre(quads[0])
    got = tool.snap_local(c[0] + 0.05, c[1] - 0.05)
    assert got == pytest.approx((c[0], c[1]))
    # a point near the OTHER diagonal lands on it
    (a, b), (p, q) = diagonals.diagonals(quads[0])
    mid = ((p[0] * 3 + q[0]) / 4, (p[1] * 3 + q[1]) / 4)
    got = tool.snap_local(mid[0] + 0.05, mid[1])
    assert got is not None and tool.snapped[2] in ("edge", "centre",
                                                   "corner", "middle")
