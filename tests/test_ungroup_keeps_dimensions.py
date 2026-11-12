# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Removing an extrude / revolve but keeping what's inside keeps the
shapes' Smart Dimensions (2026-11-12, the user's Exercise 9 rectangle
lost them twice)."""

from khervecad import sketch_constraints as sc
from khervecad.model import CadNode, DocumentModel


def test_ungrouping_a_feature_brings_its_dimensions_out():
    m = DocumentModel()
    obj = CadNode("component", "Ex")
    m.root.add(obj)
    obj.add(CadNode("circle", "First", {"x": 0, "y": 0, "radius": 1}))
    rect = CadNode("rect", "Base", {"x": 0, "y": 0, "width": 60,
                                    "height": 20})
    obj.add(rect)
    later = CadNode("circle", "Later", {"x": 50, "y": 0, "radius": 4})
    obj.add(later)
    obj.params[sc.KEY] = [{"kind": "diameter", "refs": ["2.o"],
                           "value": 8.0}]
    ext = m.wrap_nodes([rect], "linear_extrude")
    ext.params[sc.KEY] = [{"kind": "length", "refs": ["0.e0"],
                           "value": 60.0}]
    m.ungroup(ext)
    got = {r["kind"]: r["refs"] for r in sc.rows(obj)}
    assert got["length"] == ["1.e0"]           # the rectangle's, back out
    assert got["diameter"] == ["2.o"]          # the later circle's, intact
