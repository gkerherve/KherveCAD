"""Shell / hollow: geometry (shell.py), the node, its program and the
real OpenSCAD engine.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

from PyQt5.QtWidgets import QApplication

from khervecad import document, mesh, scadparse, shell
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _closed(tris) -> bool:
    count = Counter()
    for a, b, c in tris:
        for u, w in ((a, b), (b, c), (c, a)):
            count[(u, w)] += 1
    return all(n == 1 and count[(w, u)] == 1
               for (u, w), n in count.items())


def _cube(a=20.0):
    x0 = y0 = z0 = 0.0
    x1 = y1 = z1 = a
    quads = [((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)),
             ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)),
             ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)),
             ((x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)),
             ((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)),
             ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))]
    return [t for a_, b, c, d in quads for t in ((a_, b, c), (a_, c, d))]


# ------------------------------------------------------------ geometry
def test_a_closed_shell_of_a_cube_has_the_right_wall_and_volume():
    tris = _cube(20.0)
    assert shell.volume(tris) == pytest.approx(8000.0)
    out = shell.shell(tris, 2.0)
    assert _closed(out)
    assert shell.volume(out) == pytest.approx(8000 - 16 ** 3)
    inner = [t for t in out if all(2 - 1e-6 <= v[0] <= 18 + 1e-6
                                   for v in t)]
    assert len(inner) == 12                          # the offset cube


@pytest.mark.parametrize("side", ["top", "bottom", "+x", "-x", "+y", "-y"])
def test_an_open_shell_is_watertight_with_a_bridged_rim(side):
    out = shell.shell(_cube(20.0), 2.0, open=side)
    assert _closed(out)
    # the cavity opens on that side: volume drops by one wall's slab
    assert shell.volume(out) == pytest.approx(8000 - 16 ** 3 - 16 * 16 * 2)


def test_a_wall_with_no_room_leaves_the_solid():
    tris = _cube(20.0)
    assert shell.volume(shell.shell(tris, 10.0)) == pytest.approx(8000.0)
    assert shell.volume(shell.shell(tris, 12.0)) == pytest.approx(8000.0)


def test_even_thickness_keeps_corners_the_same_thickness():
    out = shell.inner_surface(_cube(20.0), 2.0)
    pts = {v for t in out for v in t}
    assert all(abs(v[i] - 2) < 1e-6 or abs(v[i] - 18) < 1e-6
               for v in pts for i in range(3))


# ---------------------------------------------------------- the node
def _cup(doc, **params):
    settings = dict(thickness=2.0, open="top", open_angle=30.0, detail=4.0)
    settings.update(params)
    node = doc.add_node("shell", settings)
    doc.add_node("cylinder", dict(radius_bottom=15.0, radius_top=15.0,
                                  height=30.0, segments=24), parent=node)
    return node


def test_the_node_previews_as_a_hollow_cup(app):
    doc = DocumentModel()
    doc.set_global_fn(False)
    _cup(doc)
    assert validate(doc.root) == {}
    tris = mesh.tessellate(doc.root)
    assert tris and _closed(tris)
    solid = math.pi * 225 * 30 * (math.sin(2 * math.pi / 24) * 24
                                  / (2 * math.pi))
    assert shell.volume(tris) < 0.5 * solid          # mostly cavity


def test_codegen_and_round_trip(app, tmp_path):
    doc = DocumentModel()
    doc.set_global_fn(False)
    _cup(doc, open="-x")
    code1 = doc.to_scad()
    assert 'kcad_shell(thickness = 2, open = "-x"' in code1
    path = tmp_path / "shell.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    other.set_global_fn(False)
    assert not scadparse.import_scad(other, str(path))
    assert other.to_scad().splitlines()[3:] == code1.splitlines()[3:]
    node = next(n for n in other.root.walk() if n.type == "shell")
    assert node.params["open"] == "-x" and node.params["thickness"] == 2.0


def test_shell_validation(app):
    doc = DocumentModel()
    doc.set_global_fn(False)
    thick = doc.add_node("shell", dict(thickness=12.0))
    doc.add_node("cube", dict(width=20.0, depth=20.0, height=20.0),
                 parent=thick)
    bad = doc.add_node("shell", dict(open="sideways"))
    doc.add_node("cube", parent=bad)
    loop = doc.add_node("for_loop")
    nested = doc.add_node("shell", parent=loop)
    doc.add_node("cube", parent=nested)
    errors = validate(doc.root)
    assert "no room" in errors[thick.id]
    assert "open side" in errors[bad.id]
    assert "for" in errors[nested.id]


def test_the_example_loads_and_validates(app):
    from khervecad import examples
    doc = DocumentModel()
    build = next(b for n, _c, b in examples.EXAMPLES if "shell" in n)
    examples.load_example(doc, build)
    assert validate(doc.root) == {}
    assert _closed(mesh.tessellate(doc.root))


# ---------------------------------------------------------- the engine
def _openscad_binary():
    for candidate in (shutil.which("openscad"), "/opt/homebrew/bin/openscad",
                      "/usr/local/bin/openscad",
                      "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"):
        if candidate and Path(candidate).exists():
            return candidate
    return None


def test_openscad_renders_the_same_cup_as_the_preview(app, tmp_path):
    binary = _openscad_binary()
    if binary is None:
        pytest.skip("OpenSCAD is not installed")
    from khervecad import engine
    doc = DocumentModel()
    doc.set_global_fn(False)
    _cup(doc)
    scad, stl = tmp_path / "cup.scad", tmp_path / "cup.stl"
    scad.write_text(doc.to_scad())
    run = subprocess.run([binary, "-o", str(stl), str(scad)],
                         capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stderr[-1500:]
    exact = engine.parse_stl(str(stl))
    preview = mesh.tessellate(doc.root)
    assert shell.volume(exact) == pytest.approx(shell.volume(preview),
                                                rel=0.002)
