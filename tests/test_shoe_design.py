"""The Shoe Builder (shoe_design.py, shoe_dialog.py, library_shoes.py):
every preset builds clean and stands on the floor, size sets the
length, specs are checked, insert keeps the spec for an update, the
builder window draws its views and the MCP tools build a shoe.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from khervecad import library, mcp_schema, mesh, scadparse
from khervecad import shoe_design as D
from khervecad.model import DocumentModel, validate


def _box(node):
    tris = mesh.tessellate(node)
    pts = [p for t in tris for p in t]
    return ([min(p[i] for p in pts) for i in range(3)],
            [max(p[i] for p in pts) for i in range(3)])


@pytest.mark.parametrize("name", list(D.PRESETS))
def test_every_preset_builds_clean(name):
    _root, warnings = scadparse.parse_scad(D.program({"preset": name}))
    assert not warnings, name
    node = D.build({"preset": name})
    assert not validate(node), name
    lo, hi = _box(node)
    assert -2.0 < lo[2] < 1.0, name          # stands on the floor
    assert hi[2] > 30.0, name


def test_size_sets_the_length_and_men_are_wider():
    a = D.build({"preset": "Classic black pump", "size": 36})
    b = D.build({"preset": "Classic black pump", "size": 41})
    la, lb = _box(a), _box(b)
    assert lb[1][0] - lb[0][0] > la[1][0] - la[0][0] + 25
    w = D.build({"upper": "Loafer", "heel": "None", "size": 42})
    m = D.build({"upper": "Loafer", "heel": "None", "size": 42,
                 "gender": "Men"})
    ww = _box(w)[1][1] - _box(w)[0][1]
    mw = _box(m)[1][1] - _box(m)[0][1]
    assert mw > ww * 1.02


def test_heel_height_is_what_it_says():
    low = _box(D.build({"heel_height": 40}))
    high = _box(D.build({"heel_height": 110}))
    assert high[1][2] - low[1][2] == pytest.approx(70, abs=3)


def test_bad_specs_are_refused():
    for bad in ({"toe": "Hexagonal"}, {"upper_colour": "Plaid"},
                {"preset": "Moon boot"}, {"laces": 3}):
        with pytest.raises(D.SpecError):
            D.normalise(bad)


def test_a_pair_is_two_shoes():
    one = _box(D.build({"preset": "Ballet flat"}))
    two = _box(D.build({"preset": "Ballet flat", "pair": True}))
    assert two[1][1] - two[0][1] > 2 * (one[1][1] - one[0][1])


def test_insert_keeps_the_spec_for_update():
    model = DocumentModel()
    part = D.insert(model, {"preset": "Work boot"})
    assert part.params["shoe"]["upper"] == "Work boot"
    again = D.insert(model, {"preset": "Work boot", "upper_colour": "Black"},
                     replace=part)
    assert again.params["shoe"]["upper_colour"] == "Black"
    assert sum(1 for n in model.root.children
               if (n.params or {}).get("shoe")) == 1


def test_presets_are_library_parts_and_mcp_tools_exist():
    labels = {spec.get("label") for spec in library.PARTS.values()
              if spec.get("category") == "Shoes"}
    assert set(D.PRESETS) <= labels
    node = library.build_part("shoe_running_shoe",
                              {"size": 44, "_color": "Red"})
    assert node is not None
    names = {t["name"] for t in mcp_schema.TOOLS}
    assert {"list_shoe_options", "build_shoe"} <= names


def test_builder_window_and_mcp_tool():
    from PyQt5.QtWidgets import QApplication
    from khervecad import shoe_dialog
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    app = QApplication.instance() or QApplication([])
    assert app is not None
    win = MainWindow()
    panel = shoe_dialog.open_builder(win)
    panel.set_spec({"preset": "High-top basketball"})
    pix = panel._views[0].pixmap()
    assert pix is not None and not pix.isNull()
    assert panel.spec()["upper"] == "High-top"
    panel._apply(None)
    assert shoe_dialog.selected_shoe(win) is not None
    panel.close()
    ex = McpToolExecutor(win)
    result = ex.execute("build_shoe", {"preset": "Oxford dress shoe",
                                    "size": 44})
    assert result["length_mm"] == pytest.approx(288.3, abs=0.2)
    assert "Pump" in ex.execute("list_shoe_options", {})["uppers"]
