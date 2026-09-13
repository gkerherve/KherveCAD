"""Playing cards for the Part Library — one card at a time.

Each card is complete: a paper body with **rounded corners** (the hull
of four corner circles, extruded — convex, so the preview is exact), the
rank and a small suit sign in the top-left corner **and again in the
bottom-right, turned half round**, the pips in the standard layout (the
lower ones upside down, as printed), court cards with a frame, the big
letter and a crown, tiara or cap, mirrored top and bottom, and a
patterned back on the underside. Print is raised ink, so it prints in a
second colour.

Four parts, one per suit, whose size list is the rank (Ace ... King);
a Joker part (red or black) and a plain back. Poker size by default
(63.5 x 88.9 mm), every dimension editable.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .model import CadNode

CATEGORY = "Playing cards"
PAPER, RED, BLACK, BACK = "#f7f5ee", "#c8102e", "#161616", "#1f3c88"
#: raised ink on the face and the back (mm)
INK = 0.4

RANKS = (("Ace", "A"), ("Two", "2"), ("Three", "3"), ("Four", "4"),
         ("Five", "5"), ("Six", "6"), ("Seven", "7"), ("Eight", "8"),
         ("Nine", "9"), ("Ten", "10"), ("Jack", "J"), ("Queen", "Q"),
         ("King", "K"))
SUITS = {"spades": ("Spades", BLACK), "hearts": ("Hearts", RED),
         "diamonds": ("Diamonds", RED), "clubs": ("Clubs", BLACK)}

DEFAULT = dict(width=63.5, height=88.9, thickness=0.8, corner=3.2)
FIELDS = [("width", "Width"), ("height", "Height"),
          ("thickness", "Thickness"), ("corner", "Corner radius")]

#: pip positions, (column -1..1 of 20 % of the width, row -1..1 of
#: 30 % of the height); a pip below the middle is printed upside down
PIPS = {
    "2": [(0, 1), (0, -1)],
    "3": [(0, 1), (0, 0), (0, -1)],
    "4": [(-1, 1), (1, 1), (-1, -1), (1, -1)],
    "5": [(-1, 1), (1, 1), (0, 0), (-1, -1), (1, -1)],
    "6": [(-1, 1), (1, 1), (-1, 0), (1, 0), (-1, -1), (1, -1)],
    "7": [(-1, 1), (1, 1), (0, 0.5), (-1, 0), (1, 0), (-1, -1), (1, -1)],
    "8": [(-1, 1), (1, 1), (0, 0.5), (-1, 0), (1, 0), (0, -0.5),
          (-1, -1), (1, -1)],
    "9": [(-1, 1), (1, 1), (-1, 1 / 3), (1, 1 / 3), (0, 0),
          (-1, -1 / 3), (1, -1 / 3), (-1, -1), (1, -1)],
    "10": [(-1, 1), (1, 1), (0, 2 / 3), (-1, 1 / 3), (1, 1 / 3),
           (-1, -1 / 3), (1, -1 / 3), (0, -2 / 3), (-1, -1), (1, -1)],
}


# ── small builders ──────────────────────────────────────────────────

def _circle(x, y, r, name="Circle"):
    return CadNode("circle", name, dict(x=float(x), y=float(y),
                                        radius=float(r)))


def _poly(points, name="Shape"):
    return CadNode("polygon", name, dict(
        x=0.0, y=0.0, points=[[round(float(px), 4), round(float(py), 4)]
                              for px, py in points]))


def _rect(x, y, w, h, name="Bar"):
    return CadNode("rect", name, dict(x=float(x), y=float(y),
                                      width=float(w), height=float(h)))


def _hull(*kids, name="Hull"):
    hull = CadNode("hull", name)
    for kid in kids:
        hull.add(kid)
    return hull


def _place(kids, x=0.0, y=0.0, s=1.0, turn=0.0, name="Place"):
    """Translate, turn and scale 2D *kids* (only the steps needed)."""
    inner = kids
    if s != 1.0:
        scale = CadNode("scale", "Size", dict(x=float(s), y=float(s),
                                              z=1.0))
        for kid in inner:
            scale.add(kid)
        inner = [scale]
    if turn:
        rot = CadNode("rotate", "Turn", dict(x=0.0, y=0.0, z=float(turn)))
        for kid in inner:
            rot.add(kid)
        inner = [rot]
    move = CadNode("translate", name, dict(x=float(x), y=float(y), z=0.0))
    for kid in inner:
        move.add(kid)
    return move


def _text(value, cx, baseline, size, name=None):
    """Text centred on *cx* (the text node has no alignment: the width
    is estimated from the font's proportions)."""
    width = size * (0.58 if value.isdigit() else 0.66) * len(value)
    return CadNode("text", name or f"'{value}'", dict(
        x=round(cx - width / 2.0, 3), y=round(baseline, 3), text=value,
        size=float(size)))


def suit_shape(suit):
    """The suit sign, about 1.2 tall, centred on the origin."""
    if suit == "hearts":
        tip = (0.0, -0.6)
        return [_hull(_circle(-0.27, 0.17, 0.31), _circle(*tip, 0.02),
                      name="Left lobe"),
                _hull(_circle(0.27, 0.17, 0.31), _circle(*tip, 0.02),
                      name="Right lobe")]
    if suit == "diamonds":
        return [_poly([(0, 0.62), (0.44, 0), (0, -0.62), (-0.44, 0)],
                      "Diamond")]
    if suit == "spades":
        tip = (0.0, 0.62)
        return [_hull(_circle(-0.27, -0.1, 0.31), _circle(*tip, 0.02),
                      name="Left lobe"),
                _hull(_circle(0.27, -0.1, 0.31), _circle(*tip, 0.02),
                      name="Right lobe"),
                _poly([(0, -0.15), (0.2, -0.62), (-0.2, -0.62)], "Stem")]
    return [_circle(0.0, 0.3, 0.26, "Top leaf"),
            _circle(-0.29, -0.1, 0.26, "Left leaf"),
            _circle(0.29, -0.1, 0.26, "Right leaf"),
            _circle(0.0, 0.03, 0.16, "Heart"),
            _poly([(0, -0.05), (0.18, -0.62), (-0.18, -0.62)], "Stem")]


def _pip(suit, x, y, size, turn=0.0):
    return _place(suit_shape(suit), x, y, size, turn, name="Pip")


def _rounded(w, h, r):
    r = max(min(r, w / 2.0 - 0.1, h / 2.0 - 0.1), 0.1)
    return _hull(*[_circle(sx * (w / 2.0 - r), sy * (h / 2.0 - r), r,
                           "Corner") for sx in (-1, 1) for sy in (-1, 1)],
                 name="Rounded outline")


def _painted(colour, node, material="Matte", name=None):
    paint = CadNode("color", name or "Colour", dict(
        color=colour, alpha=1.0, material=material))
    paint.add(node)
    return paint


def _layer(z, height, kids, name):
    """2D *kids* extruded *height* at *z* (one union)."""
    ext = CadNode("linear_extrude", name, dict(height=float(height)))
    for kid in kids:
        ext.add(kid)
    return _place([ext], 0.0, 0.0, name=f"{name} height") if not z else \
        _lift(ext, z)


def _lift(node, z):
    move = CadNode("translate", "Lift", dict(x=0.0, y=0.0, z=float(z)))
    move.add(node)
    return move


def _dims(dims):
    d = dict(DEFAULT)
    for key in DEFAULT:
        try:
            d[key] = float(dims.get(key, d[key]))
        except (TypeError, ValueError):
            pass
    return d


# ── faces ───────────────────────────────────────────────────────────

def _index(rank, suit, w, h):
    """Rank and suit sign in the top-left corner."""
    size = 6.2 if len(rank) == 1 else 5.2
    cx = -w / 2.0 + 5.2
    top = h / 2.0 - 3.4
    return [_text(rank, cx, top - size, size, "Rank"),
            _pip(suit, cx, top - size - 4.6, 3.4)]


def _both_corners(make):
    """What *make()* draws in the top-left corner, and the same again
    turned half round into the bottom-right — so the card reads from
    either end."""
    return [_place(make(), name="Top-left index"),
            _place(make(), turn=180.0, name="Bottom-right index")]


def _emblem(rank):
    """Crown (K), tiara (Q) or cap (J), about 12 wide, base at y = 0."""
    if rank == "K":
        return [_poly([(-6, 0), (6, 0), (6, 4.5), (3, 2), (0, 6), (-3, 2),
                       (-6, 4.5)], "Crown"),
                _circle(-6, 4.7, 0.8), _circle(0, 6.2, 0.8),
                _circle(6, 4.7, 0.8)]
    if rank == "Q":
        return [_poly([(-5, 0), (5, 0), (5, 2.4), (2.5, 1.3), (1.2, 3.5),
                       (0, 1.8), (-1.2, 3.5), (-2.5, 1.3), (-5, 2.4)],
                      "Tiara"),
                _circle(-5, 2.8, 0.7), _circle(0, 4.4, 0.8),
                _circle(5, 2.8, 0.7)]
    return [_poly([(-5.5, 0), (5.5, 0), (4, 3.5), (0, 4.6), (-4, 3.5)],
                  "Cap"),
            _poly([(3, 3.5), (7.5, 8.5), (4.9, 4.2)], "Feather")]


def _court(rank, suit, w, h):
    fx, fy, bar = w / 2.0 - 9.0, h / 2.0 - 12.5, 0.5
    art = [_rect(-fx, fy - bar, 2 * fx, bar, "Frame top"),
           _rect(-fx, -fy, 2 * fx, bar, "Frame bottom"),
           _rect(-fx, -fy, bar, 2 * fy, "Frame left"),
           _rect(fx - bar, -fy, bar, 2 * fy, "Frame right"),
           _poly([(-fx, -3.3), (fx, 2.7), (fx, 3.3), (-fx, -2.7)],
                 "Divider")]

    def half():
        return [_text(rank, 0.0, 6.5, 15.0, "Letter"),
                _place(_emblem(rank), 0.0, 22.5, name="Emblem"),
                _pip(suit, -fx + 4.2, fy - 4.6, 4.2)]
    art.append(_place(half(), name="Upper half"))
    art.append(_place(half(), turn=180.0, name="Lower half"))
    return art


def _pip_field(rank, suit, w, h):
    if rank == "A":
        return [_pip(suit, 0.0, 0.0, 19.0 if suit == "spades" else 16.0)]
    if rank in ("J", "Q", "K"):
        return _court(rank, suit, w, h)
    return [_pip(suit, cx * w * 0.2, ry * h * 0.3, 7.2,
                 180.0 if ry < 0 else 0.0) for cx, ry in PIPS[rank]]


def _back_pattern(w, h):
    """A border and a lattice of small diamonds, like a casino back."""
    fx, fy = w / 2.0 - 3.2, h / 2.0 - 3.2
    kids = [_rect(-fx, fy - 0.9, 2 * fx, 0.9, "Border top"),
            _rect(-fx, -fy, 2 * fx, 0.9, "Border bottom"),
            _rect(-fx, -fy, 0.9, 2 * fy, "Border left"),
            _rect(fx - 0.9, -fy, 0.9, 2 * fy, "Border right")]
    step = 4.6
    ni = int((fx - 3.0) // step)
    nj = int((fy - 3.0) // step)
    for offset, name in ((0.0, "Lattice"), (step / 2.0, "Offset lattice")):
        rows = CadNode("for_loop", f"{name} rows", dict(
            variable="j", start=float(-nj), end=float(nj - (1 if offset
                                                            else 0)),
            step=1.0))
        cols = CadNode("for_loop", f"{name} columns", dict(
            variable="i", start=float(-ni - (1 if offset else 0)),
            end=float(ni), step=1.0))
        spot = CadNode("translate", "Spot", dict(
            x=f"i * {step} + {offset}", y=f"j * {step} + {offset}", z=0.0))
        turn = CadNode("rotate", "Diamond", dict(x=0.0, y=0.0, z=45.0))
        turn.add(_rect(-1.05, -1.05, 2.1, 2.1, "Diamond"))
        spot.add(turn)
        cols.add(spot)
        rows.add(cols)
        kids.append(rows)
    return kids


def _card(name, d, face, ink, back=True):
    w, h, t = d["width"], d["height"], d["thickness"]
    card = CadNode("union", name)
    body = CadNode("linear_extrude", "Card", dict(height=t))
    body.add(_rounded(w, h, d["corner"]))
    card.add(_painted(PAPER, body, name="Paper"))
    if face:
        print_ = CadNode("linear_extrude", "Face print", dict(height=INK))
        for kid in face:
            print_.add(kid)
        card.add(_painted(ink, _lift(print_, t), name="Ink"))
    if back:
        pattern = CadNode("linear_extrude", "Back print",
                          dict(height=INK))
        for kid in _back_pattern(w, h):
            pattern.add(kid)
        card.add(_painted(BACK, _lift(pattern, -INK), name="Back ink"))
    return card


# ── parts ───────────────────────────────────────────────────────────

def rank_of(dims):
    """The rank symbol for the size chosen ("Seven" -> "7")."""
    wanted = str(dims.get("_size") or dims.get("rank") or "Ace").strip()
    for word, symbol in RANKS:
        if wanted.lower() in (word.lower(), symbol.lower()):
            return word, symbol
    return RANKS[0]


def build_card(suit, dims):
    d = _dims(dims)
    word, rank = rank_of(dims)
    label, ink = SUITS[suit]
    w, h = d["width"], d["height"]
    face = _both_corners(lambda: _index(rank, suit, w, h))
    face += _pip_field(rank, suit, w, h)
    return _card(f"{word} of {label}", d, face, ink)


def _star(r_out, r_in, points=5):
    pts = []
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.pi / 2 + i * math.pi / points
        pts.append((r * math.cos(a), r * math.sin(a)))
    return _poly(pts, "Star")


def build_joker(dims):
    d = _dims(dims)
    w, h = d["width"], d["height"]
    red = "red" in str(dims.get("_size") or "Red").lower()
    ink = RED if red else BLACK

    def corner():
        return [_text(letter, -w / 2.0 + 4.6, h / 2.0 - 8.0 - i * 5.4,
                      4.4, f"'{letter}'")
                for i, letter in enumerate("JOKER")]
    face = _both_corners(corner)
    face.append(_star(15.0, 6.0))
    face.append(_place([_text("JOKER", 0.0, -30.0, 6.0)], name="Title"))
    face.append(_place([_text("JOKER", 0.0, -30.0, 6.0)], turn=180.0,
                       name="Title turned"))
    return _card(f"{'Red' if red else 'Black'} Joker", d, face, ink)


def build_back(dims):
    return _card("Card back", _dims(dims), None, BLACK)


def _rank_sizes():
    return {word: dict(DEFAULT) for word, _symbol in RANKS}


PARTS = {
    f"card_{key}": dict(label=f"Playing card — {label}", category=CATEGORY,
                        sizes=_rank_sizes(), fields=FIELDS,
                        build=lambda d, k=key: build_card(k, d))
    for key, (label, _ink) in SUITS.items()
}
PARTS["card_joker"] = dict(label="Playing card — Joker", category=CATEGORY,
                           sizes={"Red joker": dict(DEFAULT),
                                  "Black joker": dict(DEFAULT)},
                           fields=FIELDS, build=build_joker)
PARTS["card_back"] = dict(label="Playing card — back only",
                          category=CATEGORY,
                          sizes={"Poker size": dict(DEFAULT),
                                 "Bridge size": dict(DEFAULT,
                                                     width=57.15)},
                          fields=FIELDS, build=build_back)
