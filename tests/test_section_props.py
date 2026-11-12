"""Section Properties (2026-11-12, the user, from SolidWorks' Evaluate
tab): the figures against hand calculations, the window, the ribbon
button and the MCP `section` tool.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import icons_cad, ribbon, section_props, toolbar_style, tooltips
from khervecad.mcp_tools import McpToolExecutor

BEAM = ("rotate([90, 0, 0]) linear_extrude(300) polygon([[-50, 0], "
        "[50, 0], [50, 10], [3, 10], [3, 190], [50, 190], [50, 200], "
        "[-50, 200], [-50, 190], [-3, 190], [-3, 10], [-50, 10]]); "
        "// I beam\n")


def _sec(*loops):
    return {"axis": "z", "offset": 0.0, "plane": ("x", "y"),
            "outlines": [{"points": list(p), "closed": True, "area": 0.0}
                         for p in loops],
            "bounds": [0, 0, 1, 1]}


def test_a_rectangle_off_the_origin():
    """b h³ / 12 about its own centre, wherever it stands."""
    p = section_props.properties(
        _sec([(10, 20), (50, 20), (50, 40), (10, 40)]))
    assert p["area"] == pytest.approx(800)
    assert p["perimeter"] == pytest.approx(120)
    assert p["centroid"] == pytest.approx([30, 30])
    assert p["iu"] == pytest.approx(40 * 20 ** 3 / 12)
    assert p["iv"] == pytest.approx(20 * 40 ** 3 / 12)
    # wider than tall: stiffest about the upright axis
    assert p["iuv"] == 0.0 and p["angle"] == pytest.approx(90)
    assert p["i1"] == pytest.approx(p["iv"])
    assert p["j"] == pytest.approx(p["iu"] + p["iv"])
    assert p["zu"] == pytest.approx(40 * 20 ** 2 / 6)
    assert p["ru"] == pytest.approx(20 / math.sqrt(12))


def test_a_hole_subtracts():
    """A square tube: outer counter-clockwise, the hole clockwise."""
    outer = [(0, 0), (40, 0), (40, 40), (0, 40)]
    hole = [(10, 10), (10, 30), (30, 30), (30, 10)]
    p = section_props.properties(_sec(outer, hole))
    assert p["area"] == pytest.approx(1600 - 400)
    assert p["iu"] == pytest.approx((40 ** 4 - 20 ** 4) / 12)
    assert p["perimeter"] == pytest.approx(240)


def test_principal_axes_of_a_turned_rectangle():
    """A 60 x 20 bar turned 30°."""
    t = math.radians(30)
    pts = [(x * math.cos(t) - y * math.sin(t),
            x * math.sin(t) + y * math.cos(t))
           for x, y in ((-30, -10), (30, -10), (30, 10), (-30, 10))]
    p = section_props.properties(_sec(pts))
    assert p["i1"] == pytest.approx(20 * 60 ** 3 / 12)
    assert p["i2"] == pytest.approx(60 * 20 ** 3 / 12)
    # bending about the bar's SHORT axis is the stiffest: 30° + 90°
    assert p["angle"] % 180 == pytest.approx(120)


def test_nothing_cut_gives_nothing():
    assert section_props.properties(
        {"axis": "z", "offset": 0, "plane": ("x", "y"), "outlines": [],
         "bounds": None}) == {}


def test_painted_in_both_styles_with_steps():
    for style in ("Fusion", "SolidWorks"):
        assert icons_cad.icon("section_properties", style) is not None
    assert tooltips.TIPS["section_properties"][2]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.resize(1500, 950)
    toolbar_style.apply(w, "SolidWorks", remember=False)
    w.show()
    QTest.qWait(50)
    yield w
    toolbar_style.apply(w, "KherveCAD", remember=False)
    w._dirty = False
    w.close()


def _button(win):
    return [a for a in ribbon.panel_actions(win, "analyse")[1]
            if a.data() == "section_properties"][0]


def test_the_window_gives_an_i_beams_textbook_figures(win):
    McpToolExecutor(win).execute("apply_code", {"code": BEAM})
    QTest.qWait(150)
    before = set(QApplication.topLevelWidgets())
    _button(win).trigger()
    QTest.qWait(100)
    dlg = [x for x in QApplication.topLevelWidgets() if x not in before
           and type(x).__name__ == "SectionDialog"][0]
    dlg.axis.setCurrentIndex(dlg.axis.findData("y"))
    QTest.qWait(50)
    p = dlg.props
    assert p["area"] == pytest.approx(2 * 100 * 10 + 180 * 6)
    assert p["iu"] == pytest.approx((100 * 200 ** 3 - 94 * 180 ** 3) / 12)
    assert p["iv"] == pytest.approx(2 * 10 * 100 ** 3 / 12
                                    + 180 * 6 ** 3 / 12)
    assert p["centroid"] == pytest.approx([0, 100])
    assert "20,982,667 mm⁴" in dlg.browser.toPlainText()
    # the plane shown in 3D, and put back on closing
    assert win.view3d.cut_state() is None
    dlg.show_cut.setChecked(True)
    QTest.qWait(50)
    cut = win.view3d.cut_state()
    assert cut["axis"] == "y" and cut["offset"] == pytest.approx(-150)
    dlg.offset.setValue(-100)
    QTest.qWait(50)
    assert win.view3d.cut_state()["offset"] == pytest.approx(-100)
    dlg.close()
    QTest.qWait(50)
    assert win.view3d.cut_state() is None


def test_an_empty_document_says_so(win):
    _button(win).trigger()
    QTest.qWait(50)
    assert "Nothing to analyse" in win.statusBar().currentMessage()


def test_the_mcp_section_tool_returns_them(win):
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code": BEAM})
    QTest.qWait(150)
    out = ex.execute("section", {"axis": "y", "wait_for_exact": False})
    props = out["properties"]
    assert props["centroid"] == {"x": 0.0, "z": 100.0}
    assert props["about_centroid"]["I_x"] == pytest.approx(20982667, rel=1e-5)
    assert props["section_modulus"]["x"] == pytest.approx(209827, rel=1e-5)
