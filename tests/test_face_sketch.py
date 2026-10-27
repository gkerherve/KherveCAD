"""Sketch on any face: the face Group's frame, the turn, drawing inside it,
leaving.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import face_sketch, mesh, sketch_mode, toolbar_style

_APP = QApplication.instance() or QApplication([])


@pytest.mark.parametrize("normal", [(0, 0, 1), (1, 0, 0), (0, -1, 0),
                                    (1, 1, 1), (0.3, -0.5, 0.8)])
def test_the_frame_lies_on_the_face(normal):
    right, up, n = face_sketch.frame_for(normal)
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))
    assert dot(right, n) == pytest.approx(0, abs=1e-9)
    assert dot(up, n) == pytest.approx(0, abs=1e-9)
    assert dot(right, up) == pytest.approx(0, abs=1e-9)
    # the Group turned by euler_for maps its +Z onto the normal
    from khervecad.model import DocumentModel
    g = DocumentModel().add_node("union", {})
    rx, ry, rz = face_sketch.euler_for(normal)
    g.params.update(rx=rx, ry=ry, rz=rz)
    z = face_sketch._normal_of(g)
    nn = [c / math.sqrt(sum(v * v for v in normal)) for c in normal]
    assert z == pytest.approx(nn, abs=1e-4)


@pytest.fixture
def win():
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.resize(1200, 800)
    toolbar_style.apply(w, "SolidWorks", remember=False)
    w.show()
    yield w
    toolbar_style.apply(w, "KherveCAD", remember=False)
    w._dirty = False
    w.close()


def test_sketch_on_a_slanted_face_and_extrude_out_of_it(win):
    m = win.model
    m.add_node("cube", dict(width=40, depth=40, height=20))
    normal = (1.0, 0.0, 1.0)                  # a 45° face, say
    group = face_sketch.make(win, m.root.children[0], [30, 20, 15],
                             normal)
    for _ in range(4):
        _APP.processEvents()
    assert sketch_mode.sketching(win)
    assert win._face_sketch is group
    scene = win.view2d.scene()
    assert scene.scope_root() is group        # drawing inside it
    # the sketch's 0, 0 is the part origin on the face, not the click
    cx, cy = face_sketch.to_local(group, [30, 20, 15])
    rect = scene._create("rect", dict(x=cx - 5, y=cy - 5, width=10,
                                      height=10))
    assert rect.parent is group
    # the rectangle lies on the face, round the clicked point
    pts = [p for t in mesh.tessellate(group) for p in t]
    centre = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
    assert centre == pytest.approx([30, 20, 15], abs=1e-6)
    n = [1 / math.sqrt(2), 0, 1 / math.sqrt(2)]
    for p in pts:                             # every point in the plane
        d = sum((p[i] - [30, 20, 15][i]) * n[i] for i in range(3))
        assert abs(d) < 1e-6
    sketch_mode.finish(win)
    for _ in range(4):
        _APP.processEvents()
    assert win._face_sketch is None and group.parent is m.root
    assert scene.scope_root() is m.root
    # Edit Sketch on the shape opens the same face again
    from khervecad import normal_to
    win.builder.tree.select_nodes([rect])
    normal_to.edit(win)
    for _ in range(4):
        _APP.processEvents()
    assert win._face_sketch is group


def test_an_empty_face_sketch_goes_on_exit(win):
    m = win.model
    m.add_node("cube", {})
    group = face_sketch.make(win, m.root.children[0], [10, 10, 20],
                             (0, 0, 1))
    for _ in range(3):
        _APP.processEvents()
    sketch_mode.finish(win)
    for _ in range(3):
        _APP.processEvents()
    assert group.parent is None


def test_sketch_mode_with_a_part_selected_asks_for_its_face(win):
    from khervecad import normal_to
    m = win.model
    cube = m.add_node("cube", dict(width=10, depth=10, height=10))
    other = m.add_node("cube", dict(x=40))
    win.builder.tree.select_nodes([cube])
    sketch_mode.create_action(win).trigger()
    view = win.view3d
    assert view._pick_cb is not None
    assert [n for n, _t in view._pick_groups] == [cube]   # only its faces
    view._pick_cb(dict(kind="face", pos=[5, 5, 10], dir=[0, 0, 1]), cube)
    for _ in range(3):
        _APP.processEvents()
    assert sketch_mode.sketching(win) and win._face_sketch is not None
    act = sketch_mode.create_action(win)
    assert act.text().replace("\n", " ") == "Exit Sketch Mode"
    act.trigger()                                 # the same button exits
    for _ in range(3):
        _APP.processEvents()
    assert not sketch_mode.sketching(win)
    assert act.text() == "Sketch Mode"
    del other, normal_to


def test_a_face_sketch_starts_at_the_part_origin(win):
    """A sketch on a face takes the part's origin (seen on the face) as
    its 0, 0, wherever the face was clicked, so its Position is real."""
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code":
                              "translate([-49, -21, 0]) cube([98, 42, 20]);"})
    _APP.processEvents()
    part = win.model.root.children[-1]
    group = face_sketch.make(win, part, (28.0, 3.0, 20.0), (0, 0, 1))
    assert [group.params[k] for k in ("x", "y", "z")] == [0, 0, 20]
    win.model.remove_node(group)


def test_an_old_face_sketch_is_rebased_without_moving(win):
    """A sketch made at the click point moves onto the origin; its
    shapes and fixed points keep their place in the part."""
    m = win.model
    g = m.add_node("union", dict(x=28.0, y=0.0, z=20.0))
    g.params[face_sketch.KEY] = True
    ext = m.add_node("linear_extrude", dict(height=5), parent=g)
    c = m.add_node("circle", dict(x=-3.0, y=1.0, radius=6), parent=ext)
    ext.params["constraints"] = [{"kind": "fix", "refs": ["0.c"],
                                  "at": [-3.0, 1.0]}]
    before = face_sketch.to_world(g, -3.0, 1.0)
    assert face_sketch.rebase(g)
    assert [g.params[k] for k in ("x", "y", "z")] == [0, 0, 20]
    assert (c.params["x"], c.params["y"]) == (25.0, 1.0)
    assert ext.params["constraints"][0]["at"] == [25.0, 1.0]
    assert face_sketch.to_world(g, 25.0, 1.0) == before
    assert not face_sketch.rebase(g)
    m.remove_node(g)
