"""The Test parts for printer library: support-free first-try prints.

Pins the shipped files to `khervecad.tools.print_tests` (the generator
is the source of truth) and, when OpenSCAD is installed, renders what
the SHIPPED .kcad compiles to — so an importer change that lost a
chamfer or detached a piece fails here — and checks it is one closed
solid standing flat on the bed with almost nothing facing down past
45°.

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

from khervecad import document, library, library_groups, mesh, scadparse
from khervecad.model import DocumentModel, validate
from khervecad.tools import print_tests

STEMS = sorted(print_tests.PARTS)


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _load(stem):
    doc = DocumentModel()
    document.load_kcad(doc, str(print_tests.folder() / f"{stem}.kcad"))
    return doc


@pytest.mark.parametrize("stem", STEMS)
def test_the_shipped_file_matches_the_generator(app, stem, tmp_path):
    print_tests.write(stem, print_tests.program(stem),
                      tmp_path / f"{stem}.kcad")
    fresh = (tmp_path / f"{stem}.kcad").read_text()
    shipped = (print_tests.folder() / f"{stem}.kcad").read_text()
    assert fresh == shipped, f"{stem}.kcad is out of step with print_tests"


@pytest.mark.parametrize("stem", STEMS)
def test_every_part_parses_cleanly_and_is_one_object(app, stem):
    _root, warnings = scadparse.parse_scad(print_tests.program(stem))
    assert warnings == []
    doc = _load(stem)
    assert validate(doc.root) == {}
    objects = [c for c in doc.root.children if c.type == "component"]
    assert [o.name for o in objects] == [stem]
    assert mesh.tessellate(objects[0]), f"{stem} previews empty"


def test_the_section_is_in_the_library_and_the_3d_printing_menu(app):
    ids = [pid for pid, spec in library.PARTS.items()
           if spec["category"] == print_tests.SECTION]
    assert len(ids) == len(STEMS)
    printing = dict((name, spec) for name, _icon, spec in
                    library_groups.SECTIONS[0][1])["3D printing"]
    assert print_tests.SECTION in printing


@pytest.mark.skipif(not print_tests.openscad_binary(),
                    reason="OpenSCAD is not installed")
@pytest.mark.parametrize("stem", STEMS)
def test_every_part_prints_without_supports(app, stem):
    pytest.importorskip("manifold3d")
    code = _load(stem).to_scad()
    report = print_tests.printability(code, print_tests.openscad_binary())
    assert report["pieces"] == 1, report
    assert abs(report["zmin"]) < 0.01, report
    assert report["bed_mm2"] > 100, report
    assert report["overhang_mm2"] < print_tests.MAX_OVERHANG_MM2, report
