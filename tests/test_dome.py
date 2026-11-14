"""SolidWorks' Dome (2026-11-14, the user): a flat face bulged out (or
dented in) by a height, its edge kept, the part closed.

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


def _closed(tris):
    """Every edge used exactly twice, in opposite directions."""
    from collections import Counter
    k = lambda p: tuple(round(c, 6) for c in p)          # noqa: E731
    e = Counter()
    for t in tris:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            e[(k(a), k(b))] += 1
    return all(e[(b, a)] == n for (a, b), n in e.items())


def _tess(code):
    from khervecad import mesh, scadparse
    root = scadparse.parse_scad(code)[0]
    return root, [tuple(t[:3]) for t in mesh.tessellate(root)]


def test_a_round_face_becomes_half_an_ellipsoid():
    _r, base = _tess("cylinder(r = 20, h = 10, $fn = 96);")
    _r, domed = _tess("kcad_dome(height = 15) "
                      "cylinder(r = 20, h = 10, $fn = 96);")
    added = _vol(domed) - _vol(base)
    assert added == pytest.approx(2 / 3 * math.pi * 400 * 15, rel=0.03)
    assert max(p[2] for t in domed for p in t) == pytest.approx(25, abs=0.3)
    assert _closed(domed)


def test_reverse_dents_the_face_in():
    _r, base = _tess("cylinder(r = 20, h = 30, $fn = 96);")
    _r, dented = _tess("kcad_dome(height = 15, reverse = true) "
                       "cylinder(r = 20, h = 30, $fn = 96);")
    assert _vol(base) - _vol(dented) == pytest.approx(
        2 / 3 * math.pi * 400 * 15, rel=0.03)
    assert _closed(dented)


def test_a_square_face_keeps_its_edge_and_stays_closed():
    _r, domed = _tess("kcad_dome(height = 8) cube(20);")
    assert _closed(domed)
    top = max(p[2] for t in domed for p in t)
    assert top == pytest.approx(28, abs=0.5)
    # the rim of the top face is still at z = 20
    rim = [p for t in domed for p in t
           if abs(p[0]) < 1e-6 or abs(p[0] - 20) < 1e-6]
    assert max(p[2] for p in rim) == pytest.approx(20)


def test_a_picked_side_face_domes_sideways():
    _r, domed = _tess("kcad_dome(height = 5, pick = [[20, 10, 10]]) "
                      "cube(20);")
    assert max(p[0] for t in domed for p in t) == pytest.approx(25,
                                                                 abs=0.4)
    assert max(p[2] for t in domed for p in t) == pytest.approx(20)
    assert _closed(domed)


def test_the_dome_round_trips_through_scad():
    root, _t = _tess("kcad_dome(height = 6, reverse = true) cube(20);")
    node = next(n for n in root.walk() if n.type == "dome")
    assert node.params["height"] == 6 and node.params["reverse"] is True
    assert "kcad_dome(" in root.to_scad()


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


def test_the_dome_button_opens_its_window_and_takes_clicked_faces(window):
    """Select a cube, press Dome: the window opens on the top face; a
    click on the +x side domes that face instead, Reverse dents it, OK
    keeps the Dome."""
    from khervecad import dome_pick, fillet_pick, mesh, scadparse
    cube = scadparse.parse_scad("cube(20);")[0].children[0]
    window.model.root.add(cube)
    window.model.structure_changed.emit()
    window.builder.active_tree().select_nodes([cube])
    window._apply_operation("dome")
    node = next(n for n in window.model.root.walk() if n.type == "dome")
    panel = window._dome_panel
    assert panel is not None and panel.isVisible()
    world = [t for t in fillet_pick.meshes(window, node)[0]
             if all(abs(v[0] - 20) < 1e-6 for v in t)]
    window.view3d._pick_cb({"kind": "face", "tris": [world[0]]}, node)
    assert len(node.params["pick"]) == 1
    panel.fields["reverse"].setChecked(True) if hasattr(
        panel, "fields") and "reverse" in panel.fields else \
        window.model.set_param(node, "reverse", True)
    panel.ok.click()
    assert not panel.isVisible() and dome_pick._panel(window) is None
    tris = mesh.tessellate(window.model.root)
    assert min(p[0] for t in tris for p in t) == pytest.approx(0)
    assert max(p[0] for t in tris for p in t) == pytest.approx(20)  # in
    assert _vol(tris) < 8000 - 100
