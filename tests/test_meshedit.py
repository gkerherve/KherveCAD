"""Edit Mode: polyhedra edited vertex by vertex (meshedit.py), the 3D
view's mouse and keys (meshedit_ui.py) and the MCP edit_mesh tool.

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
from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import mesh, meshedit
from khervecad.model import CadNode


def _cube():
    return meshedit.triangles_to_mesh(mesh.tessellate(CadNode(
        "cube", "c", dict(width=20, depth=20, height=20))))


def _volume(points, faces):
    tris = []
    for f in faces:
        ring = f[::-1]
        for k in range(1, len(ring) - 1):
            tris.append((points[ring[0]], points[ring[k]],
                         points[ring[k + 1]]))
    v = 0.0
    for a, b, c in tris:
        v += (a[0] * (b[1] * c[2] - b[2] * c[1])
              - a[1] * (b[0] * c[2] - b[2] * c[0])
              + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
    return v


# ------------------------------------------------------------ geometry

def test_a_cube_opens_as_eight_vertices_and_six_quads():
    points, faces = _cube()
    assert len(points) == 8 and len(faces) == 6
    assert all(len(f) == 4 for f in faces)
    assert meshedit.check(points, faces) is None
    assert _volume(points, faces) == pytest.approx(8000.0)


def test_a_cylinder_keeps_its_cap_and_merges_its_sides():
    points, faces = meshedit.triangles_to_mesh(
        mesh.tessellate(CadNode("cylinder", "c", dict()), fn=24))
    assert meshedit.check(points, faces) is None
    assert sum(1 for f in faces if len(f) == 4) == 24       # side quads
    assert sum(1 for f in faces if len(f) == 24) == 2       # n-gon caps
    assert len(points) == 48                  # the fans' centres went


def test_every_operation_keeps_the_solid_closed():
    points, faces = _cube()
    top = [i for i, p in enumerate(points) if p[2] == 20]
    p, f, sel = meshedit.subdivide(points, faces, top)
    assert meshedit.check(p, f) is None
    assert len(sel) == 9 and len(p) == 13          # 4 mids + 1 centre
    assert _volume(p, f) == pytest.approx(8000.0)
    p, f, sel, normal = meshedit.extrude(p, f, sel, 5.0)
    assert meshedit.check(p, f) is None
    assert normal == pytest.approx((0.0, 0.0, 1.0))
    assert _volume(p, f) == pytest.approx(8000.0 + 400.0 * 5.0)
    a, b = meshedit.edges(f)[0]
    p2, f2, new = meshedit.split_edge(p, f, a, b, 0.25)
    assert new == len(p) and meshedit.check(p2, f2) is None
    p3, f3, new = meshedit.poke(p, f, 0)
    assert meshedit.check(p3, f3) is None
    p4, f4, _ = meshedit.dissolve(p3, f3, [new])
    assert meshedit.check(p4, f4) is None and len(p4) == len(p)
    p5, f5, sel = meshedit.merge(points, faces, top[:2])
    assert meshedit.check(p5, f5) is None and len(p5) == 7


def test_extrude_refuses_without_a_rim():
    points, faces = _cube()
    assert meshedit.extrude(points, faces, []) is None
    assert meshedit.extrude(points, faces, range(8)) is None


def test_proportional_move_fades_and_mirror_moves_the_twin():
    points = [[-10.0, 0.0, 0.0], [10.0, 0.0, 0.0], [12.0, 0.0, 0.0],
              [40.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    out = meshedit.move(points, [1], (0, 0, 10), proportional=5.0)
    assert out[1][2] == pytest.approx(10.0)
    assert 0.0 < out[2][2] < 10.0                   # within the radius
    assert out[3][2] == 0.0                         # beyond it
    out = meshedit.move(points, [1], (3, 0, 10), mirror="x")
    assert out[0] == pytest.approx([-13.0, 0.0, 10.0])
    out = meshedit.move(points, [4], (3, 0, 10), mirror="x")
    assert out[4] == pytest.approx([0.0, 0.0, 10.0])   # stays on plane


def test_convert_keeps_an_objects_name_placement_and_colour():
    from khervecad.model import DocumentModel
    model = DocumentModel()
    comp = model.add_node("component", dict(x=50.0), name="Wedge")
    col = CadNode("color", "red", dict(color="#ff0000", alpha=1.0))
    col.add(CadNode("cube", "c", dict(width=10, depth=10, height=10)))
    comp.add(col)
    poly, why = meshedit.convert(model, comp)
    assert why is None and poly.type == "polyhedron"
    assert poly.parent.type == "color"
    assert poly.parent.params["color"] == "#ff0000"
    assert poly.parent.parent is comp and comp.params["x"] == 50.0
    assert meshedit.find_editable(comp) is poly         # opens again


def test_convert_refuses_inside_a_loop_and_an_instance():
    from khervecad.model import DocumentModel
    model = DocumentModel()
    loop = model.add_node("for_loop")
    cube = CadNode("cube", "c", dict())
    loop.add(cube)
    assert meshedit.convert(model, cube)[0] is None
    ref = model.add_node("reference", dict(ref="x"))
    assert meshedit.convert(model, ref)[0] is None


def test_an_edited_polyhedron_round_trips_through_openscad_code():
    from khervecad.model import DocumentModel
    from khervecad import scadparse
    model = DocumentModel()
    cube = model.add_node("cube")
    poly, _ = meshedit.convert(model, cube)
    p, f, sel = meshedit.subdivide(poly.params["points"],
                                   poly.params["faces"], range(4))
    model.set_param(poly, "points", p)
    model.set_param(poly, "faces", f)
    root, _warnings = scadparse.parse_scad(model.to_scad())
    back = [n for n in root.walk() if n.type == "polyhedron"][0]
    assert [[float(v) for v in r] for r in back.params["points"]] == p
    assert back.params["faces"] == f


# ---------------------------------------------------------- Edit Mode

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(1300, 860)
    win.show()
    app.processEvents()
    yield win
    session = getattr(win, "_edit_session", None)
    if session is not None:
        session.exit()
    win._dirty = False
    win.close()


def _move(view, pt, buttons=Qt.NoButton):
    QApplication.sendEvent(view, QMouseEvent(
        QEvent.MouseMove, QPointF(pt), Qt.NoButton, buttons,
        Qt.NoModifier))


def _open_cube(window):
    cube = window.model.add_node("cube")
    window.builder.tree.select_nodes([cube])
    session = window.set_edit_mode(True)
    window.view3d.fit()
    QApplication.processEvents()
    return session


def _screen(session, i):
    p = session._camera()[0](session.world[i])
    return QPoint(int(round(p[0])), int(round(p[1])))


def test_tab_opens_edit_mode_on_the_selection_and_closes_it(window):
    cube = window.model.add_node("cube")
    window.builder.tree.select_nodes([cube])
    view = window.view3d
    QTest.keyClick(view, Qt.Key_Tab)
    session = window._edit_session
    assert session is not None and view.edit_tool is session
    assert session.node.type == "polyhedron" and len(session.points) == 8
    assert window._edit_mesh_act.isChecked()
    QTest.keyClick(view, Qt.Key_Tab)
    assert window._edit_session is None and view.edit_tool is None
    assert not window._edit_mesh_act.isChecked()


def test_dragging_a_vertex_moves_it_and_keeps_the_solid(window):
    session = _open_cube(window)
    view = window.view3d
    _proj, _front, vis = session._screen()
    i = sorted(vis)[0]
    start = _screen(session, i)
    before = list(session.node.params["points"][i])
    QTest.mousePress(view, Qt.LeftButton, Qt.NoModifier, start)
    for k in range(1, 6):
        _move(view, start + QPoint(0, -8 * k), Qt.LeftButton)
    QTest.mouseRelease(view, Qt.LeftButton, Qt.NoModifier,
                       start + QPoint(0, -40))
    after = session.node.params["points"][i]
    assert after != before
    assert after[2] > before[2]                     # dragged up = +z
    assert session.selection == {i}
    assert meshedit.check(session.node.params["points"],
                          session.node.params["faces"]) is None


def test_grab_then_escape_puts_it_back(window):
    session = _open_cube(window)
    view = window.view3d
    before = [list(p) for p in session.node.params["points"]]
    QTest.keyClick(view, Qt.Key_A)
    centre = view.rect().center()
    _move(view, centre)
    QTest.keyClick(view, Qt.Key_G)
    _move(view, centre + QPoint(30, 0))
    QTest.keyClick(view, Qt.Key_Z)                  # along Z only
    _move(view, centre + QPoint(30, -30))
    session._commit_now()
    moved = session.node.params["points"]
    assert all(m[0] == b[0] and m[1] == b[1] for m, b in zip(moved, before))
    assert moved[0][2] != before[0][2]
    QTest.keyClick(view, Qt.Key_Escape)
    assert session.node.params["points"] == before
    assert window._edit_session is session          # Esc cancelled only


def test_ctrl_click_on_an_edge_adds_a_vertex(window):
    session = _open_cube(window)
    view = window.view3d
    proj, front, _vis = session._screen()
    face = session.faces[front.index(True)]
    a, b = face[0], face[1]
    pa, pb = _screen(session, a), _screen(session, b)
    QTest.mouseClick(view, Qt.LeftButton, Qt.ControlModifier,
                     (pa + pb) / 2)
    points = session.node.params["points"]
    assert len(points) == 9 and session.selection == {8}
    assert meshedit.check(points, session.node.params["faces"]) is None


def test_extrude_follows_the_mouse_along_the_normal(window):
    session = _open_cube(window)
    view = window.view3d
    top = max(range(len(session.faces)), key=lambda f: meshedit.face_centre(
        session.world, session.faces[f])[2])
    c = session._camera()[0](meshedit.face_centre(session.world,
                                                  session.faces[top]))
    at = QPoint(int(c[0]), int(c[1]))
    QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, at)
    assert session.selection == set(session.faces[top])
    _move(view, at)
    QTest.keyClick(view, Qt.Key_E)
    _move(view, at + QPoint(0, -30))
    QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, at + QPoint(0, -30))
    pts = session.node.params["points"]
    assert len(pts) == 12 and len(session.node.params["faces"]) == 10
    assert max(p[2] for p in pts) > 20.0
    assert meshedit.check(pts, session.node.params["faces"]) is None


def _step(model):
    """Take the pending undo snapshot as a step of its own."""
    merge, model.UNDO_MERGE_S = model.UNDO_MERGE_S, -1.0
    try:
        model._capture_timer.stop()
        model._capture()
    finally:
        model.UNDO_MERGE_S = merge


def test_undo_gives_the_cube_back_and_closes_edit_mode(window):
    model = window.model
    cube = model.add_node("cube")
    _step(model)
    window.builder.tree.select_nodes([cube])
    session = window.set_edit_mode(True)
    _step(model)
    assert session is not None
    session.selection = {0}
    session._write(meshedit.move(session.points, [0], (0, 0, 3)), now=True)
    _step(model)
    model.undo_stack.undo()                 # the move
    assert window._edit_session is session
    assert session.node.type == "polyhedron"
    assert session.points[0][2] == pytest.approx(0.0)
    model.undo_stack.undo()                 # the conversion
    assert any(n.type == "cube" for n in model.root.walk())
    assert window._edit_session is None


# ---------------------------------------------------------------- MCP

def test_mcp_edit_mesh_open_move_and_extrude(window):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(window)
    cube = window.model.add_node("cube")
    out = ex.execute("edit_mesh", {"node_id": cube.id, "operation": "open"})
    assert "error" not in out, out
    assert out["converted"] and out["vertex_count"] == 8
    assert len(out["points"]) == 8 and len(out["faces"]) == 6
    poly = out["node_id"]
    out = ex.execute("edit_mesh", {
        "node_id": poly, "operation": "move",
        "within": {"min": [-1, -1, 19], "max": [21, 21, 21]},
        "delta": [0, 0, 5]})
    assert "error" not in out, out
    assert max(p[2] for p in out["selected_points"]) == pytest.approx(25.0)
    out = ex.execute("edit_mesh", {
        "node_id": poly, "operation": "extrude",
        "within": {"min": [-1, -1, 24], "max": [21, 21, 26]},
        "distance": 10})
    assert "error" not in out, out
    assert out["vertex_count"] == 12
    assert all(p[2] == pytest.approx(35.0) for p in out["selected_points"])
    bad = ex.execute("edit_mesh", {"node_id": poly, "operation": "merge",
                                   "vertices": [0, 6]})
    assert "error" in bad or meshedit.check(
        window.model.find(poly).params["points"],
        window.model.find(poly).params["faces"]) is None
    info = ex.execute("get_document_info", {})
    assert "edit_mode" in info
