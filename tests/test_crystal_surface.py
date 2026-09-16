"""Crystal surfaces (crystal_surface.py, crystal_surface_dialog.py) and
the build_surface MCP tool.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import crystal_build as cb
from khervecad import crystal_surface as cs
from khervecad.crystal_library import get
from khervecad.scadparse import parse_scad


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    return win


def _stats(key, miller, **kw):
    spec = cs.SurfaceSpec(get(key), cs.parse_miller(miller), **kw)
    return cs.program(spec)[1]


def test_parse_miller():
    assert cs.parse_miller("111") == (1, 1, 1)
    assert cs.parse_miller("1-10") == (1, -1, 0)
    assert cs.parse_miller("(2 2 0)") == (1, 1, 0)
    assert cs.parse_miller("10-10") == (1, 0, 0)
    assert cs.parse_miller([0, 0, 0, 1]) == (0, 0, 1)
    with pytest.raises(cb.BuildError):
        cs.parse_miller("1-11-1")          # i != -(h + k)


@pytest.mark.parametrize("key, miller, cell, spacing, angle", [
    ("si", "111", 0.38403, 0.31356, 120),  # a/√2, a/√3
    ("si", "100", 0.38403, 0.27155, 90),   # a/4 per atomic layer
    ("cu", "111", 0.25561, 0.20871, 120),
    ("quartz", "0001", 0.49134, 0.54052, 120),
    ("nacl", "100", 0.39882, 0.28201, 90),
])
def test_primitive_surface_cells(key, miller, cell, spacing, angle):
    st = _stats(key, miller, repeat=(1, 1), layers=1)
    assert st["surface_cell_nm"][0] == pytest.approx(cell, abs=1e-4)
    assert st["interplanar_spacing_nm"] == pytest.approx(spacing, abs=1e-4)
    assert st["surface_angle_deg"] == pytest.approx(angle, abs=0.01)


def test_layer_holds_the_bulk_density():
    """Surface cell area × spacing × atoms per layer = the crystal's
    atoms per volume, for any orientation."""
    for key, miller in (("si", "111"), ("rutile", "110"), ("gan", "10-10"),
                        ("quartz", "10-10"), ("srtio3", "110")):
        c = get(key)
        spec = cs.SurfaceSpec(c, cs.parse_miller(miller), layers=1)
        cell = cs.surface_cell(spec)
        U, V = cell["U"], cell["V"]
        vol = abs(U[0] * V[1] - U[1] * V[0]) * cell["d"]
        assert len(cell["atoms"]) / vol == pytest.approx(
            len(c.atoms) / c.volume(), rel=1e-6), (key, miller)


def test_si111_ends_on_a_whole_bilayer():
    spec = cs.SurfaceSpec(get("si"), (1, 1, 1), layers=2)
    zs = sorted({round(p[2], 2) for _e, p in cs.surface_cell(spec)["atoms"]},
                reverse=True)
    assert zs[0] == 0 and zs[1] == pytest.approx(-0.78, abs=0.01)
    assert max(z for z in zs) <= 0 and len(zs) == 4


def test_program_imports_and_refuses_too_big():
    code, st = cs.program(cs.SurfaceSpec(get("quartz"), (0, 0, 1),
                                         repeat=(3, 3), layers=2))
    root, _warn = parse_scad(code)
    assert any(n.type == "component" for n in root.walk())
    assert st["atoms"] == 3 * 3 * 18
    with pytest.raises(cb.BuildError):
        cs.program(cs.SurfaceSpec(get("quartz"), (0, 0, 1), repeat=(80, 80),
                                  layers=60, fn=32))


def test_mcp_and_dialog(window):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(window)
    dry = ex.execute("build_surface", {"crystal": "si", "miller": "111",
                                       "dry_run": True})
    assert dry["dry_run"] and not window.model.root.children
    out = ex.execute("build_surface", {"crystal": "rutile", "miller": "110",
                                       "repeat": [4, 2], "layers": 2})
    assert out["objects"] and window.model.unit == "nm"
    assert "error" in ex.execute("build_surface", {"crystal": "si",
                                                   "miller": "abc"})
    from khervecad import crystal_surface_dialog as dlg
    panel = dlg.open_builder(window)
    panel.miller.setText("0001")
    panel.crystal.setCurrentIndex(panel.crystal.findData("gan"))
    panel._refresh()
    assert panel.go.isEnabled() and "GaN" in panel.estimate.text()
    panel.miller.setText("xyz")
    panel._refresh()
    assert not panel.go.isEnabled()
    assert math.isfinite(panel.term.value())
