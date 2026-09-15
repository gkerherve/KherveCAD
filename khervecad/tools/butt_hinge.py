"""Write the three-part printable butt hinges of the Brackets library:
parts/Brackets/Butt Hinge.kcad (a bolt screws in) and Butt Hinge 2.kcad
(a pin slides in and clicks home).

    python -m khervecad.tools.butt_hinge            # both, into parts/
    python -m khervecad.tools.butt_hinge --style slide OUT.kcad ...

Each hinge prints as three separate parts, put together after printing:

* **Leaf A** — three knuckles (both ends and the middle). The far end
  knuckle is tapped and blind: the bolt screws into it, so it cannot
  work loose as the hinge swings, and the closed end hides the tip.
* **Leaf B** — the two knuckles between them, turning on the bolt.
* **Bolt** — Ø10 mm with a coarse 2 mm thread (a printed M8 × 1.25
  thread is too fine to hold once it has its clearance), a round head
  the size of the knuckles and a 6 mm hex socket, so it comes out with
  an Allen key. It prints lying down on a flat, so its layers run
  along it: stood on end, the sideways load a hinge puts on its pin
  would shear it between two layers.

**Butt Hinge 2** has the same leaves and a **Pin** instead of the bolt:
no thread, it slides in. Its tip is slit into two prongs with a lug on
each side; the lugs stand 0.3 mm proud of the bore, so the prongs flex
to pass it and spring out into a groove inside the blind end knuckle —
the pin clicks home and a firm pull on its head takes it out again
(the lugs' back faces slope, they are not square). The lugs sit only
on the sides: the prongs flex sideways, never up or down.

Every mating surface has an FDM clearance: FIT between the bolt and
the bores and thread, GAP between knuckles, SWING round the other
leaf's knuckles (each leaf is scooped where the other's knuckles turn,
so the hinge swings the full 180°). The bores are truncated teardrops,
so their tops print without sagging onto the bolt, and a fillet joins
each knuckle to its leaf, where printed hinges crack. The tap is the
bolt's own helix grown by FIT, started at the same point and sliced
the same way, so in the assembled model the two threads are in phase.

Each part is modelled in its print orientation as an Object at its own
origin — Leaf A and Leaf B lie flat, the Bolt on its flat — and the
Bolt's placement lifts it into the knuckles. Publish to Printables
writes each Object as its own STL at that origin, ready to slice.

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

LENGTH = 75.0          # along the bolt
KNUCKLES = 5           # Leaf A has the odd ones (1st, 3rd, 5th)
WIDTH = 38.0           # each leaf, from the bolt axis to its outer edge
LEAF_T = 4.5
KNUCKLE_R = 9.0        # the axis is KNUCKLE_R above the mounting face
LIP = 1.5              # the plate runs this far past the axis under its
                       # own knuckles: ending on the axis, its corner sat
                       # on the knuckle's tangent line (a non-manifold edge)
GAP = 0.4              # axial gap between neighbouring knuckles
SWING = 0.4            # radial clearance round the other leaf's knuckles
TRIM = 1.0             # thinnest plate edge left where that clearance
                       # meets the bed
FIT = 0.3              # radial clearance, bolt <-> bores and thread
BOLT_D = 10.0
SHANK_D = 9.9          # a hair under the thread's crest, which would
                       # otherwise lie on the shank's own surface
PITCH = 2.0
FLAT = 4.6             # the bolt's print flat, this far below its axis
HEAD_L = 6.0
SOCKET = 6.0           # hex key, across flats
SOCKET_DEPTH = 5.0
THREAD_START = 58.0    # x where the bolt's thread and the tap begin
BOLT_END = 72.5
TAP_END = 73.0         # blind end of the tap: a 2 mm wall is left
SCREW_D = 4.5          # clearance for 4 mm (No. 8) countersunk screws
SINK_D = 9.0           # 90° countersink
HOLES = ((15.0, 17.0), (60.0, 17.0), (37.5, 30.0))   # (x, |y|)
FILLET = 2.5           # knuckle-to-leaf fillet
EDGE = 0.5             # chamfer on the knuckle ends
LEAD = 0.8             # chamfer at the bolt's entry and the tap's
CORNER_R = 4.0         # the leaves' outer corners
SLICES_PER_TURN = 24   # a coarser helix misses FIT by its chord sag
SEGMENTS = 96
BRASS = "#d1ad59"
BOLT_COLOUR = "#a8843f"

# Butt Hinge 2's slide-in pin (x along the hinge, r from the axis)
LUG_R = 5.6            # 0.3 over the bore: how far each prong flexes
LUG_HALF = 2.5         # lugs only where |z| < this, on the prongs' sides
LUG_X = (68.9, 69.7, 70.8, 72.05)     # back face, crest, lead-in ramp
GROOVE_R = 5.9         # the lugs sit free in it, 0.3 all round
GROOVE_X = (68.5, 69.3, 71.4, 72.2)   # 45° flanks
SLIT_W = 1.2           # lets each prong move 0.6, twice what it needs
SLIT_START = 58.5      # 14 mm prongs: about 1 % strain to pass the bore
SLIT_RELIEF = 0.9      # a round end, so the slit does not crack on

#: style -> the library file it writes
STYLES = {"screw": "Butt Hinge", "slide": "Butt Hinge 2"}

BORE_R = BOLT_D / 2.0 + FIT


def _model():
    from khervecad import model
    return model


def _node(type_, name, children=(), **params):
    node = _model().CadNode(type_, name, params)
    for child in children:
        node.add(child)
    return node


def _pts(points):
    return [[round(u, 4), round(v, 4)] for u, v in points]


def _along_x(name, child, x=0.0, y=0.0, z=0.0):
    """*child*, built along +Z, turned to run along +X from (x, y, z)."""
    return _node("translate", name, [
        _node("rotate", "Along X", [child], x=0.0, y=90.0, z=0.0)],
        x=x, y=y, z=z)


def _profile_along_x(name, points, x0, x1):
    """A (y, z) profile extruded along X from x0 to x1."""
    return _node("translate", name, [
        _node("rotate", "Profile on YZ", [
            _node("linear_extrude", name, [
                _node("polygon", f"{name} profile", x=0.0, y=0.0,
                      points=_pts(points))],
                height=round(x1 - x0, 4), twist=0.0, scale=1.0,
                center=False, segments=0)],
            x=90.0, y=0.0, z=90.0)],
        x=round(x0, 4), y=0.0, z=0.0)


def _revolved_x(name, points, x=0.0, z=0.0):
    """A solid of revolution about the X axis: *points* are (r, x)."""
    return _along_x(name, _node("rotate_extrude", name, [
        _node("polygon", f"{name} profile", x=0.0, y=0.0,
              points=_pts(points))],
        angle=360.0, segments=SEGMENTS), z=z, x=x)


def _cone_x(name, r1, r2, x0, x1, z):
    return _along_x(name, _node("cylinder", name, x=0.0, y=0.0, z=0.0,
                                height=round(x1 - x0, 4),
                                radius_bottom=r1, radius_top=r2,
                                segments=SEGMENTS, center=False),
                    x=x0, z=z)


def _arc(cx, cy, r, a0, a1, n):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
            for i in range(n + 1)]


def knuckle_span(k):
    """(x0, x1) of knuckle *k*, the gap shared with its neighbours."""
    step = LENGTH / KNUCKLES
    x0 = k * step + (GAP / 2.0 if k > 0 else 0.0)
    x1 = (k + 1) * step - (GAP / 2.0 if k < KNUCKLES - 1 else 0.0)
    return x0, x1


def owned(leaf):
    """The knuckle indices of leaf "A" (even) or "B" (odd)."""
    first = 0 if leaf == "A" else 1
    return list(range(first, KNUCKLES, 2))


def thread_profile(d_major):
    from khervecad.library import thread_profile as iso
    return iso(d_major, PITCH)


def thread(name, d_major, x0, x1, z):
    """The helix from x0 to x1 about the axis at height *z*. The bolt and
    the tap both come from here with the same x0 and slice spacing, so
    they share one helix — only the diameter differs."""
    turns = (x1 - x0) / PITCH
    ext = _node("linear_extrude", name, [
        _node("polygon", f"{name} profile", x=0.0, y=0.0,
              points=thread_profile(d_major))],
        height=round(x1 - x0, 4), twist=round(-360.0 * turns, 3),
        scale=1.0, center=False,
        segments=int(round(turns * SLICES_PER_TURN)))
    return _along_x(name, ext, x=x0, z=z)


# ---------------------------------------------------------------- leaves

def _plate_outline(s):
    """The leaf seen from above, outer corners rounded; *s* = -1 for Leaf
    A (towards -y), +1 for Leaf B."""
    w, r = WIDTH, CORNER_R
    # 0.01 short of each end: flush with the end knuckles, the plate's
    # top edge lay on their end faces
    lo, hi = 0.01, LENGTH - 0.01
    far = [(hi, LIP)]
    far += [(x, y) for x, y in _arc(hi - r, -w + r, r, 0.0, -90.0, 8)]
    far += [(x, y) for x, y in _arc(lo + r, -w + r, r, -90.0, -180.0, 8)]
    far += [(lo, LIP)]
    pts = [(x, -y) for x, y in far] if s > 0 else far
    return pts if s < 0 else list(reversed(pts))


def _fillet_profile(s):
    """(y, z) outline of the fillet between the leaf's top face and its
    knuckle: the corner outside both, bounded by an arc tangent to each,
    closed inside the knuckle and dipping into the plate (a face lying
    on the plate's top would be a coplanar seam)."""
    r, t, rk = FILLET, LEAF_T, KNUCKLE_R
    zc = t + r
    yc = -math.sqrt((rk + r) ** 2 - (rk - zc) ** 2)
    a1 = math.degrees(math.atan2(rk - zc, -yc))
    arc = _arc(yc, zc, r, -90.0, a1, 10)
    top = arc[-1][1]
    pts = [(yc, t - 0.5)] + arc + [(-4.0, top), (-4.0, t - 0.5)]
    return [(-y, z) for y, z in pts] if s > 0 else pts


def _teardrop():
    """(y, z) outline of a bore round the axis at z = KNUCKLE_R: a circle
    whose top is two 45° lines and a short flat, so the roof of a
    horizontal hole prints without sagging onto the bolt."""
    r = BORE_R
    top = r * 1.12
    pts = _arc(0.0, KNUCKLE_R, r, 135.0, 405.0, 48)
    t = r / math.sqrt(2.0)
    u = t - (top - t)
    return pts + [(u, KNUCKLE_R + top), (-u, KNUCKLE_R + top)]


def _knuckle(k):
    x0, x1 = knuckle_span(k)
    rk, e = KNUCKLE_R, EDGE
    return _revolved_x(f"Knuckle {k + 1}", [
        (0.0, 0.0), (rk - e, 0.0), (rk, e), (rk, x1 - x0 - e),
        (rk - e, x1 - x0), (0.0, x1 - x0)], x=x0, z=rk)


def _scoop(k):
    """Room round the other leaf's knuckle *k* to turn in — a cylinder
    about the axis, plus a trim where it meets the bed almost at a
    tangent and would leave the plate a feather edge thinner than TRIM."""
    x0, x1 = knuckle_span(k)
    # 0.01 into the neighbouring knuckles: starting on their end faces
    # left the two faces coplanar
    x0 = -1.0 if k == 0 else x0 - GAP - 0.01
    x1 = LENGTH + 1.0 if k == KNUCKLES - 1 else x1 + GAP + 0.01
    rs = KNUCKLE_R + SWING
    edge = math.sqrt(rs ** 2 - (KNUCKLE_R - TRIM) ** 2)
    return _node("union", f"Swing clearance {k + 1}", [
        _cone_x("Swing clearance", rs, rs, x0, x1, KNUCKLE_R),
        # topped above TRIM so its edge lies inside the cylinder, not on it
        _node("cube", "Feather-edge trim", x=round(x0, 4),
              y=round(-edge, 4), z=-1.0, width=round(x1 - x0, 4),
              depth=round(2 * edge, 4), height=TRIM + 1.2, center=False)])


def _entry_chamfer(name, x):
    """A 45° lead-in where the bolt enters a bore at face *x*, running on
    past the bore's wall so the two cross rather than touch."""
    return _cone_x(name, BORE_R + LEAD + 0.5, BORE_R - 0.3, x - 0.5,
                   x + LEAD + 0.3, KNUCKLE_R)


def _screw_holes(s):
    holes = []
    for x, y in HOLES:
        y = s * y
        holes.append(_node("cylinder", "Screw hole", x=x, y=y, z=-0.01,
                           height=LEAF_T + 0.02, radius_bottom=SCREW_D / 2,
                           radius_top=SCREW_D / 2, segments=32,
                           center=False))
        sink = (SINK_D - SCREW_D) / 2.0
        holes.append(_node("cylinder", "Countersink", x=x, y=y,
                           z=round(LEAF_T - sink, 4), height=sink + 0.01,
                           radius_bottom=SCREW_D / 2,
                           radius_top=SINK_D / 2 + 0.01, segments=32,
                           center=False))
    return holes


def leaf(which, style="screw"):
    """Leaf "A" (three knuckles, the last one tapped for the bolt or
    grooved for the pin) or "B" (two knuckles, the same for both)."""
    s = -1 if which == "A" else 1
    mine = owned(which)
    theirs = [k for k in range(KNUCKLES) if k not in mine]
    body = [_node("linear_extrude", "Plate", [
        _node("polygon", "Plate outline", x=0.0, y=0.0,
              points=_pts(_plate_outline(s)))],
        height=LEAF_T, twist=0.0, scale=1.0, center=False, segments=0)]
    for k in mine:
        body.append(_knuckle(k))
        x0, x1 = knuckle_span(k)
        # stopped short of the knuckle's end chamfer: ending on its end
        # face, or on the ring where the chamfer starts, left coplanar
        # faces and doubled edges
        stop = EDGE + 0.2
        body.append(_profile_along_x(f"Fillet {k + 1}",
                                     _fillet_profile(s), x0 + stop,
                                     x1 - stop))
    cuts = [_scoop(k) for k in theirs]
    if which == "A" and style == "slide":
        # a plain blind bore, and the groove the pin's lugs click into
        cuts.append(_profile_along_x("Bore", _teardrop(), -1.0, TAP_END))
        g0, g1, g2, g3 = GROOVE_X
        cuts.append(_revolved_x("Snap groove", [
            (BORE_R - 0.8, g0), (BORE_R - 0.2, g0), (GROOVE_R, g1),
            (GROOVE_R, g2), (BORE_R - 0.2, g3), (BORE_R - 0.8, g3)],
            z=KNUCKLE_R))
        cuts.append(_entry_chamfer("Pin entry", 0.0))
        cuts.append(_entry_chamfer("Lead-in",
                                   knuckle_span(KNUCKLES - 1)[0]))
    elif which == "A":
        cuts.append(_profile_along_x("Bore", _teardrop(), -1.0,
                                     THREAD_START + 1.0))
        cuts.append(thread("Tapped thread", BOLT_D + 2 * FIT,
                           THREAD_START, TAP_END, KNUCKLE_R))
        cuts.append(_entry_chamfer("Bolt entry", 0.0))
        cuts.append(_entry_chamfer("Tap entry",
                                   knuckle_span(KNUCKLES - 1)[0]))
    else:
        cuts.append(_profile_along_x("Bore", _teardrop(), -1.0,
                                     LENGTH + 1.0))
    cuts += _screw_holes(s)
    solid = _node("difference", f"Leaf {which}", [
        _node("union", "Leaf and knuckles", body)] + cuts)
    return _node("component", f"Leaf {which}", [solid],
                 color=BRASS, alpha=1.0)


# ------------------------------------------------------------------ bolt

def _head():
    """The round head, the knuckles' size, bearing face at x = 0."""
    rk = KNUCKLE_R
    return _revolved_x("Head", [
        (0.0, -HEAD_L), (rk - 1.0, -HEAD_L), (rk, -HEAD_L + 1.0),
        (rk, -EDGE), (rk - EDGE, 0.0), (0.0, 0.0)], z=FLAT)


def _print_flat():
    """Everything below the bed: the flat the bolt or pin prints on."""
    rk = KNUCKLE_R
    return _node("cube", "Print flat", x=-HEAD_L - 1.0, y=-rk - 1.0,
                 z=-rk - 1.0, width=BOLT_END + HEAD_L + 2.0,
                 depth=2 * rk + 2.0, height=rk + 1.0, center=False)


def _tip_chamfer():
    """A 45° cone meeting the tip's end face at r_in, under the thread's
    root; drawn on past the face so the two cross rather than touch.
    0.45 and not 0.5: at 0.5 it crossed the root exactly on one of the
    thread's slice planes, a doubled edge."""
    r = BOLT_D / 2.0
    r_in = r - 0.6134 * PITCH - 0.45
    return _revolved_x("Tip chamfer", [
        (r_in - 1.0, BOLT_END + 1.0),
        (r + 1.5, BOLT_END - (r + 1.5 - r_in)),
        (r + 1.5, BOLT_END + 1.0)], z=FLAT)


def bolt():
    """The bolt in its print pose: axis along +X, FLAT above the bed,
    the head's bearing face at x = 0."""
    rk = KNUCKLE_R
    head = _head()
    shank = _cone_x("Shank", SHANK_D / 2, SHANK_D / 2, -0.5,
                    THREAD_START + 0.5, FLAT)
    body = _node("union", "Head, shank and thread", [
        head, shank, thread("Thread", BOLT_D, THREAD_START, BOLT_END,
                            FLAT)])
    flat = _print_flat()
    socket = _along_x("Hex socket", _node(
        "cylinder", "Hex socket", x=0.0, y=0.0, z=0.0,
        height=SOCKET_DEPTH + 0.01,
        radius_bottom=round(SOCKET / math.sqrt(3.0), 4),
        radius_top=round(SOCKET / math.sqrt(3.0), 4), segments=6,
        center=False), x=-HEAD_L - 0.01, z=FLAT)
    solid = _node("difference", "Bolt", [body, flat, socket,
                                         _tip_chamfer()])
    return _node("component", "Bolt", [solid], color=BOLT_COLOUR,
                 alpha=1.0, z=round(KNUCKLE_R - FLAT, 4))


def pin():
    """Butt Hinge 2's pin, posed like the bolt: plain, its tip slit into
    two prongs with a lug on each side that clicks into the groove of
    Leaf A's blind end knuckle."""
    rk, r = KNUCKLE_R, SHANK_D / 2.0
    shank = _cone_x("Shank", r, r, -0.5, BOLT_END, FLAT)
    l0, l1, l2, l3 = LUG_X
    ring = _revolved_x("Lug ring", [
        (r - 0.45, l0), (r - 0.05, l0), (LUG_R, l1), (LUG_R, l2),
        (r - 0.05, l3), (r - 0.45, l3)], z=FLAT)
    sides = _node("cube", "Sides only", x=l0 - 0.5, y=-rk,
                  z=FLAT - LUG_HALF, width=l3 - l0 + 1.0, depth=2 * rk,
                  height=2 * LUG_HALF, center=False)
    body = _node("union", "Head, shank and lugs", [
        _head(), shank, _node("intersection", "Lugs", [ring, sides])])
    slit = _node("cube", "Slit", x=SLIT_START, y=-SLIT_W / 2, z=-1.0,
                 width=BOLT_END - SLIT_START + 1.0, depth=SLIT_W,
                 height=2 * rk + 2.0, center=False)
    relief = _node("cylinder", "Slit relief", x=SLIT_START, y=0.0, z=-1.0,
                   height=2 * rk + 2.0, radius_bottom=SLIT_RELIEF,
                   radius_top=SLIT_RELIEF, segments=24, center=False)
    solid = _node("difference", "Pin", [body, _print_flat(), slit, relief,
                                        _tip_chamfer()])
    return _node("component", "Pin", [solid], color=BOLT_COLOUR,
                 alpha=1.0, z=round(KNUCKLE_R - FLAT, 4))


def parts(style="screw"):
    """The three Objects, placed as the assembled hinge lying open."""
    return [leaf("A", style), leaf("B", style),
            bolt() if style == "screw" else pin()]


def write(path, style="screw"):
    from PyQt5.QtWidgets import QApplication
    from khervecad import document
    from khervecad.model import DocumentModel
    _app = QApplication.instance() or QApplication([])
    doc = DocumentModel()
    # the document-wide $fn would round the 6-sided socket (no key could
    # turn the bolt) and coarsen the 96-sided knuckles
    doc.global_fn_on = False
    for part in parts(style):
        doc.root.add(part)
    document.save_kcad(doc, str(path))


def default_path(style):
    from khervecad import library_kcad
    return library_kcad.PARTS_DIR / "Brackets" / f"{STYLES[style]}.kcad"


def main(argv=None):
    import argparse
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    ap = argparse.ArgumentParser(description="Write the butt hinges.")
    ap.add_argument("--style", choices=sorted(STYLES),
                    help="screw (Butt Hinge) or slide (Butt Hinge 2)")
    ap.add_argument("out", nargs="*", help="where to write it")
    args = ap.parse_args(argv)
    if args.out and not args.style:
        ap.error("name the --style to write to OUT")
    for style in ([args.style] if args.style else list(STYLES)):
        for path in (args.out or [default_path(style)]):
            write(path, style)
            print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
