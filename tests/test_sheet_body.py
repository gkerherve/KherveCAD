"""Sheet metal bodies and the SHEET METAL tab (sheet_body.py,
sheet_metal_ops.py, sheet_metal_ui.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import shutil
import subprocess

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import scadparse, sheet_body as sb, sheet_metal_ops as ops
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _vol(tris):
    return sum(sb._dot(a, sb._cross(b, c)) for a, b, c in tris) / 6


def _box(tris):
    return [(min(v[k] for t in tris for v in t),
             max(v[k] for t in tris for v in t)) for k in range(3)]


def _body(**kw):
    p = {k: v for k, v in sb._DEFAULTS.items()}
    p.update(kw)
    return sb.build(p)


def test_a_box_of_four_flanges_measures_its_outline_outside():
    body = _body(flanges=[[0, i, 20, 90] for i in range(4)])
    assert not body.errors
    tris = sb.folded_tris(body)
    box = _box(tris)
    for (lo, hi), (want_lo, want_hi) in zip(box, ((0, 100), (0, 60),
                                                 (0, 20))):
        assert abs(lo - want_lo) < 1e-6 and abs(hi - want_hi) < 1e-6
    # the folded volume is the flat blank's (allowance from K = 0.44
    # against the true mid fibre: within a percent)
    pat = sb.flat_pattern(body)
    assert len(pat["bend_table"]) == 4
    flat = _vol(sb.flat_tris(pat, body.t))
    assert abs(_vol(tris) - flat) / flat < 0.01


def test_the_flat_pattern_adds_each_bend_allowance():
    body = _body(flanges=[[0, 0, 20, 90]])
    pat = sb.flat_pattern(body)
    t, r, k = 2.0, 2.0, 0.44
    ba = math.pi / 2 * (r + k * t)
    setback = r + t
    want = 60 - setback + ba + 20 - setback
    assert abs(pat["height"] - want) < 1e-6
    assert abs(pat["bend_table"][0]["allowance"] - ba) < 1e-4


def test_fold_hem_contour_chain_and_down():
    fold = _body(folds=[[30, -10, 30, 70, 90]])
    assert not fold.errors
    tris = sb.folded_tris(fold)
    assert abs(sb.flat_pattern(fold)["width"] - 100) < 1e-6   # the blank
    assert _box(tris)[2][1] > 25                               # stood up
    hem = sb.folded_tris(_body(hems=[[0, 0, 10]]))
    assert abs(_box(hem)[2][1] - 5.0) < 1e-6                   # t + gap + t
    chan = sb.folded_tris(_body(contour=[[0, 30], [0, 0], [50, 0],
                                         [50, 30]]))
    assert [round(v) for v in sum(_box(chan), ())] == [0, 50, 0, 60, 0, 30]
    down = sb.folded_tris(_body(flanges=[[0, 0, 20, -90]]))
    assert abs(_box(down)[2][0] + 18) < 1e-6
    chain = _body(flanges=[[0, 0, 20, 90], [1, 2, 15, 90]])
    assert not chain.errors and len(chain.bends) == 2


def test_errors_name_the_problem():
    assert _body(flanges=[[5, 0, 20, 90]]).errors
    assert _body(flanges=[[0, 0, 1, 90]]).errors          # too short


def test_perforation_keeps_clear_of_edges_and_bends():
    body = _body(flanges=[[0, 0, 20, 90]])
    pat = sb.flat_pattern(body, [4, 8])
    assert pat["holes"]
    bend_y = pat["bend_table"][0]["start"][1]
    for x, y, d in pat["holes"]:
        assert abs(y - bend_y) > 4                # margin + radius
        assert 4 - 1e-6 <= x <= 96 + 1e-6


def test_document_round_trip_rules_and_openscad(app, tmp_path):
    m = DocumentModel()
    b = ops.insert_base(m)
    ops.add_flange(m, b, 0, 0, 20, 90)
    ops.add_flange(m, b, 0, 2, 20, 90, then=[(10, 90)])
    ops.add_hem(m, b, 0, 1, 8)
    ops.perforate(m, b, 4, 8)
    ops.set_rule(m, "Steel 1.5", thickness=1.5, bend_radius=1.0)
    ops.apply_rule(m, b, "Steel 1.5")
    assert b.params["thickness"] == "smr_Steel_1_5_t"
    assert not validate(m.root)
    d = ops.describe(m, b)
    assert d["thickness"] == 1.5 and d["bends"] == 4 and not d["errors"]
    code = m.to_scad()
    root, _w = scadparse.parse_scad(code)
    m2 = DocumentModel()
    m2.root = root
    assert m2.to_scad().split("\n", 3)[3] == code.split("\n", 3)[3]
    ops.set_flat(m, b, True)
    assert ops.describe(m, b)["flat"]
    exe = shutil.which("openscad")
    if exe:
        path = tmp_path / "s.scad"
        path.write_text(m.to_scad())
        r = subprocess.run([exe, "-o", str(tmp_path / "s.stl"), str(path)],
                           capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stderr[-500:]


def test_convert_a_plate_and_the_old_part(app):
    m = DocumentModel()
    cube = m.add_node("cube", dict(size=[80, 50, 3], center=False))
    body = ops.convert(m, cube)
    assert body.type == sb.KIND and body.params["thickness"] == 3
    assert cube.parent is None
    old = m.add_node("sheet_metal", {})
    body2 = ops.convert(m, old)
    assert len(body2.params["flanges"]) == 2
    upright = m.add_node("cube", dict(size=[80, 2, 50]))
    body3 = ops.convert(m, upright)
    assert body3.parent.type == "rotate"
    with pytest.raises(ValueError):
        ops.convert(m, m.add_node("sphere", {}))


def test_exports(tmp_path):
    body = _body(flanges=[[0, 0, 20, 90], [0, 2, 20, -90]])
    pat = sb.flat_pattern(body, [3, 6])
    path = sb.flat_dxf(pat, tmp_path / "f.dxf")
    text = open(path).read()
    assert "BEND_UP" in text and "BEND_DOWN" in text and "CIRCLE" in text
    csv = sb.bend_table_csv(pat).splitlines()
    assert len(csv) == 3 and csv[0].startswith("bend,")


def test_the_tab_builds_a_part_by_its_buttons(app, tmp_path):
    from khervecad import sheet_metal_ui as ui
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        win.model.clear()
        acts = {a.data(): a for a in ui.actions(win)}
        ui.ANSWERS.update({
            "sm_flange": {"height": 25.0, "angle": 90.0},
            "sm_flange_edge": (0, 0),
            "sm_hem": {"length": 8.0}, "sm_hem_edge": (0, 2),
            "sm_perforate": {"diameter": 4.0, "pitch": 8.0},
            "sm_fold": {"x1": 20, "y1": -5, "x2": 20, "y2": 65}})
        acts["sm_base"].trigger()
        body = next(n for n in win.model.root.walk() if n.type == sb.KIND)
        win.builder.active_tree().select_nodes([body])
        for key in ("sm_flange", "sm_hem", "sm_perforate", "sm_fold"):
            acts[key].trigger()
        assert len(body.params["flanges"]) == 1
        assert len(body.params["hems"]) == 1
        assert len(body.params["folds"]) == 1
        assert body.params["perforate"]
        acts["sm_unfold"].trigger()
        assert body.params["flat"]
        acts["sm_refold"].trigger()
        assert not body.params["flat"]
        assert ui.export_dxf(win, str(tmp_path / "a.dxf"))
        assert ui.export_bend_table(win, str(tmp_path / "a.csv"))
        comp = ui.flat_pattern(win)
        assert comp is not None
        assert not ops.describe(win.model, body)["errors"]
    finally:
        ui.ANSWERS.clear()
        win._dirty = False
        win.close()


def test_every_tab_icon_is_painted():
    from khervecad import icons_cad
    from khervecad.sheet_metal_ui import COMMANDS
    for style in ("Fusion", "SolidWorks"):
        for key in COMMANDS:
            assert icons_cad.icon(key, style) is not None, (key, style)


def test_mcp_builds_a_box_and_exports(app, tmp_path):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    ex = McpToolExecutor(win)
    try:
        out = ex.execute("sheet_metal", dict(
            action="create", outline=[[0, 0], [120, 0], [120, 80], [0, 80]],
            thickness=1.5, bend_radius=1.5))
        assert "error" not in out, out
        nid = out["id"]
        for edge in range(4):
            out = ex.execute("sheet_metal", dict(action="flange", node_id=nid,
                                                 edge=edge, height=30))
            assert not out["errors"], out
        out = ex.execute("sheet_metal", dict(
            action="path_flange", node_id=nid, panel=1, edge=2,
            segments=[[10, 90]]))
        assert out["bends"] == 5 and not out["errors"]
        out = ex.execute("sheet_metal", dict(action="set_rule", rule="Alu",
                                             thickness=2, node_id=nid))
        assert "Alu" in out["rules"]
        out = ex.execute("sheet_metal", dict(action="state", node_id=nid))
        assert out["thickness"] == 2 and out["rule"] == "Alu"
        csv = ex.execute("sheet_metal", dict(action="export_bend_table",
                                             node_id=nid))["csv"]
        assert csv.count("\n") == 6
        path = str(tmp_path / "b.dxf")
        assert ex.execute("sheet_metal", dict(
            action="export_dxf", node_id=nid, path=path))["path"] == path
        bad = ex.execute("sheet_metal", dict(action="flange", node_id=nid,
                                             panel=9, edge=0, height=10))
        assert "error" in bad
        assert ex.execute("sheet_metal", dict(action="state",
                                              node_id=nid))["bends"] == 5
    finally:
        win._dirty = False
        win.close()
