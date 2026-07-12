"""A garden of procedural flower examples for the Examples menu.

Each flower is built the way the fractal tree is — a Python builder loops
petals / seeds / stamens and unrolls them into the object tree, using only
coloured solids so every bloom previews in the built-in viewer. The shared
primitive helpers live in :mod:`khervecad.examples`; this module is
imported at the end of that one, which extends ``EXAMPLES`` with
``FLOWER_EXAMPLES``.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .examples import (EXAMPLES, _color, _cube, _cyl, _ext, _petal, _place,
                       _root, _rot, _sphere)
from .model import CadNode


def tulip() -> CadNode:
    """A single upright tulip: closed egg-shaped 6-tepal bloom on a tall
    leafy stem."""
    stem_h = 200.0
    stem = _color("Stem", "#3f8f3f",
                  _cyl("Stem", 3.4, stem_h, r2=2.3, segments=20))

    def leaf(length, width, height, side, bend):
        n = 10
        pts = [[round(width * math.sin(math.pi * i / n), 2),
                round(length * i / n, 2)] for i in range(n + 1)]
        pts += [[round(-width * math.sin(math.pi * i / n), 2),
                 round(length * i / n, 2)] for i in range(n, -1, -1)]
        blade = _color("Leaf", "#3f8f3f", _ext(
            "Leaf", 1.6, CadNode("polygon", "Leaf blade",
                                 dict(x=0.0, y=0.0, points=pts))))
        return _rot(_place(_rot(blade, x=bend), y=1.5, z=height), z=side)

    def tepal(length, width, thick, lean, base_r, azimuth, color):
        egg = CadNode("scale", "Tepal shape",
                      dict(x=width / 2.0, y=thick / 2.0, z=length / 2.0))
        egg.add(_sphere("Tepal blade", 1.0, seg=16))
        blade = _color("Tepal", color, egg)
        lifted = _place(blade, z=length / 2.0 * 0.92)
        leaned = _rot(lifted, x=lean)
        return _rot(_place(leaned, y=base_r), z=azimuth)

    bloom = CadNode("union", "Bloom")
    bloom.add(_color("Base", "#8fae3f", _cyl("Base", 5.0, 4.0, segments=24)))
    for k in range(3):                                  # outer whorl
        bloom.add(tepal(62.0, 34.0, 20.0, -11.0, 6.0, k * 120.0, "#c9302b"))
    for k in range(3):                                  # inner whorl (+60°)
        bloom.add(tepal(58.0, 30.0, 18.0, -14.0, 4.0,
                        60.0 + k * 120.0, "#e04a3f"))
    return _root(stem, leaf(95, 15, 20, 40.0, 55.0),
                 leaf(85, 13, 60, 320.0, 50.0), _place(bloom, z=stem_h))


def rose() -> CadNode:
    """A furled, rounded rose: concentric rings of cupped petals (a
    near-vertical bud core opening to a wide outer ring), a green
    receptacle, a stem and two toothed leaves."""
    def petal_round(length, width, thick, lean, color, seg=16):
        core = _sphere("Petal core", 1.0, seg=seg)
        shaped = CadNode("scale", "Petal shape",
                         dict(x=width / 2.0, y=thick / 2.0, z=length / 2.0))
        shaped.add(core)
        return _color("Petal", color,
                      _rot(_place(shaped, z=length / 2.0), x=lean))

    def petal_flat(length, width, thick, lean, color, seg=22):
        cone = _cyl("Blade", width / 2.0, length,
                    r2=max(width * 0.12, 0.6), segments=seg)
        flat = CadNode("scale", "Flatten",
                       dict(x=1.0, y=max(thick / width, 0.05), z=1.0))
        flat.add(cone)
        return _color("Petal", color, _rot(flat, x=lean))

    def leaf_toothed(length, width, height, side):
        n = 18

        def edge(sign):
            out = []
            for i in range(n + 1):
                t = i / n
                env = math.sin(math.pi * t)
                tooth = 1.0 + (0.16 * math.sin(t * n * math.pi)
                               if 0.03 < t < 0.98 else 0.0)
                out.append([round(sign * width * env * tooth, 2),
                            round(length * t, 2)])
            return out

        pts = edge(1.0) + list(reversed(edge(-1.0)))
        blade = _color("Leaf", "#4a7a3a", _ext(
            "Leaf", 1.2, CadNode("polygon", "Leaf blade",
                                 dict(x=0.0, y=0.0, points=pts))))
        return _rot(_place(_rot(blade, x=62.0), y=2.0, z=height), z=side)

    stem_h = 110.0
    stem = _color("Stem", "#3f7a3f",
                  _cyl("Stem", 2.8, stem_h, r2=1.9, segments=20))
    receptacle = CadNode("scale", "Dome", dict(x=1.0, y=1.0, z=0.55))
    receptacle.add(_sphere("Receptacle", 6.0, seg=24))

    bloom = CadNode("union", "Bloom")
    bloom.add(_color("Receptacle", "#4d7a3d", receptacle))
    #        count, base r, lean°, length, width, thick, colour, rounded
    rings = [(3, 0.0, 8.0, 13, 8.5, 7.5, "#7a0a1f", True),
             (5, 1.5, 25.0, 18, 11.5, 9.0, "#93132c", True),
             (6, 3.5, 42.0, 23, 15.0, 7.5, "#b31f34", False),
             (7, 5.5, 60.0, 28, 18.5, 6.5, "#cf3348", False),
             (8, 8.0, 78.0, 33, 22.0, 5.5, "#e2536a", False)]
    for ri, (count, r, lean, length, width, thick, color, rounded) in \
            enumerate(rings):
        for k in range(count):
            az = ri * 21.0 + k * 360.0 / count
            petal = (petal_round(length, width, thick, lean, color)
                     if rounded else
                     petal_flat(length, width, thick, lean, color))
            bloom.add(_rot(_place(petal, y=r), z=az))
    return _root(stem, leaf_toothed(28, 8, 32, 95.0),
                 leaf_toothed(24, 7, 54, 250.0), _place(bloom, z=stem_h))


def daisy() -> CadNode:
    """A classic daisy: two staggered rings of long white ray petals lying
    nearly flat around a low domed yellow centre, on a thin leafy stem."""
    stem_h = 82.0
    stem = _color("Stem", "#4a9a4a",
                  _cyl("Stem", 1.6, stem_h, r2=1.1, segments=16))

    def leaf(length, width, height, side):
        n = 8
        pts = [[round(width * (i / n) * (1 - i / n) * 4, 2),
                round(length * i / n, 2)] for i in range(n + 1)]
        pts += [[-p[0], p[1]] for p in reversed(pts[:-1])]
        blade = _color("Leaf", "#4aa04a", _ext(
            "Leaf", 0.8, CadNode("polygon", "Leaf blade",
                                 dict(x=0.0, y=0.0, points=pts))))
        return _rot(_place(_rot(blade, x=70.0), z=height), z=side)

    head = CadNode("union", "Head")
    dome = CadNode("scale", "Dome", dict(x=1.0, y=1.0, z=0.45))
    dome.add(_sphere("Receptacle", 6.0, seg=32))
    head.add(_color("Centre", "#f4c430", dome))
    for k in range(12):                                 # florets on the disc
        rr = 1.2 + 4.2 * math.sqrt(k / 12.0)
        floret = _sphere("Floret", 0.6, z=2.4, seg=8)
        head.add(_color("Floret", "#c98f10",
                        _rot(_place(floret, x=rr), z=k * 137.5)))
    for ri, (count, base_r, lean, length, width) in enumerate(
            [(20, 0.5, 84.0, 27, 6.0), (20, 2.0, 87.0, 24, 5.5)]):
        for k in range(count):
            az = ri * (360.0 / count / 2) + k * 360.0 / count
            head.add(_rot(_place(_petal(length, width, 1.4, lean, "#fbfbf5"),
                                 y=base_r), z=az))
    return _root(stem, leaf(24, 7, 30.0, 60.0), leaf(20, 6, 48.0, 220.0),
                 _place(head, z=stem_h))


def lily() -> CadNode:
    """A tiger/stargazer-style lily: 6 recurved star tepals, protruding
    stamens and a central pistil, on a tall leafy stem."""
    stem_h = 150.0
    stem = _color("Stem", "#3f8f3f",
                  _cyl("Stem", 3.0, stem_h, r2=2.0, segments=24))

    def leaf(length, width, height, side):
        n = 8
        pts = [[round(width * math.sin(math.pi * i / n), 2),
                round(length * i / n, 2)] for i in range(n + 1)]
        pts += [[round(-width * math.sin(math.pi * i / n), 2),
                 round(length * i / n, 2)] for i in range(n, -1, -1)]
        blade = _color("Leaf", "#3f8f3f", _ext(
            "Leaf", 1.2, CadNode("polygon", "Leaf blade",
                                 dict(x=0.0, y=0.0, points=pts))))
        return _rot(_place(_rot(blade, x=68.0), y=1.6, z=height), z=side)

    def stamen(flen, r_base, lean, az):
        unit = CadNode("union", "Stamen")
        unit.add(_color("Filament", "#d8c98a",
                        _cyl("Filament", 0.45, flen, segments=8)))
        unit.add(_color("Anther", "#6b3410",
                        _place(_cube("Anther", 1.6, 1.6, 3.6, center=True),
                               z=flen)))
        return _rot(_place(_rot(unit, x=lean), y=r_base), z=az)

    def pistil(flen):
        unit = CadNode("union", "Pistil")
        unit.add(_color("Style", "#8fae5a",
                        _cyl("Style", 0.55, flen, segments=10)))
        for i in range(3):
            unit.add(_color("Stigma", "#5c7a3a",
                            _rot(_place(_sphere("Stigma lobe", 1.1, z=flen,
                                                seg=8), y=1.4), z=i * 120.0)))
        return unit

    bloom = CadNode("union", "Bloom")
    for k in range(6):
        az = k * 60.0
        bloom.add(_rot(_place(_petal(42.0, 16.0, 2.6, 62.0, "#e8743b"),
                              y=2.5), z=az))
        if k % 2 == 0:                                  # throat speckles
            for s in range(2):
                speck = _sphere("Speckle", 0.55, y=4.0 + s * 3.0,
                                z=1.0 + s * 0.8, seg=6)
                bloom.add(_color("Speckle", "#7a2e1a",
                                 _rot(speck, z=az + (s - 0.5) * 8.0)))
    for k in range(6):                                  # stamens
        bloom.add(stamen(26.0, 2.0, 38.0, k * 60.0 + 30.0))
    bloom.add(pistil(30.0))
    return _root(stem, leaf(55, 7, 26, 35.0), leaf(50, 6.5, 52, 155.0),
                 leaf(46, 6, 82, 280.0), leaf(36, 5, 112, 15.0),
                 _place(bloom, z=stem_h))


def daffodil() -> CadNode:
    """A daffodil: six flat yellow tepals behind a projecting orange
    trumpet corona, on a leafy green stem."""
    stem_h = 130.0

    def trumpet_profile():
        n = 10
        base_r_in, base_r_out = 4.0, 4.6
        rim_r_in, rim_r_out = 9.0, 9.6
        h = 16.0
        pts = []
        for i in range(n + 1):                          # inner wall, up
            t = i / n
            pts.append([round(base_r_in + (rim_r_in - base_r_in)
                              * t ** 1.5, 2), round(h * t, 2)])
        pts.append([round(rim_r_in + 1.1, 2), round(h + 1.6, 2)])
        pts.append([round(rim_r_out + 0.3, 2), round(h + 0.4, 2)])
        for i in range(n, -1, -1):                      # outer wall, down
            t = i / n
            pts.append([round(base_r_out + (rim_r_out - base_r_out)
                              * t ** 1.5, 2), round(h * t, 2)])
        return pts

    def leaf(length, width, height, side):
        n = 10
        pts = [[round(width * math.sin(math.pi * i / n), 2),
                round(length * i / n, 2)] for i in range(n + 1)]
        pts += [[round(-width * math.sin(math.pi * i / n), 2),
                 round(length * i / n, 2)] for i in range(n, -1, -1)]
        blade = _color("Leaf", "#3f8f3f", _ext(
            "Leaf", 1.2, CadNode("polygon", "Leaf blade",
                                 dict(x=0.0, y=0.0, points=pts))))
        return _rot(_place(_rot(blade, x=70.0), y=2.0, z=height), z=side)

    stem = _color("Stem", "#4a9c3f",
                  _cyl("Stem", 2.4, stem_h, r2=1.7, segments=20))
    head = CadNode("union", "Head")
    for k in range(6):                                  # flat tepal star
        head.add(_rot(_place(_petal(24.0, 14.0, 2.2, 84.0, "#f7d417",
                                    seg=24), y=2.0), z=k * 60.0))
    trumpet = CadNode("rotate_extrude", "Trumpet",
                      dict(angle=360, segments=64))
    trumpet.add(CadNode("polygon", "Trumpet wall",
                        dict(x=0.0, y=0.0, points=trumpet_profile())))
    head.add(_color("Trumpet", "#f5a623", trumpet))
    return _root(stem, leaf(62, 7, 8, 95.0), leaf(52, 6, 26, 255.0),
                 _place(_rot(head, x=20.0), z=stem_h))


def calla_lily() -> CadNode:
    """A calla lily: a curled white spathe funnel around a yellow spadix,
    on a leafy stem."""
    stem_h = 150.0
    stem = _color("Stem", "#3f8f3f",
                  _cyl("Stem", 3.2, stem_h, r2=2.2, segments=20))

    def leaf(length, width, tilt, side):
        n = 12
        pts = [[round(width * math.sin(math.pi * i / n) ** 0.7, 2),
                round(length * i / n, 2)] for i in range(n + 1)]
        pts += [[round(-width * math.sin(math.pi * i / n) ** 0.7, 2),
                 round(length * i / n, 2)] for i in range(n, -1, -1)]
        blade = _color("Leaf", "#357a35", _ext(
            "Leaf", 1.2, CadNode("polygon", "Leaf blade",
                                 dict(x=0.0, y=0.0, points=pts))))
        return _rot(_place(_rot(blade, x=tilt), z=3.0), z=side)

    n = 16
    inner, outer = [], []
    for i in range(n + 1):
        t = i / n
        z = 55.0 * t
        r = 3.0 + 23.0 * (t ** 1.6)             # trumpet flare
        inner.append([round(r, 2), round(z, 2)])
        outer.append([round(r + 1.6, 2), round(z, 2)])
    profile = CadNode("polygon", "Spathe profile",
                      dict(x=0.0, y=0.0, points=inner + list(reversed(outer))))
    shell = CadNode("rotate_extrude", "Spathe shell",
                    dict(angle=300, segments=64))     # open C, not full 360
    shell.add(profile)
    spadix = _color("Spadix", "#f2c200",
                    _cyl("Spadix", 2.2, 40.0, r2=1.2, segments=24))
    bloom = CadNode("union", "Bloom")
    bloom.add(_color("Spathe", "#f7f3e8", shell))
    bloom.add(_place(spadix, z=2.0))
    return _root(stem, leaf(75, 26, 22.0, 200.0), leaf(62, 21, 18.0, 335.0),
                 _place(_rot(bloom, x=25.0), z=stem_h))


#: (menu label, category, builder) — registered into examples.EXAMPLES.
FLOWER_EXAMPLES = [
    ("Tulip", "Flowers", tulip),
    ("Rose", "Flowers", rose),
    ("Daisy", "Flowers", daisy),
    ("Lily", "Flowers", lily),
    ("Daffodil", "Flowers", daffodil),
    ("Calla lily", "Flowers", calla_lily),
]

# extend the shared list in place, so every `examples.EXAMPLES` reference
# (imported before or after this module) sees the flowers
EXAMPLES.extend(FLOWER_EXAMPLES)
