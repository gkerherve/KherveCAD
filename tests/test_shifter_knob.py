"""The TH8S contest knob: it parses cleanly into KherveCAD and, with
OpenSCAD installed, each part prints as one solid with no supports.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from pathlib import Path

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import scadparse
from khervecad.tools import print_tests, shifter_knob


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_the_knob_parses_without_warnings(app):
    root, warnings = scadparse.parse_scad(shifter_knob.program())
    assert not warnings
    names = {n.name for n in root.walk() if n.type == "component"}
    assert {"Knob body", "Shift badge"} <= names


#: Thrustmaster's files are not in the repository: the check runs
#: where they were downloaded
STEP = Path.home() / "Downloads" / "Design piece.stp"


@pytest.mark.parametrize("part", ["body", "badge", "fit"])
def test_each_part_prints_without_supports(part, tmp_path):
    """Our own surfaces never face down past 45 deg; the official
    sleeve's thread and roof (inside r = 11.3, below z = 43) are
    Thrustmaster's, and every thread has them."""
    openscad = print_tests.openscad_binary()
    if not openscad:
        pytest.skip("OpenSCAD not installed")
    if not STEP.exists():
        pytest.skip("Thrustmaster's Design piece.stp not downloaded")
    np = pytest.importorskip("numpy")
    pytest.importorskip("manifold3d")
    pytest.importorskip("OCP")
    sleeve = shifter_knob.design_piece_stl(STEP, tmp_path / "sleeve.stl")
    code = shifter_knob.program((part,), sleeve=str(sleeve))
    check = print_tests.printability(code, openscad)
    assert check["pieces"] == 1
    assert check["zmin"] == pytest.approx(0, abs=1e-6)
    assert check["bed_mm2"] > 300
    src, out = tmp_path / "p.scad", tmp_path / "p.off"
    src.write_text(code)
    import subprocess
    from khervecad import engine
    subprocess.run([openscad, *engine.backend_args(openscad), "-o",
                    str(out), str(src)], capture_output=True, check=True)
    v, t = print_tests._off(out)
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    n = np.cross(b - a, c - a)
    area = np.linalg.norm(n, axis=1) / 2
    nz = n[:, 2] / np.maximum(2 * area, 1e-12)
    cen = (a + b + c) / 3
    ours = ~((np.hypot(cen[:, 0], cen[:, 1]) < 11.3) & (cen[:, 2] < 43))
    down = (nz < -0.7072) & (cen[:, 2] > 0.3) & ours
    assert area[down].sum() < print_tests.MAX_OVERHANG_MM2
