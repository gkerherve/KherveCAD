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
