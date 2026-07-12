"""Tests for the raw-OpenSCAD passthrough node.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import document, mesh
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


CODE = "include <BOSL2/std.scad>\ncuboid([20,20,20], rounding=3);"


def test_raw_node_is_a_leaf_and_valid(model):
    n = model.add_node("scad_raw")
    n.params["code"] = CODE
    assert not n.is_container()
    assert validate(model.root) == {}


def test_raw_code_is_emitted_verbatim(model):
    n = model.add_node("scad_raw")
    n.params["code"] = CODE
    code = model.to_scad()
    assert "include <BOSL2/std.scad>" in code
    assert "cuboid([20,20,20], rounding=3);" in code


def test_raw_node_has_no_builtin_geometry(model):
    n = model.add_node("scad_raw")
    n.params["code"] = CODE
    assert mesh.tessellate(model.root, fn=model.effective_fn()) == []


def test_hidden_raw_node_emits_nothing(model):
    n = model.add_node("scad_raw")
    n.params["code"] = "sphere(5);"
    model.set_visible(n, False)
    assert "sphere(5);" not in model.to_scad()


MODULE_SCAD = """\
module widget(n = 3) {
    for (i = [0:n]) translate([i*10,0,0]) cube(5);
}
widget(4);
"""


def test_module_scad_imports_empty_with_warnings(app, tmp_path):
    """A module-based program the parser can't model comes in empty."""
    from khervecad import scadparse
    m = DocumentModel()
    f = tmp_path / "widget.scad"
    f.write_text(MODULE_SCAD, encoding="utf-8")
    warns = scadparse.import_scad(m, str(f))
    assert mesh.tessellate(m.root, fn=m.effective_fn()) == []
    assert any("not supported" in w or "unsupported" in w for w in warns)


def test_load_scad_raw_keeps_the_program(app, tmp_path):
    """The raw fallback loads the whole file into a scad_raw node."""
    from khervecad.mainwindow import MainWindow
    f = tmp_path / "widget.scad"
    f.write_text(MODULE_SCAD, encoding="utf-8")
    w = MainWindow()
    w._load_scad_raw(str(f))
    raw = [n for n in w.model.root.walk() if n.type == "scad_raw"]
    assert len(raw) == 1
    assert "module widget" in raw[0].params["code"]
    assert "module widget" in w.model.to_scad()


VECTOR_SCAD = """\
plate = [100, 50, 5];
cube(plate);
translate([0, 0, plate.z]) cylinder(h = 10, d = 6);
"""


def test_vector_accessor_scad_hard_fails_to_parse(app, tmp_path):
    """A file using the vector .x/.z accessor can't tokenize — the raw
    fallback (offered on any import error) is the way to open it."""
    import pytest
    from khervecad import scadparse
    f = tmp_path / "vec.scad"
    f.write_text(VECTOR_SCAD, encoding="utf-8")
    m = DocumentModel()
    with pytest.raises(Exception):
        scadparse.import_scad(m, str(f))
    # ...but it still loads verbatim as a raw block
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w._load_scad_raw(str(f))
    assert "plate.z" in w.model.to_scad()


def test_raw_node_round_trips(model):
    n = model.add_node("scad_raw")
    n.params["code"] = CODE
    fd, path = tempfile.mkstemp(suffix=".kcad")
    os.close(fd)
    try:
        document.save_kcad(model, path)
        m2 = DocumentModel()
        document.load_kcad(m2, path)
    finally:
        os.remove(path)
    raw = next(x for x in m2.root.walk() if x.type == "scad_raw")
    assert raw.params["code"] == CODE
