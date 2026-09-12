"""Imported meshes: rotation and scale on the node, a cache that holds
several files, paths that survive a moved project folder, and the
centre / floor / units fixes.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import document, engine, mesh, meshimport, scadparse
from khervecad.model import DocumentModel


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


def _box(path, lo=(0, 0, 0), hi=(10, 20, 30)):
    """Write a closed box STL spanning *lo*..*hi*."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5),
             (2, 3, 7, 6), (3, 0, 4, 7)]
    tris = []
    for a, b, cc, d in quads:
        tris += [(c[a], c[b], c[cc]), (c[a], c[cc], c[d])]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine.write_stl(tris, str(path))
    return str(path)


def _extent(tris):
    pts = [v for t in tris for v in t]
    return [(round(min(v[i] for v in pts), 6),
             round(max(v[i] for v in pts), 6)) for i in range(3)]


def test_preview_applies_rotation_and_scale(tmp_path):
    path = _box(tmp_path / "b.stl")
    tris = mesh.stl_mesh(dict(path=path, x=1.0, y=0.0, z=0.0,
                              rx=0.0, ry=0.0, rz=90.0, scale=2.0))
    # scaled to 20 x 40 x 60, turned 90° about Z, then moved 1 in X
    assert _extent(tris) == [(-39.0, 1.0), (0.0, 20.0), (0.0, 60.0)]


def test_old_nodes_without_the_new_params_still_tessellate(tmp_path):
    path = _box(tmp_path / "b.stl")
    assert _extent(mesh.stl_mesh(dict(path=path, x=0.0, y=0.0, z=5.0))) \
        == [(0.0, 10.0), (0.0, 20.0), (5.0, 35.0)]


def test_cache_keeps_several_files(tmp_path, monkeypatch):
    a, b = _box(tmp_path / "a.stl"), _box(tmp_path / "b.stl")
    real, calls = engine.parse_mesh, []
    monkeypatch.setattr(engine, "parse_mesh",
                        lambda p: calls.append(p) or real(p))
    mesh._stl_cache.clear()
    for path in (a, b, a, b, a):
        mesh.stl_mesh(dict(path=path, x=0.0, y=0.0, z=0.0))
    assert calls == [a, b]          # each file parsed once, not per draw


def test_codegen_writes_rotate_and_scale_only_when_set(model):
    node = model.add_node("stl_import", dict(path="m.stl"))
    assert "rotate" not in model.root.to_scad()
    assert "scale" not in model.root.to_scad()
    node.params.update(rx=90.0, scale=25.4)
    code = model.root.to_scad()
    assert ('translate([0, 0, 0]) rotate([90, 0, 0]) scale(25.4) '
            'import("m.stl", convexity=10)') in code


def test_rotate_and_scale_fold_back_on_import(model):
    model.add_node("stl_import", dict(path="m.stl", x=1.0, y=2.0,
                                      z=3.0, ry=45.0, scale=10.0))
    code = model.root.to_scad()
    root, _warnings = scadparse.parse_scad(code)
    stl = [n for n in root.walk() if n.type == "stl_import"]
    assert len(stl) == 1 and stl[0].parent is root
    p = stl[0].params
    assert (p["x"], p["y"], p["z"], p["rx"], p["ry"], p["rz"],
            p["scale"]) == (1.0, 2.0, 3.0, 0.0, 45.0, 0.0, 10.0)
    again = DocumentModel()
    again.root = root
    assert again.root.to_scad() == code            # lossless


def test_a_rotated_translate_is_not_folded(app):
    root, _ = scadparse.parse_scad(
        'rotate([90, 0, 0]) translate([5, 0, 0]) import("m.stl");')
    assert root.children[0].type == "rotate"


def test_saved_path_is_relative_inside_the_project(model, tmp_path):
    stl = _box(tmp_path / "proj" / "meshes" / "b.stl")
    node = model.add_node("stl_import", dict(path=stl))
    doc = tmp_path / "proj" / "doc.kcad"
    document.save_kcad(model, str(doc))
    saved = json.loads(doc.read_text(encoding="utf-8"))
    assert saved["version"] == document.FORMAT_VERSION
    [child] = saved["tree"]["children"]
    assert child["params"]["path"] == "meshes/b.stl"
    assert node.params["path"] == stl                  # live node untouched
    # the whole folder moves: it still opens with the mesh found
    moved = tmp_path / "elsewhere"
    (tmp_path / "proj").rename(moved)
    other = DocumentModel()
    document.load_kcad(other, str(moved / "doc.kcad"))
    [loaded] = [n for n in other.root.walk() if n.type == "stl_import"]
    assert Path(loaded.params["path"]) == moved / "meshes" / "b.stl"
    assert mesh.stl_mesh(dict(loaded.params))


def test_a_mesh_outside_the_project_stays_absolute(model, tmp_path):
    stl = _box(tmp_path / "library" / "b.stl")
    model.add_node("stl_import", dict(path=stl))
    doc = tmp_path / "proj" / "doc.kcad"
    doc.parent.mkdir()
    document.save_kcad(model, str(doc))
    saved = json.loads(doc.read_text(encoding="utf-8"))
    assert saved["tree"]["children"][0]["params"]["path"] == stl


def test_a_missing_mesh_is_found_beside_the_document(tmp_path, app):
    """A document saved with an absolute path — on Windows, say — finds
    its mesh when the file was moved in next to it."""
    _box(tmp_path / "b.stl")
    doc = tmp_path / "doc.kcad"
    doc.write_text(json.dumps({
        "format": "kcad", "version": 6, "tree": {
            "type": "root", "name": "root", "visible": True, "params": {},
            "children": [{"type": "stl_import", "name": "Import STL",
                          "visible": True, "params": {
                              "path": "C:\\Users\\me\\parts\\b.stl",
                              "x": 0.0, "y": 0.0, "z": 0.0}}]}}),
        encoding="utf-8")
    model = DocumentModel()
    document.load_kcad(model, str(doc))
    [node] = [n for n in model.root.walk() if n.type == "stl_import"]
    assert Path(node.params["path"]) == tmp_path / "b.stl"
    assert node.params["scale"] == 1.0              # old file, new default


def test_scad_import_reads_mesh_paths_beside_the_file(model, tmp_path):
    _box(tmp_path / "parts" / "b.stl")
    scad = tmp_path / "assembly.scad"
    scad.write_text('import("parts/b.stl");\n', encoding="utf-8")
    scadparse.import_scad(model, str(scad))
    [node] = [n for n in model.root.walk() if n.type == "stl_import"]
    assert Path(node.params["path"]) == tmp_path / "parts" / "b.stl"


def test_centre_floor_and_units(model, tmp_path):
    stl = _box(tmp_path / "b.stl", lo=(100, 100, 100), hi=(110, 120, 130))
    comp = model.new_component("Part")
    node = model.add_node("stl_import", dict(path=stl), parent=comp)
    assert meshimport.mesh_nodes([comp]) == [node]
    assert meshimport.size_text(node) == " (10 × 20 × 30 mm)"
    meshimport.place(model, node)
    assert _extent(mesh.stl_mesh(dict(node.params))) == \
        [(-5.0, 5.0), (-10.0, 10.0), (-15.0, 15.0)]
    meshimport.place(model, node, floor=True)
    assert _extent(mesh.stl_mesh(dict(node.params)))[2] == (0.0, 30.0)
    meshimport.set_scale(model, node, 25.4)
    assert meshimport.size_text(node) == " (254 × 508 × 762 mm)"


def test_a_non_positive_scale_is_an_error(model, tmp_path):
    from khervecad.model import validate
    node = model.add_node("stl_import", dict(path=_box(tmp_path / "b.stl"),
                                             scale=0.0))
    assert "scale" in validate(model.root).get(node.id, "")
