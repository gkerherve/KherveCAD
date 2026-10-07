"""The TH8S contest knob: it parses cleanly into KherveCAD and, with
OpenSCAD installed, each part prints as one solid with no supports.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

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


@pytest.mark.parametrize("part", ["body", "badge"])
def test_each_part_prints_without_supports(part):
    openscad = print_tests.openscad_binary()
    if not openscad:
        pytest.skip("OpenSCAD not installed")
    try:
        import manifold3d  # noqa: F401
    except ImportError:
        pytest.skip("manifold3d not installed")
    check = print_tests.printability(shifter_knob.program((part,)),
                                     openscad)
    assert check["pieces"] == 1
    assert check["zmin"] == pytest.approx(0, abs=1e-6)
    assert check["bed_mm2"] > 300
    assert check["overhang_mm2"] < print_tests.MAX_OVERHANG_MM2
