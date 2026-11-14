"""SolidWorks' Full Round Fillet (2026-11-14, Exercise 6): side face,
centre face, side face -> a half round tangent to both sides.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest

# the exercise's upright: 76 along X, 60 along Y, 60 tall
BLOCK = "cube([76, 60, 60]);"
LOST = 60 * 30 * 76 - math.pi * 30 ** 2 / 2 * 76      # box - half bar


def _vol(tris):
    from khervecad import analysis
    return analysis.mass_properties(tris)["volume"]


def _tess(code):
    from khervecad import mesh, scadparse
    root = scadparse.parse_scad(code)[0]
    return root, [tuple(t[:3]) for t in mesh.tessellate(root)]


def test_three_faces_make_a_half_round_of_half_the_width():
    _r, base = _tess(BLOCK)
    _r, t = _tess("kcad_full_round(pick = [[38, 0, 30], [38, 30, 60], "
                  "[38, 60, 30]]) " + BLOCK)
    assert _vol(base) - _vol(t) == pytest.approx(LOST, rel=0.01)
    assert max(p[2] for tri in t for p in tri) == pytest.approx(60, abs=0.01)
    # at the top, the round is only at the middle
    top = [p for tri in t for p in tri if p[2] > 59.99]
    assert all(abs(p[1] - 30) < 2 for p in top)


def test_the_centre_face_alone_finds_its_sides():
    _r, t = _tess("kcad_full_round(pick = [[38, 30, 60]]) " + BLOCK)
    _r, base = _tess(BLOCK)
    assert _vol(base) - _vol(t) == pytest.approx(LOST, rel=0.01)


def test_no_pick_rounds_the_top_across_its_narrow_way():
    """A 76 x 60 top: the sides are the pair facing each other across
    the 60 (they share the longest edge with it)."""
    _r, t = _tess("kcad_full_round() " + BLOCK)
    _r, base = _tess(BLOCK)
    assert _vol(base) - _vol(t) == pytest.approx(LOST, rel=0.01)


def test_round_trips_and_flags_two_picks():
    root, _t = _tess("kcad_full_round(pick = [[38, 30, 60]]) " + BLOCK)
    node = next(n for n in root.walk() if n.type == "full_round")
    assert node.params["pick"] == [[38, 30, 60]]
    assert "kcad_full_round(" in root.to_scad()
    from khervecad import full_round
    node.params["pick"] = [[38, 0, 30], [38, 30, 60]]
    assert full_round._check(node, {})


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


def test_the_button_takes_side_centre_side_clicks(window):
    from khervecad import fillet_pick, mesh, scadparse
    cube = scadparse.parse_scad(BLOCK)[0].children[0]
    window.model.root.add(cube)
    window.model.structure_changed.emit()
    window.builder.active_tree().select_nodes([cube])
    window._apply_operation("full_round")
    node = next(n for n in window.model.root.walk()
                if n.type == "full_round")
    panel = window._full_round_panel
    assert panel is not None and panel.isVisible()
    world = fillet_pick.meshes(window, node)[0]

    def face(test):
        return next(t for t in world if all(test(v) for v in t))
    for f in (face(lambda v: abs(v[1]) < 1e-6),
              face(lambda v: abs(v[2] - 60) < 1e-6),
              face(lambda v: abs(v[1] - 60) < 1e-6)):
        window.view3d._pick_cb({"kind": "face", "tris": [f]}, node)
    assert len(node.params["pick"]) == 3
    panel.ok.click()
    assert not panel.isVisible()
    tris = mesh.tessellate(window.model.root)
    assert 76 * 60 * 60 - _vol(tris) == pytest.approx(LOST, rel=0.01)
