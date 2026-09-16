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
