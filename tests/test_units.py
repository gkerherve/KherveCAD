"""The document's display unit: a label on every readout, a factor for
what is physically dimensioned (mass, print time, STL/3MF), never a
rescale of the geometry.

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
import time
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtCore import QPointF
from PyQt5.QtWidgets import QApplication

from khervecad import analysis, document, drawing, units
from khervecad.engine import parse_mesh
from khervecad.model import DocumentModel


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    return win


@pytest.fixture
def ex(window):
    from khervecad.mcp_tools import McpToolExecutor
    return McpToolExecutor(window)


def call(ex, _tool, **params):
    result = ex.execute(_tool, params)
    assert "error" not in result, f"{_tool} failed: {result.get('error')}"
    return result


def _cube(model, size=10.0):
    return model.add_node("cube", dict(width=size, depth=size,
                                       height=size))


# ── the table ──────────────────────────────────────────────────────

def test_every_spelling_reaches_one_code():
    assert units.normalise("µm") == units.normalise("micron") == "um"
    assert units.normalise("Nanometres") == "nm"
    assert units.normalise("inches") == units.normalise('"') == "in"
    assert units.normalise("m") == "m"
    with pytest.raises(ValueError):
        units.normalise("furlong")
    assert units.coerce("furlong") == "mm"          # a hand-edited file


def test_factors_and_labels():
    assert units.to_mm("nm") == 1e-6
    assert units.to_mm("in") == 25.4
    assert units.symbol("um") == "µm"
    assert units.name("cm") == "centimetres"
    assert units.length(36.0600, "nm") == "36.06 nm"
    assert units.length(30.0, "mm") == "30 mm"
    # a real quantity never prints as 0
    assert units.tidy(4e-5) == "4e-05"
    assert units.cm3(1000.0, "mm") == pytest.approx(1.0)
    assert units.cm3(1.0, "cm") == pytest.approx(1.0)
    assert units.significant(5.23598e-13) == pytest.approx(5.23598e-13)
    assert [c for c, _l in units.choices()] == list(units.UNITS)
    assert units.printable("mm") and not units.printable("nm")


# ── the document ───────────────────────────────────────────────────

def test_the_unit_round_trips_through_kcad(app, tmp_path):
    model = DocumentModel()
    _cube(model)
    model.set_unit("nm")
    path = tmp_path / "particle.kcad"
    document.save_kcad(model, str(path))
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["version"] == document.FORMAT_VERSION >= 9
    assert saved["unit"] == "nm"
    other = DocumentModel()
    seen = []
    other.unit_changed.connect(seen.append)
    document.load_kcad(other, str(path))
    assert other.unit == "nm" and seen == ["nm"]
    # the geometry was never touched by the label
    [cube] = [n for n in other.root.walk() if n.type == "cube"]
    assert cube.params["width"] == 10.0


def test_an_old_file_opens_in_millimetres(app, tmp_path):
    path = tmp_path / "old.kcad"
    path.write_text(json.dumps({
        "format": "kcad", "version": 8,
        "tree": {"type": "root", "name": "root", "visible": True,
                 "params": {}, "children": []}}), encoding="utf-8")
    model = DocumentModel()
    model.unit = "cm"                        # a previous document's
    document.load_kcad(model, str(path))
    assert model.unit == "mm"
    path.write_text(path.read_text().replace(
        '"version": 8', '"version": 9, "unit": "parsec"'))
    document.load_kcad(model, str(path))
    assert model.unit == "mm"                # unknown: open, don't refuse


def test_changing_the_unit_is_one_undo_step(app):
    model = DocumentModel()
    _cube(model)
    app.processEvents()
    time.sleep(model.UNDO_MERGE_S + 0.05)    # its own step, not merged
    model.set_unit("um")
    app.processEvents()
    assert model.unit == "um"
    model.undo_stack.undo()
    assert model.unit == "mm"
    model.undo_stack.redo()
    assert model.unit == "um"
    with pytest.raises(ValueError):
        model.set_unit("cubit")


def test_new_document_and_examples_are_millimetres(window):
    window.model.set_unit("nm")
    window._dirty = False                # no "discard changes?" box
    window.new_document()
    assert window.model.unit == "mm"
    from khervecad.examples import load_example
    window.model.set_unit("m")
    load_example(window.model, lambda: DocumentModel().root)
    assert window.model.unit == "mm"


# ── the readouts ───────────────────────────────────────────────────

def test_status_bar_and_sketch_follow_the_unit(window):
    window.model.set_unit("nm")
    assert window._zoom_label.text().startswith("1 nm = ")
    window._cursor_moved(QPointF(1.0, 2.0))
    assert window._cursor_label.text().endswith("2.0 nm")
    window._show_dimensions([((0, 0, 0), (100, 0, 0), (0, 49.13, 0))])
    assert window._dims_label.text().endswith("nm")
    got = []
    window.scene.measure_changed.connect(got.append)
    window.scene._emit_measure(QPointF(0, 0), QPointF(3, 4))
    assert got[-1].startswith("distance: 5.00 nm")
    assert window.view2d._unit() == "nm"
    assert window._dirty                     # a document change
    actions = [a.text() for a in window.menuBar().actions()]
    edit = window.menuBar().actions()[actions.index("&Edit")].menu()
    assert "Document &Units..." in [a.text() for a in edit.actions()]


def test_mass_goes_through_true_cm3(app):
    from khervecad.analysis_dialog import mass_html
    props = analysis.mass_properties(
        [t for t in _box_tris(10.0)])
    html_mm = mass_html(props, "Steel", 20.0, "€", "mm")
    assert "1,000 mm³" in html_mm and "Print time" in html_mm
    html_nm = mass_html(props, "Steel", 20.0, "€", "nm")
    assert "nm³" in html_nm and "not estimated" in html_nm
    assert "7.85e-18 g" in html_nm           # 1000 nm³ of steel


def test_print_check_judges_the_part_at_its_real_size(app):
    started = time.monotonic()
    report = analysis.print_check(_box_tris(100.0), unit="nm")
    assert time.monotonic() - started < 5.0
    names = {c["name"]: c for c in report["checks"]}
    assert names["Scale"]["status"] == "warn"
    assert names["Wall thickness"]["status"] == "fail"
    assert "nm" in names["Wall thickness"]["message"]
    # the same box in mm prints fine, as before
    ok = analysis.print_check(_box_tris(100.0))
    assert ok["summary"] == "pass"
    assert "Scale" not in {c["name"] for c in ok["checks"]}


def test_blueprint_title_block_names_the_unit(window):
    from khervecad.blueprint_scene import BlueprintScene, mass_text
    scene = BlueprintScene()
    scene.unit = "um"
    scene.refresh_title()
    assert scene.title.data["units"] == "µm"
    cells = {c["key"]: c for c in drawing.title_block_cells(
        {}, "1:1", "A3", scene.title.data["units"])}
    assert cells["units"]["text"] == "µm"
    assert mass_text(1000.0, "Steel", "mm") == "7.85 g"
    assert mass_text(1000.0, "Steel", "nm").endswith(" g")
    lay = drawing.layout(_box_tris(10.0), views=("Front",), unit="in")
    assert lay["units"] == "in"


# ── MCP ────────────────────────────────────────────────────────────

def test_mcp_reports_and_sets_the_unit(ex, window):
    _cube(window.model)
    info = call(ex, "get_document_info")
    assert (info["unit"], info["units"]) == ("mm", "millimetres")
    assert info["bounds"]["size"] == info["bounds_mm"]["size"]
    assert call(ex, "set_render_options", unit="nm")["unit"] == "nm"
    info = call(ex, "get_document_info")
    assert info["units"] == "nanometres" and info["mm_per_unit"] == 1e-6
    assert info["bounds"]["size"] == pytest.approx([10, 10, 10])
    assert info["bounds_mm"]["size"] == pytest.approx([1e-5] * 3)
    assert "error" in ex.execute("set_render_options", {"unit": "cubit"})


def test_mcp_mass_in_a_nanometre_document(ex, window):
    node = _cube(window.model)
    window.model.set_unit("nm")
    out = call(ex, "mass_properties", node_ids=[node.id], material="Steel")
    assert out["unit"] == "nm" and out["volume"] == pytest.approx(1000.0)
    assert out["volume_mm3"] == pytest.approx(1e-15)
    assert out["mass_g"] == pytest.approx(7.85e-18)
    assert out["cost"] is None and out["print_time_h_rough"] is None
    assert "units_warning" in out
    window.model.set_unit("cm")
    out = call(ex, "mass_properties", node_ids=[node.id], material="Steel")
    assert out["mass_g"] == pytest.approx(7850.0)
    assert out["cost"] is not None


def test_stl_export_is_1to1_unless_scaled(ex, window, tmp_path):
    _cube(window.model)
    window.model.set_unit("cm")
    one = tmp_path / "one.stl"
    out = call(ex, "export_document", path=str(one))
    assert "1:1" in out["units_note"] and out["scale"] == 1.0
    assert _extent(parse_mesh(str(one))) == pytest.approx(10.0)
    real = tmp_path / "real.stl"
    out = call(ex, "export_document", path=str(real), scale_to_mm=True)
    assert out["scale"] == 10.0
    assert _extent(parse_mesh(str(real))) == pytest.approx(100.0)
    window.model.set_unit("mm")
    plain = call(ex, "export_document", path=str(tmp_path / "mm.stl"))
    assert "units_note" not in plain


def test_scaling_a_3mf_file(tmp_path):
    path = tmp_path / "part.3mf"
    model = (b'<?xml version="1.0"?><model unit="millimeter" '
             b'xmlns="http://schemas.microsoft.com/3dmanufacturing/'
             b'core/2015/02"><resources><object id="1"><mesh><vertices>'
             b'<vertex x="0" y="0" z="0"/><vertex x="10" y="0" z="0"/>'
             b'<vertex x="0" y="5" z="0"/></vertices><triangles>'
             b'<triangle v1="0" v2="1" v3="2"/></triangles></mesh>'
             b'</object></resources></model>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("3D/3dmodel.model", model)
        z.writestr("[Content_Types].xml", b"<Types/>")
    units.scale_mesh_file(str(path), 2.5)
    [tri] = parse_mesh(str(path))
    assert tri[1] == (25.0, 0.0, 0.0) and tri[2] == (0.0, 12.5, 0.0)
    with zipfile.ZipFile(path) as z:
        assert "[Content_Types].xml" in z.namelist()


def test_printables_text_names_the_unit(window):
    from khervecad import printables
    _cube(window.model)
    window.model.set_unit("nm")
    text = printables.default_description(window, "Quartz particle")
    assert "10 x 10 x 10 nm" in text and "1:1" in text
    form = printables.form_answers(window, title="Quartz particle")
    assert "10 x 10 x 10 nm" in form and "10 x 10 x 10 mm" in form
    window.model.set_unit("mm")
    assert printables.units_note(window.model) == ""


# ── helpers ────────────────────────────────────────────────────────

def _box_tris(s):
    """A closed, outward-wound s×s×s box standing on the plate."""
    tmp = [(0, 0, 0), (s, 0, 0), (s, s, 0), (0, s, 0),
           (0, 0, s), (s, 0, s), (s, s, s), (0, s, s)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5),
             (2, 3, 7, 6), (3, 0, 4, 7)]
    tris = []
    for a, b, c, d in faces:
        tris.append((tmp[a], tmp[b], tmp[c]))
        tris.append((tmp[a], tmp[c], tmp[d]))
    return [tuple(tuple(float(x) for x in v) for v in t) for t in tris]


def _extent(tris):
    xs = [v[0] for t in tris for v in t]
    return max(xs) - min(xs)
