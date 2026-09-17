"""Library ▸ Engineering ▸ Mechanisms & motion: every mechanism parses,
lands as Objects with prefixed Customizer variables beside what is
there, moves when its slider does, keeps its gears clear, and renders in
OpenSCAD.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import subprocess

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import anchors, analysis, library, library_motion as lm
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _parts(doc, comps):
    env = anchors.doc_env(doc)
    return {c.name: anchors.local_tris(c, env=env, fn=doc.effective_fn())
            for c in comps}


def _var(doc, suffix):
    return next(n for n in doc.global_assigns()
                if n.params["variable"].endswith(suffix))


@pytest.mark.parametrize("pid", list(lm.MECHANISMS))
def test_mechanism_inserts_with_sliders_and_moves(app, pid):
    from khervecad.customizer_panel import annotated
    assert pid in library.PARTS
    doc = DocumentModel()
    comps = lm.insert(pid, doc)
    assert comps and all(c.type == "component" for c in comps)
    assert not validate(doc.root)
    sliders = annotated(doc)
    assert sliders
    prefix = lm.MECHANISMS[pid][1] + "_"
    assert all(n.params["variable"].startswith(prefix) for n in sliders)
    label = lm.MECHANISMS[pid][0]
    assert all(n.params["group"].startswith(label) for n in sliders)
    driver = sliders[0]
    before = _parts(doc, comps)
    spec = driver.params["options"].split(":")
    lo, hi = float(spec[0]), float(spec[-1])
    driver.params["value"] = round(lo + (hi - lo) * 0.37)
    after = _parts(doc, comps)
    assert any(before[k] != after[k] for k in before)


def test_a_second_copy_gets_its_own_variables_and_stands_beside(app):
    doc = DocumentModel()
    first = lm.insert("motion_crank", doc)
    second = lm.insert("motion_crank", doc)
    names = [n.params["variable"] for n in doc.global_assigns()]
    assert "crank_angle" in names and "crank2_angle" in names
    assert len(set(c.name for c in first + second)) == len(first) * 2
    assert all(c.params["x"] > 0 for c in second)
    code = doc.to_scad_map()[0]
    assert "m = crank2_m" in code          # named arguments keep their name
    assert "gear's centre" in code          # comments are not renamed


@pytest.mark.parametrize("pid,var,parts", [
    ("motion_gear_pair", "_angle", ("Drive gear", "Driven gear")),
    ("motion_rack", "_angle", ("Pinion", "Rack")),
    ("motion_planetary", "_angle", ("Sun", "Planets", "Ring")),
])
def test_gears_stay_in_mesh_without_touching(app, pid, var, parts):
    doc = DocumentModel()
    comps = lm.insert(pid, doc)
    angle = _var(doc, var)
    for value in (0, 23, 140):
        angle.params["value"] = value
        meshes = _parts(doc, comps)
        result = analysis.interference([(n, meshes[n]) for n in parts])
        assert all(r["status"] == "clear" for r in result), (value, result)


def test_build_gives_one_node_for_the_part_library(app):
    node = library.default_part("motion_four_bar")
    assert node.type == "union" and node.children


def test_mechanisms_render_in_openscad(app, tmp_path):
    from tests.test_gears import _openscad
    binary = _openscad()
    if binary is None:
        pytest.skip("OpenSCAD not installed")
    for pid in ("motion_planetary", "motion_scissor"):
        doc = DocumentModel()
        lm.insert(pid, doc)
        src = tmp_path / f"{pid}.scad"
        src.write_text(doc.to_scad_map()[0])
        out = tmp_path / f"{pid}.stl"
        run = subprocess.run([binary, "-o", str(out), str(src)],
                             capture_output=True, text=True, timeout=300)
        assert run.returncode == 0, run.stderr
        assert out.stat().st_size > 1000
