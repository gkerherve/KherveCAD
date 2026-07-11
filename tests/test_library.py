"""Tests for the vacuum parts library.

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

from khervecad import library, mesh, scadparse
from khervecad.model import DocumentModel


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


def _insert(model, part_id, size_table, size, extra=None):
    dims = dict(size_table[size])
    dims.setdefault("port_length", 60.0)
    if extra:
        dims.update(extra)
    node = library.build_part(part_id, dims)
    model.root.add(node)
    model.structure_changed.emit()
    return node


def test_cf40_flange_dimensions(model):
    node = _insert(model, "cf_flange", library.CF_SIZES, "CF40 (DN40)")
    code = model.root.to_scad()
    assert "r1=34.95" in code                 # flange OD 69.9 / 2
    assert "for (a = [0 : 60 : 330])" in code  # 6 bolts every 60 deg
    assert "r1=17.5" in code                  # bore 35 / 2
    tris = mesh.tessellate(model.root)
    assert len(tris) > 100


def test_bolt_count_scales_with_size(model):
    _insert(model, "cf_flange", library.CF_SIZES, "CF100 (DN100)")
    code = model.root.to_scad()
    assert "for (a = [0 : 22.5 : 348.75])" in code   # 16 bolts
    loop = next(n for n in model.root.walk() if n.type == "for_loop")
    assert len(loop.loop_values()) == 16


def test_custom_size_any_dimensions(model):
    dims = dict(flange_od=250.0, thickness=25.0, bolt_circle=220.0,
                bolts=24, bolt_hole=9.0, bore=180.0, tube_od=200.0,
                port_length=80.0)
    library_node = library.build_part("cf_flange", dims)
    model.root.add(library_node)
    code = model.root.to_scad()
    assert "r1=125" in code                   # custom OD works
    assert "for (a = [0 : 15 : 352.5])" in code


def test_tee_has_three_ports(model):
    node = _insert(model, "cf_tee", library.CF_SIZES, "CF40 (DN40)")
    ports = [n for n in node.walk() if n.name.startswith("Port ")]
    assert len(ports) == 3
    tris = mesh.tessellate(model.root)
    xs = [v[0] for t in tris for v in t]
    zs = [v[2] for t in tris for v in t]
    assert max(xs) == pytest.approx(60.0, abs=1.0)   # +X port
    assert min(xs) == pytest.approx(-60.0, abs=1.0)  # -X port
    assert max(zs) == pytest.approx(60.0, abs=1.0)   # +Z port


def test_cross_has_four_ports(model):
    node = _insert(model, "cf_cross", library.CF_SIZES, "CF63 (DN63)")
    ports = [n for n in node.walk() if n.name.startswith("Port ")]
    assert len(ports) == 4
    zs = [v[2] for t in mesh.tessellate(model.root) for v in t]
    assert min(zs) == pytest.approx(-60.0, abs=1.0)  # -Z port too


def test_kf_flange(model):
    _insert(model, "kf_flange", library.KF_SIZES, "KF25 (DN25)",
            extra=dict(port_length=30.0))
    code = model.root.to_scad()
    assert "r1=20" in code                    # flange OD 40 / 2
    assert "r1=12" in code                    # bore 24 / 2
    assert mesh.tessellate(model.root)


def test_turbo_pump_builds(model):
    node = library.build_part("turbo", {})
    model.root.add(node)
    code = model.root.to_scad()
    assert "r1=76.2" in code                  # CF100 inlet flange OD/2
    assert "r1=14" in code                    # KF25 exhaust tube OD/2
    tris = mesh.tessellate(model.root)
    zs = [v[2] for t in tris for v in t]
    assert max(zs) > 110.0                    # inlet flange on top
    assert min(zs) < -40.0                    # base collar below


def test_parts_reimport_from_generated_code(model, tmp_path):
    _insert(model, "cf_flange", library.CF_SIZES, "CF16 (DN16)")
    code = model.to_scad()
    root, warnings = scadparse.parse_scad(code)
    assert not warnings
    other = DocumentModel()
    other.root = root
    assert other.root.to_scad() == model.root.to_scad()
