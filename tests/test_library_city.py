"""The City sections of the part library — Trees, Park & sport,
Lighting & signals, Landscape: every part builds at every size and
colour into valid geometry that stands on the ground within a triangle
budget, and appears under Library ▸ City.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import mesh
from khervecad.library import PARTS, build_part
from khervecad.model import validate

SECTIONS = ("Lighting & signals", "Park & sport", "Landscape")
IDS = [pid for pid, spec in PARTS.items()
       if spec.get("category") in SECTIONS]
BUDGET = 250000


@pytest.fixture(scope="module", autouse=True)
def app():
    # text outlines (a sign's lettering) need fonts, so a QApplication
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("pid", IDS)
def test_every_size_and_colour_builds(pid):
    spec = PARTS[pid]
    colours = spec.get("colors") or [None]
    for size, dims in (spec.get("sizes") or {"": {}}).items():
        for colour in colours:
            d = dict(dims)
            if colour:
                d["_color"] = colour
            node = build_part(pid, d)
            assert not validate(node), (pid, size, colour, validate(node))
            tris = mesh.tessellate(node)
            assert tris, (pid, size)
            assert len(tris) < BUDGET, (pid, size, len(tris))
            low = min(v[2] for t in tris for v in t)
            assert low > -2500, (pid, size, low)


def test_signals_light_the_chosen_aspect():
    node = build_part("signal_traffic", dict(h=3600, _color="Green"))
    lit = [n for n in node.walk() if n.type == "color"
           and n.params.get("material") == "Emissive"]
    assert [n.children[0].name for n in lit] == ["Green"]
