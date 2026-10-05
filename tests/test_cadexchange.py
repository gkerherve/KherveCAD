"""CAD exchange: STEP / IGES / BREP / 3DM out and back in (cadexchange.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import analysis, cadexchange as cx, scadparse

occ = pytest.mark.skipif(not cx.occ_available(),
                         reason="OpenCascade (cadquery-ocp) not installed")
rhino = pytest.mark.skipif(not cx.rhino_available(),
                           reason="rhino3dm not installed")

PLATE = """
color("red") difference() { cube([40, 30, 10]);   // Plate
    translate([20, 15, -1]) cylinder(h = 12, r = 5); }
translate([60, 0, 0]) rotate_extrude() translate([10, 0]) circle(3);
translate([0, 50, 0]) linear_extrude(8) difference() { circle(10);
    circle(6); }
"""


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _volume(tris):
    return analysis.mass_properties(tris)["volume"]


def _occ_volume(path):
    from OCP.STEPControl import STEPControl_Reader
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp
    reader = STEPControl_Reader()
    reader.ReadFile(str(path))
    reader.TransferRoots()
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(reader.OneShape(), props)
    return props.Mass()


@occ
def test_step_is_exact_where_the_model_is(tmp_path):
    import math
    root, _w = scadparse.parse_scad(PLATE)
    out = tmp_path / "plate.step"
    report = cx.export_model(root, out, fn=48)
    assert report.parts == 3 and report.faceted == 0
    text = out.read_text(errors="replace")
    # the bore and the tube are true cylinders, the ring a true torus
    assert "CYLINDRICAL_SURFACE" in text and "TOROIDAL_SURFACE" in text
    plate = 40 * 30 * 10 - math.pi * 25 * 10
    torus = 2 * math.pi ** 2 * 10 * 9
    tube = math.pi * (100 - 36) * 8
    assert _occ_volume(out) == pytest.approx(plate + torus + tube,
                                             rel=1e-6)
    assert "exact" in report.sentence("STEP")


@occ
def test_unknown_shapes_are_faceted_and_named(tmp_path):
    root, _w = scadparse.parse_scad(
        "linear_extrude(5, twist = 90) square(10);  // Twisty")
    report = cx.export_model(root, tmp_path / "t.step")
    assert report.faceted == 1 and report.exact == 0
    assert "Twisty" in report.sentence("STEP")
    from khervecad import mesh
    parts = cx.read_parts(tmp_path / "t.step")
    preview = _volume(mesh.tessellate(root))
    # the very facets of the preview, sewn into a closed solid
    assert _volume(parts[0].tris) == pytest.approx(preview, rel=1e-6)


@occ
@pytest.mark.parametrize("ext", [".step", ".iges", ".brep"])
def test_round_trip_keeps_the_shape(tmp_path, ext):
    root, _w = scadparse.parse_scad(PLATE)
    out = tmp_path / ("m" + ext)
    cx.export_model(root, out, fn=48)
    parts = cx.read_parts(out, "Fine")
    total = sum(_volume(p.tris) for p in parts)
    assert total == pytest.approx(_occ_volume_of(root, tmp_path), rel=0.01)


def _occ_volume_of(root, tmp_path):
    p = tmp_path / "ref.step"
    cx.export_model(root, p, fn=48)
    return _occ_volume(p)


@occ
def test_step_keeps_names_and_colours(tmp_path):
    root, _w = scadparse.parse_scad(PLATE)
    out = tmp_path / "m.step"
    cx.export_model(root, out)
    parts = cx.read_parts(out)
    assert parts[0].name == "Plate" and parts[0].color == "#ff0000"
    assert len({p.name for p in parts}) == 3      # unique names


@occ
def test_export_is_in_real_millimetres(tmp_path):
    root, _w = scadparse.parse_scad("cube(10);")
    out = tmp_path / "cm.step"
    cx.export_model(root, out, unit_mm=10.0)      # a cm document
    assert _occ_volume(out) == pytest.approx(1e6, rel=1e-9)


@rhino
def test_rhino_round_trip(tmp_path):
    root, _w = scadparse.parse_scad(PLATE)
    out = tmp_path / "m.3dm"
    report = cx.export_model(root, out, fn=48)
    assert "Rhino" in report.sentence("Rhino 3DM")
    parts = cx.read_parts(out)
    assert [p.name for p in parts][0] == "Plate"
    assert parts[0].color == "#ff0000"
    assert _volume(parts[0].tris) > 0


def test_missing_engine_says_what_to_install(monkeypatch):
    monkeypatch.setattr(cx, "occ_available", lambda: False)
    assert "pip install cadquery-ocp" in cx.missing(".step")
    with pytest.raises(ValueError, match="cadquery-ocp"):
        cx.read_parts("x.step")


@occ
def test_window_import_and_export(app, tmp_path, monkeypatch):
    from khervecad import cadexchange_ui
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    from PyQt5.QtWidgets import QMessageBox

    def refuse(*a, **k):
        raise AssertionError(f"a message box opened: {a[1:3]}")
    monkeypatch.setattr(QMessageBox, "warning", refuse)
    monkeypatch.setattr(QMessageBox, "information", refuse)
    root, _w = scadparse.parse_scad(PLATE)
    src = tmp_path / "supplier.step"
    cx.export_model(root, src, fn=48)
    win = MainWindow()
    win.open_any(str(src))                      # what Open and a drop do
    objs = [n for n in win.model.root.children if n.type == "component"]
    assert len(objs) == 1 and objs[0].name == "supplier"
    groups = [c.name for c in objs[0].children]
    assert groups[0] == "Plate"
    assert (tmp_path / "supplier parts" / "Plate.stl").is_file()
    assert "3 parts" in win.statusBar().currentMessage()
    # and back out: no dialog when not interactive
    report = cadexchange_ui.export_cad(win, str(tmp_path / "back.step"),
                                       interactive=False)
    assert report.parts == 1
    # the MCP tools take the same doors
    ex = McpToolExecutor(win)
    got = ex.execute("export_document", {"path": str(tmp_path / "x.iges")})
    assert got.get("format") == "IGES", got
    got = ex.execute("open_document", {"path": str(src), "quality": "Draft",
                                       "discard_unsaved_changes": True})
    assert "error" not in got, got
    assert [p["name"] for p in got["parts"]][0] == "Plate"
    win._dirty = False
    win.deleteLater()


@occ
def test_an_imported_part_exports_its_own_exact_surface(app, tmp_path):
    """Import a supplier's STEP, move it, send it back: the surfaces are
    the file's own, not the preview's triangles."""
    from khervecad import cadexchange_ui
    from khervecad.model import DocumentModel
    root, _w = scadparse.parse_scad(PLATE)
    src = tmp_path / "supplier.step"
    cx.export_model(root, src, fn=48)
    before = _occ_volume(src)
    model = DocumentModel()
    parts = cx.read_parts(src)
    obj = cadexchange_ui.place_parts(model, src, parts)
    obj.params["x"] = 100.0                          # the user moved it
    out = tmp_path / "back.step"
    report = cx.export_model(model.root, out)
    assert report.faceted == 0 and report.exact == 3
    assert _occ_volume(out) == pytest.approx(before, rel=1e-9)
    assert "CYLINDRICAL_SURFACE" in out.read_text(errors="replace")
