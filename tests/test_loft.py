"""Tests for the loft geometry (loft.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from khervecad import loft


def _tris(sections, **kw):
    points, faces = loft.loft(sections, **kw)
    return loft.triangles(points, faces)


def _bounds(tris):
    pts = [v for tri in tris for v in tri]
    return ([min(p[i] for p in pts) for i in range(3)],
            [max(p[i] for p in pts) for i in range(3)])


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


def test_a_straight_flat_ended_tube_is_a_closed_prism():
    tris = _tris([[0, 0, 0, 5, 5], [0, 0, 20, 5, 5]], sides=24, smooth=0,
                 caps="flat")
    lo, hi = _bounds(tris)
    assert lo == pytest.approx([-5, -5, 0], abs=1e-9)
    assert hi == pytest.approx([5, 5, 20], abs=1e-9)
    assert _closed(tris)
    prism = 24 / 2 * 25 * math.sin(2 * math.pi / 24) * 20
    assert _volume(tris) == pytest.approx(prism)       # outward, exact


def test_round_ends_add_a_dome_at_each_end():
    tris = _tris([[0, 0, 0, 5, 5], [0, 0, 20, 5, 5]], sides=24, smooth=0)
    lo, hi = _bounds(tris)
    assert (lo[2], hi[2]) == pytest.approx((-5.0, 25.0))
    assert _closed(tris) and _volume(tris) > 0


def test_an_elliptical_section_keeps_its_width_and_height():
    """Along +X the frame's normal is world +Z: h is up, w across."""
    tris = _tris([[0, 0, 0, 10, 3], [40, 0, 0, 10, 3]], smooth=0,
                 caps="flat")
    lo, hi = _bounds(tris)
    assert (lo[1], hi[1]) == pytest.approx((-10.0, 10.0), abs=1e-9)
    assert (lo[2], hi[2]) == pytest.approx((-3.0, 3.0), abs=1e-9)


def test_the_path_passes_through_every_section():
    sections = [[0, 0, 0, 2, 2], [10, 5, 5, 3, 3], [20, 0, 15, 2, 2],
                [25, -5, 30, 1, 1]]
    dense = loft.path(sections, 4)
    for row in sections:
        assert any(all(abs(a - b) < 1e-9 for a, b in zip(row, d))
                   for d in dense)
    assert len(dense) == 3 * 5 + 1


def test_frames_stay_orthonormal_and_do_not_flip():
    """A rotation-minimising frame along a helix: unit, orthogonal, and
    each normal close to the one before (no sudden twist)."""
    centres = [(10 * math.cos(t / 8), 10 * math.sin(t / 8), t)
               for t in range(60)]
    tangents, normals, binormals = loft.frames(centres)
    for t, n, b in zip(tangents, normals, binormals):
        assert sum(x * x for x in n) == pytest.approx(1.0)
        assert abs(sum(x * y for x, y in zip(t, n))) < 1e-9
        assert sum(x * x for x in b) == pytest.approx(1.0)
    for n0, n1 in zip(normals, normals[1:]):
        assert sum(x * y for x, y in zip(n0, n1)) > 0.9


def test_a_bent_limb_is_one_closed_outward_surface():
    tris = _tris([[0, 0, 0, 6, 5], [0, 0, 30, 4.5, 4], [15, 0, 50, 3, 3],
                  [35, 0, 55, 2, 2]], sides=20, smooth=3)
    assert _closed(tris) and _volume(tris) > 0


def test_radii_never_fold_the_tube():
    tris = _tris([[0, 0, 0, 5, 5], [0, 0, 10, 0, 0], [0, 0, 20, 5, 5]],
                 smooth=2)
    assert _closed(tris)


def test_fewer_than_two_sections_make_nothing():
    assert loft.loft([[0, 0, 0, 5, 5]]) == ([], [])
    assert loft.loft([]) == ([], [])


# ── the loft node: codegen, round trip, validation, the real engine ─

import os
import shutil
import subprocess

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

from PyQt5.QtWidgets import QApplication

from khervecad import document, mesh, scadparse
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _strip(code):
    return "\n".join(ln for ln in code.splitlines()
                     if not ln.startswith("//")).strip()


def test_the_loft_node_previews_as_one_closed_tube(app):
    doc = DocumentModel()
    doc.add_node("loft")
    tris = mesh.tessellate(doc.root)
    assert tris and _closed(tris) and _volume(tris) > 0


def test_loft_codegen_calls_a_helper_defined_once(app):
    doc = DocumentModel()
    doc.add_node("loft")
    doc.add_node("loft", dict(caps="flat"))
    code = doc.to_scad()
    assert code.count("module kcad_loft(") == 1
    assert code.count("function kcad_loft_path(") == 1
    calls = [ln for ln in code.splitlines()
             if ln.lstrip().startswith("kcad_loft(")]
    assert len(calls) == 2 and 'caps = "flat"' in calls[1]


def test_loft_round_trips_with_a_loop_variable(app, tmp_path):
    doc = DocumentModel()
    loop = doc.add_node("for_loop", dict(variable="k", start=0.0,
                                         end=2.0, step=1.0))
    doc.add_node("loft", dict(sections=[[0.0, "k * 20", 0.0, "k + 3", 3.0],
                                        [0.0, "k * 20", 25.0, 2.0, 2.0]],
                              smooth=1, caps="flat"), parent=loop)
    code1 = doc.to_scad()
    path = tmp_path / "loft.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    assert not scadparse.import_scad(other, str(path))
    assert _strip(other.to_scad()) == _strip(code1)
    lofts = [n for n in other.root.walk() if n.type == "loft"]
    assert lofts[0].params["sections"][0][3] == "k + 3"


def test_loft_validation(app):
    doc = DocumentModel()
    one = doc.add_node("loft", dict(sections=[[0.0, 0.0, 0.0, 5.0, 5.0]]))
    short = doc.add_node("loft", dict(sections=[[0.0, 0.0, 0.0, 5.0],
                                                [0.0, 0.0, 9.0, 5.0]]))
    typo = doc.add_node("loft", dict(sections=[[0.0, 0.0, 0.0, "r0", 5.0],
                                               [0.0, 0.0, 9.0, 5.0, 5.0]]))
    errors = validate(doc.root)
    assert "at least 2" in errors[one.id]
    assert "5 values" in errors[short.id]
    assert "section 0" in errors[typo.id]


def _openscad_binary():
    for candidate in (shutil.which("openscad"), "/opt/homebrew/bin/openscad",
                      "/usr/local/bin/openscad",
                      "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"):
        if candidate and Path(candidate).exists():
            return candidate
    return None


ENGINE_CASES = {
    "straight_flat": dict(sections=[[0.0, 0.0, 0.0, 5.0, 5.0],
                                    [0.0, 0.0, 20.0, 5.0, 5.0]],
                          sides=16, smooth=0, caps="flat"),
    "bent_round": dict(sections=[[0.0, 0.0, 0.0, 6.0, 5.0],
                                 [0.0, 0.0, 30.0, 4.5, 4.0],
                                 [15.0, 0.0, 50.0, 3.0, 3.0],
                                 [35.0, 8.0, 55.0, 2.0, 2.0]],
                       sides=12, smooth=2, caps="round"),
    "elliptic_along_x": dict(sections=[[0.0, 0.0, 0.0, 10.0, 3.0],
                                       [40.0, 0.0, 0.0, 10.0, 3.0]],
                             sides=20, smooth=0, caps="flat"),
    "ten_sides": dict(sections=[[0.0, 0.0, 0.0, 4.0, 4.0],
                                [10.0, 10.0, 5.0, 3.0, 3.0],
                                [20.0, 0.0, 10.0, 2.0, 2.0]],
                      sides=10, smooth=3, caps="round"),
    "helix": dict(sections=[[10 * math.cos(a), 10 * math.sin(a),
                             4.0 * a, 2.0, 2.0]
                            for a in [i * 0.6 for i in range(8)]],
                  sides=14, smooth=2, caps="round"),
}


@pytest.mark.parametrize("case", sorted(ENGINE_CASES))
def test_openscad_builds_the_same_tube_as_the_preview(app, tmp_path,
                                                      case):
    """kcad_loft runs loft.py's formulas in OpenSCAD's language; the
    exact render must match the preview in extent and volume."""
    binary = _openscad_binary()
    if binary is None:
        pytest.skip("OpenSCAD is not installed")
    from khervecad import engine
    doc = DocumentModel()
    doc.add_node("loft", ENGINE_CASES[case])
    scad, stl = tmp_path / f"{case}.scad", tmp_path / f"{case}.stl"
    scad.write_text(doc.to_scad())
    run = subprocess.run([binary, "-o", str(stl), str(scad)],
                         capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stderr[-1500:]
    exact = engine.parse_stl(str(stl))
    preview = mesh.tessellate(doc.root)
    for got, want in zip(_bounds(exact), _bounds(preview)):
        assert got == pytest.approx(want, abs=0.01), case
    assert _volume(exact) == pytest.approx(_volume(preview), rel=0.002)
