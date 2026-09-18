"""Musical instruments for the Part Library — tuned by their own physics.

A bar of a marimba, xylophone, vibraphone or glockenspiel is a free-free
beam: its pitch goes as thickness / length², so every bar's length comes
from its note's frequency (`bar_length`, with a gentler exponent than the
bare ½ because real bars are arched underneath). The bars are laid out
like a piano keyboard — naturals in front, accidentals behind, raised —
on rails at their nodal points (22.4 % from each end), and a marimba's
resonators are quarter-wave tubes, c / 4f long, capped at the frame.
Keyboards lay 23.5 mm white keys with the black keys between them; a
grand piano is its real plan (straight spine, S-curved bentside, round
tail) with the lid propped open. Drums are shells, heads, hoops and lugs,
a cymbal one thin revolved bell-and-bow profile; the drum kit sets them
out round a throne as a right-handed drummer plays them.

Everything is boolean-free, so the preview is exact, and repeated pieces
(bars, tubes, keys, lugs) are ONE for-loop over value rows each, so a
marimba stays a short, editable tree. Strings, winds and hand percussion
are in `library_music_more`.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .model import CadNode

CATEGORY = "Musical instruments"
SOUND_MM_S = 343000.0             # speed of sound, mm / s
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#",
              "B")
_SHARPS = {1, 3, 6, 8, 10}

WOOD = "#7a3b22"                  # rosewood / padauk bars
DARK = "#1d1e21"
CHROME = "#c9ced6"
FELT = "#8b1e24"
BRASS = "#c9a24a"
BRONZE = "#b98a3a"
HEAD = "#f1eee4"                  # coated drum head
IVORY = "#f6f3ea"


# ── notes ─────────────────────────────────────────────────────────────

def midi(name: str) -> int:
    """MIDI number of a note name ("A4" = 69, "F#3", "Bb2")."""
    name = name.strip()
    letter = name[0].upper()
    rest = name[1:]
    shift = 0
    while rest and rest[0] in "#b":
        shift += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    return 12 * (int(rest) + 1) + NOTE_NAMES.index(letter) + shift


def freq(m: int) -> float:
    """Equal-tempered frequency (Hz), A4 = 440."""
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def is_sharp(m: int) -> bool:
    return m % 12 in _SHARPS


def note_name(m: int) -> str:
    return f"{NOTE_NAMES[m % 12]}{m // 12 - 1}"


def bar_length(m: int, lo: int, length_lo: float, exponent: float) -> float:
    """Length of the bar sounding *m* in a set whose lowest bar (*lo*) is
    *length_lo* long: L ∝ f^-exponent (0.5 for a plain bar)."""
    return length_lo * (freq(lo) / freq(m)) ** exponent


def closed_pipe(m: int, radius: float = 0.0) -> float:
    """Length of a pipe closed at one end sounding *m*: a quarter wave,
    less the open end's correction (0.6 r)."""
    return SOUND_MM_S / (4.0 * freq(m)) - 0.6 * radius


def fret_position(scale: float, n: int) -> float:
    """Distance of fret *n* from the nut on a *scale* mm string."""
    return scale * (1.0 - 2.0 ** (-n / 12.0))


def keyboard_layout(lo: int, hi: int, pitch: float):
    """[(midi, x, sharp)] — naturals *pitch* apart, each accidental
    halfway between its two neighbours — and the number of naturals."""
    out, k = [], -1
    for m in range(lo, hi + 1):
        if is_sharp(m):
            out.append((m, (k + 0.5) * pitch, True))
        else:
            k += 1
            out.append((m, k * pitch, False))
    return out, k + 1


# ── nodes ─────────────────────────────────────────────────────────────

def _f(v):
    """A number rounded for the program, or an expression kept as is."""
    return v if isinstance(v, str) else round(float(v), 3)


def group(name, kids=()):
    g = CadNode("union", name)
    for k in kids:
        if k is not None:
            g.add(k)
    return g


def paint(name, colour, material, kids, alpha=1.0):
    """A colour node holding *kids* (one colour, one material)."""
    c = CadNode("color", name, dict(color=colour, alpha=alpha,
                                    material=material))
    for k in kids if isinstance(kids, (list, tuple)) else [kids]:
        if k is not None:
            c.add(k)
    return c


def cyl(name, r, h, x=0.0, y=0.0, z=0.0, r2=None, seg=48):
    return CadNode("cylinder", name, dict(
        x=_f(x), y=_f(y), z=_f(z), height=_f(h), radius_bottom=_f(r),
        radius_top=_f(r if r2 is None else r2), segments=seg,
        center=False))


def box(name, x, y, z, w, d, h):
    """A cube from its low corner."""
    return CadNode("cube", name, dict(x=_f(x), y=_f(y), z=_f(z),
                                      width=_f(w), depth=_f(d),
                                      height=_f(h), center=False))


def cbox(name, cx, cy, z, w, d, h):
    """A cube centred in x and y, standing on *z*."""
    return box(name, cx - w / 2.0, cy - d / 2.0, z, w, d, h)


def sphere(name, r, x=0.0, y=0.0, z=0.0, seg=32):
    return CadNode("sphere", name, dict(x=_f(x), y=_f(y), z=_f(z),
                                        radius=_f(r), segments=seg))


def capsule(name, a, b, r, seg=8):
    return CadNode("capsule", name, dict(
        x1=_f(a[0]), y1=_f(a[1]), z1=_f(a[2]), x2=_f(b[0]), y2=_f(b[1]),
        z2=_f(b[2]), radius=_f(r), segments=seg))


def ellipsoid(name, rx, ry, rz, x=0.0, y=0.0, z=0.0, seg=32):
    return CadNode("ellipsoid", name, dict(x=_f(x), y=_f(y), z=_f(z),
                                           rx=_f(rx), ry=_f(ry), rz=_f(rz),
                                           segments=seg))


def move(node, x=0.0, y=0.0, z=0.0, name="Place"):
    t = CadNode("translate", name, dict(x=_f(x), y=_f(y), z=_f(z)))
    t.add(node)
    return t


def turn(node, x=0.0, y=0.0, z=0.0, name="Turn"):
    r = CadNode("rotate", name, dict(x=_f(x), y=_f(y), z=_f(z)))
    r.add(node)
    return r


def polygon(name, pts):
    return CadNode("polygon", name, dict(
        x=0.0, y=0.0, points=[[_f(a), _f(b)] for a, b in pts]))


def revolve(name, pts, seg=96, angle=360.0):
    """rotate_extrude of a (r, z) profile."""
    rev = CadNode("rotate_extrude", name, dict(angle=float(angle),
                                              segments=seg))
    rev.add(polygon(f"{name} profile",
                    [(max(r, 0.0), z) for r, z in pts]))
    return rev


def extrude(name, shape, height, z=0.0, scale=1.0):
    ex = CadNode("linear_extrude", name, dict(
        height=_f(height), twist=0.0, scale=float(scale), center=False,
        segments=0))
    ex.add(shape)
    return move(ex, z=z, name=f"{name} level") if z else ex


def torus(name, R, r, angle=360.0, seg=48):
    """A ring (or a bend, *angle* < 360) round Z in the XY plane."""
    rev = CadNode("rotate_extrude", name, dict(angle=float(angle),
                                              segments=seg))
    rev.add(CadNode("circle", f"{name} section", dict(
        x=_f(R), y=0.0, radius=_f(r), angle=360.0, start_angle=0.0,
        segments=16)))
    return rev


def values(rows):
    """Rows as a for-loop value list (a single row bracketed once more,
    or it would be iterated element by element)."""
    text = ", ".join("[" + ", ".join(repr(_f(v)) for v in row) + "]"
                     for row in rows)
    return f"[{text}]" if len(rows) == 1 else text


def loop(name, rows, body, var="p"):
    lp = CadNode("for_loop", name, dict(variable=var, start=0.0, end=0.0,
                                        step=1.0, values=values(rows)))
    for b in body if isinstance(body, (list, tuple)) else [body]:
        lp.add(b)
    return lp


def num(dims, key, default):
    try:
        return float(dims.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def table(dims, sizes):
    """The size row named by ``_size`` (else the first), overlaid with
    whatever fields the dialog edited."""
    row = dict(sizes.get(dims.get("_size", ""), next(iter(sizes.values()))))
    row.update({k: v for k, v in dims.items()
                if k != "_size" and v is not None})
    return row


def choice(dims, options, default=None):
    """(colour, material) the dialog's colour combo picked."""
    name = dims.get("_color") or default or next(iter(options))
    return options.get(name, options[default or next(iter(options))])


def tripod(name, top, spread, colour=CHROME, tube=11.0, leg=6.0,
           joint=None):
    """A stand: three legs splayed from *joint* to the floor and a tube
    up to *top*."""
    joint = joint if joint is not None else min(top * 0.35, 260.0)
    kids = [cyl("Tube", tube, top, seg=24)]
    for k in range(3):
        a = math.radians(90.0 + 120.0 * k)
        kids.append(capsule(f"Leg {k + 1}", (0.0, 0.0, joint),
                            (spread * math.cos(a), spread * math.sin(a),
                             leg), leg))
    return paint(name, colour, "Metal", kids)


# ── tuned bars ────────────────────────────────────────────────────────

def mallet_instrument(name, row, bar_colour, bar_material, frame_colour,
                      tube_colour=None, tube_material="Metal", case=False):
    """Bars laid out like a keyboard over rails, on a frame (or in a
    case), optionally with resonators. *row* gives lo/hi notes, the
    lowest bar's length, the length exponent, widths, thickness, the
    bar top height, gap and accidental lift."""
    lo, hi = midi(row["lo"]), midi(row["hi"])
    W0, W1 = float(row["w_lo"]), float(row["w_hi"])
    T, gap = float(row["thickness"]), float(row.get("gap", 6.0))
    lift = float(row.get("lift", 0.0))
    top = max(float(row["height"]), T + 20.0)
    pitch = W0 + gap
    layout, naturals = keyboard_layout(lo, hi, pitch)
    x_mid = (naturals - 1) * pitch / 2.0

    def length(m):
        return max(bar_length(m, lo, float(row["l_lo"]),
                              float(row["exponent"])), W1 * 2.2)

    def width(m):
        t = (m - lo) / max(hi - lo, 1)
        return W0 + (W1 - W0) * t

    bars, tubes, rows_y = [], [], {False: [], True: []}
    for m, x, sharp in layout:
        L, W = length(m), width(m)
        if sharp:
            y = (length(m - 1) + L) / 2.0 + gap * 2.0
            z = top - T + lift
        else:
            y, z = 0.0, top - T
        x -= x_mid
        bars.append((x, y, z, L, W))
        rows_y[sharp].append((x, y, L, z))
        if tube_colour:
            r = min(W * 0.42, 40.0)
            tl = min(max(closed_pipe(m, r), 60.0), top * 0.8)
            tubes.append((x, y, z - 40.0 - tl, tl, r))

    kids = [paint("Bars", bar_colour, bar_material, [loop(
        f"Bars {note_name(lo)}–{note_name(hi)}", bars, box(
            "Bar", "p[0] - p[4] / 2", "p[1] - p[3] / 2", "p[2]", "p[4]",
            "p[3]", T))])]
    rails = []
    for sharp, pts in rows_y.items():
        if not pts:
            continue
        (xa, ya, La, za), (xb, yb, Lb, zb) = pts[0], pts[-1]
        for side in (-1, 1):
            hull = CadNode("hull", f"{'Back' if sharp else 'Front'} rail")
            for (x, y, L, z) in ((xa, ya, La, za), (xb, yb, Lb, zb)):
                hull.add(cbox("Rail end", x, y + side * 0.276 * L, z - 12.0,
                              14.0, 10.0, 12.0))
            rails.append(hull)
    kids.append(paint("Rails", FELT, "Matte", rails))

    xs = [b[0] for b in bars]
    x0, x1 = min(xs) - W0 - 30.0, max(xs) + W0 + 30.0
    y_front = -length(lo) / 2.0 - 20.0
    y_back = max(b[1] + b[3] / 2.0 for b in bars) + 20.0
    if case:
        wall = 10.0
        kids.append(paint("Case", frame_colour, "Plastic", [
            box("Case floor", x0, y_front, 0.0, x1 - x0, y_back - y_front,
                wall),
            box("Case front", x0, y_front, 0.0, x1 - x0, wall, top - T - 12),
            box("Case back", x0, y_back - wall, 0.0, x1 - x0, wall,
                top - T - 12 + lift),
            box("Case bass end", x0, y_front, 0.0, wall, y_back - y_front,
                top - T - 12 + lift),
            box("Case treble end", x1 - wall, y_front, 0.0, wall,
                y_back - y_front, top - T - 12 + lift),
        ]))
    else:
        rail_z = top - T - 12.0
        ends = []
        for label, xe, ye0, ye1 in (
                ("Bass end", x0, y_front, y_back),
                ("Treble end", x1 - 30.0, bars[-1][1] - bars[-1][3] / 2 - 30,
                 max(b[1] + b[3] / 2 for b in bars[-3:]) + 30)):
            ends.append(box(f"{label} board", xe, ye0, rail_z - 120.0, 30.0,
                            ye1 - ye0, 120.0))
            for yl in (ye0 + 25.0, ye1 - 25.0):
                ends.append(cyl(f"{label} leg", 18.0, rail_z - 120.0,
                                xe + 15.0, yl, 0.0, seg=24))
                ends.append(sphere("Castor", 22.0, xe + 15.0, yl, 22.0,
                                   seg=16))
        ends.append(capsule("Stretcher", (x0 + 15.0, 0.0, 180.0),
                            (x1 - 15.0, 0.0, 180.0), 16.0))
        kids.append(paint("Frame", frame_colour, "Plastic", ends))
    if tubes:
        kids.append(paint("Resonators", tube_colour, tube_material, [loop(
            "Resonator tubes", tubes, cyl("Tube", "p[4]", "p[3]", "p[0]",
                                          "p[1]", "p[2]", seg=24))]))
    return group(name, kids)


BAR_WOODS = {"Rosewood": ("#6e3420", "Plastic"),
             "Padauk": ("#a04a2a", "Plastic"),
             "Synthetic (Kelon)": ("#4f2a22", "Plastic"),
             "Maple (practice)": ("#d6b07a", "Plastic")}

MARIMBA_SIZES = {
    "4.3 octaves (A2–C7)": dict(lo="A2", hi="C7", l_lo=540.0, exponent=0.33,
                                w_lo=64.0, w_hi=40.0, thickness=22.0,
                                height=860.0, lift=20.0),
    "5 octaves (C2–C7)": dict(lo="C2", hi="C7", l_lo=610.0, exponent=0.33,
                              w_lo=70.0, w_hi=40.0, thickness=24.0,
                              height=880.0, lift=20.0),
    "4 octaves (C3–C7)": dict(lo="C3", hi="C7", l_lo=470.0, exponent=0.33,
                              w_lo=58.0, w_hi=40.0, thickness=22.0,
                              height=850.0, lift=20.0),
}
XYLOPHONE_SIZES = {
    "3.5 octaves (F4–C8)": dict(lo="F4", hi="C8", l_lo=360.0,
                                exponent=0.34, w_lo=40.0, w_hi=32.0,
                                thickness=22.0, height=880.0, lift=15.0),
    "3 octaves (C5–C8)": dict(lo="C5", hi="C8", l_lo=300.0, exponent=0.34,
                              w_lo=38.0, w_hi=32.0, thickness=22.0,
                              height=880.0, lift=15.0),
}
VIBRAPHONE_SIZES = {
    "3 octaves (F3–F6)": dict(lo="F3", hi="F6", l_lo=385.0, exponent=0.36,
                              w_lo=57.0, w_hi=36.0, thickness=12.0,
                              height=860.0, lift=10.0),
    "3.5 octaves (C3–F6)": dict(lo="C3", hi="F6", l_lo=430.0,
                                exponent=0.36, w_lo=60.0, w_hi=36.0,
                                thickness=12.0, height=860.0, lift=10.0),
}
GLOCKENSPIEL_SIZES = {
    "2.5 octaves (G5–C8)": dict(lo="G5", hi="C8", l_lo=200.0,
                                exponent=0.36, w_lo=25.0, w_hi=22.0,
                                thickness=8.0, height=40.0, gap=4.0,
                                lift=8.0),
    "2 octaves (C6–C8)": dict(lo="C6", hi="C8", l_lo=170.0, exponent=0.36,
                              w_lo=25.0, w_hi=22.0, thickness=8.0,
                              height=40.0, gap=4.0, lift=8.0),
}
HEIGHT_FIELD = [("height", "Bar height")]


def build_marimba(dims):
    colour, material = choice(dims, BAR_WOODS, "Rosewood")
    return mallet_instrument("Marimba", table(dims, MARIMBA_SIZES), colour,
                             material, "#2a2522", BRASS, "Metal")


def build_xylophone(dims):
    colour, material = choice(dims, BAR_WOODS, "Padauk")
    return mallet_instrument("Xylophone", table(dims, XYLOPHONE_SIZES),
                             colour, material, "#2a2522", CHROME, "Metal")


VIBE_FINISH = {"Silver": ("#c9ccd1", "Metal"), "Gold": ("#d3b15c", "Metal"),
               "Black": ("#2b2c30", "Metal")}


def build_vibraphone(dims):
    row = table(dims, VIBRAPHONE_SIZES)
    colour, material = choice(dims, VIBE_FINISH, "Silver")
    part = mallet_instrument("Vibraphone", row, colour, material, DARK,
                             "#d3b15c", "Metal")
    # the damper felt along the bars and the sustain pedal
    lo = midi(row["lo"])
    layout, naturals = keyboard_layout(lo, midi(row["hi"]),
                                       float(row["w_lo"]) + 6.0)
    span = (naturals - 1) * (float(row["w_lo"]) + 6.0)
    top = float(row["height"])
    part.add(paint("Damper", FELT, "Matte", [
        capsule("Damper bar", (-span / 2, -float(row["l_lo"]) * 0.45,
                               top - 16.0),
                (span / 2, -float(row["l_lo"]) * 0.3, top - 16.0), 5.0)]))
    part.add(paint("Pedal", DARK, "Metal", [
        cbox("Sustain pedal", 0.0, -float(row["l_lo"]) / 2 - 90.0, 0.0,
             240.0, 70.0, 20.0),
        capsule("Pedal rod", (0.0, -float(row["l_lo"]) / 2 - 60.0, 20.0),
                (0.0, -float(row["l_lo"]) * 0.45, top - 20.0), 4.0)]))
    return part


def build_glockenspiel(dims):
    return mallet_instrument("Glockenspiel", table(dims, GLOCKENSPIEL_SIZES),
                             "#d4d7dc", "Metal", "#3a2418", case=True)


RAINBOW = ["#d7263d", "#f46036", "#f7b32b", "#6dbf4b", "#1b998b",
           "#2e86de", "#5f4bb6", "#c2549d"]


def build_toy_xylophone(dims):
    """A child's xylophone: eight rainbow bars of the C-major scale on a
    wooden frame, each held by two nails, and two ball mallets."""
    row = table(dims, TOY_SIZES)
    n = int(num(row, "notes", 8))
    scale = [0, 2, 4, 5, 7, 9, 11]
    notes = [midi("C5") + 12 * (i // 7) + scale[i % 7] for i in range(n)]
    L0, W, T = float(row["l_lo"]), float(row["width"]), 8.0
    pitch = W + 6.0
    x0 = -(n - 1) * pitch / 2.0
    kids = []
    frame_h = 22.0
    lengths = [bar_length(m, notes[0], L0, 0.5) for m in notes]
    ya, yb = 0.276 * lengths[0], 0.276 * lengths[-1]
    rails = []
    for side in (-1, 1):
        hull = CadNode("hull", "Rail")
        hull.add(cbox("Rail end", x0 - 20.0, side * ya, 0.0, 16.0, 16.0,
                      frame_h))
        hull.add(cbox("Rail end", -x0 + 20.0, side * yb, 0.0, 16.0, 16.0,
                      frame_h))
        rails.append(hull)
    kids.append(paint("Frame", "#d9b27c", "Plastic", rails))
    nails = []
    for i, (m, L) in enumerate(zip(notes, lengths)):
        x = x0 + i * pitch
        kids.append(paint(f"Bar {note_name(m)}", RAINBOW[i % len(RAINBOW)],
                          "Plastic", [cbox("Bar", x, 0.0, frame_h, W, L,
                                           T)]))
        for y in (-0.276 * L, 0.276 * L):
            nails.append(cyl("Nail head", 2.5, 1.0, x, y, frame_h + T,
                             seg=8))
    kids.append(paint("Nails", CHROME, "Metal", nails))
    for k, dx in enumerate((-30.0, 30.0)):
        yb_ = -lengths[0] / 2 - 40.0
        kids.append(paint(f"Mallet {k + 1}", "#d9b27c", "Plastic", [
            capsule("Handle", (dx, yb_, 5.0), (dx * 3, yb_ - 200.0, 5.0),
                    4.0)]))
        kids.append(paint(f"Mallet head {k + 1}", "#d7263d", "Plastic", [
            sphere("Ball", 12.0, dx, yb_, 12.0, seg=24)]))
    return group("Toy xylophone", kids)


TOY_SIZES = {"8 notes": dict(notes=8, l_lo=170.0, width=32.0),
             "12 notes": dict(notes=12, l_lo=190.0, width=30.0),
             "15 notes": dict(notes=15, l_lo=200.0, width=28.0)}


# ── keyboards ─────────────────────────────────────────────────────────

WHITE_PITCH = 23.5


def keys(lo, hi, top, y_front=-150.0, name="Keys"):
    """White and black keys, their front at *y_front*, white tops at
    *top*: two loops. Returns (node, width)."""
    layout, naturals = keyboard_layout(lo, hi, WHITE_PITCH)
    width = naturals * WHITE_PITCH
    x0 = -width / 2.0
    whites = [(x0 + x,) for m, x, s in layout if not s]
    blacks = [(x0 + x + WHITE_PITCH / 2.0,) for m, x, s in layout if s]
    white = box("White key", "p[0] + 0.5", y_front, top - 22.0,
                WHITE_PITCH - 1.0, -y_front, 22.0)
    black = box("Black key", "p[0] - 6.5", y_front + 55.0, top - 12.0, 13.0,
                -y_front - 55.0, 22.0)
    node = group(name, [
        paint("White keys", IVORY, "Plastic", [loop(
            f"{len(whites)} white keys", whites, white)]),
        paint("Black keys", "#141416", "Plastic", [loop(
            f"{len(blacks)} black keys", blacks, black)]),
    ])
    return node, width


KEY_RANGES = {"61 keys (C2–C7)": ("C2", "C7"),
              "76 keys (E1–G7)": ("E1", "G7"),
              "88 keys (A0–C8)": ("A0", "C8"),
              "49 keys (C2–C6)": ("C2", "C6")}
KEYBOARD_SIZES = {k: dict(height=110.0) for k in KEY_RANGES}
CASE_FINISH = {"Black": ("#1e1f22", "Plastic"),
               "White": ("#eceae4", "Plastic"),
               "Red (stage)": ("#b3202a", "Plastic"),
               "Walnut": ("#5b3a24", "Plastic")}


def build_keyboard(dims):
    """A digital keyboard: keys in a case, a control panel with a
    display and knobs behind them."""
    size = dims.get("_size") or next(iter(KEY_RANGES))
    lo, hi = KEY_RANGES.get(size, KEY_RANGES["61 keys (C2–C7)"])
    H = max(num(dims, "height", 110.0), 60.0)
    colour, material = choice(dims, CASE_FINISH, "Black")
    top = H - 12.0
    kb, width = keys(midi(lo), midi(hi), top, -150.0)
    cheek, depth = 50.0, 330.0
    case = paint("Case", colour, material, [
        box("Key bed", -width / 2 - cheek, -165.0, 0.0, width + 2 * cheek,
            depth, top - 25.0),
        box("Bass cheek", -width / 2 - cheek, -165.0, 0.0, cheek, depth,
            H),
        box("Treble cheek", width / 2, -165.0, 0.0, cheek, depth, H),
        box("Panel", -width / 2, 0.0, 0.0, width, depth - 165.0, H),
    ])
    panel = paint("Controls", "#101012", "Plastic", [
        cbox("Display", 0.0, 80.0, H, 180.0, 50.0, 1.0),
    ])
    knobs = paint("Knobs", CHROME, "Metal", [loop(
        "Knobs", [(-width / 2 + 60 + 40 * i,) for i in range(4)],
        cyl("Knob", 9.0, 12.0, "p[0]", 80.0, H, seg=24))])
    return group("Keyboard", [case, kb, panel, knobs])


def grand_outline(W, L, n=24):
    """The plan of a grand piano's case, keyboard edge on y = 0: the
    straight bass spine at x = -W/2, the treble side straight for a
    quarter of the length, the S-curved bentside, the round tail."""
    pts = [(-W / 2, 0.0), (W / 2, 0.0), (W / 2, 0.25 * L)]
    for i in range(1, n + 1):
        u = i / n
        s = u * u * (3.0 - 2.0 * u)
        pts.append((W / 2 - 0.55 * W * s, (0.25 + 0.6 * u) * L))
    cx, cy, rx, ry = -W / 2, 0.85 * L, 0.45 * W, 0.15 * L
    for i in range(1, n + 1):
        a = math.radians(90.0 * i / n)
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return pts


GRAND_SIZES = {
    "Baby grand (1.55 m)": dict(length=1550.0, width=1480.0),
    "Parlour grand (1.85 m)": dict(length=1850.0, width=1500.0),
    "Concert grand (2.74 m)": dict(length=2740.0, width=1570.0),
}
PIANO_FINISH = {"Polished ebony": ("#111114", "Plastic"),
                "White": ("#f0eee8", "Plastic"),
                "Walnut": ("#4e3020", "Plastic"),
                "Mahogany": ("#5e2418", "Plastic")}


def build_grand_piano(dims):
    """A grand piano: case rim, soundboard and gold iron plate inside,
    lid on its prop stick, 88 keys, three legs on castors, the lyre
    with three pedals, and a bench."""
    from . import mesh
    row = table(dims, GRAND_SIZES)
    L = max(num(row, "length", 1850.0), 1300.0)
    W = max(num(row, "width", 1500.0), 1300.0)
    colour, material = choice(dims, PIANO_FINISH, "Polished ebony")
    base, rim_h = 600.0, 290.0
    top = base + rim_h
    outline = grand_outline(W, L)
    inner = mesh.offset_outline(outline, -28.0)
    rim = CadNode("difference", "Rim ring")
    rim.add(polygon("Case outline", outline))
    rim.add(polygon("Inside", inner))
    case = [extrude("Rim", rim, rim_h, base),
            extrude("Bottom", polygon("Bottom", outline), 30.0, base)]
    # the lid, hinged along the spine and open 35 degrees
    lid = move(turn(move(extrude("Lid", polygon("Lid", outline), 18.0),
                         x=W / 2, name="From the hinge"),
                    y=-35.0, name="Open"), -W / 2, 0.0, top, "On the spine")
    reach = 0.8 * W
    stick_x = -W / 2 + reach * math.cos(math.radians(35.0))
    stick_top = top + reach * math.sin(math.radians(35.0))
    case += [lid,
             box("Key bed", -W / 2, -175.0, 640.0, W, 190.0, 40.0),
             box("Bass cheek", -W / 2, -175.0, 640.0, 60.0, 190.0, 120.0),
             box("Treble cheek", W / 2 - 60.0, -175.0, 640.0, 60.0, 190.0,
                 120.0),
             move(turn(box("Music desk", -330.0, 0.0, 0.0, 660.0, 12.0,
                           260.0), x=-15.0), 0.0, 170.0, top, "Desk"),
             ]
    legs = []
    for label, (lx, ly) in (("Bass leg", (-W / 2 + 90.0, 110.0)),
                            ("Treble leg", (W / 2 - 90.0, 110.0)),
                            ("Tail leg", (-W / 2 + 0.2 * W, 0.86 * L))):
        legs.append(cyl(label, 45.0, base - 30.0, lx, ly, 30.0, r2=65.0,
                        seg=24))
    legs.append(box("Lyre post", -60.0, 120.0, 90.0, 120.0, 40.0,
                    base - 90.0))
    legs.append(box("Pedal box", -110.0, 90.0, 40.0, 220.0, 70.0, 60.0))
    legs.append(cbox("Bench seat", 0.0, -620.0, 450.0, 760.0, 360.0, 60.0))
    for bx in (-340.0, 340.0):
        for by in (-760.0, -480.0):
            legs.append(cyl("Bench leg", 22.0, 450.0, bx, by, 0.0, seg=16))
    kids = [paint("Case", colour, material, case + legs)]
    kids.append(paint("Soundboard", "#d8b578", "Matte", [
        extrude("Soundboard", polygon("Soundboard", inner), 6.0,
                base + 30.0)]))
    kids.append(paint("Iron plate", "#c7a24e", "Metal", [
        extrude("Plate", polygon("Plate", mesh.offset_outline(inner, -20.0)),
                10.0, base + 150.0)]))
    kids.append(paint("Hardware", BRASS, "Metal", [
        capsule("Prop stick", (stick_x, 0.45 * L, top),
                (stick_x, 0.45 * L, stick_top - 4.0), 10.0),
        loop("Pedals", [(-45.0,), (0.0,), (45.0,)],
             box("Pedal", "p[0] - 11", 20.0, 60.0, 22.0, 90.0, 10.0)),
        sphere("Castor", 28.0, -W / 2 + 90.0, 110.0, 28.0, seg=16),
        sphere("Castor", 28.0, W / 2 - 90.0, 110.0, 28.0, seg=16),
        sphere("Castor", 28.0, -W / 2 + 0.2 * W, 0.86 * L, 28.0, seg=16),
    ]))
    kb, _width = keys(midi("A0"), midi("C8"), 720.0, -160.0)
    kids.append(move(kb, y=10.0, name="Keyboard"))
    kids.append(paint("Bench top", "#1a1a1c", "Matte", [
        cbox("Cushion", 0.0, -620.0, 510.0, 740.0, 340.0, 25.0)]))
    return group("Grand piano", kids)


# ── drums ─────────────────────────────────────────────────────────────

SHELLS = {"Black": ("#16171a", "Plastic"),
          "Red sparkle": ("#a3141f", "Metal"),
          "Natural maple": ("#c98f55", "Plastic"),
          "White pearl": ("#ece8df", "Plastic"),
          "Blue sparkle": ("#1f4f9e", "Metal"),
          "Green": ("#2f6b3a", "Plastic")}


def drum(name, D, depth, shell, lugs=8, taper=1.0, head=HEAD,
         hoops=True, bottom=True):
    """An upright drum standing on z = 0 (its bottom hoop, else its
    bottom head): shell, head(s), hoops and a loop of lugs."""
    R = D / 2.0
    b = (3.8 if hoops else 0.8) if bottom else 0.0
    colour, material = shell
    kids = [paint("Shell", colour, material, [
        cyl("Shell", R * taper, depth, z=b, r2=R, seg=96)])]
    heads = [cyl("Top head", R + 0.5, 0.8, z=depth + b, seg=96)]
    if bottom:
        heads.append(cyl("Bottom head", R * taper + 0.5, 0.8, z=b - 0.8,
                         seg=96))
    kids.append(paint("Heads", head, "Matte", heads))
    metal = []
    if hoops:
        metal.append(revolve("Top hoop", [(R + 0.3, b + depth - 8.0),
                                          (R + 4.0, b + depth - 8.0),
                                          (R + 4.0, b + depth + 3.0),
                                          (R + 0.3, b + depth + 3.0)]))
        if bottom:
            metal.append(revolve("Bottom hoop", [
                (R * taper + 0.3, 0.0), (R * taper + 4.0, 0.0),
                (R * taper + 4.0, b + 7.0), (R * taper + 0.3, b + 7.0)]))
    if lugs:
        lug = move(cbox("Lug", 6.0, 0.0, 0.0, 14.0, 12.0, depth * 0.4),
                   x=R - 1.0, z=b + depth * 0.3, name="On the shell")
        metal.append(loop(f"{lugs} lugs", [(360.0 * i / lugs,)
                                           for i in range(lugs)],
                          turn(lug, z="p[0]", name="Round")))
    if metal:
        kids.append(paint("Hardware", CHROME, "Metal", metal))
    return group(name, kids)


def cymbal(name, D, bell=0.2, height=None, thickness=1.6, hole=6.0,
           colour=BRONZE):
    """One thin revolved profile — bell and bow — centred on the axis,
    its underside at the edge at z = 0."""
    R = D / 2.0
    h = height if height is not None else D * 0.07
    rb = R * bell
    top = []
    n = 14
    for i in range(n + 1):
        r = hole + (R - hole) * i / n
        if r <= rb:
            z = h * 0.55 + h * 0.45 * math.cos(math.pi * r / (2 * rb)) ** 0.7
        else:
            z = h * 0.55 * (1.0 - (r - rb) / (R - rb)) ** 1.25
        top.append((r, z + thickness))
    pts = top + [(r, z - thickness) for r, z in reversed(top)]
    return paint(name, colour, "Gold", [revolve(name, pts, seg=72)])


def cymbal_stand(name, D, height, tilt=12.0, boom=0.0):
    """A cymbal on a tripod stand; *boom* > 0 leans it out on a boom."""
    kids = [tripod("Stand", height - 20.0, 260.0)]
    c = cymbal("Cymbal", D)
    felt = paint("Felt", FELT, "Matte", [cyl("Felt", 12.0, 8.0, z=-4.0)])
    top = group("Cymbal on its tilter", [c, felt])
    top = turn(top, x=tilt, name="Tilt")
    if boom:
        kids.append(paint("Boom", CHROME, "Metal", [
            capsule("Boom", (0.0, 0.0, height - 20.0),
                    (boom, 0.0, height + boom * 0.35), 8.0)]))
        kids.append(move(top, boom, 0.0, height + boom * 0.35 + 8.0,
                         "On the boom"))
    else:
        kids.append(move(top, z=height, name="On the stand"))
    return group(name, kids)


SNARE_SIZES = {'14" × 5.5"': dict(diameter=356.0, depth=140.0),
               '14" × 6.5"': dict(diameter=356.0, depth=165.0),
               '13" × 3.5" (piccolo)': dict(diameter=330.0, depth=90.0)}
TOM_SIZES = {'12" × 8"': dict(diameter=305.0, depth=203.0),
             '10" × 8"': dict(diameter=254.0, depth=203.0),
             '13" × 9"': dict(diameter=330.0, depth=229.0)}
FLOOR_TOM_SIZES = {'16" × 16"': dict(diameter=406.0, depth=406.0),
                   '14" × 14"': dict(diameter=356.0, depth=356.0),
                   '18" × 16"': dict(diameter=457.0, depth=406.0)}
BASS_SIZES = {'22" × 18"': dict(diameter=559.0, depth=457.0),
              '20" × 16"': dict(diameter=508.0, depth=406.0),
              '24" × 14"': dict(diameter=610.0, depth=356.0)}
CYMBAL_SIZES = {'18" crash': dict(diameter=457.0, height=1250.0),
                '20" ride': dict(diameter=508.0, height=1150.0),
                '16" crash': dict(diameter=406.0, height=1200.0),
                '10" splash': dict(diameter=254.0, height=1250.0)}
HIHAT_SIZES = {'14" hi-hats': dict(diameter=356.0, height=880.0),
               '13" hi-hats': dict(diameter=330.0, height=860.0)}
DRUM_FIELDS = [("diameter", "Diameter"), ("depth", "Depth")]
CYMBAL_FIELDS = [("diameter", "Diameter"), ("height", "Height")]


def _shell(dims):
    return choice(dims, SHELLS, "Black")


def build_snare(dims):
    row = table(dims, SNARE_SIZES)
    D, d = num(row, "diameter", 356.0), num(row, "depth", 140.0)
    snare = drum("Snare drum", D, d, _shell(dims), lugs=10)
    snare.add(paint("Strainer", CHROME, "Metal", [
        cbox("Strainer", D / 2 + 8.0, 0.0, d * 0.3, 16.0, 30.0, d * 0.4)]))
    return snare


def _snare_on_stand(dims, x, y, top):
    row = table(dims, SNARE_SIZES)
    d = num(row, "depth", 140.0)
    kids = [tripod("Snare stand", top - d - 10.0, 250.0),
            paint("Basket", CHROME, "Metal", [
                torus("Basket ring", 120.0, 5.0, seg=32)])]
    kids[1] = move(kids[1], z=top - d - 10.0, name="Basket")
    kids.append(move(build_snare(dims), z=top - d, name="On the stand"))
    return move(group("Snare on its stand", kids), x, y, name="Snare")


def build_tom(dims):
    row = table(dims, TOM_SIZES)
    return drum("Tom", num(row, "diameter", 305.0), num(row, "depth", 203.0),
                _shell(dims), lugs=6)


def build_floor_tom(dims):
    row = table(dims, FLOOR_TOM_SIZES)
    D, d = num(row, "diameter", 406.0), num(row, "depth", 406.0)
    lift = 110.0
    tom = drum("Floor tom", D, d, _shell(dims), lugs=8)
    legs = []
    for k in range(3):
        a = math.radians(90.0 + 120.0 * k)
        ca, sa = math.cos(a), math.sin(a)
        legs.append(capsule(f"Leg {k + 1}", ((D / 2 + 20) * ca,
                                             (D / 2 + 20) * sa, d * 0.8),
                            ((D / 2 + 70) * ca, (D / 2 + 70) * sa,
                             -lift + 6.0), 6.0))
    tom.add(paint("Legs", CHROME, "Metal", legs))
    return move(tom, z=lift, name="Floor tom on its legs")


def build_bass_drum(dims):
    """A bass drum lying on its side, its axis along Y with the
    resonant head facing -Y, on two spurs."""
    row = table(dims, BASS_SIZES)
    D, d = num(row, "diameter", 559.0), num(row, "depth", 457.0)
    R = D / 2.0
    upright = drum("Bass drum", D, d, _shell(dims), lugs=10)
    upright.add(paint("Port", DARK, "Matte", [
        cyl("Port", 60.0, 1.2, R * 0.45, 0.0, -2.0, seg=32)]))
    lying = turn(upright, x=90.0, name="On its side")
    placed = move(lying, 0.0, d / 2.0, R + 4.0, "Centred")
    spurs = []
    for side in (-1, 1):
        spurs.append(capsule("Spur", (side * R * 0.8, -d * 0.2, R * 0.55),
                             (side * (R + 120.0), -d * 0.4, 7.0), 7.0))
    return group("Bass drum", [placed, paint("Spurs", CHROME, "Metal",
                                             spurs)])


def build_cymbal(dims):
    row = table(dims, CYMBAL_SIZES)
    D, H = num(row, "diameter", 457.0), num(row, "height", 1250.0)
    return cymbal_stand("Cymbal", D, H)


def build_hihat(dims):
    row = table(dims, HIHAT_SIZES)
    D, H = num(row, "diameter", 356.0), num(row, "height", 880.0)
    kids = [tripod("Hi-hat stand", H + 60.0, 250.0, tube=10.0),
            move(cymbal("Top hat", D), z=H + 16.0, name="Top"),
            move(turn(cymbal("Bottom hat", D), x=180.0, name="Upside down"),
                 z=H, name="Bottom"),
            paint("Pedal", DARK, "Metal", [
                move(turn(cbox("Footboard", 0.0, 0.0, 0.0, 90.0, 280.0,
                               12.0), x=12.0), 0.0, -320.0, 30.0,
                     "Pedal")])]
    return group("Hi-hat", kids)


def build_throne(dims):
    H = max(num(dims, "height", 500.0), 350.0)
    return group("Drum throne", [
        tripod("Base", H - 60.0, 280.0),
        paint("Seat", DARK, "Matte", [cyl("Seat", 190.0, 80.0, z=H - 60.0,
                                          r2=175.0, seg=64)])])


KIT_SIZES = {"5-piece kit": dict(toms=2), "4-piece kit": dict(toms=1),
             "6-piece kit": dict(toms=3)}


def build_drum_kit(dims):
    """A five-piece kit as a right-handed drummer sits at it (drummer at
    +Y facing -Y, so their left is +X): bass drum, snare and hi-hat on
    the left, rack toms on the bass drum, floor tom and ride on the
    right, a crash on a boom, the throne behind."""
    toms = int(num(table(dims, KIT_SIZES), "toms", 2))
    shell = dict(_color=dims.get("_color") or "Black")
    bass = BASS_SIZES['22" × 18"']
    R = bass["diameter"] / 2.0
    kids = [build_bass_drum(dict(shell, **bass))]
    kids.append(_snare_on_stand(dict(shell, **SNARE_SIZES['14" × 5.5"']),
                                260.0, 420.0, 640.0))
    kids.append(move(build_hihat(HIHAT_SIZES['14" hi-hats']), 560.0,
                     380.0, name="Hi-hat (left)"))
    rack = [('10" × 8"', 180.0), ('12" × 8"', -180.0),
            ('13" × 9"', 0.0)][:toms]
    arms = []
    for i, (size, x) in enumerate(rack):
        spec = TOM_SIZES[size]
        tom = turn(build_tom(dict(shell, **spec)), x=-12.0,
                   name="Tilted to the drummer")
        z = 2 * R + 60.0
        kids.append(move(tom, x, 60.0, z, f"Rack tom {i + 1}"))
        arms.append(capsule("Tom arm", (x * 0.3, 0.0, 2 * R + 6.0),
                            (x, 60.0, z + 30.0), 9.0))
    if arms:
        kids.append(paint("Tom mount", CHROME, "Metal", arms))
    kids.append(move(build_floor_tom(dict(shell,
                                          **FLOOR_TOM_SIZES['16" × 16"'])),
                     -500.0, 420.0, name="Floor tom (right)"))
    kids.append(move(cymbal_stand("Crash", 457.0, 1100.0, boom=260.0),
                     380.0, -120.0, name="Crash (left)"))
    kids.append(move(cymbal_stand("Ride", 508.0, 1020.0, tilt=-10.0,
                                  boom=-240.0), -560.0, 60.0,
                     name="Ride (right)"))
    kids.append(move(build_throne({"height": 520.0}), 0.0, 760.0,
                     name="Throne"))
    return group("Drum kit", kids)


def _part(label, build, sizes, fields=(), colors=None):
    spec = dict(label=label, category=CATEGORY, sizes=sizes,
                fields=list(fields), build=build)
    if colors:
        spec["colors"] = list(colors)
    return spec


PARTS = {
    "music_marimba": _part("Marimba (tuned bars + resonators)",
                           build_marimba, MARIMBA_SIZES, HEIGHT_FIELD,
                           BAR_WOODS),
    "music_xylophone": _part("Xylophone (concert)", build_xylophone,
                             XYLOPHONE_SIZES, HEIGHT_FIELD, BAR_WOODS),
    "music_vibraphone": _part("Vibraphone", build_vibraphone,
                              VIBRAPHONE_SIZES, HEIGHT_FIELD, VIBE_FINISH),
    "music_glockenspiel": _part("Glockenspiel (in its case)",
                                build_glockenspiel, GLOCKENSPIEL_SIZES),
    "music_toy_xylophone": _part("Toy xylophone (rainbow)",
                                 build_toy_xylophone, TOY_SIZES),
    "music_keyboard": _part("Keyboard (digital)", build_keyboard,
                            KEYBOARD_SIZES, [("height", "Height")],
                            CASE_FINISH),
    "music_grand_piano": _part("Grand piano (lid open)", build_grand_piano,
                               GRAND_SIZES,
                               [("length", "Length"), ("width", "Width")],
                               PIANO_FINISH),
    "music_drum_kit": _part("Drum kit", build_drum_kit, KIT_SIZES,
                            colors=SHELLS),
    "music_snare": _part("Snare drum", build_snare, SNARE_SIZES,
                         DRUM_FIELDS, SHELLS),
    "music_tom": _part("Tom-tom", build_tom, TOM_SIZES, DRUM_FIELDS,
                       SHELLS),
    "music_floor_tom": _part("Floor tom (on legs)", build_floor_tom,
                             FLOOR_TOM_SIZES, DRUM_FIELDS, SHELLS),
    "music_bass_drum": _part("Bass drum", build_bass_drum, BASS_SIZES,
                             DRUM_FIELDS, SHELLS),
    "music_cymbal": _part("Cymbal on a stand", build_cymbal, CYMBAL_SIZES,
                          CYMBAL_FIELDS),
    "music_hihat": _part("Hi-hat", build_hihat, HIHAT_SIZES, CYMBAL_FIELDS),
    "music_throne": _part("Drum throne", build_throne,
                          {"Standard": dict(height=500.0)},
                          [("height", "Seat height")]),
}

#: dialog fields that are counts
COUNT_FIELDS = {"notes", "toms"}

#: label -> submenu of the Musical instruments menu
GROUPS = {
    "Tuned percussion": ("Marimba", "Xylophone", "Vibraphone",
                         "Glockenspiel", "Toy xylophone"),
    "Drums & cymbals": ("Drum kit", "Snare", "Tom", "Floor tom",
                        "Bass drum", "Cymbal", "Hi-hat", "Drum throne"),
    "Keyboards": ("Keyboard", "Grand piano"),
}
GROUP_ORDER = ["Keyboards", "Strings", "Winds & brass", "Tuned percussion",
               "Drums & cymbals", "Hand percussion", "Accessories"]


def group_of(label: str) -> str:
    """The submenu a part's *label* goes in."""
    from . import library_music_more
    for name, starts in list(GROUPS.items()) + \
            list(library_music_more.GROUPS.items()):
        if any(label.startswith(s) for s in starts):
            return name
    return "Accessories"
