"""The cars' front and rear ends (Qt-free).

A car is recognised by its face, so the lamps, grille, plate and
intakes are not floated near the nose: `surface_y` walks the body's own
sections until it finds the one that contains the point, so every piece
is planted ON the bodywork and stands the same few millimetres proud of
it, whatever the shape of the nose.

What goes on: headlamps (round, twin round, slim, or covered pop-ups
with driving lamps in the bumper) in a dark recess behind a lens,
indicators, the grille of the marque (BMW kidneys with bars, the
Mercedes star in a slatted grille, a Bugatti horseshoe, a supercar's
mouth), a lower intake with a splitter and fog lamps, and a real
NUMBER PLATE — a 520 x 110 European plate, or a square one where the
nose is too narrow for it. The rear gets its lights, reversing lamps,
a plate, a diffuser and exhausts.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

LAMP = "#eef3f7"
AMBER = "#e08a1e"
TAIL = "#c4121b"
TRIM = "#1e1f22"
DARK = "#111214"
CHROME = "#dfe2e6"
PLATE = "#f2f2ee"
PLATE_INK = "#26282c"

#: a European plate
PLATE_W, PLATE_H = 520.0, 110.0
#: how far a lens or a plate stands proud of the panel it sits on
PROUD = 16.0


def surface_y(car, x, z, front=True, reach=0.36):
    """The y of the body's outer surface at (x, z), found by walking
    the sections in from the nose (or the tail). Falls back to the
    furthest station it looked at, so a piece is never left floating in
    mid air."""
    steps = 120
    for i in range(steps + 1):
        s = (reach * i / steps) if front else (1.0 - reach * i / steps)
        a = car.half_width(s)
        if a < 1e-6 or abs(x) > a * 0.97:
            continue
        u = x / a
        if car.bottom(s) - 10 <= z <= car.body_top_at(s, u) + 10:
            return car.y(s)
    return None          # not on the bodywork: the caller skips it


def _normal(car, x, z, h, front=True):
    """(y at z, dy/dz) of the body's face there: a nose that slopes
    forward wants its lamps and plate raked to match, or they stand out
    of it like shelves."""
    y = surface_y(car, x, z, front)
    if y is None:
        return None, 0.0
    up = surface_y(car, x, z + h * 0.5, front)
    down = surface_y(car, x, z - h * 0.5, front)
    if up is None or down is None:
        return y, 0.0
    return y, (up - down) / h


def steep_z(car, x, z, h, front=True, limit=3.0, lift=0.45,
            fallback=False):
    """The nearest z at or above *z* where the face is steep enough to
    carry a lamp or a plate. On a wedge the bottom of the nose is all
    but horizontal, and anything put there lies flat like a shelf."""
    step = max(12.0, h * 0.25)
    for i in range(int(lift * car.H / step) + 1):
        zz = z + i * step
        y, slope = _normal(car, x, zz, h, front)
        if y is not None and abs(slope) <= limit:
            return zz
    # a wedge has no upright face at all. Its LAMPS lie on the skin of
    # the nose, which is where they really sit; a plate or an intake
    # would only hang under the prow like a shelf, so it is left off.
    if not fallback:
        return None
    s = 0.05 if front else 0.95
    a = car.half_width(s)
    if a < 1e-6 or abs(x) > a * 0.95:
        return None
    return car.body_top_at(s, x / a) - h * 0.5


def _lens(kit, car, x, z, r, colour, front=True, depth=70.0):
    """A round lamp: a dark recess, a chrome rim and the lens, all
    along the face's own normal."""
    z = steep_z(car, x, z, 2 * r, front, fallback=True)
    if z is None:
        return
    y, slope = _normal(car, x, z, 2 * r, front)
    if y is None:
        return
    sign = 1.0 if front else -1.0
    ny, nz = -sign, -sign * slope        # out of the bodywork
    n = math.hypot(ny, nz)
    ny, nz = ny / n, nz / n

    def at(d):
        return (x, y + ny * d, z + nz * d)
    kit.path([at(0.0), at(-depth)], r, DARK, "Matte", sides=20)
    # a round lamp STANDS OUT of its wing — buried in the panel it
    # reads as a slit, which is what the 911's did
    kit.path([at(-6.0), at(PROUD * 1.1)], r + 14, CHROME, "Metal",
             sides=24)
    kit.path([at(PROUD * 0.5), at(PROUD * 1.9)], r, colour, "Emissive",
             sides=24)


def _panel(kit, car, x, z, w, h, colour, material="Plastic", front=True,
           proud=PROUD, rake=0.0, depth=26.0):
    """A rectangular lamp, plate or grille panel laid ON the bodywork,
    raked to the slope of the panel it sits on."""
    z = steep_z(car, x, z, h, front)
    if z is None:
        return
    y, slope = _normal(car, x, z, h, front)
    if y is None:
        return
    slope = max(-1.0, min(1.0, slope))   # never rake so far that a
    sign = 1.0 if front else -1.0        # corner reaches past the nose
    ny, nz = -sign, -sign * slope
    n = math.hypot(ny, nz)
    ny, nz = ny / n, nz / n
    ca, sa = math.cos(math.radians(rake)), math.sin(math.radians(rake))
    pts = []
    for dx, dv in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2),
                   (-w / 2, h / 2)):
        px = x + dx * ca - dv * sa * 0.0
        # the panel runs up the face: +dv along the surface, not up z
        pz = z + dv * abs(ny) + dx * sa
        py = y + slope * dv * abs(ny) + dv * 0.0
        for d in (proud, proud - depth):
            pts.append((px, py + ny * d, pz + nz * d))
    kit.solid(pts, colour, material)


def _slats(kit, car, x, z, w, h, n, vertical, front=True):
    """Chrome bars across a dark grille recess."""
    _panel(kit, car, x, z, w, h, DARK, "Matte", front, proud=PROUD * 0.3,
           depth=40)
    for i in range(n):
        t = (i + 0.5) / n - 0.5
        if vertical:
            _panel(kit, car, x + t * w, z, w / n * 0.35, h * 0.92, CHROME,
                   "Metal", front, proud=PROUD * 0.8, depth=18)
        else:
            _panel(kit, car, x, z + t * h, w * 0.94, h / n * 0.35, CHROME,
                   "Metal", front, proud=PROUD * 0.8, depth=18)


def number_plate(kit, car, z, front=True):
    """A white plate with its dark border, narrowed to a square plate
    where the nose has no room for a European one."""
    a = car.half_width(0.03 if front else 0.97)
    w, h = PLATE_W, PLATE_H
    if w > 1.5 * a:                       # a narrow prow: a square plate
        w, h = 320.0, 160.0
    _panel(kit, car, 0.0, z, w + 24, h + 24, PLATE_INK, "Matte", front,
           proud=PROUD * 0.6, depth=20)
    _panel(kit, car, 0.0, z, w, h, PLATE, "Matte", front, depth=16)


# ------------------------------------------------------------- the face

def face(car, s):
    """(half width, floor z, top z) of the body where a face's details
    go — every piece is placed as a fraction of THAT, so nothing lands
    under a low nose or floats over a tall one."""
    a = car.half_width(s)
    zb = car.bottom(s)
    zt = car.body_top_at(s, 0.0)
    return a, zb, max(zt, zb + 120.0)


def front(kit, car, paint):
    spec = car.spec
    W = car.W
    a, zb, zt = face(car, 0.06)
    span = zt - zb
    z_lamp = zb + 0.66 * span
    if getattr(car, "measured", None):
        # a drawn nose has real wings: the lamps sit up on their crowns,
        # not halfway down a guessed face
        a2, zb2, zt2 = face(car, 0.11)
        a, z_lamp = max(a, a2), zt2 - 0.14 * (zt2 - zb2)
    z_grille = zb + 0.44 * span
    z_low = zb + 0.17 * span
    kind = spec["lights"]
    for side in (-1, 1):
        if kind == "round":
            r = min(0.09 * W, 0.30 * span, 100.0)
            _lens(kit, car, side * a * 0.58, z_lamp, r, LAMP)
        elif kind == "twin":
            r = min(0.055 * W, 0.20 * span, 72.0)
            for k in (0, 1):
                _lens(kit, car, side * (a * 0.60 - k * 2.3 * r), z_lamp, r,
                      LAMP)
        elif kind == "slim":
            w, h = min(0.26 * W, 0.62 * a), 0.16 * span
            _panel(kit, car, side * a * 0.58, z_lamp, w, h, DARK, "Matte",
                   proud=PROUD * 0.5, depth=30)
            _panel(kit, car, side * a * 0.58, z_lamp, w * 0.9, h * 0.6,
                   LAMP, "Emissive", rake=side * -8.0)
            _panel(kit, car, side * a * 0.62, z_lamp - 0.13 * span,
                   w * 0.45, 0.05 * span, AMBER, "Emissive")
        elif kind == "popup":
            s2 = 0.10
            x = side * car.half_width(s2) * 0.58
            kit.obox(x, car.y(s2), car.top(s2) - 4, 0.19 * W, 0.20 * W, 12,
                     0.0, TRIM, "Matte")
            _panel(kit, car, side * a * 0.52, z_grille, 0.13 * W,
                   0.14 * span, LAMP, "Emissive")
        if kind in ("round", "twin"):
            _panel(kit, car, side * a * 0.86, z_lamp - 0.06 * span,
                   min(0.07 * W, 0.18 * a), 0.09 * span, AMBER, "Emissive")

    _grille(kit, car, a, zb, zt, z_grille)

    # lower intake, splitter and fog lamps
    _panel(kit, car, 0.0, z_low, 1.25 * a, 0.20 * span, DARK, "Matte",
           proud=PROUD * 0.4, depth=45)
    for side in (-1, 1):
        _lens(kit, car, side * a * 0.70, z_low,
              min(0.035 * W, 0.09 * span, 45.0), LAMP, depth=40)
    y0 = car.y(0.0)
    kit.box(-0.86 * a, y0 - 6, car.bottom(0.0) - 6, 0.86 * a, y0 + 120,
            car.bottom(0.0) + 14, TRIM, "Matte")


def _grille(kit, car, a, zb, zt, z_mid):
    kind = car.spec["grille"]
    W, span = car.W, zt - zb
    plate_z = zb + 0.24 * span
    if kind == "kidney":
        for side in (-1, 1):
            x = side * min(0.055 * W, 0.30 * a)
            w, h = min(0.105 * W, 0.5 * a), 0.30 * span
            _panel(kit, car, x, z_mid, w, h, CHROME, "Metal",
                   proud=PROUD * 0.55, depth=34)
            _slats(kit, car, x, z_mid, w * 0.84, h * 0.86, 6, True)
    elif kind == "star":
        w, h = 1.15 * a, 0.34 * span
        _panel(kit, car, 0.0, z_mid, w + 26, h + 26, CHROME, "Metal",
               proud=PROUD * 0.35, depth=26)
        _slats(kit, car, 0.0, z_mid, w, h, 4, False)
        y = surface_y(car, 0.0, z_mid)
        if y is not None:
            r = min(0.05 * W, 0.16 * span, 72.0)
            kit.path([(0, y - 34, z_mid), (0, y - 6, z_mid)], r, CHROME,
                     "Metal", sides=24)
            for k in range(3):
                ang = math.radians(90 + 120 * k)
                kit.bar((0, y - 40, z_mid),
                        (r * 0.86 * math.cos(ang), y - 40,
                         z_mid + r * 0.86 * math.sin(ang)), 8, TRIM)
    elif kind == "horseshoe":
        w, h = min(0.46 * W, 1.0 * a), 0.42 * span
        _panel(kit, car, 0.0, z_mid, w + 24, h + 24, CHROME, "Metal",
               proud=PROUD * 0.4, depth=34)
        _slats(kit, car, 0.0, z_mid, w, h, 7, False)
    else:                                   # a mid-engined car's mouth
        _slats(kit, car, 0.0, z_mid, 1.1 * a, 0.26 * span, 3, False)
        plate_z = zb + 0.72 * span          # up on the nose, out of it
    number_plate(kit, car, plate_z)


# -------------------------------------------------------------- the tail

def rear(kit, car, paint):
    spec = car.spec
    W = car.W
    a, zb, zt = face(car, 0.94)
    span = zt - zb
    z = zb + 0.62 * span
    kind = spec["tails"]
    if kind == "bar":
        _panel(kit, car, 0.0, z, 1.5 * a, 0.14 * span, DARK, "Matte",
               front=False, proud=PROUD * 0.4, depth=30)
        _panel(kit, car, 0.0, z, 1.45 * a, 0.09 * span, TAIL, "Emissive",
               front=False)
    for side in (-1, 1):
        if kind == "round":
            r = min(0.05 * W, 0.16 * span, 62.0)
            for k2 in (0, 1):
                _lens(kit, car, side * (a * 0.70 - k2 * 2.3 * r), z, r,
                      TAIL, front=False, depth=50)
        elif kind == "slim":
            w, h = min(0.24 * W, 0.6 * a), 0.15 * span
            _panel(kit, car, side * a * 0.60, z, w, h, DARK, "Matte",
                   front=False, proud=PROUD * 0.4, depth=30)
            _panel(kit, car, side * a * 0.60, z, w * 0.9, h * 0.6, TAIL,
                   "Emissive", front=False)
        _panel(kit, car, side * a * 0.28, z - 0.18 * span,
               min(0.08 * W, 0.2 * a), 0.06 * span, LAMP, "Emissive",
               front=False)
    number_plate(kit, car, zb + 0.30 * span, front=False)
    z_low = zb + 0.13 * span
    _panel(kit, car, 0.0, z_low, 1.25 * a, 0.18 * span, DARK, "Matte",
           front=False, proud=PROUD * 0.4, depth=60)
    y1 = car.y(1.0)
    for i2 in range(-2, 3):
        kit.box(i2 * 0.26 * a - 9, y1 - 150, z_low - 0.08 * span,
                i2 * 0.26 * a + 9, y1 - 10, z_low + 0.06 * span, TRIM,
                "Matte")
