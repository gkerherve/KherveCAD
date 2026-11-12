# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""SolidWorks' Cut panel (cut_feature)."""


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
