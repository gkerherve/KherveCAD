"""Mass properties, the 3D-print check and the interference check.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

from PyQt5.QtWidgets import QApplication

from khervecad import analysis


@pytest.fixture(scope="session")
def app():
    # session-scoped: this module sorts first, so it creates the
    # QApplication — a module-scoped owner would let PyQt delete it
    # when the module ends, under every later test
    return QApplication.instance() or QApplication([])


def _box(x0, y0, z0, w, d, h):
    x1, y1, z1 = x0 + w, y0 + d, z0 + h
    quads = [((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)),
             ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)),
             ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)),
             ((x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)),
             ((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)),
             ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))]
    return [t for a, b, c, d_ in quads for t in ((a, b, c), (a, c, d_))]


# ------------------------------------------------------ mass properties
def test_mass_properties_of_a_cube():
    p = analysis.mass_properties(_box(0, 0, 0, 20, 20, 20))
    assert p["volume"] == pytest.approx(8000.0)
    assert p["area"] == pytest.approx(2400.0)
    assert p["centroid"] == pytest.approx([10.0, 10.0, 10.0])
    assert p["size"] == [20.0, 20.0, 20.0]
    assert analysis.mass(8000.0, "PLA") == pytest.approx(9.92)
    assert analysis.cost(100.0, 20.0) == pytest.approx(2.0)
    assert analysis.print_time(8000.0) > 0


# ---------------------------------------------------------- print check
def test_a_cube_on_the_plate_passes():
    r = analysis.print_check(_box(0, 0, 0, 20, 20, 20))
    status = {c["name"]: c["status"] for c in r["checks"]}
    assert status == {"Watertight": "pass", "Overhangs": "pass",
                      "Wall thickness": "pass", "Footprint": "pass"}
    assert r["summary"] == "pass"


def test_an_open_mesh_fails_watertight():
    tris = _box(0, 0, 0, 20, 20, 20)[:-2]           # one face missing
    w = analysis.watertight(tris)
    assert not w["ok"] and w["boundary_edges"] == 4
    r = analysis.print_check(tris)
    assert r["checks"][0]["status"] == "fail"


def test_a_t_shape_has_overhangs_that_are_highlighted():
    stem = _box(8, 8, 0, 4, 4, 20)
    top = _box(0, 0, 20, 20, 20, 4)               # its underside hangs
    r = analysis.print_check(stem + top)
    over = next(c for c in r["checks"] if c["name"] == "Overhangs")
    assert over["status"] in ("warn", "fail")
    assert r["overhang_tris"]
    assert all(all(v[2] == 20 for v in t) for t in r["overhang_tris"])
    # two separate boxes: the whole underside (400) hangs; the surface
    # is both boxes' area, the stem's plate face included
    assert r["overhang_fraction"] == pytest.approx(
        400 / ((2 * 400 + 4 * 80) + (4 * 80 + 2 * 16)), rel=0.01)


def test_a_thin_plate_is_measured():
    r = analysis.print_check(_box(0, 0, 0, 30, 30, 0.4), min_wall=0.8)
    wall = next(c for c in r["checks"] if c["name"] == "Wall thickness")
    assert wall["status"] == "fail"                # under 60 % of it
    assert r["thinnest"] == pytest.approx(0.4, abs=0.01)
    borderline = analysis.print_check(_box(0, 0, 0, 30, 30, 0.6),
                                      min_wall=0.8)
    assert next(c for c in borderline["checks"]
                if c["name"] == "Wall thickness")["status"] == "warn"
    thick = analysis.print_check(_box(0, 0, 0, 30, 30, 3.0), min_wall=0.8)
    assert next(c for c in thick["checks"]
                if c["name"] == "Wall thickness")["status"] == "pass"


def test_a_tall_pin_warns_about_its_footprint():
    r = analysis.print_check(_box(0, 0, 0, 3, 3, 60))
    foot = next(c for c in r["checks"] if c["name"] == "Footprint")
    assert foot["status"] == "warn"


# --------------------------------------------------------- interference
def test_interference_states():
    a = _box(0, 0, 0, 10, 10, 10)
    overlapping = _box(5, 5, 5, 10, 10, 10)
    touching = _box(10, 0, 0, 10, 10, 10)
    apart = _box(30, 0, 0, 10, 10, 10)
    inner = _box(2, 2, 2, 4, 4, 4)
    out = analysis.interference([("A", a), ("Overlap", overlapping),
                                 ("Touch", touching), ("Apart", apart),
                                 ("Inner", inner)])
    by_pair = {(p["a"], p["b"]): p for p in out}
    assert by_pair[("A", "Overlap")]["status"] == "intersect"
    assert by_pair[("A", "Overlap")]["points"]
    assert by_pair[("A", "Touch")]["status"] == "clear"
    assert by_pair[("A", "Apart")]["status"] == "clear"
    assert by_pair[("A", "Inner")]["status"] == "contains"
    assert by_pair[("Apart", "Inner")]["status"] == "clear"
    assert by_pair[("Overlap", "Inner")]["status"] == "intersect"  # 5..6
    assert len(out) == 10


# ------------------------------------------------------- the GUI / MCP
@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    yield win
    win._dirty = False
    win.close()


def test_dialogs_open_and_the_print_check_highlights(window):
    from khervecad.analysis_dialog import open_analysis
    model = window.model
    stem = model.add_node("cube", dict(width=4.0, depth=4.0, height=20.0,
                                       x=8.0, y=8.0))
    model.add_node("cube", dict(width=20.0, depth=20.0, height=4.0, z=20.0))
    window.builder.active_tree().select_nodes([stem])
    mass = open_analysis(window, "mass")
    assert "Volume" in mass.browser.toPlainText()
    mass.close()
    check = open_analysis(window, "print", nodes=list(model.root.children))
    assert "Overhangs" in check.browser.toPlainText()
    check.show_box.setChecked(True)
    assert window.view3d.highlight_mesh
    check.close()
    assert window.view3d.highlight_mesh == window._highlight_tris()
    inter = open_analysis(window, "interference", nodes=[])
    text = inter.browser.toPlainText()
    assert "clear" in text or "INTERSECT" in text
    inter.close()


def test_mcp_tools_report(window):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(window)
    model = window.model
    a = model.add_node("cube", dict(width=10.0, depth=10.0, height=10.0))
    b = model.add_node("cube", dict(width=10.0, depth=10.0, height=10.0,
                                    x=5.0))
    props = ex.execute("mass_properties", {"node_ids": [a.id],
                                           "material": "Steel"})
    assert props["volume_mm3"] == pytest.approx(1000.0)
    assert props["mass_g"] == pytest.approx(7.85)
    check = ex.execute("check_printability", {"node_ids": [a.id]})
    assert check["summary"] == "pass"
    inter = ex.execute("check_interference", {"node_ids": [a.id, b.id]})
    assert inter["pairs"][0]["status"] == "intersect"
    everything = ex.execute("check_interference", {})
    assert len(everything["pairs"]) == 1
