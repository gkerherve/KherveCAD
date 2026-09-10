"""Tests for the mesh nodes (bake.py) and the rows/choice editors.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import bake, document, mesh, scadparse
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


def _closed(tris) -> bool:
    count = Counter()
    for a, b, c in tris:
        for u, w in ((a, b), (b, c), (c, a)):
            count[(u, w)] += 1
    return all(n == 1 and count[(w, u)] == 1
               for (u, w), n in count.items())


def _volume(tris) -> float:
    total = 0.0
    for a, b, c in tris:
        total += (a[0] * (b[1] * c[2] - b[2] * c[1])
                  - a[1] * (b[0] * c[2] - b[2] * c[0])
                  + a[2] * (b[0] * c[1] - b[1] * c[0]))
    return total / 6.0


# ── polyhedron ──────────────────────────────────────────────────────

def test_the_default_polyhedron_is_a_closed_outward_tetrahedron(model):
    node = model.add_node("polyhedron")
    assert validate(model.root).get(node.id) is None
    tris = mesh.tessellate(model.root)
    assert len(tris) == 4 and _closed(tris)
    # OpenSCAD's clockwise-from-outside faces become outward triangles
    assert _volume(tris) == pytest.approx(20 ** 3 / 6)


def test_polyhedron_codegen_is_native_openscad(model):
    model.add_node("polyhedron")
    code = model.to_scad()
    assert "polyhedron(points = [[0, 0, 0], [20, 0, 0]" in code
    assert "faces = [[0, 1, 2], [0, 3, 1]" in code
    assert "kcad_" not in code                  # no helper needed


def test_polyhedron_validation_names_the_broken_edge(model):
    cube = mesh.cube_mesh(dict(x=0.0, y=0.0, z=0.0, width=10.0,
                               depth=10.0, height=10.0, center=False))
    points, faces = bake.to_polyhedron(cube)
    box = model.add_node("polyhedron", dict(points=points,
                                            faces=faces[:-1]))  # a hole
    assert "not closed" in validate(model.root)[box.id]
    node = model.add_node("polyhedron")
    node.params["faces"] = node.params["faces"][:3]
    assert "4 faces" in validate(model.root)[node.id]
    node.params["faces"] = [[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 3, 2]]
    assert "wrong way" in validate(model.root)[node.id]
    node.params["faces"] = [[0, 1, 9], [0, 3, 1], [0, 2, 3], [1, 3, 2]]
    assert "point 9" in validate(model.root)[node.id]
    node.params["points"] = node.params["points"][:3]
    assert "4 points" in validate(model.root)[node.id]


def test_polyhedron_imports_and_round_trips(model, tmp_path):
    root, warnings = scadparse.parse_scad(
        "polyhedron(points=[[0,0,0],[10,0,0],[0,10,0],[0,0,10]],"
        " faces=[[0,1,2],[0,3,1],[0,2,3],[1,3,2]]);")
    assert not warnings
    node = root.children[0]
    assert node.type == "polyhedron"
    assert node.params["faces"][3] == [1, 3, 2]
    model.add_node("polyhedron")
    code1 = model.to_scad()
    path = tmp_path / "poly.scad"
    document.export_scad(model, str(path))
    other = DocumentModel()
    assert not scadparse.import_scad(other, str(path))
    strip = lambda c: "\n".join(ln for ln in c.splitlines()  # noqa: E731
                                if not ln.startswith("//")).strip()
    assert strip(other.to_scad()) == strip(code1)


def test_to_polyhedron_welds_and_turns_faces_for_openscad(model):
    cube = mesh.cube_mesh(dict(x=0.0, y=0.0, z=0.0, width=10.0,
                               depth=10.0, height=10.0, center=False))
    points, faces = bake.to_polyhedron(cube)
    assert len(points) == 8 and len(faces) == 12
    node = model.add_node("polyhedron", dict(points=points, faces=faces))
    assert validate(model.root).get(node.id) is None
    tris = mesh.tessellate(model.root)
    assert _closed(tris) and _volume(tris) == pytest.approx(1000.0)


# ── editors ─────────────────────────────────────────────────────────

def test_rows_editor_reads_numbers_and_keeps_expressions(app):
    from khervecad.rowsedit import RowsEditor
    seen = []
    editor = RowsEditor([[1.0, 2.0, 3.0]], ["X", "Y", "Z"], seen.append)
    assert editor.rows() == [[1.0, 2.0, 3.0]]
    editor.table.item(0, 2).setText("h * 2")
    assert seen[-1] == [[1.0, 2.0, "h * 2"]]
    editor.table.item(0, 0).setText("")
    assert editor.rows() is None                # mid-edit: not committed
    editor.set_rows([[4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
    assert editor.rows() == [[4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]


def test_free_rows_are_whole_number_lists(app):
    from khervecad.rowsedit import RowsEditor
    seen = []
    editor = RowsEditor([[0, 1, 2]], None, seen.append)
    editor.table.item(0, 0).setText("3; 4, 5, 6")
    assert seen[-1] == [[3, 4, 5, 6]]
    editor.table.item(0, 0).setText("a, b")
    assert editor.rows() is None


def test_the_properties_panel_edits_a_polyhedron(model):
    from khervecad.properties import PropertiesPanel
    from khervecad.rowsedit import RowsEditor
    node = model.add_node("polyhedron")
    panel = PropertiesPanel(model)
    panel.set_node(node)
    editor = panel._editors["points"]
    assert isinstance(editor, RowsEditor)
    editor.table.item(1, 0).setText("25")
    assert node.params["points"][1] == [25.0, 0.0, 0.0]
