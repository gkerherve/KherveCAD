"""The surface-science UHV parts (sample holders, transfer arms,
manipulators, prep and analysis tools) and the Chamber Designer.

Run with: python -m pytest tests/  (offscreen Qt).

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
from PyQt5.QtWidgets import QApplication, QMainWindow

from khervecad import chamber_design as cd
from khervecad import library, library_manip, library_uhv, library_xps, mesh
from khervecad.model import CadNode, DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _holder(node):
    root = CadNode("union", "root")
    root.add(node)
    return root


@pytest.mark.parametrize("pid", list(library_uhv.PARTS)
                         + list(library_manip.PARTS)
                         + list(library_xps.PARTS))
def test_every_uhv_part_builds_in_every_size(app, pid):
    for size, row in library.PARTS[pid]["sizes"].items():
        node = library.build_part(pid, dict(row, _size=size))
        assert not validate(_holder(node)), (pid, size)
        colours = mesh.part_colours(_holder(node))
        assert any(c[2] == "Metal" for c in colours), (pid, size)


def test_uhv_parts_are_in_the_vacuum_library():
    assert set(library_uhv.PARTS) <= set(library.PARTS)
    assert {library.PARTS[p]["category"] for p in library_uhv.PARTS} == {
        "Vacuum"}


def _names(node):
    return {n.name for n in node.walk()}


def test_tools_reach_the_sample(app):
    """The business end of a port tool sits `reach` below the sealing
    face: a manipulator's flag plate, a transfer arm's sample."""
    arm = library.build_part("transfer_sample", dict(
        library_uhv.TRANSFER_SIZES["Travel 300 mm, flag fork (CF40)"],
        reach=200.0))
    assert {"Flag fork", "Sample crystal", "Magnet carriage"} <= _names(arm)
    pts = library.build_part("transfer_sample", dict(
        library_uhv.TRANSFER_SIZES["Travel 600 mm, PTS bayonet (CF40)"]))
    assert {"Bayonet cup", "PTS sample holder"} <= _names(pts)
    manip = library.build_part("manipulator_xyzt", dict(
        library_uhv.XYZT_SIZES["XYZT, Z 200 mm, flag head + LN2 (CF100)"]))
    assert {"Copper block", "LN2 reservoir", "Rotary drive (T)",
            "Flag sample plate"} <= _names(manip)


def test_prep_and_analysis_tools_carry_their_details(app):
    leed = library.default_part("leed")
    assert {"Grid 1", "Grid 4", "Phosphor screen",
            "Rear viewport"} <= _names(leed)
    hsa = library.default_part("analyser_lens")
    assert {"Entrance nozzle", "Outer hemisphere (mu-metal shield)",
            "Detector housing"} <= _names(hsa)
    gun = library.default_part("sputter_gun")
    assert {"Ionisation chamber", "Leak valve", "SHV connector"} <= \
        _names(gun)


# ── chamber design ──────────────────────────────────────────────────

def _components(node):
    return [n for n in node.walk() if n.type == "component"]


@pytest.mark.parametrize("name", list(cd.PRESETS))
def test_every_preset_builds_without_clashes(app, name):
    spec = cd.preset(name)
    assert cd.clashes(spec) == [], name
    node = cd.build(spec)
    assert not validate(_holder(node))
    names = {n.name for n in _components(node)}
    for p in spec["ports"]:
        if cd.ACCESSORIES[p["accessory"]][1]:
            assert any(n.startswith(p["name"] + ":") for n in names), \
                (name, p["name"])
    assert "Chamber" in names


def test_the_bench_stands_on_the_floor_under_the_chamber(app):
    spec = cd.preset("Preparation chamber (LEED, sputter, evaporator)")
    spec["beam_height"] = 1200.0
    for kind in cd.BENCHES:
        spec["bench"] = kind
        node = cd.build(spec)
        tris = mesh.tessellate(_holder(node))
        low = min(p[2] for t in tris for p in t)
        assert low == pytest.approx(0.0, abs=1.0) if kind != "none" \
            else low > 500.0, kind
    # the chamber itself rides at the beam height
    spec["bench"] = "none"
    tris = mesh.tessellate(_holder(cd.build(spec)))
    assert min(p[2] for t in tris for p in t) > 1200.0 - spec["radius"] - 450


def test_turning_the_chamber_turns_its_ports_but_not_the_bench(app):
    spec = cd.preset("Preparation chamber (LEED, sputter, evaporator)")
    spec["bench"] = "frame"
    upright = cd.build(spec)
    spec["ry"] = 30.0
    turned = cd.build(spec)
    assert any(n.type == "rotate" and n.name == "Chamber orientation"
               for n in turned.walk())
    floor = [min(p[2] for t in mesh.tessellate(_holder(n)) for p in t)
             for n in (upright, turned)]
    assert floor[0] == pytest.approx(floor[1], abs=1.0)


def test_a_port_aims_at_its_own_focal_point(app):
    spec = cd.normalise(dict(cd.new_spec(body="cylinder", radius=150.0),
                             height=600.0, bench="none", beam_height=0.0))
    p = cd.port("Side", "CF63 (DN63)", 90.0, 0.0, 260.0, "viewport",
                focus=200.0)
    spec["ports"] = [p]
    assert cd.wall_distance(spec, p) == pytest.approx(150.0)
    node = cd.build(spec)
    tris = mesh.tessellate(_holder(node))
    far = [t for t in tris if max(q[0] for q in t) > 200.0]
    assert far, "the port reaches out past the wall"
    assert min(q[2] for t in far for q in t) > 120.0, \
        "and it sits at its focal height, not at the centre"


def test_a_variant_picks_the_size_row_of_the_accessory(app):
    p = cd.port("M", "CF100 (DN100)", 0.0, 0.0, 400.0, "manipulator",
                variant="Omniax style Z600, CF160 base, motorised, PTS head")
    dims = cd.accessory_dims(p)
    assert dims["z_travel"] == 600.0
    assert dims["mount"] == "CF100 (DN100)"     # the port's flange wins
    assert dims["reach"] == 400.0
    assert cd.normalise(dict(cd.new_spec(), ports=[dict(p, variant="nope")])
                        )["ports"][0]["variant"] == ""


def test_spin_turns_the_accessory_about_its_port(app):
    p = cd.port("Mono", "CF63 (DN63)", 90.0, 0.0, 250.0, "mono", spin=90.0)
    spec = cd.normalise(dict(cd.new_spec(radius=170.0), bench="none",
                             beam_height=0.0, ports=[p]))
    node = cd.build(spec)
    assert any(n.type == "rotate" and n.params.get("z") == 90.0
               for n in node.walk())


def test_clashes_find_overlapping_and_short_ports():
    spec = cd.new_spec(radius=150.0)
    spec["ports"] = [cd.port("A", "CF100 (DN100)", 90, 0, 250),
                     cd.port("B", "CF100 (DN100)", 90, 10, 250),
                     cd.port("C", "CF40 (DN40)", 0, 0, 120),
                     cd.port("D", "KF25 (DN25)", 180, 0, 200, "leed")]
    found = cd.problems(cd.normalise(spec))
    text = " ".join(m for m, _p in found)
    assert "A and B flanges collide" in text
    assert "C: too short" in text
    assert "D: LEED optics needs a CF flange" in text
    assert {0, 1} in [ports for _m, ports in found]


def test_ports_clear_every_body():
    for body in cd.BODIES:
        spec = cd.normalise(dict(cd.new_spec(body=body), height=400.0))
        for theta in (0.0, 45.0, 90.0, 135.0, 180.0):
            p = cd.port("P", "CF63 (DN63)", theta, 30.0, 0.0)
            p["length"] = cd.min_length(spec, p)
            spec["ports"] = [p]
            assert cd.clashes(spec) == [], (body, theta)
            assert not validate(_holder(cd.build(spec)))


def test_kf_ports_and_json_round_trip():
    spec = cd.preset("Load lock (fast entry, carousel)")
    assert any(cd.family(p["flange"]) == "KF" for p in spec["ports"])
    again = cd.normalise(json.loads(json.dumps(spec)))
    assert again == spec


# ── the designer window ─────────────────────────────────────────────

class _Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.model = DocumentModel()


def test_designer_builds_and_updates_in_place(app):
    from khervecad import chamber_dialog
    win = _Window()
    dlg = chamber_dialog.open_designer(win)
    assert chamber_dialog.open_designer(win) is dlg
    assert dlg.table.rowCount() == len(dlg.spec["ports"]) > 5
    dlg.build_now()
    assert len(win.model.root.children) == 1
    first = win.model.root.children[0]
    dlg._add_port(150.0, 200.0)
    dlg._drag_port(len(dlg.spec["ports"]) - 1, 140.0, 210.0)
    assert dlg.spec["ports"][-1]["theta"] == 140.0
    dlg.build_now(replace=True)
    assert len(win.model.root.children) == 1
    assert win.model.root.children[0] is not first
    dlg.map.resize(900, 420)
    dlg.map.grab()                               # paints without error
    dlg.close()
