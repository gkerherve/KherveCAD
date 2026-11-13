# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""SolidWorks' Cut panel (cut_feature)."""
import pytest


def test_a_lofted_cut_of_one_profile_or_two_really_cuts():
    # the user: Lofted Cut "does not look like working" — the heights
    # were a flat list (refused) and one profile made no loft at all
    from khervecad import cut_feature as cf, mesh, analysis
    from khervecad.model import CadNode, DocumentModel, validate
    for kinds in (["rect"], ["slot"], ["rect", "circle"]):
        m = DocumentModel()
        obj = CadNode("component", "Part")
        m.root.add(obj)
        part = CadNode("cube", "Block", {"width": 60, "depth": 40,
                                         "height": 20})
        obj.add(part)
        g = CadNode("union", "Sketch", {"x": 0, "y": 0, "z": 20})
        obj.add(g)
        for k in kinds:
            g.add({"rect": CadNode("rect", "R", {"x": 10, "y": 10,
                                                 "width": 20, "height": 10}),
                   "slot": CadNode("line", "S", {"x1": 10, "y1": 20,
                                                 "x2": 40, "y2": 20,
                                                 "width": 8}),
                   "circle": CadNode("circle", "C", {"x": 20, "y": 15,
                                                     "radius": 3})}[k])
        assert cf.apply(m, g, part, "lofted_cut") is not None
        assert not validate(m.root), kinds
        vol = analysis.mass_properties(mesh.tessellate(obj, {}))["volume"]
        assert vol < 48000 - 500, kinds



def test_a_new_sketch_on_a_face_is_never_taken_over_by_regions(
        monkeypatch):
    # the user: Extruded Cut no longer let a face be clicked — the region
    # pick of the existing sketches ran first
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from khervecad.mainwindow import MainWindow
    from khervecad import cut_feature as cf, sketch_regions
    w = MainWindow()
    w.show()
    app.processEvents()
    m = w.model
    obj = m.add_node("component", {}, name="Part")
    obj.visible = True
    m.add_node("cube", {"width": 40, "depth": 30, "height": 10},
               parent=obj)
    for y in (0, 20):                       # two existing sketches
        ext = m.add_node("linear_extrude", {"height": 5}, parent=obj)
        m.add_node("circle", dict(x=10, y=y, radius=3), parent=ext)
    w.builder.open_component(obj)
    app.processEvents()
    called = []
    real = sketch_regions.start_any
    monkeypatch.setattr(sketch_regions, "start_any",
                        lambda *a, **k: called.append(1) or real(*a, **k))
    cf.start(w, "extruded_cut", {"source": "face", "where": "3d"})
    app.processEvents()
    assert called == []
    assert w.view3d._pick_cb is not None      # waiting for the face
    w.view3d.cancel_pick()


LUG = """
union() {
    hull() { translate([-50, 105]) circle(d=0.2, $fn=32); translate([50, 105]) circle(d=0.2, $fn=32); };
    hull() { translate([50, 105]) circle(d=0.2, $fn=32); translate([50, 175]) circle(d=0.2, $fn=32); };
    hull() { translate([-50, 175]) circle(d=0.2, $fn=32); translate([-50, 105]) circle(d=0.2, $fn=32); };
    kcad_arc(p1 = [50, 175], p2 = [-50, 175], bulge = 1, d = 0.2);
    %hull() { translate([-50, 175]) circle(d=0.5, $fn=32); translate([50, 175]) circle(d=0.5, $fn=32); };
    translate([0, 175]) circle(r=23.5, $fn=64);
}
"""


def test_a_boss_of_lines_round_a_circle_is_the_lug_with_its_hole():
    """The user's lug (a SolidWorks exercise): lines and an arc closing
    a U round a Ø47 circle, finished as an Extruded Boss. It came out as
    hair-thin walls and a solid disc; it is the closed area, the circle
    a hole — as the same sketch extruded from Sketch Mode."""
    import math
    from khervecad import analysis, cut_feature as cf, mesh, scadparse
    from khervecad.model import DocumentModel, validate
    m = DocumentModel()
    root, _w = scadparse.parse_scad(LUG)
    for node in list(root.children):
        m.root.add(node)
    group = next(n for n in m.root.children if n.type == "union")
    tool = cf.apply(m, group, None, "extruded_boss")
    assert tool is not None and tool.type == "linear_extrude"
    assert [c.type for c in tool.children] == ["regions"]
    assert not validate(m.root)
    vol = analysis.mass_properties(mesh.tessellate(m.root, {}))["volume"]
    area = 100 * 70 + math.pi * 50 ** 2 / 2 - math.pi * 23.5 ** 2
    assert vol == pytest.approx(area * cf.DEPTH, rel=0.02)


def test_one_closed_shape_still_extrudes_as_drawn():
    from khervecad import cut_feature as cf
    from khervecad.model import CadNode, DocumentModel
    m = DocumentModel()
    g = CadNode("union", "Sketch")
    m.root.add(g)
    g.add(CadNode("rect", "R", {"x": 0, "y": 0, "width": 20,
                                "height": 10}))
    tool = cf.apply(m, g, None, "extruded_boss")
    assert [c.type for c in tool.children] == ["rect"]
