"""The crystal library and builder (crystal.py, crystal_library.py,
crystal_build.py, crystal_dialog.py) and their MCP tools.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from dataclasses import replace

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import crystal as cr
from khervecad import crystal_build as cb
from khervecad import mesh
from khervecad.crystal_library import CATEGORIES, LIBRARY, get
from khervecad.model import validate
from khervecad.scadparse import parse_scad


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    return win


# ------------------------------------------------------------- library
@pytest.mark.parametrize("key", list(LIBRARY))
def test_every_crystal_matches_its_density_and_bonds(key):
    """A missing atom shows in the density, a slipped coordinate in the
    nearest distance."""
    c = LIBRARY[key]
    assert c.category in CATEGORIES
    assert c.computed_density() == pytest.approx(c.density, rel=0.025)
    for a, b, d in c.bonds:
        assert c.nearest(a, b) == pytest.approx(d, rel=0.015), (a, b)


@pytest.mark.parametrize("key", [k for k, c in LIBRARY.items()
                                 if c.polyhedra])
def test_polyhedra_are_whole_and_closed(key):
    c = LIBRARY[key]
    sites = c.polyhedra_sites()
    assert sites
    sizes = {len(ligands) for _i, _p, ligands in sites}
    assert len(sizes) == 1 and sizes.pop() in (4, 6, 8)
    for _i, _p, ligands in sites:
        points, faces = cr.polyhedron(ligands)
        assert len(points) == len(ligands)
        edges = set()
        for f in faces:
            edges |= {(a, b) for a, b in zip(f, f[1:] + f[:1])}
        # every edge once each way: closed and consistently wound
        assert all((b, a) in edges for a, b in edges)


def test_quartz_is_the_structure_checked_by_hand():
    q = get("quartz")
    assert q.composition() == {"Si": 3, "O": 6}
    assert q.polyhedra_label() == "SiO4 tetrahedra"
    assert q.nearest("Si", "O") == pytest.approx(1.604, abs=0.002)


def test_custom_crystals_are_checked():
    c = cr.custom({"a": 0.5, "units": "nm",
                   "atoms": [["na", 0, 0, 0], ["Cl", 0.5, 0.5, 0.5]]})
    assert c.a == pytest.approx(5.0)
    assert c.composition() == {"Na": 1, "Cl": 1}
    for bad in ({"a": 5, "atoms": []},
                {"a": 5, "atoms": [["Xx", 0, 0, 0]]},
                {"a": -1, "atoms": [["Na", 0, 0, 0]]},
                {"a": 5, "alpha": 180, "atoms": [["Na", 0, 0, 0]]}):
        with pytest.raises(ValueError):
            cr.custom(bad)


# ------------------------------------------------------------- builder
def _built(spec):
    code, stats = cb.program(spec)
    root, warnings = parse_scad(code)
    assert not warnings
    assert not validate(root)
    return root, stats


@pytest.mark.parametrize("spec", [
    cb.Spec(get("quartz")),
    cb.Spec(get("nacl"), build="particle", size=3, fill="atoms"),
    cb.Spec(get("cu"), build="particle", shape="octahedron", size=4),
    cb.Spec(get("rutile"), build="particle", shape="cube", size=3,
            fill="polyhedra"),
    cb.Spec(get("gan"), build="particle", shape="hexagonal_prism", size=4,
            height=3),
    cb.Spec(get("au"), build="particle", shape="box", box=(3, 2, 1.5)),
    cb.Spec(get("srtio3"), build="unit_cell"),
], ids=lambda s: f"{s.crystal.key}-{s.build}-{s.shape}")
def test_the_count_is_what_the_view_draws(spec):
    """The builder counts with the loops the program runs: its triangle
    estimate is exactly what the preview tessellates."""
    root, stats = _built(spec)
    assert len(mesh.tessellate(root, fn=spec.fn)) == stats["triangles"]


def test_a_hemisphere_of_blocks_stacks_each_column_with_a_while():
    """The r = 50 nm quartz dome first built by hand: 2322 blocks of
    10^3 cells."""
    root, stats = _built(cb.Spec(get("quartz"), build="particle",
                                 shape="hemisphere", size=100, fill="blocks",
                                 block=10))
    assert stats["particle"]["blocks"] == 2322
    assert any(n.type == "while_loop" for n in root.walk())
    zs = [v[2] for t in mesh.tessellate(root) for v in t]
    assert min(zs) == pytest.approx(0, abs=1e-6)
    assert max(zs) == pytest.approx(48.48, abs=0.01)


def test_a_triclinic_lattice_takes_the_general_path():
    c = cr.custom({"a": 5, "b": 6, "c": 7, "alpha": 80, "beta": 85,
                   "gamma": 95, "atoms": [["Na", 0, 0, 0],
                                          ["Cl", 0.5, 0.5, 0.5]]})
    root, stats = _built(cb.Spec(c, size=4))
    assert not stats["particle"]["uses_while"]
    assert len(mesh.tessellate(root)) == stats["triangles"]


def test_auto_fills_big_particles_with_blocks_and_refuses_the_rest():
    stats = cb.program(cb.Spec(get("au"), build="particle", size=60))[1]
    assert stats["particle"]["fill"] == "blocks"
    assert stats["triangles"] <= cb.BUDGET
    with pytest.raises(cb.BuildError, match="blocks"):
        cb.program(cb.Spec(get("au"), build="particle", size=20,
                           fill="atoms"))


def test_bad_specs_are_refused():
    for field, value in (("shape", "torus"), ("size", 0), ("gap", 0.9),
                         ("build", "everything")):
        with pytest.raises(cb.BuildError):
            replace(cb.Spec(get("cu")), **{field: value}).check()


# --------------------------------------------------------------- apply
def test_apply_builds_three_objects_in_nanometres(window):
    stats = cb.apply(window, cb.Spec(get("quartz"), size=4))
    model = window.model
    assert model.unit == "nm"
    names = [o["name"] for o in stats["objects"]]
    assert len(names) == 3 and any("unit cell" in n for n in names)
    variables = {n.params["variable"] for n in model.root.walk()
                 if n.type == "assign"}
    assert {"quartz_r", "quartz_na"} <= variables
    again = cb.apply(window, cb.Spec(get("quartz"), build="unit_cell"))
    assert again["variables_prefix"] == "quartz2"


def test_apply_into_a_millimetre_document_says_so(window):
    window.model.add_node("cube")
    stats = cb.apply(window, cb.Spec(get("cu"), build="unit_cell"))
    assert window.model.unit == "mm"
    assert any("true size" in note for note in stats["notes"])


def test_mcp_tools(window):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(window)
    assert len(ex.execute("list_crystals", {})["crystals"]) == len(LIBRARY)
    one = ex.execute("list_crystals", {"crystal": "rutile"})
    assert one["polyhedra"] == "TiO6 octahedra" and len(one["atoms"]) == 6
    dry = ex.execute("build_crystal", {"crystal": "cu", "build": "particle",
                                       "size_nm": 4, "dry_run": True})
    assert dry["dry_run"] and dry["particle"]["cells"] > 0
    assert not any(n.type == "component" for n in window.model.root.walk())
    out = ex.execute("build_crystal", {"crystal": "zno", "size_nm": 4})
    assert len(out["objects"]) == 3
    assert "Choices" in ex.execute("build_crystal",
                                   {"crystal": "unobtainium"})["error"]


def test_scatter_spreads_particles_over_the_area(window):
    """Several particles sparse over a patch: inside it, on the plane,
    never touching."""
    spec = cb.Spec(get("au"), build="scatter", shape="hemisphere", size=6,
                   count=15, area=(60.0, 40.0), seed=3, min_gap=1.0)
    root, stats = _built(spec)
    assert stats["scatter"]["particles"] == 15
    spots = cb._scatter_spots(spec)
    for i, (x, y, z, _turn) in enumerate(spots):
        assert abs(x) <= 30 and abs(y) <= 20 and z == 0
        for x2, y2, _z2, _t2 in spots[i + 1:]:
            gap = ((x - x2) ** 2 + (y - y2) ** 2) ** 0.5
            assert gap >= 6 + 1 - 1e-9        # two footprints and the gap
    assert len(mesh.tessellate(root, fn=spec.fn)) == stats["triangles"]


def test_a_scattered_sphere_rests_on_the_plane():
    spec = cb.Spec(get("cu"), build="scatter", shape="sphere", size=5,
                   count=3, area=(50.0, 50.0))
    assert all(z == pytest.approx(2.5) for _x, _y, z, _t
               in cb._scatter_spots(spec))


def test_scatter_repeats_with_its_seed_and_owns_up_when_full():
    same = [cb._scatter_spots(cb.Spec(get("cu"), build="scatter", seed=7))
            for _ in range(2)]
    assert same[0] == same[1]
    _root, stats = _built(cb.Spec(get("cu"), build="scatter", size=10,
                                  count=50, area=(30.0, 30.0)))
    assert stats["scatter"]["particles"] < 50
    assert any("particles asked for" in note for note in stats["notes"])


def test_dialog_counts_refuses_and_builds(window):
    from khervecad import crystal_dialog
    panel = crystal_dialog.open_builder(window)
    panel.crystal.setCurrentIndex(panel.crystal.findData("nacl"))
    panel.build.setCurrentIndex(panel.build.findData("particle"))
    panel.fill.setCurrentIndex(panel.fill.findData("atoms"))
    panel.size.setValue(40)
    panel._refresh()
    assert not panel.go.isEnabled()          # a 40 nm ball of atoms
    panel.size.setValue(3)
    panel._refresh()
    assert panel.go.isEnabled() and "cells" in panel.estimate.text()
    panel.build_now()
    assert any(n.type == "component" for n in window.model.root.children)
    panel.close()
