"""The City Builder (city.py): generated layouts, outside-only
buildings, loops for repeated items, and the build_city tool.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import city, mesh
from khervecad.model import CadNode, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    return win


@pytest.mark.parametrize("layout", ["village", "town", "city"])
def test_layouts_build_and_tessellate(layout):
    r = city.build({"layout": layout})
    assert r["counts"]["buildings"] > 5 and r["counts"]["lights"] > 0
    root = CadNode("union", "root", {})
    for node in r["nodes"].values():
        root.add(node)
    assert not validate(root)
    assert len(mesh.tessellate(root)) > 1000


def test_every_style_builds():
    for i, style in enumerate(city.STYLES):
        node = city.build_building(dict(style=style, w=10000, d=9000,
                                        floors=3), i)
        assert mesh.tessellate(node), style


def test_repeated_items_are_loops_not_copies():
    pts = [(i * 10000.0, 0.0, 0.0) for i in range(40)]
    lights = city.build_lights(pts)
    assert sum(1 for n in lights.walk() if n.type == "for_loop") == 1
    assert len(mesh.tessellate(lights)) >= 40 * 12


def test_bad_style_and_empty_spec_are_refused():
    with pytest.raises(city.CityError):
        city.build({"buildings": [{"style": "castle"}]})
    with pytest.raises(city.CityError):
        city.build({})


def test_build_city_tool_replaces_previous_build(window):
    out = city.build_city(window, {"layout": "village", "seed": 3})
    names = [o["name"] for o in out["objects"]]
    assert "City buildings" in names and "Street lights" in names
    city.build_city(window, {"layout": "village", "seed": 4})
    top = [c.name for c in window.model.root.children]
    assert top.count("City buildings") == 1
    dry = city.build_city(window, {"layout": "town", "dry_run": True})
    assert dry["dry_run"] and dry["counts"]["roads"] == 8


def test_spec_is_resolved_saved_and_undone(window, tmp_path):
    from khervecad import document
    from khervecad.model import DocumentModel
    city.build_city(window, {"layout": "village", "seed": 2})
    stored = window.model.city
    assert stored and stored["buildings"][0]["wall"] in \
        ("brick", "concrete", "render", "stone")
    assert isinstance(stored["lights"], list) and stored["lights"]
    path = tmp_path / "v.kcad"
    document.save_kcad(window.model, str(path))
    other = DocumentModel()
    document.load_kcad(other, str(path))
    assert other.city == stored


def test_every_wall_roof_and_tree_kind_builds():
    from khervecad import city_buildings as B, city_trees as T
    for wall in B.WALLS:
        for roof in B.ROOF_KINDS:
            for mat in B.ROOFS:
                n = B.build_building(dict(style="house", wall=wall,
                                          roof=roof, roof_material=mat))
                assert mesh.tessellate(n)
    for kind in T.TREE_KINDS:
        assert len(mesh.tessellate(T.build_trees([dict(kind=kind)]))) < 6000


def test_surface_materials_are_known_everywhere():
    from khervecad import glrender, view3d
    from khervecad.model import MATERIALS
    assert set(glrender.SURFACES) <= set(MATERIALS)
    assert set(glrender.SURFACES) <= set(view3d.MATERIAL_STYLES)


def test_builder_window_places_edits_and_builds(window):
    from PyQt5.QtCore import QPointF
    from khervecad import city_dialog
    panel = city_dialog.open_builder(window)
    panel._add_road([[-30000, 0], [30000, 0]])
    panel.style_combo.setCurrentText("cottage")
    panel._place("building", QPointF(0, 12000))
    b = panel.spec["buildings"][-1]
    assert abs(((b["rz"] + 180) % 360) - 180) in (0, 180)
    panel.b_wall.setCurrentText("brick")
    panel._wall_changed()
    assert b["wall"] == "brick"
    panel._place("tree", QPointF(5000, -6000))
    panel._place("light", QPointF(-5000, 5000))
    panel._rotate_selected(90)
    panel._build()
    assert window.model.city["buildings"][0]["wall"] == "brick"
    names = [c.name for c in window.model.root.children]
    assert "City buildings" in names and "City roads" in names
    panel.close()


def test_a_city_is_built_on_a_landscape():
    spec = {"layout": "village", "seed": 2,
            "terrain": {"kind": "hills", "height": 25000, "seed": 3}}
    r = city.build(spec)
    assert r["spec"]["terrain"]["kind"] == "hills"
    root = CadNode("union", "root", {})
    for node in r["nodes"].values():
        root.add(node)
    assert not validate(root)
    from khervecad import bake
    for p in root.walk():
        if p.type == "polyhedron":
            assert bake._check_polyhedron(p.params) is None, p.name
    # buildings stand on their pads, lights at ground height
    from khervecad.city_ground import Ground
    s = r["spec"]
    land = Ground(s["terrain"], city._extent(s), s["roads"], s["buildings"],
                  margin=max(s["ground"]["margin"], 10000.0),
                  road_style=city.road_style)
    comp = r["nodes"]["City buildings"]
    placed = [n for n in comp.children if n.type == "translate"]
    assert placed and all(abs(n.params["z"] - pad) < 1.0
                          for n, pad in zip(placed, land.pads))
    assert max(land.pads) - min(land.pads) > 1000     # really on a hill
    heights = [max(v[2] for t in mesh.tessellate(n) for v in t)
               for n in placed[:3]]
    assert all(h > 3000 for h in heights)
