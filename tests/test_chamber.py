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
from khervecad import library, library_uhv, mesh
from khervecad.model import CadNode, DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _holder(node):
    root = CadNode("union", "root")
    root.add(node)
    return root


@pytest.mark.parametrize("pid", list(library_uhv.PARTS))
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

@pytest.mark.parametrize("name", list(cd.PRESETS))
def test_every_preset_builds_without_clashes(app, name):
    spec = cd.preset(name)
    assert cd.clashes(spec) == [], name
    node = cd.build(spec)
    assert not validate(_holder(node))
    objects = [n for n in node.children if n.type == "component"]
    accessories = [p for p in spec["ports"]
                   if cd.ACCESSORIES[p["accessory"]][1]]
    assert len(objects) >= 1 + len(accessories)


def test_analysis_chamber_has_a_mu_metal_liner_with_port_openings(app):
    spec = cd.preset("XPS analysis chamber (analyser, X-rays, mu-metal)")
    node = cd.build(spec)
    liner = next(n for n in node.children if n.name == "Mu-metal liner")
    openings = [n for n in liner.walk() if n.name == "Port opening"]
    assert len(openings) == len(spec["ports"])
    spec["liner"] = False
    assert "Mu-metal liner" not in {n.name for n in cd.build(spec).children}


def test_clashes_find_overlapping_and_short_ports():
    spec = cd.new_spec(radius=150.0)
    spec["ports"] = [cd.port("A", "CF100 (DN100)", 90, 0, 250),
                     cd.port("B", "CF100 (DN100)", 90, 10, 250),
                     cd.port("C", "CF40 (DN40)", 0, 0, 120),
                     cd.port("D", "KF25 (DN25)", 180, 0, 200, "leed")]
    found = cd.problems(cd.normalise(spec))
    text = " ".join(m for m, _p in found)
    assert "A and B flanges overlap" in text
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
