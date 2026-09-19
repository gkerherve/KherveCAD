"""Animals (library_animals.py, library_animals_real.py): every cartoon
toy and every life-size animal builds clean, within a triangle budget,
standing on the ground and facing -Y, and both sit in Library ▸ Toys &
models ▸ Animals.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest

from khervecad import library, library_groups, mesh
from khervecad import library_animals as C
from khervecad import library_animals_real as R
from khervecad.model import validate

BUDGET = 150_000


def _check(node):
    assert not validate(node)
    tris = mesh.tessellate(node)
    assert 0 < len(tris) < BUDGET
    zs = [v[2] for t in tris for v in t]
    assert abs(min(zs)) < max(zs) * 0.03          # on the ground
    return tris


@pytest.mark.parametrize("name", list(C.SPECIES))
def test_cartoon_animals_build(name):
    tris = _check(C.build(name))
    height = max(v[2] for t in tris for v in t)
    assert 40 < height < 200                      # a toy, in mm


@pytest.mark.parametrize("name", list(R.SPECIES))
def test_realistic_animals_build_at_life_size(name):
    tris = _check(R.build(name))
    xs = [v[0] for t in tris for v in t]
    ys = [v[1] for t in tris for v in t]
    length = max(ys) - min(ys)
    assert length > 300                           # life size, in mm
    assert abs(max(xs) + min(xs)) < length * 0.1  # symmetric


def test_heads_face_minus_y():
    for name in ("Horse", "Cow", "Giraffe"):
        spec = R.SPECIES[name]
        j = R.rig(spec)
        assert j["neck"][1][1] < j["ribs"][0][1]


def test_markings_lie_on_the_blended_skin():
    spec = R.SPECIES["Zebra"]
    j = R.rig(spec)
    body = R._masses(spec, j)
    q, n = R.surface(body, [0, 0, spec["H"] - spec["D"] * 0.5], [1, 0, 0])
    assert q[0] > spec["W"] * 0.4 and n[0] > 0.5


def test_animals_menu():
    sub = {name: cats for section in library_groups.SECTIONS
           for name, _icon, cats in section[1]}
    assert sub["Animals"] == ["Cartoon animals"]      # realistic: hidden
    assert not any(pid.startswith("animal_") for pid in library.PARTS)
    cats = {library.PARTS[pid]["category"] for pid in library.PARTS
            if pid.startswith("cartoon_")}
    assert cats == {"Cartoon animals"}
    assert len(C.SPECIES) >= 25 and len(R.SPECIES) >= 20


def test_labrador_matches_the_photograph():
    """The Labrador template was traced from a side photograph scaled to
    the breed standard's 570 mm at the withers: keep its proportions."""
    lab = R.LAB
    top = lab["ribs"][0][2] + lab["ribs"][1][2]
    assert 540 < top < 590                           # withers ~570 mm
    brisket = lab["ribs"][0][2] - lab["ribs"][1][2]
    assert 240 < brisket < 290                       # chest to the elbow
    loin = lab["loin"][0][2] - lab["loin"][1][2]
    assert loin > brisket + 60                       # the tuck-up
    hip, stifle, hock = [q for q, _r in lab["hind"][:3]]
    assert stifle[2] < hip[2] and hock[1] > stifle[1]  # hock behind
    tris = mesh.tessellate(R.build("Dog (Labrador)"))
    ys = [v[1] for t in tris for v in t]
    zs = [v[2] for t in tris for v in t]
    assert 1150 < max(ys) - min(ys) < 1400           # nose to tail tip
    assert 600 < max(zs) < 720                       # the head's top
