"""Overlapping parts are merged for the drawing only (drawmerge.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest

from khervecad import csg, drawmerge, mesh
from khervecad.model import CadNode

pytestmark = pytest.mark.skipif(not csg.available(),
                                reason="Manifold not installed")


def _cube(x=0.0, z=0.0, w=10.0):
    return mesh.tessellate(CadNode("cube", params=dict(
        width=w, depth=w, height=w, x=x, z=z)))


def _tube(z0, h, x=5.0, y=5.0):
    return mesh.tessellate(CadNode("cylinder", params=dict(
        height=h, radius_bottom=2.0, radius_top=2.0, segments=24,
        x=x, y=y, z=z0)), fn=24)


def test_a_tube_through_a_wall_becomes_one_solid():
    tris, joined = drawmerge.merged(_cube() + _tube(5.0, 15.0))
    assert joined == 2
    from khervecad import analysis
    vol = analysis.mass_properties(tris)["volume"]
    assert vol < 1000 + 3.15 * 4 * 15          # the overlap counted once


def test_parts_that_only_touch_stay_apart():
    raw = _cube() + _cube(z=10.0)
    tris, joined = drawmerge.merged(raw)
    assert joined == 0 and tris == raw


def test_the_meeting_curve_is_an_edge_on_the_drawing():
    from khervecad import fillet
    from khervecad.blueprint_scene import Geometry
    raw = _cube() + _tube(5.0, 15.0)

    def ring(tris):
        """crease edges on the tube where it meets the cube's top face"""
        return [e for e in fillet.crease_edges(tris, 30.0)
                if abs(e.a[2] - 10.0) < 1e-3 and abs(e.b[2] - 10.0) < 1e-3
                and abs(((e.a[0] - 5) ** 2 + (e.a[1] - 5) ** 2) ** 0.5 - 2)
                < 0.05]
    assert not ring(Geometry(raw, merge=False).tris)
    merged = Geometry(raw)
    assert merged.joined == 2 and len(ring(merged.tris)) >= 20
    assert Geometry(raw, merge=False).raw == raw      # the model's copy


@pytest.fixture(scope="session")
def app():
    # session-scoped: a QApplication owned by one test was deleted under
    # every later test (a bus error in the next module)
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_the_drawing_picker_lists_a_wrapping_objects_sheet(app):
    from khervecad import drawing_set
    from khervecad.mainwindow import MainWindow
    from khervecad.blueprint import open_blueprint
    win = MainWindow()
    try:
        m = win.model
        a = m.add_node("cube", dict(width=10.0, depth=10.0, height=10.0))
        b = m.add_node("cube", dict(width=10.0, depth=10.0, height=10.0,
                                    x=20.0))
        wrap = m.wrap_nodes([a, b], "union")
        m.make_component(wrap) if hasattr(m, "make_component") else None
        comp = next(c for c in m.all_components())
        bp = open_blueprint(win)
        drawing_set.show(bp, comp.name)          # sheet 2 = the wrapper
        drawing_set.show(bp, None)
        names = [bp.drawing_combo.itemData(i)
                 for i in range(bp.drawing_combo.count())]
        assert comp.name in names
        assert "of" in bp.drawing_page.text()
        drawing_set.step_drawing(bp, 1)
        assert bp.current == names[1]
        assert drawing_set.delete_current(bp) and bp.current is None
        bp.close()
    finally:
        win._dirty = False
        win.close()


def test_an_object_name_with_symbols_gives_an_ascii_module():
    """'Chamber body Ø250' made `module Chamber_body_Ø250`, which
    OpenSCAD refuses — the whole chamber lost its exact render."""
    from khervecad.model import module_name
    assert module_name("Chamber body Ø250 x 600") == "Chamber_body_D250_x_600"
    assert module_name("Château 45°").isascii()
