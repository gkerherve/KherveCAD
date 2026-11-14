"""SolidWorks' Draft (2026-11-14, the user: the Features tab's tools
KherveCAD lacked): side faces tilted about a neutral plane.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest


def _vol(tris):
    from khervecad import analysis
    return analysis.mass_properties(tris)["volume"]


def _box(s=20.0):
    from khervecad import mesh
    from khervecad.model import CadNode
    cube = CadNode("cube", "Cube", {"width": s, "depth": s, "height": s,
                                    "size": s, "center": False})
    return [tuple(t[:3]) for t in mesh.tessellate(cube)]


def _frustum(a1, a2, h):
    return h / 3 * (a1 + a2 + math.sqrt(a1 * a2))


def test_a_box_drafted_from_the_bottom_is_a_frustum():
    from khervecad import analysis, draft
    tris = draft.draft_tris(_box(), 5.0, "bottom")
    top = 20 - 2 * 20 * math.tan(math.radians(5))
    assert _vol(tris) == pytest.approx(_frustum(400, top * top, 20),
                                       rel=1e-6)
    assert "watertight" not in str(
        [c for c in analysis.print_check(tris).get("checks", [])
         if c.get("status") == "fail"])
    zs = [p[2] for t in tris for p in t]
    assert min(zs) == 0 and max(zs) == 20     # nothing moves in z


def test_the_top_as_neutral_plane_narrows_the_bottom():
    from khervecad import draft
    tris = draft.draft_tris(_box(), 5.0, "top")
    bottom = [p for t in tris for p in t if abs(p[2]) < 1e-9]
    xs = [p[0] for p in bottom]
    d = 20 * math.tan(math.radians(5))
    assert min(xs) == pytest.approx(d) and max(xs) == pytest.approx(20 - d)


def test_only_the_picked_face_is_drafted():
    from khervecad import draft
    # the face x = 20 alone: the box becomes a wedge-topped prism
    tris = draft.draft_tris(_box(), 5.0, "bottom", picks=[(20, 10, 10)])
    top = [p for t in tris for p in t if abs(p[2] - 20) < 1e-9]
    d = 20 * math.tan(math.radians(5))
    assert max(p[0] for p in top) == pytest.approx(20 - d)
    assert min(p[0] for p in top) == pytest.approx(0)
    assert max(p[1] for p in top) == pytest.approx(20)   # y untouched
    assert _vol(tris) == pytest.approx(8000 - 20 * 20 * d / 2, rel=1e-6)


def test_the_draft_node_round_trips_and_bakes(tmp_path):
    from khervecad import mesh, scadparse
    root, warnings = scadparse.parse_scad(
        "kcad_draft(angle = 5, neutral = \"bottom\") cube(20);")
    node = next(n for n in root.walk() if n.type == "draft")
    assert node.params["angle"] == 5
    tris = mesh.tessellate(root)
    top = 20 - 2 * 20 * math.tan(math.radians(5))
    assert _vol(tris) == pytest.approx(_frustum(400, top * top, 20),
                                       rel=1e-4)
    assert "kcad_draft(" in root.to_scad()


# ------------------------------------------------- the window, by clicks
@pytest.fixture
def window():
    from PyQt5.QtWidgets import QApplication
    from khervecad.mainwindow import MainWindow
    QApplication.instance() or QApplication([])
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    QApplication.processEvents()
    yield w
    w._dirty = False
    w.close()


def test_the_draft_button_opens_its_window_and_takes_clicked_faces(window):
    """Select a cube, press Draft: the window opens (angle, neutral
    plane, faces); a click on the +x side drafts that face alone, a
    second click takes it back, OK keeps the Draft."""
    from khervecad import draft_pick, fillet_pick, scadparse
    cube = scadparse.parse_scad("cube(20);")[0].children[0]
    window.model.root.add(cube)
    window.model.structure_changed.emit()
    window.builder.active_tree().select_nodes([cube])
    window._apply_operation("draft")
    node = next(n for n in window.model.root.walk() if n.type == "draft")
    panel = window._draft_panel
    assert panel is not None and panel.isVisible()
    world = [t for t in fillet_pick.meshes(window, node)[0]
             if all(abs(v[0] - 20) < 1e-6 for v in t)]
    desc = {"kind": "face", "tris": [world[0]]}
    view = window.view3d
    view._pick_cb(desc, node)
    assert len(node.params["pick"]) == 1
    view._pick_cb(desc, node)                # again: back to every side
    assert node.params["pick"] == []
    view._pick_cb(desc, node)
    panel.ok.click()
    assert not panel.isVisible() and node.parent is not None
    from khervecad import mesh
    tris = mesh.tessellate(window.model.root)
    d = 20 * math.tan(math.radians(3))
    assert _vol(tris) == pytest.approx(8000 - 20 * 20 * d / 2, rel=1e-4)
    assert draft_pick._panel(window) is None
