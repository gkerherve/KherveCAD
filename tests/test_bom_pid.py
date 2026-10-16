"""Bill of materials, P&ID and the Blueprint parts list.

Run with: python -m pytest tests/  (offscreen Qt).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import os
import sys
import zipfile
from pathlib import Path
from xml.dom import minidom

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QApplication

from khervecad import bom, document, pid, pid_render, pid_symbols, scadparse
from khervecad.mcp_server import IMAGE_KEY, valid_png_b64
from khervecad.mcp_tools import McpToolExecutor
from khervecad.model import DocumentModel

PROGRAM = """
module Pump_unit() {
  color([0.8, 0.47, 0.24]) translate([0, 0, 0]) cylinder(r = 10, h = 100);  // Copper tube
  for (i = [0 : 3]) translate([i * 20, 0, 0]) cube([2, 30, 40]);  // Aluminium fin
  color("#202020") cube([50, 40, 5]);  // Base plate
}
module Tank_unit() {
  cylinder(r = 30, h = 80);  // Tank shell
}
Pump_unit();  // Pump unit
translate([100, 0, 0]) Tank_unit();  // Tank unit
"""


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    m = DocumentModel()
    root, _w = scadparse.parse_scad(PROGRAM)
    m.root = root
    return m


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    win._confirm_discard = lambda: True
    root, _w = scadparse.parse_scad(PROGRAM)
    win.model.root = root
    win.model.structure_changed.emit()
    yield win
    for attr in ("_pid_window", "_bom_window", "_blueprint"):
        w = getattr(win, attr, None)
        if w is not None:
            w.close()
    win._dirty = False
    win.close()


def call(ex, tool, **params):
    result = ex.execute(tool, params)
    assert "error" not in result, f"{tool}: {result.get('error')}"
    return result


# ── BOM ────────────────────────────────────────────────────────────

def _line(b, name):
    for ln in b.flat():
        if ln.name == name:
            return ln
    raise AssertionError(f"no line {name}: {[x.name for x in b.flat()]}")


def test_parts_and_their_labelled_components(model):
    b = bom.build(model)
    names = [ln.name for ln in b.lines]
    assert names == ["Pump unit", "Tank unit"]
    pump = _line(b, "Pump unit")
    assert pump.kind == "part"
    assert {c.name for c in pump.children} == {
        "Copper tube", "Aluminium fin", "Base plate"}
    assert _line(b, "Pump unit").values["item"] == "1"
    assert _line(b, "Base plate").values["item"].startswith("1.")


def test_a_loop_counts_every_iteration(model):
    fin = _line(bom.build(model), "Aluminium fin")
    assert fin.qty == 4 and fin.unit == "pc"


def test_materials_from_words_and_colours(model):
    b = bom.build(model)
    assert _line(b, "Aluminium fin").get("material") == "Aluminium"
    tube = _line(b, "Copper tube")
    assert tube.get("material") == "Copper" and not tube.estimated
    plate = _line(b, "Base plate")
    assert plate.estimated                     # guessed from the colour
    assert "black" in plate.get("finish")


def test_a_tube_is_listed_by_length_in_metres(model):
    tube = _line(bom.build(model), "Copper tube")
    assert tube.unit == "m" and tube.qty == pytest.approx(0.1, abs=1e-3)


def test_descriptions_say_what_the_node_is(model):
    b = bom.build(model)
    assert "plate 5 mm thick" in _line(b, "Base plate").get("description")
    assert "cylinder Ø60 × 80" in _line(b, "Tank shell").get("description")


def test_mass_is_volume_times_density(model):
    plate = _line(bom.build(model), "Base plate")
    vol_cm3 = 50 * 40 * 5 / 1000.0
    want = vol_cm3 * bom.DENSITY[plate.get("material")] / 1000.0
    assert plate.get("mass_each") == pytest.approx(want, rel=0.02)
    pump = _line(bom.build(model), "Pump unit")
    assert pump.get("mass_total") == pytest.approx(sum(
        c.get("mass_total") for c in pump.children), rel=1e-6)


def test_typed_fields_live_on_the_nodes_and_round_trip(model, tmp_path):
    b = bom.build(model)
    plate = _line(b, "Base plate")
    bom.set_fields(plate.nodes, {"material": "Stainless steel",
                                 "supplier": "Acme", "cost": 12.5,
                                 "part_no": "BP-1"})
    b = bom.build(model)
    plate = _line(b, "Base plate")
    assert plate.get("material") == "Stainless steel"
    assert not plate.estimated
    assert plate.get("supplier") == "Acme"
    assert plate.get("part_no") == "BP-1"
    assert plate.get("cost_total") == pytest.approx(12.5)
    path = tmp_path / "doc.kcad"
    document.save_kcad(model, str(path))
    again = DocumentModel()
    document.load_kcad(again, str(path))
    assert _line(bom.build(again), "Base plate").get("supplier") == "Acme"
    with pytest.raises(KeyError):
        bom.set_fields(plate.nodes, {"colour": "red"})


def test_a_bom_field_is_not_geometry(model):
    from khervecad import mesh
    comp = model.components()[0]
    before = mesh.exact_key(comp)
    bom.set_fields([comp], {"supplier": "Acme"})
    assert mesh.exact_key(comp) == before


def test_exports(model, tmp_path):
    b = bom.build(model)
    for ext in (".csv", ".html", ".json", ".xlsx"):
        out = tmp_path / f"bom{ext}"
        bom.export(b, out)
        assert out.stat().st_size > 200
    data = json.loads((tmp_path / "bom.json").read_text())
    assert data["totals"]["lines"] == len(b.flat())
    with zipfile.ZipFile(tmp_path / "bom.xlsx") as z:
        for name in z.namelist():
            minidom.parseString(z.read(name))        # well-formed XML
        sheet = z.read("xl/worksheets/sheet1.xml").decode()
    assert "Aluminium fin" in sheet and "TOTAL" in sheet
    assert "Copper tube" in (tmp_path / "bom.csv").read_text("utf-8-sig")
    with pytest.raises(ValueError):
        bom.export(b, tmp_path / "bom.doc")


def test_bom_mcp_tool(window, tmp_path):
    ex = McpToolExecutor(window)
    got = call(ex, "bill_of_materials")
    assert got["totals"]["lines"] >= 5
    item = next(r["item"] for r in got["rows"] if r["name"] == "Base plate")
    set_ = call(ex, "bill_of_materials", action="set", item=item,
                fields={"supplier": "Acme", "cost": 3})
    assert set_["line"]["supplier"] == "Acme"
    out = tmp_path / "b.xlsx"
    assert call(ex, "bill_of_materials", action="export",
                path=str(out))["written"]
    assert out.exists()
    err = ex.execute("bill_of_materials", {"action": "set", "item": "9.9",
                                           "fields": {"notes": "x"}})
    assert "error" in err


def test_bom_window_edits_a_cell(window):
    from khervecad import bom_window
    w = bom_window.open_bom(window)
    keys = [k for k, _h in bom.COLUMNS]
    found = w.tree.findItems("Base plate", Qt.MatchRecursive,
                             keys.index("name"))
    assert found
    item = found[0]
    item.setText(keys.index("supplier"), "Acme")
    QApplication.processEvents()
    line = _line(bom.build(window.model), "Base plate")
    assert line.get("supplier") == "Acme"


# ── P&ID ───────────────────────────────────────────────────────────

def test_every_symbol_draws_and_its_ports_turn(app):
    for kind, sym in pid_symbols.SYMBOLS.items():
        for rot in (0, 90, 180, 270):
            prims = pid_symbols.placed_prims(kind, 50, 50, rot, rot == 90)
            assert prims, kind
            for name, ((x, y), d) in pid_symbols.port_points(
                    kind, 50, 50, rot).items():
                assert d in "lrud"
    # a quarter turn clockwise on the sheet: left becomes up
    (pt, d), = [v for k, v in pid_symbols.port_points(
        "gate_valve", 0, 0, 90).items() if k == "in"]
    assert d == "u" and pt == pytest.approx((0, -6))


def test_tags_number_by_prefix():
    d = pid.Diagram()
    assert d.add_symbol("pump", 50, 50)["tag"] == "P-101"
    assert d.add_symbol("pump_inline", 80, 50)["tag"] == "P-102"
    assert d.add_symbol("ball_valve", 80, 80)["tag"] == "V-101"
    with pytest.raises(pid.PidError):
        d.add_symbol("teapot", 0, 0)


def test_routes_are_square_and_avoid_symbols():
    d = pid.Diagram()
    coil = d.add_symbol("coil", 52.5, 70)
    eev = d.add_symbol("expansion_valve", 105, 172.5, mirror=True)
    ln = d.connect({"symbol": eev["id"], "port": "out"},
                   {"symbol": coil["id"], "port": "in"})
    pts = ln["points"]
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in zip(pts, pts[1:]))
    box = d.box(coil)
    for a, b in zip(pts[1:-2], pts[2:-1]):          # the middle legs
        assert not pid._seg_hits_box(a, b, box)
    # it enters the coil from the left, as the port faces
    assert pts[-2][0] < pts[-1][0]


def test_moving_a_symbol_drags_its_lines():
    d = pid.Diagram()
    a = d.add_symbol("pump", 50, 50)
    b = d.add_symbol("tank", 150, 60)
    ln = d.connect({"symbol": a["tag"], "port": "out"},
                   {"symbol": b["tag"], "port": "l_hi"},
                   service="HWF", size="28", material="CU")
    assert ln["number"] == "28-HWF-001-CU"
    d.move(a["id"], 50, 100)
    assert ln["points"][0] == list(d.ports(a)["out"][0])


def test_check_and_schedules():
    d = pid.Diagram()
    p = d.add_symbol("pump_inline", 50, 50)
    v = d.add_symbol("ball_valve", 100, 50)
    t = d.add_symbol("instrument", 75, 30, tag="PT-301")
    assert any("not connected" in x for x in d.check())
    d.connect({"symbol": p["id"], "port": "out"},
              {"symbol": v["id"], "port": "in"}, service="HWR")
    sch = d.schedules()
    assert [r["tag"] for r in sch["equipment"]] == ["P-101"]
    assert [r["tag"] for r in sch["valves"]] == ["V-101"]
    assert sch["instruments"][0]["function"] == \
        "Pressure transmitter"
    assert sch["lines"][0]["service"] == "Heating water return"
    d.add_symbol("ball_valve", 120, 50, tag="V-101")
    assert any("used 2 times" in x for x in d.check())
    del t


def test_a_tee_is_a_dot():
    d = pid.Diagram()
    a = d.add_symbol("pump_inline", 50, 50)
    b = d.add_symbol("tank", 150, 50)
    main = d.connect({"symbol": a["id"], "port": "out"},
                     {"symbol": b["id"], "port": "l_hi"})
    g = d.add_symbol("pressure_gauge", 80, 30)
    y = main["points"][0][1]
    d.connect({"symbol": g["id"], "port": "pv"}, {"x": 80, "y": y},
              kind="secondary", arrow=False)
    assert (80.0, y) in d.junctions()


def test_drawing_exports(app, tmp_path):
    d = pid.Diagram()
    a = d.add_symbol("compressor", 60, 60)
    b = d.add_symbol("plate_hx", 120, 60)
    d.connect({"symbol": a["id"], "port": "discharge"},
              {"symbol": b["id"], "port": "a_in"}, service="RHG")
    d.add_note("NOTE", 30, 150)
    for ext in (".pdf", ".svg", ".png", ".dxf"):
        out = tmp_path / f"p{ext}"
        pid_render.export(d, out)
        assert out.stat().st_size > 500, ext
    assert "PROCESS" in (tmp_path / "p.dxf").read_text()
    pid_render.export_schedules(d, tmp_path / "s.xlsx")
    pid_render.export_schedules(d, tmp_path / "s.csv")
    assert "EQUIPMENT" in (tmp_path / "s.csv").read_text("utf-8-sig")


def test_diagram_is_saved_in_the_document(tmp_path, model):
    d = pid.Diagram()
    d.add_symbol("pump", 50, 50)
    model.pid = d.to_dict()
    path = tmp_path / "doc.kcad"
    document.save_kcad(model, str(path))
    again = DocumentModel()
    document.load_kcad(again, str(path))
    assert pid.Diagram(again.pid).symbols[0]["tag"] == "P-101"
    again.clear()
    assert again.pid is None


def test_from_model_recognises_parts(app):
    m = DocumentModel()
    root, _w = scadparse.parse_scad(
        "module Compressor() { cube(10); }\nmodule Circulating_pump() "
        "{ cube(10); }\nCompressor();  // Compressor\n"
        "Circulating_pump();  // Circulating pump\n")
    m.root = root
    d, found = pid.from_model(m)
    kinds = {k for _n, k in found}
    assert {"compressor", "pump_inline"} <= kinds


def _mouse(canvas, kind, x, y, button=Qt.LeftButton):
    p = QPoint(int(canvas._pan.x() + x * canvas._zoom),
               int(canvas._pan.y() + y * canvas._zoom))
    buttons = button if kind != QEvent.MouseButtonRelease else Qt.NoButton
    canvas.event(QMouseEvent(kind, QPointF(p), button, buttons,
                             Qt.NoModifier))


def _click(canvas, x, y):
    _mouse(canvas, QEvent.MouseButtonPress, x, y)
    _mouse(canvas, QEvent.MouseButtonRelease, x, y)


def test_window_place_connect_move_undo(window):
    pw = window.open_pid()
    pw.resize(1300, 900)
    QApplication.processEvents()
    c = pw.canvas
    c.place_kind = "pump"
    pw.set_tool("place")
    _click(c, 100, 100)
    c.place_kind = "tank"
    _click(c, 200, 100)
    d = pw.diagram
    assert [s["tag"] for s in d.symbols] == ["P-101", "TK-101"]
    pw.set_tool("connect")
    out = d.ports(d.symbols[0])["out"][0]
    inlet = d.ports(d.symbols[1])["l_hi"][0]
    _click(c, *out)
    _click(c, *inlet)
    assert len(pw.diagram.lines) == 1
    pw.set_tool("select")
    _mouse(c, QEvent.MouseButtonPress, 100, 100)
    _mouse(c, QEvent.MouseMove, 100, 140, Qt.NoButton)
    c.event(QMouseEvent(QEvent.MouseMove, QPointF(
        c._pan.x() + 100 * c._zoom, c._pan.y() + 140 * c._zoom),
        Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
    _mouse(c, QEvent.MouseButtonRelease, 100, 140)
    assert pw.diagram.symbols[0]["y"] == 140.0
    assert window.model.pid["symbols"][0]["y"] == 140.0
    pw.undo.undo()
    assert pw.diagram.symbols[0]["y"] == 100.0
    pw.undo.undo()
    assert not pw.diagram.lines
    c.selection = [pw.diagram.symbols[0]["id"]]
    pw.rotate_selected()
    assert pw.diagram.symbols[0]["rot"] == 90
    c.repaint()


def test_pid_mcp_tool(window):
    ex = McpToolExecutor(window)
    cat = call(ex, "pid", action="symbols")
    assert any(s["kind"] == "plate_hx" for s in cat["symbols"])
    added = call(ex, "pid", action="add", symbols=[
        {"kind": "compressor", "x": 60, "y": 80},
        {"kind": "plate_hx", "x": 130, "y": 80}])["added"]
    assert [a["tag"] for a in added] == ["C-101", "E-101"]
    made = call(ex, "pid", action="connect", lines=[
        {"from": "C-101.discharge", "to": "E-101.a_in",
         "service": "RHG", "size": "3/8", "material": "CU"}])
    assert made["lines"][0]["number"] == "3/8-RHG-001-CU"
    state = call(ex, "pid")
    assert len(state["symbols"]) == 2 and len(state["lines"]) == 1
    png = call(ex, "pid", action="render")
    assert valid_png_b64(png[IMAGE_KEY])
    assert window.model.pid["lines"]
    assert "error" in ex.execute("pid", {"action": "connect", "lines": [
        {"from": "C-101.nope", "to": "E-101.a_in"}]})


# ── Blueprint ──────────────────────────────────────────────────────

def test_blueprint_lists_parts_with_balloons(window):
    from khervecad import blueprint
    window._refresh_preview()
    board = blueprint.open_blueprint(window)
    board.add_bom(balloons=True)
    notes = board.scene.notes()
    lists = [n for n in notes if n.KIND == "bom"]
    assert lists and lists[0].data["style"] == "full"
    rows = lists[0].data["rows"]
    assert [r[0] for r in rows] == ["1", "2"]
    assert rows[0][2].startswith("Pump unit")
    balloons = [n for n in notes if n.KIND == "balloon"]
    assert sorted(b.data["number"] for b in balloons) == ["1", "2"]
    # balloons never sit on each other
    boxes = [b.sceneBoundingRect() for b in balloons]
    centres = [(b.mapToScene(QPointF(*b._ends()[1]))) for b in balloons]
    assert (centres[0] - centres[1]).manhattanLength() > 8
    assert boxes
    board.close()


def test_drawing_number_never_ends_in_a_double_dash():
    from khervecad.blueprint_scene import default_fields
    assert "--" not in default_fields("Air source heat pump 7 kW")["number"]
