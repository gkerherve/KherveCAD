"""Sharp-edge check, fits / clearances and the tolerance stack-up.

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

from khervecad import edgecheck, fitcheck, mesh
from khervecad.model import CadNode


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _cube(**p):
    return mesh.tessellate(CadNode("cube", params=dict(
        width=10.0, depth=10.0, height=10.0, **p)))


# ------------------------------------------------------------- Qt-free
def test_a_box_has_twelve_sharp_edges_and_a_chamfer_none():
    r = edgecheck.sharp_edges(_cube())
    assert r["status"] == "warn" and r["count"] == 12
    assert r["length"] == pytest.approx(120.0)
    assert r["tris"]
    # a 45° chamfer's creases meet at 135°: not sharper than 135
    assert edgecheck.sharp_edges(_cube(), face_angle=89.0)["count"] == 0


def test_iso_fit_limits_and_classification():
    assert fitcheck.fit_limits("H7/g6", 10) == pytest.approx((0.005, 0.029))
    assert fitcheck.fit_limits("H7/h6", 25) == pytest.approx((0.0, 0.034))
    assert fitcheck.classify(10, 0.015)["fit"] == "H7/g6"
    assert fitcheck.classify(10, 0.2)["fit"] == "H11/c11"
    assert fitcheck.classify(10, -0.02)["fit"] in ("H7/p6", "H7/s6")


def test_stackup_worst_case_and_rss():
    notes = [
        {"type": "dim", "kind": "horizontal", "a": [0, 0], "b": [20, 0],
         "tol_plus": "0.1", "tol_minus": "0.1"},
        {"type": "dim", "kind": "horizontal", "a": [0, 0], "b": [30, 0],
         "tol_plus": "±0.1"},
        {"type": "text", "text": "hello"},
        {"type": "dim", "kind": "horizontal", "a": [0, 0], "b": [45, 0],
         "tol_plus": "0.05", "tol_minus": "0.05"},
    ]
    r = fitcheck.stackup(notes, [3, {"index": 0, "sign": -1},
                                 {"index": 1, "sign": -1}], [-0.5, 0.5])
    assert r["nominal"] == pytest.approx(-5.0)
    assert r["status"] == "fail"
    r = fitcheck.stackup(notes, [3, {"index": 0, "sign": -1},
                                 {"index": 1, "sign": -1}], [-5.2, -4.8])
    assert (r["worst_min"], r["worst_max"]) == pytest.approx((-5.25, -4.75))
    assert r["rss_max"] - r["rss_min"] == pytest.approx(
        2 * (0.1 ** 2 * 2 + 0.05 ** 2) ** 0.5)
    assert r["status"] == "warn"           # only RSS fits ±0.2
    with pytest.raises(ValueError):
        fitcheck.stackup(notes, [2])


# ------------------------------------------------------- window / MCP
@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    yield win
    win._dirty = False
    win.close()


@pytest.fixture
def ex(window):
    from khervecad.mcp_tools import McpToolExecutor
    return McpToolExecutor(window)


def test_mcp_sharp_edges_then_fillet_them(window, ex):
    a = window.model.add_node("cube", dict(width=10.0, depth=10.0,
                                           height=10.0))
    out = ex.execute("check_sharp_edges", {"node_ids": [a.id],
                                           "highlight": True})
    assert out["count"] == 12 and out["status"] == "warn"
    assert window.view3d.highlight_mesh
    seeds = out["per_node"][0]["fillet_seeds"]
    assert len(seeds) == 12
    fil = ex.execute("fillet_edges", {"node_id": a.id, "edges": seeds,
                                      "radius": 1.0})
    assert fil["edges"] == 12


def test_dialogs_open_fillet_and_note(window):
    from khervecad.engcheck_dialog import open_check
    model = window.model
    a = model.add_node("cube", dict(width=10.0, depth=10.0, height=10.0))
    dlg = open_check(window, "sharp", nodes=[a])
    assert "12 sharp" in dlg.browser.toPlainText()
    dlg.fillet()
    assert a.parent.type == "fillet" and len(a.parent.params["edges"]) == 12
    dlg.add_note()
    notes = model.drawing["notes"]
    assert any(n.get("text") == edgecheck.NOTE_TEXT for n in notes)
    dlg.close()
    window._blueprint.close()
    b = model.add_node("cube", dict(width=10.0, depth=10.0, height=10.0,
                                    x=10.05))
    fit = open_check(window, "fit", nodes=[a.parent, b])
    assert "Clearances" in fit.browser.toPlainText()
    fit.close()


def test_mcp_fits_pin_in_bore(window, ex):
    model = window.model
    plate = model.add_node("cube", dict(width=10.0, depth=10.0,
                                        height=10.0, x=-5.0, y=-5.0))
    gap = model.add_node("cube", dict(width=10.0, depth=10.0, height=10.0,
                                      x=5.05, y=-5.0))
    out = ex.execute("check_fits", {"node_ids": [plate.id, gap.id],
                                    "clearance": 0.1})
    pair = out["pairs"][0]
    assert pair["gap"] == pytest.approx(0.05, abs=1e-6)
    assert pair["status"] == "warn"
    # a Ø9.98 pin in a Ø10 bore: 0.02 diametral = H7/g6
    bore = model.add_node("difference", {})
    model.add_node("cube", dict(width=20.0, depth=20.0, height=10.0,
                                x=-10.0, y=-10.0), parent=bore)
    model.add_node("cylinder", dict(r=5.0, h=30.0, z=-10.0), parent=bore)
    pin = model.add_node("cylinder", dict(r=4.99, h=20.0, z=-5.0))
    out = ex.execute("check_fits", {"node_ids": [bore.id, pin.id]})
    info = out["pairs"][0]
    assert "pin" in info
    out = ex.execute("check_fits", {"node_ids": [bore.id, pin.id],
                                    "nominal": 10,
                                    "diametral_clearance": 0.02})
    assert out["fit"]["fit"] == "H7/g6"


def test_mcp_stackup_reads_the_saved_sheet(window, ex):
    window.model.drawing = {"notes": [
        {"type": "dim", "kind": "vertical", "a": [0, 0], "b": [0, 12],
         "tol_plus": "0.2", "tol_minus": "0.1", "view": "v1"}]}
    out = ex.execute("tolerance_stackup", {"limits": [11, 13]})
    assert out["worst_max"] == pytest.approx(12.2)
    assert out["status"] == "pass"
    assert out["dimensions"][0]["nominal"] == 12.0


# ------------------------------------------------------------- welds
def test_weld_joint_types_and_advice():
    from khervecad import weldcheck
    base = ((0, 0, 0), (100, 50, 5))            # 5 mm plate
    web = ((40, 0, 5), (45, 50, 60))            # 5 mm upright on it
    j = weldcheck.joint_of(base, web)
    assert j["joint"] == "T" and j["seam"] == pytest.approx(50)
    assert weldcheck.joint_of(base, ((0, 0, 5), (100, 50, 8)))["joint"] \
        == "lap"
    assert weldcheck.joint_of(base, ((100, 0, 0), (200, 50, 5)))[
        "joint"] == "butt"
    adv = weldcheck.advise("a", "Stainless steel", "b", "Stainless steel",
                           dict(j, thickness=2.0))
    assert adv["process"] == "TIG" and adv["size"] == 2.0
    adv = weldcheck.advise("a", "Steel", "b", "Steel", j)
    assert adv["process"] == "MIG" and adv["size"] == 3.0
    assert weldcheck.advise("a", "Aluminium", "b", "Steel", j)[
        "status"] == "fail"


def test_mcp_welds_record_and_judge(window, ex):
    model = window.model
    base = model.add_node("cube", dict(width=100.0, depth=50.0,
                                       height=5.0))
    web = model.add_node("cube", dict(width=5.0, depth=50.0, height=55.0,
                                      x=40.0, z=5.0))
    out = ex.execute("check_welds", {"node_ids": [base.id, web.id]})
    assert out["candidates"] == 1
    assert out["joints"][0]["joint"]["joint"] == "T"
    got = ex.execute("set_weld", {"a": base.id, "b": web.id,
                                  "process": "MIG", "joint": "T",
                                  "size": 9.0, "sides": "both sides"})
    assert got["summary"] == "fail"            # 9 mm leg on 5 mm plate
    got = ex.execute("set_weld", {"a": base.id, "b": web.id,
                                  "process": "MIG", "joint": "T",
                                  "size": 3.0, "note": True})
    assert got["summary"] == "pass"
    assert "WELD 1" in got["blueprint_note"]
    assert base.params["welds"][0]["with"] == web.name
    window._blueprint.close()
    from khervecad.engcheck_dialog import open_check
    dlg = open_check(window, "weld", nodes=[base, web])
    assert "recorded" in dlg.browser.toPlainText()
    dlg.close()
