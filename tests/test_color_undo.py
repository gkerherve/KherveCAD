"""Tests for per-object colour and undo/redo.

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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import mesh, scadparse
from khervecad.model import DocumentModel


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


# ----------------------------------------------------------------- color

def test_color_codegen(model):
    cube = model.add_node("cube")
    model.set_color([cube], "#ff8800")
    code = model.root.to_scad()
    assert code.startswith('color("#ff8800") {')
    wrapper = model.root.children[0]
    model.set_color([wrapper], "#00ff00", 0.5)      # reuse wrapper
    code = model.root.to_scad()
    assert 'color("#00ff00", 0.5)' in code
    assert code.count("color(") == 1


def test_set_color_reuses_parent_wrapper(model):
    cube = model.add_node("cube")
    model.set_color([cube], "#112233")
    model.set_color([cube], "#445566")              # cube's parent
    assert model.root.to_scad().count("color(") == 1


def test_colored_preview_faces(model):
    cube = model.add_node("cube")
    model.set_color([cube], "#ff0000", 0.8)
    model.add_node("sphere", dict(segments=8))
    colored = mesh.tessellate_colored(model.root)
    reds = [c for _t, c in colored if c is not None]
    assert len(reds) == 12                          # the cube's faces
    assert reds[0] == ("#ff0000", 0.8)
    assert any(c is None for _t, c in colored)      # sphere untinted


def test_color_survives_transforms(model):
    cube = model.add_node("cube")
    color = model.set_color([cube], "#123456")[0]
    model.wrap_nodes([color], "translate")
    colored = mesh.tessellate_colored(model.root)
    assert all(c == ("#123456", 1.0) for _t, c in colored)


def test_color_import(app):
    root, warnings = scadparse.parse_scad(
        'color("#ff8800") { cube(5); }\n'
        'color([1, 0, 0], 0.5) sphere(3);\n'
        'color("SteelBlue") cylinder(h=4, r=1);')
    assert not warnings
    kinds = [n.type for n in root.children]
    assert kinds == ["color", "color", "color"]
    assert root.children[0].params["color"] == "#ff8800"
    assert root.children[1].params["color"] == "#ff0000"
    assert root.children[1].params["alpha"] == 0.5
    assert root.children[2].params["color"] == "SteelBlue"


def test_color_roundtrip(model, tmp_path):
    from khervecad import document
    cube = model.add_node("cube")
    model.set_color([cube], "#abcdef", 0.7)
    code1 = model.root.to_scad()
    root, warnings = scadparse.parse_scad(code1)
    assert not warnings
    other = DocumentModel()
    other.root = root
    assert other.root.to_scad() == code1


# ------------------------------------------------------------- undo/redo

def _flush(app):
    app.processEvents()                    # deliver the 0 ms capture


def test_undo_redo_add(app, model):
    model.add_node("cube")
    _flush(app)
    assert model.undo_stack.canUndo()
    model.undo_stack.undo()
    assert model.root.children == []
    model.undo_stack.redo()
    assert model.root.children[0].type == "cube"


def test_undo_param_change(app, model):
    node = model.add_node("circle")
    _flush(app)
    import time
    time.sleep(0.5)                        # separate undo steps
    model.set_param(node, "radius", 42.0)
    _flush(app)
    model.undo_stack.undo()
    assert model.root.children[0].params["radius"] == 15.0
    model.undo_stack.redo()
    assert model.root.children[0].params["radius"] == 42.0


def test_rapid_edits_merge_into_one_step(app, model):
    node = model.add_node("circle")
    _flush(app)
    import time
    time.sleep(0.5)
    for radius in (10.0, 11.0, 12.0, 13.0):   # like dragging a handle
        model.set_param(node, "radius", radius)
        _flush(app)
    count = model.undo_stack.count()
    model.undo_stack.undo()
    assert model.root.children[0].params["radius"] == 15.0
    assert count == 2                      # add + one merged edit


def test_undo_structure_operations(app, model):
    a = model.add_node("circle")
    b = model.add_node("rect")
    _flush(app)
    import time
    time.sleep(0.5)
    model.wrap_nodes([a, b], "difference")
    _flush(app)
    assert model.root.children[0].type == "difference"
    model.undo_stack.undo()
    assert [n.type for n in model.root.children] == ["circle", "rect"]


def test_undo_restores_generated_code(app, model):
    model.add_node("sphere")
    _flush(app)
    code_one = model.root.to_scad()
    import time
    time.sleep(0.5)
    model.add_node("cube")
    _flush(app)
    model.undo_stack.undo()
    assert model.root.to_scad() == code_one
