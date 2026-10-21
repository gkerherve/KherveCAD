"""The Hole Wizard: sizes, a drilled hole square to the face, one feature
for several clicks, Update.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import hole_wizard as hw
from khervecad import mesh
from khervecad.model import DocumentModel

_APP = QApplication.instance() or QApplication([])


def test_sizes():
    p = hw.spec_params(dict(type="Clearance", size="M6", fit="Normal",
                            end="Blind", depth=8))
    assert p["diameter"] == 6.6 and p["depth"] == 8
    tap = hw.spec_params(dict(type="Tapped (drill)", size="M6"), 30)
    assert tap["diameter"] == pytest.approx(5.0) and tap["depth"] == 30
    cb = hw.spec_params(dict(type="Counterbore", size="M8"))
    assert cb["kind"] == "counterbore" and cb["head_diameter"] == 15.0


def _volume(node):
    from khervecad import analysis
    return analysis.mass_properties(mesh.tessellate(node))["volume"]


def test_holes_on_top_and_side_are_one_feature_and_cut():
    m = DocumentModel()
    block = m.add_node("cube", dict(width=40, depth=30, height=20))
    full = _volume(block)
    spec = dict(type="Clearance", size="M6", fit="Normal",
                end="Through all")
    f = hw.add_hole(m, block, [10, 15, 20], [0, 0, 1], spec)
    f2 = hw.add_hole(m, block, [30, 15, 20], [0, 0, 1], spec)
    assert f is f2 and f.name == "M6 Clearance Hole"
    diff = block.parent
    assert diff.type == "difference" and diff.children[0] is block
    holes = [n for n in f.walk() if n.type == "hole"]
    assert len(holes) == 2
    import math
    expect = full - 2 * math.pi * 3.3 ** 2 * 20
    assert _volume(diff) == pytest.approx(expect, rel=0.03)
    # a side face: the hole runs along -X into the block
    side = hw.add_hole(m, block, [40, 15, 10], [1, 0, 0], spec)
    turn = [n for n in side.walk() if n.type == "rotate"][-1]
    assert turn.params["y"] == pytest.approx(90)
    hw.update(m, f, dict(spec, size="M8"))
    assert all(h.params["diameter"] == 9.0
               for h in f.walk() if h.type == "hole")
    assert f.name == "M8 Clearance Hole"


def test_ribbon_has_the_wizard():
    from khervecad import ribbon, toolbar_style
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        toolbar_style.apply(win, "SolidWorks", remember=False)
        _t, acts = ribbon.panel_actions(win, "mechanical")
        assert acts[0].data() == "hole_wizard"
        acts[0].trigger()
        assert win._hole_panel.isVisible()
        win._hole_panel.close()
    finally:
        toolbar_style.apply(win, "KherveCAD", remember=False)
        win._dirty = False
        win.close()


def test_an_object_is_drilled_inside_at_its_own_frame():
    m = DocumentModel()
    comp = m.new_component("Plate", visible=True)
    comp.params.update(x=100.0)                   # placed in the assembly
    m.add_node("cube", dict(width=40, depth=30, height=10), parent=comp)
    spec = dict(type="Clearance", size="M4", end="Through all")
    f = hw.add_hole(m, comp, [110, 15, 10], [0, 0, 1], spec)
    assert f.parent.parent is comp                # inside the Object
    move = [n for n in f.walk() if n.type == "translate"][0]
    assert (move.params["x"], move.params["z"]) == (10, 10)


def test_mcp_hole_wizard():
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    try:
        ex = McpToolExecutor(win)
        block = win.model.add_node("cube", dict(width=30, depth=30,
                                                height=10))
        out = ex.execute("hole_wizard", dict(
            node_id=block.id, points=[[10, 10, 10], [20, 20, 10]],
            normal=[0, 0, 1], type="Counterbore", size="M5"))
        assert "error" not in out, out
        assert out["name"] == "M5 Counterbore" and len(out["holes"]) == 2
        out = ex.execute("hole_wizard", dict(action="update",
                                             node_id=out["holes"][0],
                                             size="M6"))
        assert out["name"] == "M6 Counterbore"
        bad = ex.execute("hole_wizard", dict(node_id=block.id,
                                             points=[[0, 0, 10]],
                                             size="M7"))
        assert "error" in bad
    finally:
        win._dirty = False
        win.close()


def test_every_standard_size():
    from khervecad import hole_sizes
    assert hole_sizes.sizes("ISO metric")[0] == "M1"
    assert hole_sizes.sizes("ISO metric")[-1] == "M64"
    assert "M1.6" in hw.SIZES and "M2.5" in hw.SIZES
    unc = hole_sizes.sizes("ANSI inch UNC")
    assert "1/4-20 UNC" in unc and "#8-32 UNC" in unc
    assert "#0-80 UNF" in hole_sizes.sizes("ANSI inch UNF")
    assert "#0" not in " ".join(unc)              # #0 has no coarse thread
    p = hw.spec_params(dict(type="Clearance", size="M1.6"))
    assert p["diameter"] == 1.8
    tap = hw.spec_params(dict(type="Tapped (drill)", size="1/4-20 UNC"))
    assert tap["diameter"] == pytest.approx(6.35 - 1.27, abs=0.01)
    cs = hw.spec_params(dict(type="Countersink", size="3/8-16 UNC"))
    assert cs["countersink_angle"] == 82.0          # inch heads are 82°
    for size in hw.SIZES:                           # every one builds
        for kind in hw.TYPES:
            q = hw.spec_params(dict(type=kind, size=size), 20)
            assert q["diameter"] > 0


def test_the_panel_lists_the_standard_sizes():
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        panel = hw.open_panel(win)
        assert panel.size.currentText() == "M6"
        panel.standard.setCurrentIndex(1)           # ANSI inch UNC
        names = [panel.size.itemText(i) for i in range(panel.size.count())]
        assert names[0] == "#1-64 UNC" and "1-8 UNC" in names
        assert panel.spec()["size"] in names
        panel.close()
    finally:
        win._dirty = False
        win.close()
