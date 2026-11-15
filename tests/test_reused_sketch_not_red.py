# SPDX-License-Identifier: GPL-3.0-or-later
"""A second extrude of an already-extruded sketch holds a Regions with no
shapes of its own (it reads its source's). It must not be flagged empty."""
from khervecad import model


def test_a_reused_sketch_is_not_an_empty_extrusion():
    doc = model.DocumentModel()
    root = doc.root
    ext = model.CadNode("linear_extrude", "Boss-Extrude1")
    src = model.CadNode("regions", "Regions 1")
    src.add(model.CadNode("rect", "R"))
    ext.add(src)
    root.add(ext)
    ext2 = model.CadNode("linear_extrude", "Boss-Extrude2")
    reg = model.CadNode("regions", "Regions 2")
    reg.params.update(seeds=[[1, 1]], inside=[[0]], sketch_of="Regions 1")
    ext2.add(reg)
    root.add(ext2)
    errors = model.validate(root)
    assert ext2.id not in errors and reg.id not in errors, errors
