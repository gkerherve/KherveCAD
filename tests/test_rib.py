"""SolidWorks' Rib (2026-11-14, the user's Exercise 6 video: a bearing
cradle and a pillow block, each braced by a rib): ONE open line on a
plane through the part, given a thickness about the plane, fills to the
part — the area the line closes with the part's outline there.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtTest import QTest

from test_lever_by_mouse import win  # noqa: F401

CODE = ("cube([60, 40, 10]); // Base\n"
        "translate([40, 20, 10]) cube([20, 20, 30]); // Block\n")


def _volume(win):
    from khervecad import analysis, mesh
    win.model.root.params.pop("_", None)
    tris = mesh.tessellate(win.model.root)
    return analysis.mass_properties(tris)["volume"]


def _rib_sketch(win):
    """A sketch on the plane y = 30 (through the block) holding one line
    from the block's top corner to the base's far corner."""
    from khervecad import face_sketch, refgeom_ui
    group = refgeom_ui.sketch_on(win, origin=(0, 30, 0), normal=(0, 1, 0),
                                 label="Rib plane", open_2d=False)
    a = face_sketch.to_local(group, (40, 30, 40))
    b = face_sketch.to_local(group, (0, 30, 10))
    win.model.add_node("line", dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                                    width=0.2), parent=group)
    return group


def test_a_rib_fills_from_its_line_to_the_part(win):
    from khervecad import rib_feature
    from khervecad.mcp_tools import McpToolExecutor
    McpToolExecutor(win).execute("apply_code", {"code": CODE})
    QTest.qWait(50)
    before = _volume(win)
    group = _rib_sketch(win)
    rib = rib_feature.make(win, group, thickness=10)
    QTest.qWait(50)
    assert rib is not None and rib.name.startswith("Rib")
    assert rib.params["center"] and rib.params["height"] == 10
    # the triangle 40 x 30 / 2 under the line, 10 thick, joined
    assert _volume(win) - before == pytest.approx(600 * 10, rel=0.02)


def test_the_rib_follows_its_thickness(win):
    from khervecad import rib_feature
    from khervecad.mcp_tools import McpToolExecutor
    McpToolExecutor(win).execute("apply_code", {"code": CODE})
    QTest.qWait(50)
    before = _volume(win)
    rib = rib_feature.make(win, _rib_sketch(win), thickness=10)
    win.model.set_param(rib, "height", 4)
    QTest.qWait(50)
    assert _volume(win) - before == pytest.approx(600 * 4, rel=0.02)


def test_a_line_closing_nothing_makes_no_rib(win):
    from khervecad import face_sketch, refgeom_ui, rib_feature
    from khervecad.mcp_tools import McpToolExecutor
    McpToolExecutor(win).execute("apply_code", {"code": CODE})
    QTest.qWait(50)
    group = refgeom_ui.sketch_on(win, origin=(0, 30, 0), normal=(0, 1, 0),
                                 open_2d=False)
    a = face_sketch.to_local(group, (100, 30, 100))
    b = face_sketch.to_local(group, (120, 30, 120))   # far from the part
    win.model.add_node("line", dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                                    width=0.2), parent=group)
    assert rib_feature.make(win, group, thickness=10) is None


def test_rib_by_mcp(win):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code": CODE})
    QTest.qWait(50)
    before = _volume(win)
    group = _rib_sketch(win)
    out = ex.execute("rib", {"node_id": group.id, "thickness": 8})
    assert "error" not in out, out
    QTest.qWait(50)
    assert _volume(win) - before == pytest.approx(600 * 8, rel=0.02)


def test_the_rib_button_is_on_the_features_tab_and_uses_the_selection(win):
    from khervecad import ribbon, rib_feature
    from khervecad.mcp_tools import McpToolExecutor
    title, acts = ribbon.panel_actions(win, "finish")
    rib_act = next(a for a in acts if a.data() == "rib")
    assert rib_act is rib_feature.action(win)
    McpToolExecutor(win).execute("apply_code", {"code": CODE})
    QTest.qWait(50)
    before = _volume(win)
    group = _rib_sketch(win)
    win.builder.active_tree().select_nodes([group])
    rib_act.trigger()                       # the button, as a click does
    QTest.qWait(50)
    assert any(n.name.startswith("Rib") for n in win.model.root.walk())
    assert _volume(win) - before == pytest.approx(6000, rel=0.02)


def test_leaving_a_rib_sketch_makes_the_rib(win):
    """The click flow's end: a plane sketch opened for a Rib (marked as
    the Boss / Cut sketches are) makes the rib when it is finished."""
    from khervecad import cut_feature
    from khervecad.mcp_tools import McpToolExecutor
    McpToolExecutor(win).execute("apply_code", {"code": CODE})
    QTest.qWait(50)
    before = _volume(win)
    group = _rib_sketch(win)
    group.params[cut_feature.KEY] = "rib"
    rib = cut_feature.finish(win, group)
    QTest.qWait(50)
    assert rib is not None and cut_feature.KEY not in group.params
    assert _volume(win) - before == pytest.approx(6000, rel=0.02)


def test_a_rib_on_the_front_plane_stays_in_the_middle(win):
    """The user, 2026-11-14: Rib, then the Front Plane, made the rib on
    the part's front FACE (y = -26), not on the plane through the
    middle — the sketch remembered the nearest face facing the same
    way and followed it there."""
    from khervecad import cut_feature, face_sketch, feature_pick, mesh
    from khervecad.mcp_tools import McpToolExecutor
    McpToolExecutor(win).execute("apply_code", {"code": (
        "translate([-30, -26, 0]) cube([60, 52, 10]); // Base\n"
        "translate([20, -26, 10]) cube([10, 52, 30]); // Wall\n")})
    QTest.qWait(50)
    feature_pick.start(win, "rib")
    pick = win._feature_pick
    win.view3d.release_hooks  # (armed)
    feature_pick._use_plane(win, pick, "Front (XZ)")
    QTest.qWait(100)
    group = next(n for n in win.model.root.walk()
                 if n.params.get(face_sketch.KEY))
    assert float(group.params["y"]) == pytest.approx(0, abs=1e-6)
    assert face_sketch.FACE_REF not in group.params
    # a line from the wall's top to the base's far edge, then leave
    a = face_sketch.to_local(group, (20, 0, 40))
    b = face_sketch.to_local(group, (-30, 0, 10))
    win.model.add_node("line", dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                                    width=0.2), parent=group)
    QTest.qWait(100)
    assert float(group.params["y"]) == pytest.approx(0, abs=1e-6)
    rib = cut_feature.finish(win, group)
    QTest.qWait(100)
    assert rib is not None
    m = mesh.ancestor_matrix(rib, {})
    ys = [mesh.mat_apply(m, p)[1] for t in mesh.tessellate(rib) for p in t]
    assert min(ys) == pytest.approx(-5, abs=0.01)
    assert max(ys) == pytest.approx(5, abs=0.01)
