"""Exact parts (brep.py): a STEP part kept exact, filleted and
chamfered on its true edges.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import analysis, brep, cadexchange as cx, cadexchange_ui, \
    mesh, scadparse
from khervecad.model import DocumentModel, validate

pytestmark = pytest.mark.skipif(not cx.occ_available(),
                                reason="OpenCascade not installed")


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def plate(app, tmp_path):
    root, _w = scadparse.parse_scad("cube([40, 30, 10]);  // Plate")
    path = tmp_path / "plate.step"
    cx.export_model(root, path)
    model = DocumentModel()
    obj = cadexchange_ui.place_parts(model, path, cx.read_parts(path))
    return model, obj, path


def _volume(model):
    return analysis.mass_properties(mesh.tessellate(model.root))["volume"]


def test_make_exact_keeps_the_shape(plate):
    model, obj, _p = plate
    exact = brep.make_exact(model, obj)
    assert exact.type == "brep" and validate(model.root) == {}
    assert _volume(model) == pytest.approx(12000, rel=1e-6)


def test_a_fillet_takes_away_exactly_its_volume(plate):
    model, obj, _p = plate
    exact = brep.make_exact(model, obj)
    exact.params["fillets"] = [[20, 0, 10, 3]]      # top front edge
    assert validate(model.root) == {}
    removed = (1 - math.pi / 4) * 9 * 40
    assert _volume(model) == pytest.approx(12000 - removed, rel=2e-3)


def test_a_chamfer(plate):
    model, obj, _p = plate
    exact = brep.make_exact(model, obj)
    exact.params["chamfers"] = [[40, 15, 10, 2]]
    assert _volume(model) == pytest.approx(12000 - 2 * 30, rel=1e-3)


def test_a_point_off_every_edge_says_so(plate):
    model, obj, _p = plate
    exact = brep.make_exact(model, obj)
    exact.params["fillets"] = [[20, 15, 50, 3]]
    assert "no edge near" in validate(model.root)[exact.id]


def test_step_export_keeps_the_fillet_exact(plate, tmp_path):
    model, obj, _p = plate
    exact = brep.make_exact(model, obj)
    exact.params["fillets"] = [[20, 0, 10, 3]]
    report = cx.export_model(model.root, tmp_path / "out.step")
    assert report.faceted == 0
    assert "CYLINDRICAL_SURFACE" in (tmp_path / "out.step").read_text(
        errors="replace")


def test_a_placed_part_takes_world_points(plate):
    model, obj, _p = plate
    obj.params["x"] = 100.0
    exact = brep.make_exact(model, obj)
    local = brep.to_local(exact, [120, 0, 10])
    assert local == pytest.approx([20, 0, 10])


def test_mcp_exact_part(app, tmp_path):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    root, _w = scadparse.parse_scad("cube([40, 30, 10]);")
    path = tmp_path / "p.step"
    cx.export_model(root, path)
    win = MainWindow()
    ex = McpToolExecutor(win)
    got = ex.execute("open_document", {"path": str(path),
                                       "discard_unsaved_changes": True})
    got = ex.execute("exact_part", {"node_id": got["object_id"],
                                    "fillets": [[20, 0, 10, 2]]})
    assert "error" not in got, got
    assert len(got["fillets"]) == 1
    win._dirty = False
    win.deleteLater()


def test_clicking_edges_adds_rows(app, tmp_path):
    from khervecad import brep_ui
    from khervecad.mainwindow import MainWindow
    root, _w = scadparse.parse_scad("cube([40, 30, 10]);")
    path = tmp_path / "c.step"
    cx.export_model(root, path)
    win = MainWindow()
    obj = cadexchange_ui.place_parts(win.model, path, cx.read_parts(path))
    exact = brep.make_exact(win.model, obj)
    assert brep_ui.start(win, exact, "fillets", size=1.5)
    view = win.view3d
    # an edge click: the top-front edge, as describe_pick reports it
    view._pick_cb(dict(kind="edge", seg=[[0, 0, 10], [40, 0, 10]]), exact)
    assert exact.params["fillets"] == [[20.0, 0.0, 10.0, 1.5]]
    # a face click is refused and the pick stays armed
    view._pick_cb(dict(kind="face", pos=[20, 15, 10]), exact)
    assert len(exact.params["fillets"]) == 1 and view._pick_cb
    view.cancel_pick()
    win._dirty = False
    win.deleteLater()
