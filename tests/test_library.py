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
    assert "rotate_extrude" in code           # revolved drawing profile
    assert "[34.95," in code.replace(", ", ",")   # flange OD 69.9 / 2
    assert "[17.5," in code.replace(", ", ",")    # bore 35 / 2
    assert "for (a = [0 : 60 : 330])" in code  # 6 bolts every 60 deg
    tris = mesh.tessellate(model.root)
    assert len(tris) > 100


def test_cf40_knife_edge_profile():
    p = dict(library.CF_SIZES["CF40 (DN40)"])
    profile = library.cf_profile(p, tube_length=0.0)
    rs = [r for r, _z in profile]
    zs = [z for _r, z in profile]
    knife_r = p["gasket_od"] / 2.0 - 0.9      # 23.25
    floor = p["thickness"] - 1.6              # recess floor 11.1
    tip = floor + 1.1                         # knife tip 12.2
    assert [knife_r, tip] in profile          # the knife edge point
    # the tip sits below the face but above the recess floor
    assert floor < tip < p["thickness"]
    # recess wall just outside the gasket
    assert max(rs) == p["flange_od"] / 2.0
    assert any(abs(r - (p["gasket_od"] / 2.0 + 0.3)) < 1e-6
               for r in rs)


def test_cf_flange_tube_extends_below(model):
    _insert(model, "cf_flange", library.CF_SIZES, "CF40 (DN40)",
            extra=dict(port_length=50.0))
    zs = [v[2] for t in mesh.tessellate(model.root) for v in t]
    assert min(zs) < -30.0                    # tube below the flange
    assert max(zs) == pytest.approx(12.7, abs=0.1)


def test_bolt_count_scales_with_size(model):
    _insert(model, "cf_flange", library.CF_SIZES, "CF100 (DN100)")
    code = model.root.to_scad()
    assert "for (a = [0 : 22.5 : 348.75])" in code   # 16 bolts
    loop = next(n for n in model.root.walk() if n.type == "for_loop")
    assert len(loop.loop_values()) == 16


def test_custom_size_any_dimensions(model):
    dims = dict(flange_od=250.0, thickness=25.0, bolt_circle=220.0,
                bolts=24, bolt_hole=9.0, bore=180.0, tube_od=200.0,
                gasket_od=210.0, port_length=80.0)
    library_node = library.build_part("cf_flange", dims)
    model.root.add(library_node)
    code = model.root.to_scad()
    assert "[125," in code.replace(", ", ",")  # custom OD works
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


def test_turbo_sizes(model):
    small = library.build_part("turbo", {"_size": "DN63 CF (~80 l/s)"})
    big = library.build_part("turbo", {"_size": "DN160 CF (~700 l/s)"})
    model.root.add(small)
    model.root.add(big)
    code = model.root.to_scad()
    assert "r1=57.15" in code                 # CF63 inlet OD/2
    assert "r1=101.6" in code                 # CF160 inlet OD/2
    xs_small = [v[0] for t in mesh.tessellate(small) for v in t]
    xs_big = [v[0] for t in mesh.tessellate(big) for v in t]
    assert max(xs_big) > max(xs_small)        # bodies scale


def test_gate_valve_vat_style(model):
    dims = dict(library.CF_SIZES["CF63 (DN63)"])
    node = library.build_part("valve_gate", dims)
    model.root.add(node)
    code = model.root.to_scad()
    assert "hull()" in code                   # teardrop slab body
    tris = mesh.tessellate(model.root)
    xs = [v[0] for t in tris for v in t]
    zs = [v[2] for t in tris for v in t]
    face_to_face = max(xs) - min(xs)
    assert face_to_face < 1.1 * dims["flange_od"]   # thin body
    assert max(zs) > dims["bore"] + 20.0      # bonnet + actuator above
    ports = [n for n in node.walk() if n.name.startswith("Port ")]
    assert len(ports) == 2


def test_angle_valve_ports_at_90_degrees(model):
    dims = dict(library.CF_SIZES["CF40 (DN40)"])
    node = library.build_part("valve_angle", dict(dims,
                                                  port_length=50.0))
    model.root.add(node)
    tris = mesh.tessellate(model.root)
    xs = [v[0] for t in tris for v in t]
    zs = [v[2] for t in tris for v in t]
    assert max(xs) == pytest.approx(50.0, abs=1.0)   # side port +X
    assert min(zs) == pytest.approx(-50.0, abs=1.0)  # inlet -Z
    assert max(zs) > 60.0                     # handwheel on top
    code = model.root.to_scad()
    assert "sphere(" in code                  # valve body


def test_cf_elbow_two_ports_at_right_angle(model):
    node = _insert(model, "cf_elbow", library.CF_SIZES, "CF40 (DN40)")
    ports = [n for n in node.walk() if n.name.startswith("Port ")]
    assert len(ports) == 2
    tris = mesh.tessellate(model.root)
    xs = [v[0] for t in tris for v in t]
    zs = [v[2] for t in tris for v in t]
    assert max(xs) == pytest.approx(60.0, abs=1.0)   # +X port
    assert max(zs) == pytest.approx(60.0, abs=1.0)   # +Z port
    # only two ports: no -X/-Z tube reaching -60 (flange discs reach ~-35)
    assert min(xs) > -45.0 and min(zs) > -45.0


def test_kf_fittings_build(model):
    for pid, ports in (("kf_nipple", 2), ("kf_elbow", 2), ("kf_tee", 3)):
        node = library.build_part(
            pid, dict(library.KF_SIZES["KF25 (DN25)"], port_length=30.0))
        assert len([n for n in node.walk()
                    if n.name.startswith("Port ")]) == ports
        assert mesh.tessellate(node)         # KF has no bolt holes
        assert "for (" not in node.to_scad()


def test_feedthrough_has_pins_through_flange(model):
    node = library.build_part(
        "cf_feedthrough", dict(library.CF_SIZES["CF40 (DN40)"]))
    model.root.add(node)
    assert any(n.name == "Pins" for n in node.walk())
    tris = mesh.tessellate(model.root)
    zs = [v[2] for t in tris for v in t]
    assert max(zs) > 15.0 and min(zs) < -15.0        # pins protrude both


def test_hemispherical_analyser_is_a_dome(model):
    node = library.build_part(
        "analyser_hsa",
        dict(library.ANALYSER_SIZES["R150 (CF160 mount)"],
             _size="R150 (CF160 mount)"))
    model.root.add(node)
    code = model.root.to_scad()
    assert code.count("rotate_extrude") >= 2         # revolved domes
    tris = mesh.tessellate(model.root)
    zs = [v[2] for t in tris for v in t]
    assert max(zs) > 150.0                            # dome (r_out) + detector
    assert min(zs) < -60.0                            # lens column + mount


def test_part_categories_present():
    cats = {spec.get("category") for spec in library.PARTS.values()}
    assert "Vacuum" in cats and "Fasteners" in cats
    # the new vacuum parts are registered
    for pid in ("cf_elbow", "kf_elbow", "cf_feedthrough",
                "kf_feedthrough", "analyser_hsa"):
        assert pid in library.PARTS


# -------------------------------------------------------------- chemistry

from khervecad import library_chem              # noqa: E402
from khervecad.model import validate            # noqa: E402


@pytest.mark.parametrize("part_id", list(library_chem.PARTS))
def test_every_chemistry_part_builds(model, part_id):
    spec = library_chem.PARTS[part_id]
    size = next(iter(spec["sizes"]))
    dims = dict(spec["sizes"][size])
    dims["_size"] = size
    node = library.build_part(part_id, dims)
    model.root.add(node)
    assert not validate(model.root)               # no red errors
    assert len(mesh.tessellate(node)) > 0         # renders something


def test_glassware_is_revolved_and_hollow(model):
    # the beaker is a revolved wall profile (no boolean), so its inner
    # wall really exists — the built-in preview shows the cavity.
    node = library.build_part(
        "chem_beaker", dict(library_chem.BEAKER_SIZES["250 mL"],
                            _size="250 mL"))
    code = node.to_scad()
    assert "rotate_extrude" in code
    assert 'color("#cfe8ee")' in code             # glass tint
    tris = mesh.tessellate(node)
    zs = [v[2] for t in tris for v in t]
    assert max(zs) == pytest.approx(95.0, abs=1.0)   # 250 mL height


def test_chemistry_parts_registered_with_category(model):
    for pid, spec in library_chem.PARTS.items():
        assert pid in library.PARTS
        assert library.PARTS[pid]["category"] == "Chemistry"


# -------------------------------------------------------------- fasteners

def test_thread_profile_radii():
    points = library.thread_profile(6.0, 1.0)
    import math
    radii = [math.hypot(x, y) for x, y in points]
    assert max(radii) == pytest.approx(3.0, abs=0.01)      # major
    assert min(radii) == pytest.approx(3.0 - 0.6134, abs=0.01)


def test_hex_bolt_has_helical_thread(model):
    dims = dict(library.BOLT_SIZES["M6"])
    node = library.build_part("bolt_hex", dims)
    model.root.add(node)
    code = model.root.to_scad()
    assert "twist=-7200" in code              # 20 mm / 1.0 pitch
    assert "polygon(points=" in code
    assert "$fn=6" in code                    # hex head
    assert mesh.tessellate(model.root)


def test_nut_thread_is_subtracted(model):
    dims = dict(library.BOLT_SIZES["M8"])
    node = library.build_part("nut_hex", dims)
    model.root.add(node)
    assert node.type == "difference"
    code = model.root.to_scad()
    assert "$fn=6" in code                    # hex body
    assert "twist=" in code                   # internal thread
    # clearance: hole profile major radius > bolt major radius
    hole_profile = library.thread_profile(8.0 + 0.3, 1.25)
    import math
    assert max(math.hypot(x, y) for x, y in hole_profile) > 4.0


def test_socket_screw_has_hex_socket(model):
    dims = dict(library.BOLT_SIZES["M6"])
    node = library.build_part("bolt_socket", dims)
    model.root.add(node)
    assert node.type == "difference"
    zs = [v[2] for t in mesh.tessellate(model.root) for v in t]
    assert max(zs) == pytest.approx(26.0, abs=0.2)   # 20 + head d


def test_bolts_reimport_from_generated_code(model):
    model.global_fn_on = False                 # test per-object $fn
    dims = dict(library.BOLT_SIZES["M4"])
    model.root.add(library.build_part("bolt_hex", dims))
    root, warnings = scadparse.parse_scad(model.to_scad())
    assert not warnings
    other = DocumentModel()
    other.root = root
    assert other.root.to_scad() == model.root.to_scad()


def test_parts_reimport_from_generated_code(model, tmp_path):
    model.global_fn_on = False                 # test per-object $fn
    _insert(model, "cf_flange", library.CF_SIZES, "CF16 (DN16)")
    code = model.to_scad()
    root, warnings = scadparse.parse_scad(code)
    assert not warnings
    other = DocumentModel()
    other.root = root
    assert other.root.to_scad() == model.root.to_scad()
