"""The library sections added for cards, pots and more vacuum hardware,
the Brackets / Minecraft / Pots sections read from parts/ subfolders,
the Showcase car — and the preview fix the cards needed: 2D transforms
inside an extrusion.

Run with: python -m pytest tests/  (offscreen Qt).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import (analysis, examples, library, library_cards,
                       library_kcad, library_pots, library_vacuum, mesh,
                       scadparse)
from khervecad.model import CadNode, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _bbox(tris):
    xs = [p[0] for t in tris for p in t]
    ys = [p[1] for t in tris for p in t]
    return min(xs), max(xs), min(ys), max(ys)


def _build(pid, size=None, **extra):
    spec = library.PARTS[pid]
    sizes = spec.get("sizes") or {}
    size = size or (next(iter(sizes)) if sizes else None)
    dims = dict(sizes.get(size, {}))
    if size:
        dims["_size"] = size
    dims.update(extra)
    return library.build_part(pid, dims)


# ── the preview fix: 2D transforms inside an extrusion ──────────────

def test_2d_transforms_inside_an_extrude_reach_the_preview(app):
    """They used to be dropped: a turned or scaled shape came out where
    and as big as it was drawn."""
    root, _w = scadparse.parse_scad(
        "linear_extrude(1) translate([10, 0]) rotate([0, 0, 180]) "
        "scale([2, 2, 1]) square([5, 5]);")
    x0, x1, y0, y1 = _bbox(mesh.tessellate(root))
    assert (x0, x1) == pytest.approx((0.0, 10.0))
    assert (y0, y1) == pytest.approx((-10.0, 0.0))
    ext = CadNode("linear_extrude", "e", dict(height=1.0))
    flip = CadNode("mirror", "m", dict(x=1.0, y=0.0, z=0.0))
    flip.add(CadNode("rect", "r", dict(x=2.0, y=0.0, width=3.0,
                                       height=1.0)))
    ext.add(flip)
    x0, x1, _y0, _y1 = _bbox(mesh.tessellate(ext))
    assert (x0, x1) == pytest.approx((-5.0, -2.0))
    # a mirrored outline still extrudes into an outward-facing solid
    assert analysis.mass_properties(mesh.tessellate(ext))["volume"] == \
        pytest.approx(3.0)


def test_a_2d_difference_cuts_its_hole_in_the_preview(app):
    """The hole used to be extruded as a second solid: a frame came out
    as a filled square, a pot drawn as outline-minus-inset as a block."""
    root, _w = scadparse.parse_scad(
        "linear_extrude(1) difference() { square([10, 10]); "
        "translate([2, 2]) square([6, 6]); }")
    tris = mesh.tessellate(root)
    props = analysis.mass_properties(tris)
    assert props["volume"] == pytest.approx(100.0 - 36.0)
    # one closed solid: every edge shared by exactly two faces
    edges = {}
    for tri in tris:
        keys = [tuple(round(c, 6) for c in p) for p in tri]
        for a, b in zip(keys, keys[1:] + keys[:1]):
            edge = (a, b) if a <= b else (b, a)
            edges[edge] = edges.get(edge, 0) + 1
    assert set(edges.values()) == {2}


def test_letters_keep_their_counters(app):
    solid, _w = scadparse.parse_scad("linear_extrude(1) text(\"I\", "
                                     "size=10);")
    ring, _w = scadparse.parse_scad("linear_extrude(1) text(\"O\", "
                                    "size=10);")
    o_tris = mesh.tessellate(ring)
    x0, x1, y0, y1 = _bbox(o_tris)
    centre = ((x0 + x1) / 2, (y0 + y1) / 2)
    # nothing covers the middle of the O: its counter is a hole
    top = [t for t in o_tris if all(abs(p[2] - 1.0) < 1e-6 for p in t)]
    covered = any(_in_tri(centre, t) for t in top)
    assert not covered
    assert mesh.tessellate(solid)


def _in_tri(p, t):
    (ax, ay, _), (bx, by, _), (cx, cy, _) = t
    d1 = (p[0] - bx) * (ay - by) - (ax - bx) * (p[1] - by)
    d2 = (p[0] - cx) * (by - cy) - (bx - cx) * (p[1] - cy)
    d3 = (p[0] - ax) * (cy - ay) - (cx - ax) * (p[1] - ay)
    neg = min(d1, d2, d3) < 0
    pos = max(d1, d2, d3) > 0
    return not (neg and pos)


# ── playing cards ────────────────────────────────────────────────────

def _ink(node, colour):
    root = CadNode("root")
    root.add(node)
    return [t for t, c in mesh.tessellate_colored(root)
            if c and c[0] == colour]


@pytest.mark.parametrize("pid", sorted(library_cards.PARTS))
def test_every_card_builds_and_previews(app, pid):
    for size in library.PARTS[pid]["sizes"]:
        node = _build(pid, size)
        root = CadNode("root")
        root.add(node)
        assert validate(root) == {}, (pid, size)
        assert mesh.tessellate(root), (pid, size)


def test_a_card_has_rounded_corners(app):
    card = _build("card_hearts", "Seven")
    paper = _ink(card, library_cards.PAPER)
    w, h = library_cards.DEFAULT["width"], library_cards.DEFAULT["height"]
    x0, x1, y0, y1 = _bbox(paper)
    assert (x1 - x0, y1 - y0) == pytest.approx((w, h), abs=0.05)
    # nothing reaches the sharp corner: it is rounded off
    corner = max(p[0] + p[1] for t in paper for p in t)
    assert corner < w / 2 + h / 2 - 0.8


def test_the_index_is_in_both_opposite_corners(app):
    """The deck's "7" sat in one corner only: the copy turned half round
    for the other corner vanished in the preview."""
    card = _build("card_hearts", "Seven")
    ink = _ink(card, library_cards.RED)
    w, h = library_cards.DEFAULT["width"], library_cards.DEFAULT["height"]
    pts = [p for t in ink for p in t]
    top_left = [p for p in pts if p[0] < -w / 2 + 9 and p[1] > h / 2 - 17]
    bottom_right = [p for p in pts
                    if p[0] > w / 2 - 9 and p[1] < -h / 2 + 17]
    assert top_left and bottom_right


def test_a_seven_has_seven_pips_and_the_lower_ones_turned(app):
    card = _build("card_clubs", "Seven")
    pips = [n for n in card.walk() if n.name == "Pip"]
    assert len(pips) == 7 + 2                    # the field + two indices
    turned = [n for n in pips if any(c.type == "rotate" for c in n.walk())]
    assert len(turned) == 2                      # the two low field pips
    # the second index is the whole corner turned half round
    corner = next(n for n in card.walk() if n.name == "Bottom-right index")
    assert any(c.type == "rotate" and c.params.get("z") == 180.0
               for c in corner.walk())
    ink = _ink(card, library_cards.BLACK)
    ys = [p[1] for t in ink for p in t if abs(p[0]) > 8 and abs(p[0]) < 18]
    assert min(ys) < -20 and max(ys) > 20        # pips high and low


def test_court_cards_are_drawn_top_and_bottom(app):
    king = _build("card_diamonds", "King")
    ink = _ink(king, library_cards.RED)
    inside = [p for t in ink for p in t if abs(p[0]) < 6]
    assert min(p[1] for p in inside) < -15 and max(p[1] for p in inside) > 15


def test_the_back_is_a_full_lattice(app):
    back = _ink(_build("card_spades", "Ace"), library_cards.BACK)
    x0, x1, y0, y1 = _bbox(back)
    assert x1 - x0 > 50 and y1 - y0 > 80
    assert len(back) > 500                       # many diamonds, not one


# ── pots ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("pid", sorted(library_pots.PARTS))
def test_every_pot_builds_hollow_in_every_colour(app, pid):
    spec = library.PARTS[pid]
    for size in spec["sizes"]:
        for colour in (spec["colors"][0], spec["colors"][-1]):
            node = _build(pid, size, _color=colour)
            root = CadNode("root")
            root.add(node)
            assert validate(root) == {}, (pid, size)
    node = _build(pid)
    tris = mesh.tessellate(node)
    assert tris
    if pid in ("pot_saucer", "pot_hanging"):
        return
    x0, x1, y0, y1 = _bbox(tris)
    zs = [p[2] for t in tris for p in t]
    box = (x1 - x0) * (y1 - y0) * (max(zs) - min(zs))
    volume = analysis.mass_properties(tris)["volume"]
    assert 0 < volume < 0.5 * box, pid           # a pot, not a block


def test_pots_share_a_section_with_the_bundled_ones():
    cats = {spec["category"] for pid, spec in library.PARTS.items()
            if pid.startswith("pot_") or pid in ("kcad_vase_love",
                                                 "kcad_math_plant_pots")}
    assert cats == {"Pots"}


# ── vacuum ───────────────────────────────────────────────────────────

VACUUM = [pid for pid, s in library.PARTS.items()
          if s.get("category") == "Vacuum"]


@pytest.mark.parametrize("pid", VACUUM)
def test_every_vacuum_part_is_metal(app, pid):
    # part_colours skips the node it is given (an Object's own colour is
    # its instance's business), and a one-colour part IS its colour node
    holder = CadNode("union", "holder")
    holder.add(_build(pid))
    colours = mesh.part_colours(holder)
    assert colours, pid
    assert all(len(c) == 3 for c in colours), (pid, colours)
    assert {c[2] for c in colours} <= {"Metal", "Glass", "Plastic",
                                       "Rubber", "Emissive"}
    assert any(c[2] == "Metal" for c in colours), pid


def test_many_more_vacuum_parts():
    assert len(VACUUM) >= 45
    assert set(library_vacuum.PARTS) <= set(VACUUM)


def test_elbows_close_their_corner_with_a_knuckle(app):
    for pid in ("cf_elbow", "kf_elbow"):
        names = {n.name for n in _build(pid).walk()}
        assert {"Knuckle", "Knuckle bore"} <= names, pid
    # a straight nipple needs none
    assert "Knuckle" not in {n.name for n in _build("cf_nipple").walk()}


def test_tee_flanges_clear_each_other(app):
    p = dict(library.CF_SIZES["CF100 (DN100)"])
    tee = library.build_part("cf_tee", dict(p, port_length=60.0))
    xs = [pt[0] for t in mesh.tessellate(tee) for pt in t]
    assert max(xs) >= p["flange_od"] / 2 + p["thickness"]


def test_a_viewport_keeps_its_glass_and_its_own_objects(app):
    node = _build("cf_viewport", "CF40 (DN40)")
    objects = [n for n in node.walk() if n.type == "component"]
    assert len(objects) == 2
    materials = {c[2] for c in mesh.part_colours(node)}
    assert {"Metal", "Glass"} <= materials


# ── library sections from parts/ subfolders ─────────────────────────

BRACKETS = ("Butt Hinge", "Corner Brace", "Gusset Angle", "Joist Hanger",
            "L Angle", "Mending Plate", "P Clip", "Pipe Saddle",
            "Shelf Bracket", "Slotted Angle", "Strap Hinge", "T Plate",
            "U Bolt", "Wall Hook", "Z Bracket")


def test_brackets_have_their_own_section():
    for stem in BRACKETS + ("Strong corner bracket",):
        pid = library_kcad.part_id(stem)
        assert library.PARTS[pid]["category"] == "Brackets", stem


def test_minecraft_models_have_their_own_section():
    minecraft = [pid for pid, s in library.PARTS.items()
                 if s["category"] == "Minecraft"]
    assert len(minecraft) >= 7
    assert library_kcad.part_id("MinecraftCat") in minecraft


def test_a_subfolder_names_its_section(tmp_path):
    (tmp_path / "Brackets").mkdir()
    (tmp_path / "top.kcad").write_text("{}")
    (tmp_path / "Brackets" / "hinge.kcad").write_text("{}")
    found = library_kcad.shipped(tmp_path)
    assert [p.name for p in found] == ["top.kcad", "hinge.kcad"]


# ── the Showcase car ─────────────────────────────────────────────────

def test_the_ferrari_is_in_the_showcase(app):
    entry = next(e for e in examples.EXAMPLES if e[0] == "Ferrari 288 GTO")
    assert entry[1] == "Showcase"
    root = entry[2]()
    assert root.type == "root"
    assert sum(1 for n in root.walk() if n.type == "component") > 5
    assert validate(root) == {}
