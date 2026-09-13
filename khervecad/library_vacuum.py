"""More vacuum hardware for the Part Library: fittings, chambers,
gauges, pumps and manipulators beyond the core flanges of library.py.

Everything reuses library.py's flange geometry — the revolved knife-
edge CF profile, the KF clamp head, the bolt-circle loop, the bellows —
so a part here mates with a part there. Single-material parts are left
uncoloured: `library.build_part` makes every Vacuum part stainless
steel (`metallic`). A part of several materials (a viewport's glass, an
RGA's painted electronics) is a union of OBJECTS, one per material, so
each still gets its own exact OpenSCAD render with its bolt holes cut.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .library import (_CF_FIELDS, _KF_FIELDS, _PORTS, CF_SIZES,
                      KF_SIZES, _bolt_holes, _cyl, _horiz_cyl,
                      _kf_flange_head, _kf_flange_solid, _kf_port,
                      bellows, cf_fitting, cf_flange, cf_flange_solid,
                      fitting_reach, kf_fitting)
from .model import CadNode

CATEGORY = "Vacuum"
STEEL = "#b9bfc7"
GLASS = "#cfe9f2"
PAINT_DARK = "#2f3237"
PAINT_BODY = "#8a9099"


# ── small builders ──────────────────────────────────────────────────

def _move(node, x=0.0, y=0.0, z=0.0, name="Place"):
    t = CadNode("translate", name, dict(x=float(x), y=float(y), z=float(z)))
    t.add(node)
    return t


def _turn(node, x=0.0, y=0.0, z=0.0, name="Turn"):
    r = CadNode("rotate", name, dict(x=float(x), y=float(y), z=float(z)))
    r.add(node)
    return r


def _group(kind, name, *kids):
    g = CadNode(kind, name)
    for kid in kids:
        g.add(kid)
    return g


def _union(name, *kids):
    return _group("union", name, *kids)


def _cube(name, w, d, h, x=None, y=None, z=0.0):
    """A box, centred on the Z axis unless *x*/*y* place its corner."""
    return CadNode("cube", name, dict(
        x=-w / 2.0 if x is None else float(x),
        y=-d / 2.0 if y is None else float(y), z=float(z),
        width=float(w), depth=float(d), height=float(h), center=False))


def _ring(name, r_in, r_out, height, z=0.0, segments=96):
    """A hollow cylinder as a revolved rectangle — no boolean."""
    rev = CadNode("rotate_extrude", name, dict(angle=360.0,
                                              segments=segments))
    rev.add(CadNode("polygon", f"{name} section", dict(
        x=0.0, y=0.0, points=[[round(r_in, 3), 0.0],
                              [round(r_out, 3), 0.0],
                              [round(r_out, 3), round(height, 3)],
                              [round(r_in, 3), round(height, 3)]])))
    return _move(rev, z=z, name=f"{name} height") if z else rev


def _torus(name, radius, section, z=0.0, segments=64):
    rev = CadNode("rotate_extrude", name, dict(angle=360.0,
                                              segments=segments))
    rev.add(CadNode("circle", f"{name} section", dict(
        x=float(radius), y=0.0, radius=float(section))))
    return _move(rev, z=z, name=f"{name} height") if z else rev


def _face_down(node, t, name="Face down"):
    """A flange solid (sealing face at z = t) turned over so its face
    looks down at z = 0 and its body fills 0..t."""
    return _move(_turn(node, x=180.0, name=name), z=t,
                 name=f"{name} height")


def _paint(node, colour, material="Metal", name=None, alpha=1.0):
    c = CadNode("color", name or "Colour", dict(
        color=colour, alpha=float(alpha), material=material))
    c.add(node)
    return c


def _object(name, *kids):
    """One material of a multi-material part, as its own Object — so it
    gets an exact render of its own (a colourless STL can only wear one
    colour)."""
    comp = CadNode("component", name, dict(
        x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0, color="", alpha=1.0))
    for kid in kids:
        comp.add(kid)
    return comp


def _around(count, radius, make, start=0.0):
    """*make(i)* placed *count* times round a circle of *radius*."""
    out = []
    for i in range(count):
        a = math.radians(start + 360.0 * i / count)
        out.append(_move(make(i), radius * math.cos(a),
                         radius * math.sin(a)))
    return out


def _cf(dims, default="CF40 (DN40)"):
    """CF dimensions from the dialog (numbers only), filled from a
    standard size, and the port length if given."""
    p = dict(CF_SIZES[default])
    for key, value in dims.items():
        if not str(key).startswith("_"):
            p[key] = value
    length = p.pop("port_length", None)
    return p, (float(length) if length not in (None, "") else None)


def _kf_dims(dims, default):
    p = dict(KF_SIZES[default])
    for key, value in dims.items():
        if not str(key).startswith("_"):
            p[key] = value
    length = p.pop("port_length", None)
    return p, (float(length) if length not in (None, "") else None)


def _entry(table, dims, default):
    """A size-table row for the size chosen (`_size`), with any number
    the dialog edited laid over it."""
    row = dict(table.get(str(dims.get("_size") or ""), table[default]))
    for key, value in dims.items():
        if not str(key).startswith("_"):
            row[key] = value
    return row


reach = fitting_reach


# ── CF fittings ─────────────────────────────────────────────────────

def build_cross6(dims):
    p, length = _cf(dims)
    return cf_fitting(p, ["+X", "-X", "+Y", "-Y", "+Z", "-Z"],
                      "CF 6-way cross", reach(p, length))


def build_cross5(dims):
    p, length = _cf(dims)
    return cf_fitting(p, ["+X", "-X", "+Y", "-Y", "+Z"], "CF 5-way cross",
                      reach(p, length))


def build_cube(dims):
    """A CF cube: a solid block with a CF sealing face machined in each
    of its six sides — recess and tapped bolt holes — bored through."""
    p, _length = _cf(dims)
    t = p["thickness"]
    side = p["flange_od"] + 10.0
    h = side / 2.0
    part = CadNode("difference", "CF cube")
    part.add(_cube("Block", side, side, side, z=-h))
    for axis, rot in (("X", (0.0, 90.0, 0.0)), ("Y", (-90.0, 0.0, 0.0)),
                      ("Z", (0.0, 0.0, 0.0))):
        part.add(_turn(_cyl("Bore", p["bore"] / 2.0, side + 2.0,
                            z=-h - 1.0), *rot, name=f"Bore {axis}"))
    for port in ("+X", "-X", "+Y", "-Y", "+Z", "-Z"):
        rx, ry, rz = _PORTS[port]
        face = CadNode("rotate", f"Face {port}", dict(x=rx, y=ry, z=rz))
        face.add(_cyl("Gasket recess", p["gasket_od"] / 2.0 + 0.3, 2.6,
                      z=h - 1.6))
        face.add(_bolt_holes(p, z=h - t * 0.9, height=t * 0.9 + 1.0))
        part.add(face)
    return part


REDUCERS = {"CF40 → CF16": ("CF40 (DN40)", "CF16 (DN16)"),
            "CF63 → CF40": ("CF63 (DN63)", "CF40 (DN40)"),
            "CF100 → CF63": ("CF100 (DN100)", "CF63 (DN63)"),
            "CF160 → CF100": ("CF160 (DN160)", "CF100 (DN100)")}


def _pair(table, dims, default):
    a, b = table.get(str(dims.get("_size") or ""), table[default])
    return a, b


def build_zero_reducer(dims):
    """A zero-length reducer: the large bolt pattern on one face, a
    small knife-edge face with tapped holes on the other."""
    a, b = _pair(REDUCERS, dims, "CF63 → CF40")
    big, small = dict(CF_SIZES[a]), dict(CF_SIZES[b])
    tb, ts = big["thickness"], small["thickness"]
    body = _union("Reducer body",
                  _face_down(cf_flange_solid(dict(big, bore=0.0), 0.0,
                                             "Large face"), tb),
                  _move(cf_flange_solid(dict(small, bore=0.0), 0.0,
                                        "Small face"), z=tb))
    return _group("difference", "CF zero-length reducer", body,
                  _cyl("Bore", small["bore"] / 2.0, tb + ts + 2.0, z=-1.0),
                  _bolt_holes(big, z=-1.0, height=tb + 2.0),
                  _bolt_holes(small, z=tb, height=ts + 1.0))


def build_conical(dims):
    """A conical reducer nipple: large flange, a cone, small flange."""
    a, b = _pair(REDUCERS, dims, "CF63 → CF40")
    big, small = dict(CF_SIZES[a]), dict(CF_SIZES[b])
    tb, ts = big["thickness"], small["thickness"]
    length = float(dims.get("length") or tb + ts + 70.0)
    cone = max(length - tb - ts, 5.0)
    body = _union(
        "Reducer body",
        _face_down(cf_flange_solid(dict(big, bore=0.0), 0.0, "Large flange"),
                   tb),
        _cyl("Cone", big["tube_od"] / 2.0, cone, z=tb,
             r2=small["tube_od"] / 2.0),
        _move(cf_flange_solid(dict(small, bore=0.0), 0.0, "Small flange"),
              z=tb + cone))
    return _group(
        "difference", "CF conical reducer", body,
        _cyl("Large bore", big["bore"] / 2.0, tb + 1.1, z=-1.0),
        _cyl("Cone bore", big["bore"] / 2.0, cone, z=tb,
             r2=small["bore"] / 2.0),
        _cyl("Small bore", small["bore"] / 2.0, ts + 1.5, z=tb + cone - 0.5),
        _bolt_holes(big, z=-1.0, height=tb + 2.0),
        _bolt_holes(small, z=tb + cone - 1.0, height=ts + 2.0))


def build_viewport(dims):
    """A viewport: a mounting flange, a short tube and a sealed glass
    window at its end."""
    p, _length = _cf(dims)
    t = p["thickness"]
    rb, rt = p["bore"] / 2.0, p["tube_od"] / 2.0
    top = t + max(12.0, p["tube_od"] * 0.35)
    metal = _group(
        "difference", "Viewport body",
        _union("Body",
               _face_down(cf_flange_solid(p, 0.0, "Mount flange"), t),
               _ring("Window tube", rb, rt, top - t, z=t),
               _ring("Window seat", rb * 0.86, rt + 2.0, 4.0, z=top - 4.0)),
        _bolt_holes(p, z=-1.0, height=t + 2.0))
    glass = _cyl("Window", rb * 0.93, 3.0, z=top - 6.0)
    return _union("CF viewport",
                  _object("Viewport body", _paint(metal, STEEL)),
                  _object("Window glass",
                          _paint(glass, GLASS, "Glass", alpha=0.45)))


def build_bellows_nipple(dims):
    """A flexible edge-welded bellows between two CF flanges."""
    p, length = _cf(dims)
    t = p["thickness"]
    length = length or max(90.0, p["tube_od"] * 1.8 + 2 * t)
    rb, rt = p["bore"] / 2.0, p["tube_od"] / 2.0
    span = max(length - 2 * t - 8.0, 10.0)
    return _union(
        "CF flexible bellows",
        _face_down(cf_flange(p, "Bottom flange"), t),
        _ring("Cuff", rb, rt, 4.0, z=t),
        _move(bellows(rb, (rt - rb) + rt * 0.18, span,
                      max(int(span / 3.2), 4)), z=t + 4.0),
        _ring("Cuff", rb, rt, 4.0, z=t + 4.0 + span),
        _move(cf_flange(p, "Top flange"), z=length - t))


ADAPTERS = {"CF16 → KF16": ("CF16 (DN16)", "KF16 (DN16)"),
            "CF40 → KF25": ("CF40 (DN40)", "KF25 (DN25)"),
            "CF40 → KF40": ("CF40 (DN40)", "KF40 (DN40)"),
            "CF63 → KF50": ("CF63 (DN63)", "KF50 (DN50)")}


def build_cf_kf(dims):
    """A CF to KF adapter: CF flange, tube, KF clamp head."""
    a, b = _pair(ADAPTERS, dims, "CF40 → KF25")
    cf, kf = dict(CF_SIZES[a]), dict(KF_SIZES[b])
    tc, tk = cf["thickness"], kf["thickness"]
    length = float(dims.get("length") or tc + tk + 35.0)
    r = min(cf["tube_od"], kf["tube_od"]) / 2.0
    bore = min(cf["bore"], kf["bore"]) / 2.0
    body = _union("Adapter body",
                  _face_down(cf_flange_solid(dict(cf, bore=0.0), 0.0,
                                             "CF flange"), tc),
                  _cyl("Tube", r, length - tc - tk + 0.2, z=tc - 0.1),
                  _move(_kf_flange_head(kf, "KF flange"), z=length - tk))
    return _group("difference", "CF–KF adapter", body,
                  _cyl("Bore", bore, length + 2.0, z=-1.0),
                  _bolt_holes(cf, z=-1.0, height=tc + 2.0))


# ── chambers ────────────────────────────────────────────────────────

def _port_parts(p, rot, start, length, at=(0.0, 0.0, 0.0), name="Port"):
    """(solid, bore, bolts) of a CF port whose axis is where rotate(*rot*)
    turns +Z: the tube from *start* (mm from the origin along it) to the
    flange, the flange face at *length*; the bore reaches back through a
    chamber wall."""
    t = p["thickness"]

    def framed(node, label):
        rotated = _turn(node, *rot, name=f"{name} {label}")
        return _move(rotated, *at, name=f"{name} place") if any(at) \
            else rotated
    solid = _union("Port", _cyl("Tube", p["tube_od"] / 2.0,
                                max(length - t - start, 0.5) + 0.1, z=start),
                   _move(cf_flange_solid(p, 0.0, "Flange"), z=length - t))
    bore = _cyl("Bore", p["bore"] / 2.0, length - start + 12.0,
                z=start - 10.0)
    bolts = _bolt_holes(p, z=length - t - 1.0, height=t + 2.0)
    return framed(solid, "tube"), framed(bore, "bore"), framed(bolts, "bolts")


def _ported(name, solids, cuts, ports):
    part = CadNode("difference", name)
    body = _union(f"{name} body", *solids)
    part.add(body)
    for port in ports:
        solid, bore, bolts = _port_parts(*port)
        body.add(solid)
        part.add(bore)
        part.add(bolts)
    for cut in cuts:
        part.add(cut)
    return part


SPHERE_SIZES = {
    "Ø300 (CF160 top)": dict(radius=150.0, wall=4.0, top="CF160 (DN160)",
                             side="CF63 (DN63)", small="CF40 (DN40)"),
    "Ø200 (CF100 top)": dict(radius=100.0, wall=3.0, top="CF100 (DN100)",
                             side="CF40 (DN40)", small="CF16 (DN16)"),
}


def build_sphere_chamber(dims):
    """A spherical UHV chamber: a thin shell with a large port on top, one
    below, four on the equator, four looking down at the centre from
    55° and two from below — every one aimed at the sample position —
    on a three-legged stand."""
    e = _entry(SPHERE_SIZES, dims, "Ø300 (CF160 top)")
    R, w = float(e["radius"]), float(e["wall"])
    top, side, small = (dict(CF_SIZES[e[k]]) for k in ("top", "side",
                                                        "small"))
    n = 64
    outer = [(R * math.sin(math.pi * i / n), R * math.cos(math.pi * i / n))
             for i in range(n + 1)]
    inner = [((R - w) * math.sin(math.pi * i / n),
              (R - w) * math.cos(math.pi * i / n)) for i in range(n, -1, -1)]
    shell = CadNode("rotate_extrude", "Sphere shell", dict(angle=360.0,
                                                          segments=128))
    shell.add(CadNode("polygon", "Shell section", dict(
        x=0.0, y=0.0, points=[[round(max(r, 0.0), 3), round(z, 3)]
                              for r, z in outer + inner])))
    start = R - w - 1.0
    ports = [(top, (0.0, 0.0, 0.0), start, R + 70.0),
             (side, (180.0, 0.0, 0.0), start, R + 55.0)]
    ports += [(side, (0.0, 90.0, 90.0 * k), start, R + 60.0)
              for k in range(4)]
    ports += [(small, (0.0, 55.0, 45.0 + 90.0 * k), start, R + 60.0)
              for k in range(4)]
    ports += [(small, (0.0, 125.0, 45.0 + 180.0 * k), start, R + 55.0)
              for k in range(2)]
    legs = []
    lr = R * 0.55
    leg_top = -math.sqrt(R * R - lr * lr) + w * 0.5
    foot = -R * 1.45
    for k in range(3):
        a = math.radians(30.0 + 120.0 * k)
        x, y = lr * math.cos(a), lr * math.sin(a)
        legs.append(_cyl("Leg", R * 0.045, leg_top - foot, x=x, y=y, z=foot,
                         segments=32))
        legs.append(_cyl("Foot", R * 0.09, 6.0, x=x, y=y, z=foot,
                         segments=32))
    legs.append(_ring("Leg brace", lr - R * 0.05, lr + R * 0.05, R * 0.05,
                      z=foot + R * 0.3))
    return _ported("Spherical chamber", [shell] + legs, [], ports)


CYL_SIZES = {
    "Ø152 × 300 (CF160 ends)": dict(main="CF160 (DN160)", height=300.0,
                                     side="CF63 (DN63)", small="CF40 (DN40)"),
    "Ø102 × 220 (CF100 ends)": dict(main="CF100 (DN100)", height=220.0,
                                     side="CF40 (DN40)", small="CF16 (DN16)"),
}


def build_cylinder_chamber(dims):
    """A cylindrical chamber: a tube with CF flanges at both ends, four
    side ports round its middle and smaller ones above and below."""
    e = _entry(CYL_SIZES, dims, "Ø152 × 300 (CF160 ends)")
    m, side, small = (dict(CF_SIZES[e[k]]) for k in ("main", "side",
                                                      "small"))
    H = float(e["height"])
    t = m["thickness"]
    rt, rb = m["tube_od"] / 2.0, m["bore"] / 2.0
    solids = [_cyl("Chamber wall", rt, H - 2 * t + 0.2, z=-H / 2 + t - 0.1),
              _move(cf_flange_solid(m, 0.0, "Top flange"), z=H / 2 - t),
              _move(_face_down(cf_flange_solid(m, 0.0, "Bottom flange"), t),
                    z=-H / 2)]
    cuts = [_cyl("Chamber bore", rb, H + 2.0, z=-H / 2 - 1.0),
            _bolt_holes(m, z=H / 2 - t - 1.0, height=t + 2.0),
            _bolt_holes(m, z=-H / 2 - 1.0, height=t + 2.0)]
    ports = [(side, (0.0, 90.0, 90.0 * k), rb, rt + 70.0) for k in range(4)]
    ports += [(small, (0.0, 90.0, 45.0 + 180.0 * k), rb, rt + 55.0,
               (0.0, 0.0, H * 0.28)) for k in range(2)]
    ports += [(small, (0.0, 90.0, 135.0), rb, rt + 55.0,
               (0.0, 0.0, -H * 0.28))]
    return _ported("Cylindrical chamber", solids, cuts, ports)


# ── gauges and analysers ────────────────────────────────────────────

ION_SIZES = {"Nude, CF40 (UHV24 style)": dict(mount="CF40 (DN40)",
                                               grid_r=11.0, height=48.0),
             "Nude mini, CF16": dict(mount="CF16 (DN16)", grid_r=5.5,
                                     height=30.0)}


def build_ion_gauge(dims):
    """A nude Bayard–Alpert ion gauge: on the vacuum side of a blank CF
    flange, a helical grid on four posts round a fine collector, with the
    filament beside it; on the air side the feedthrough and connector."""
    e = _entry(ION_SIZES, dims, "Nude, CF40 (UHV24 style)")
    p = dict(CF_SIZES[e["mount"]])
    t, gr, H = p["thickness"], float(e["grid_r"]), float(e["height"])
    parts = [_face_down(cf_flange(dict(p, bore=0.0), "Mount flange"), t)]
    parts += _around(4, gr + 1.4, lambda i: _cyl("Grid post", 0.7, H,
                                                 z=-H, segments=12), 45.0)
    turns = H * 0.78 / 2.2
    helix = CadNode("linear_extrude", "Grid helix", dict(
        height=round(H * 0.78, 3), twist=round(-360.0 * turns, 2), scale=1.0,
        center=False, segments=int(turns * 24)))
    helix.add(CadNode("circle", "Grid wire", dict(x=gr, y=0.0, radius=0.35)))
    parts.append(_move(helix, z=-H * 0.88))
    for z in (-H * 0.88, -H * 0.1):
        parts.append(_torus("Grid ring", gr, 0.5, z=z))
    parts.append(_cyl("Collector", 0.25, H * 0.95, z=-H * 0.95, segments=12))
    parts.append(_cyl("Filament", 0.3, H * 0.6, x=gr + 4.0, z=-H * 0.7,
                      segments=12))
    parts.append(_cyl("Feedthrough", p["bore"] * 0.32, 6.0, z=t,
                      segments=48))
    parts += _around(5, p["bore"] * 0.18, lambda i: _cyl(
        "Pin", 0.5, 12.0, z=t + 6.0, segments=12))
    parts.append(_ring("Connector shroud", p["bore"] * 0.34,
                       p["bore"] * 0.42, 14.0, z=t + 6.0))
    return _union("Ion gauge (nude)", *parts)


def build_pirani(dims):
    """An active Pirani gauge: KF port, neck, a painted electronics
    housing with a status light, and the cable connector."""
    k, _length = _kf_dims(dims, "KF16 (DN16)")
    t = k["thickness"]
    base = t + 21.0
    return _union(
        "Active Pirani gauge",
        _paint(_union("Port",
                      _face_down(_kf_flange_head(k, "KF flange"), t),
                      _cyl("Neck", k["tube_od"] / 2.0, 16.0, z=t),
                      _cyl("Collar", 13.0, 5.0, z=t + 16.0, segments=48)),
               STEEL, name="Steel"),
        _paint(_cyl("Housing", 17.0, 50.0, z=base, segments=64),
               "#34495e", "Plastic", name="Housing"),
        _paint(_cyl("Cap", 15.5, 4.0, z=base + 50.0, segments=64),
               "#1c1f24", "Plastic", name="Cap"),
        _paint(_cyl("M12 connector", 6.0, 11.0, z=base + 54.0, segments=24),
               STEEL, name="Connector"),
        _paint(_move(_turn(_cyl("Status light", 2.2, 2.0, segments=16),
                           y=90.0), x=16.6, z=base + 40.0),
               "#39d353", "Emissive", name="Status light"))


def build_manometer(dims):
    """A capacitance manometer (Baratron style): KF port and neck under
    a brushed sensor can, a black cap and the electronics connector."""
    k, _length = _kf_dims(dims, "KF16 (DN16)")
    t = k["thickness"]
    can = t + 24.0
    return _union(
        "Capacitance manometer",
        _paint(_union("Port",
                      _face_down(_kf_flange_head(k, "KF flange"), t),
                      _cyl("Neck", k["tube_od"] / 2.0, 24.0, z=t),
                      _cyl("Sensor can", 34.0, 70.0, z=can, segments=96)),
               STEEL, name="Steel"),
        _paint(_union("Top",
                      _cyl("Cap", 33.0, 10.0, z=can + 70.0, segments=96),
                      _cube("Connector box", 30.0, 20.0, 14.0,
                            z=can + 80.0)),
               "#1c1f24", "Plastic", name="Cap"),
        _paint(_cyl("Zero adjust", 3.0, 4.0, x=10.0, z=can + 94.0,
                    segments=16), "#d9a441", "Plastic", name="Zero adjust"))


RGA_SIZES = {"100 amu, CF40": dict(mount="CF40 (DN40)", probe=150.0),
             "200 amu, CF63": dict(mount="CF63 (DN63)", probe=200.0)}


def build_rga(dims):
    """A quadrupole residual gas analyser: the probe down into the
    chamber with its ionizer cage at the tip, and the electronics box
    on the air side."""
    e = _entry(RGA_SIZES, dims, "100 amu, CF40")
    p = dict(CF_SIZES[e["mount"]])
    t, L = p["thickness"], float(e["probe"])
    rp = p["bore"] * 0.38
    cage = [_torus("Ionizer ring", rp * 0.9, 0.6, z=-L - dz)
            for dz in (3.0, 11.0, 19.0)]
    cage += _around(4, rp * 0.9, lambda i: _cyl(
        "Cage rod", 0.6, 22.0, z=-L - 22.0, segments=12))
    head = _union("Head",
                  _face_down(cf_flange(dict(p, bore=0.0), "Mount flange"), t),
                  _cyl("Probe", rp, L, z=-L, segments=48), *cage,
                  _cyl("Neck", p["bore"] * 0.45, 18.0, z=t, segments=48))
    box_z = t + 18.0
    return _union(
        "Residual gas analyser (RGA)",
        _object("RGA head", _paint(head, STEEL, name="Steel")),
        _object("RGA electronics",
                _paint(_cube("Electronics", 120.0, 75.0, 58.0, z=box_z),
                       PAINT_DARK, "Plastic", name="Case"),
                _paint(_cube("Label", 60.0, 1.0, 22.0, y=37.5,
                             z=box_z + 18.0),
                       "#1a6bb3", "Plastic", name="Label")))


# ── pumps ───────────────────────────────────────────────────────────

IONPUMP_SIZES = {
    "20 l/s (CF40)": dict(port="CF40 (DN40)", width=110.0, depth=70.0,
                          height=130.0),
    "75 l/s (CF63)": dict(port="CF63 (DN63)", width=170.0, depth=100.0,
                          height=200.0),
    "150 l/s (CF100)": dict(port="CF100 (DN100)", width=240.0,
                            depth=140.0, height=280.0),
}


def build_ion_pump(dims):
    """A diode ion pump: the pump body between its two magnet blocks, a
    CF inlet on a short tube, and the HV feedthrough on the side."""
    e = _entry(IONPUMP_SIZES, dims, "75 l/s (CF63)")
    p = dict(CF_SIZES[e["port"]])
    W, D, H = float(e["width"]), float(e["depth"]), float(e["height"])
    t, neck = p["thickness"], 40.0
    body = _union(
        "Pump",
        _cube("Pump body", W, D, H),
        _cube("Magnet", W * 0.85, 14.0, H * 0.8, x=-W * 0.425, y=D / 2.0,
              z=H * 0.1),
        _cube("Magnet", W * 0.85, 14.0, H * 0.8, x=-W * 0.425,
              y=-D / 2.0 - 14.0, z=H * 0.1),
        _cyl("Inlet tube", p["tube_od"] / 2.0, neck, z=H),
        _move(cf_flange_solid(p, 0.0, "Inlet flange"), z=H + neck - t),
        _move(_turn(_cyl("HV feedthrough", 11.0, 45.0, segments=48),
                    y=90.0), x=W / 2.0 - 2.0, z=H * 0.5),
        _move(_turn(_cyl("HV connector", 14.0, 16.0, segments=48),
                    y=90.0), x=W / 2.0 + 43.0, z=H * 0.5))
    return _group("difference", "Ion pump", body,
                  _cyl("Bore", p["bore"] / 2.0, neck + 2.0, z=H - 1.0),
                  _move(_bolt_holes(p, z=-1.0, height=t + 2.0),
                        z=H + neck - t))


def build_tsp(dims):
    """A titanium sublimation pump: three filaments hanging below a blank
    CF flange, the power feedthrough and connector above it."""
    p, _length = _cf(dims)
    t = p["thickness"]
    L = 120.0 if p["flange_od"] > 50 else 70.0
    parts = [_face_down(cf_flange(dict(p, bore=0.0), "Mount flange"), t),
             _cyl("Shield rod", 1.5, L * 0.9, z=-L * 0.9, segments=16)]
    for i in range(3):
        a = math.radians(120.0 * i)
        x, y = 6.0 * math.cos(a), 6.0 * math.sin(a)
        parts.append(_cyl("Filament", 0.9, L - 12.0, x=x, y=y, z=-L,
                          segments=12))
        parts.append(CadNode("sphere", "Filament tip", dict(
            x=x, y=y, z=-L, radius=1.4, segments=16)))
    parts.append(_cyl("Feedthrough", p["bore"] * 0.3, 8.0, z=t,
                      segments=48))
    parts += _around(4, p["bore"] * 0.16, lambda i: _cyl(
        "Pin", 0.8, 14.0, z=t + 8.0, segments=12))
    parts.append(_ring("Connector shroud", p["bore"] * 0.32,
                       p["bore"] * 0.4, 16.0, z=t + 8.0))
    return _union("Titanium sublimation pump", *parts)


def build_diaphragm(dims):
    """A dry diaphragm pump: motor, crankcase, two pump heads, a KF inlet
    and an exhaust silencer on a base plate."""
    inlet = dict(KF_SIZES["KF16 (DN16)"])
    return _union(
        "Diaphragm pump",
        _paint(_cube("Base", 270.0, 140.0, 12.0, x=-140.0), "#5f646c",
               name="Base"),
        _horiz_cyl("Motor", 46.0, 130.0, x=-135.0, z=12.0 + 46.0,
                   color=PAINT_DARK),
        _paint(_cube("Crankcase", 120.0, 92.0, 72.0, x=-5.0, y=-46.0,
                     z=12.0), PAINT_BODY, name="Crankcase"),
        _paint(_union("Pump heads",
                      _cyl("Head", 30.0, 24.0, x=25.0, z=84.0, segments=64),
                      _cyl("Head", 30.0, 24.0, x=85.0, z=84.0,
                           segments=64)), "#2a2d32", name="Heads"),
        _paint(_union("Head covers",
                      _cyl("Cover", 32.0, 6.0, x=25.0, z=108.0, segments=64),
                      _cyl("Cover", 32.0, 6.0, x=85.0, z=108.0,
                           segments=64)), STEEL, name="Covers"),
        _kf_port(inlet, 25.0, 114.0, 22.0, STEEL),
        _paint(_cyl("Silencer", 10.0, 32.0, x=85.0, z=114.0, segments=32),
               "#1c1f24", "Plastic", name="Silencer"))


CRYO_SIZES = {"CF160 (~1200 l/s)": dict(port="CF160 (DN160)", height=240.0),
              "CF100 (~400 l/s)": dict(port="CF100 (DN100)", height=190.0)}


def build_cryopump(dims):
    """A cryopump: CF inlet on the cryostat can, the cold head (with its
    helium couplings) under it, a relief valve on the side."""
    e = _entry(CRYO_SIZES, dims, "CF160 (~1200 l/s)")
    p = dict(CF_SIZES[e["port"]])
    t, H = p["thickness"], float(e["height"])
    R = p["flange_od"] / 2.0 * 0.92
    head_x = R * 0.25
    body = _union(
        "Cryopump",
        _cyl("Cryostat", R, H, z=-H, segments=96),
        _cyl("Neck", p["tube_od"] / 2.0 + 2.0, 1.0, z=-0.5),
        cf_flange_solid(p, 0.0, "Inlet flange"),
        _cyl("Cold head", 45.0, 110.0, x=head_x, z=-H - 110.0, segments=64),
        _cyl("Motor cap", 38.0, 18.0, x=head_x, z=-H - 128.0, segments=64),
        _horiz_cyl("Helium supply", 8.0, 30.0, x=head_x + 44.0,
                   z=-H - 40.0),
        _horiz_cyl("Helium return", 8.0, 30.0, x=head_x + 44.0,
                   z=-H - 75.0),
        _horiz_cyl("Relief valve", 9.0, 22.0, x=R - 2.0, z=-H * 0.35))
    return _group("difference", "Cryopump", body,
                  _cyl("Inlet opening", p["bore"] / 2.0, 42.0, z=-40.0),
                  _bolt_holes(p, z=-1.0, height=t + 2.0))


# ── manipulation ────────────────────────────────────────────────────

LEAK_SIZES = {"CF16 ports": dict(port="CF16 (DN16)"),
              "CF40 ports": dict(port="CF40 (DN40)")}


def build_leak_valve(dims):
    """A variable leak valve: a block body between two CF ports, the
    bonnet and a graduated micrometer knob."""
    e = _entry(LEAK_SIZES, dims, "CF16 ports")
    p = dict(CF_SIZES[e["port"]])
    s = max(46.0, p["flange_od"] * 0.75)
    return cf_fitting(p, ["+X", "-X"], "Leak valve", s * 0.95, extra_solids=[
        _cube("Valve body", s, s * 0.85, s * 0.95, z=-s * 0.475),
        _cyl("Bonnet", s * 0.24, s * 0.55, z=s * 0.475, segments=48),
        _cyl("Scale ring", s * 0.3, 6.0, z=s * 1.03, segments=48),
        _cyl("Micrometer knob", s * 0.34, s * 0.55, z=s * 1.03 + 6.0,
             segments=30),
        _cyl("Knob cap", s * 0.26, 4.0, z=s * 1.58 + 6.0, segments=48)])


WOBBLE_SIZES = {"Reach 200 mm (CF40)": dict(mount="CF40 (DN40)",
                                            reach=200.0),
                "Reach 350 mm (CF63)": dict(mount="CF63 (DN63)",
                                            reach=350.0)}


def build_wobble(dims):
    """A wobble stick: a rod through a ball pivot in the flange, sealed
    by a bellows, with a pincer grip at the tip inside the chamber and a
    handle outside."""
    e = _entry(WOBBLE_SIZES, dims, "Reach 200 mm (CF40)")
    p = dict(CF_SIZES[e["mount"]])
    t, R = p["thickness"], float(e["reach"])
    ball = p["tube_od"] * 0.45
    return _union(
        "Wobble stick",
        _face_down(cf_flange(dict(p, bore=0.0), "Mount flange"), t),
        _cyl("Rod", 3.0, R, z=-R, segments=24),
        _cube("Jaw", 2.5, 8.0, 14.0, x=-5.5, y=-4.0, z=-R - 12.0),
        _cube("Jaw", 2.5, 8.0, 14.0, x=3.0, y=-4.0, z=-R - 12.0),
        CadNode("sphere", "Pivot ball", dict(x=0.0, y=0.0, z=t + ball * 0.6,
                                            radius=ball, segments=64)),
        _move(bellows(5.0, p["tube_od"] * 0.22, 55.0, 14), z=t + ball * 1.4),
        _cyl("Handle", 4.0, 110.0, z=t + ball * 1.4 + 55.0, segments=24),
        CadNode("sphere", "Grip", dict(x=0.0, y=0.0,
                                      z=t + ball * 1.4 + 170.0, radius=11.0,
                                      segments=48)))


TRANSFER_SIZES = {"Travel 300 mm (CF40)": dict(mount="CF40 (DN40)",
                                               travel=300.0),
                  "Travel 600 mm (CF40)": dict(mount="CF40 (DN40)",
                                               travel=600.0)}


def build_transfer_arm(dims):
    """A magnetically coupled transfer arm: a sealed tube off the flange
    with the magnet collar that drives the rod inside, and the fork the
    rod carries into the chamber."""
    e = _entry(TRANSFER_SIZES, dims, "Travel 300 mm (CF40)")
    p = dict(CF_SIZES[e["mount"]])
    t, L = p["thickness"], float(e["travel"]) + 60.0
    tube_r = min(p["tube_od"] / 2.0, 14.0)
    collar_z = t + L * 0.35
    return _union(
        "Magnetic transfer arm",
        _face_down(cf_flange(dict(p, bore=0.0), "Mount flange"), t),
        _cyl("Tube", tube_r, L, z=t, segments=48),
        _cyl("End cap", tube_r + 1.5, 6.0, z=t + L, segments=48),
        _ring("Magnet collar", tube_r + 0.5, tube_r + 11.0, 60.0, z=collar_z),
        _ring("Grip ring", tube_r + 11.0, tube_r + 13.0, 5.0, z=collar_z + 4.0),
        _ring("Grip ring", tube_r + 11.0, tube_r + 13.0, 5.0,
              z=collar_z + 51.0),
        _cyl("Rod", 4.0, 90.0, z=-90.0, segments=24),
        _cube("Fork", 26.0, 3.0, 4.0, z=-94.0),
        _cube("Prong", 3.0, 3.0, 22.0, x=-13.0, y=-1.5, z=-116.0),
        _cube("Prong", 3.0, 3.0, 22.0, x=10.0, y=-1.5, z=-116.0))


LINEAR_SIZES = {"Stroke 50 mm (CF40)": dict(mount="CF40 (DN40)",
                                            stroke=50.0),
                "Stroke 100 mm (CF63)": dict(mount="CF63 (DN63)",
                                             stroke=100.0)}


def build_linear_shift(dims):
    """A bellows-sealed linear shift: the bellows rising off the flange,
    three guide rods carrying the carriage plate, a lead screw and
    handwheel, and the push rod down into the chamber."""
    e = _entry(LINEAR_SIZES, dims, "Stroke 50 mm (CF40)")
    p = dict(CF_SIZES[e["mount"]])
    t, S = p["thickness"], float(e["stroke"])
    fr = p["flange_od"] / 2.0
    top = t + S + 20.0
    parts = [_face_down(cf_flange(p, "Mount flange"), t),
             _move(bellows(p["bore"] * 0.3, p["tube_od"] * 0.2, S + 20.0,
                           max(int((S + 20.0) / 4.0), 6)), z=t),
             _cyl("Carriage", fr * 0.8, 10.0, z=top, segments=64)]
    for i in range(3):
        a = math.radians(30.0 + 120.0 * i)
        parts.append(_cyl("Guide rod", 3.0, S + 32.0, x=fr * 0.64 *
                          math.cos(a), y=fr * 0.64 * math.sin(a), z=t,
                          segments=16))
    parts += [_cyl("Lead screw", 4.0, 40.0, z=top + 10.0, segments=24),
              _cyl("Handwheel", fr * 0.55, 8.0, z=top + 50.0, segments=48),
              _cyl("Handle", 4.0, 20.0, x=fr * 0.45, z=top + 58.0,
                   segments=16),
              _cyl("Push rod", 3.0, S + 40.0, z=-(S + 40.0), segments=24),
              _cyl("Sample plate", 9.0, 2.0, z=-(S + 42.0), segments=32)]
    return _union("Linear shift", *parts)


# ── KF hardware ─────────────────────────────────────────────────────

def build_kf_clamp(dims):
    """A KF clamp: a ring with an inner V that closes two clamp heads
    together, hinged on one side, a wing nut on the other."""
    k, _length = _kf_dims(dims, "KF25 (DN25)")
    t = k["thickness"]
    ri = k["flange_od"] / 2.0 - 1.2
    ro = ri + max(4.0, t)
    hh = t + 1.2
    section = [(ri + 1.8, -hh), (ro, -hh), (ro, hh), (ri + 1.8, hh),
               (ri, hh * 0.35), (ri, -hh * 0.35)]
    ring = CadNode("rotate_extrude", "Clamp ring", dict(angle=320.0,
                                                       segments=96))
    ring.add(CadNode("polygon", "Clamp section", dict(
        x=0.0, y=0.0, points=[[round(r, 3), round(z, 3)]
                              for r, z in section])))
    wing = _union("Wing nut",
                  _turn(_cyl("Bolt", 2.2, 24.0, z=-12.0, segments=16),
                        x=90.0),
                  _move(_turn(_cyl("Nut", 4.2, 6.0, segments=6), x=90.0),
                        y=-9.0),
                  _cube("Wings", 3.0, 3.0, 20.0, x=-1.5, y=-13.0, z=-10.0))
    hinge = _cyl("Hinge pin", 2.6, 2 * hh + 2.0, z=-hh - 1.0, segments=16)
    return _union("KF clamp", ring,
                  _turn(_move(wing, x=ro + 3.0), z=340.0, name="Wing side"),
                  _turn(_move(hinge, x=ro + 1.2), z=160.0,
                        name="Hinge side"))


def build_centering_ring(dims):
    """A KF centering ring with its O-ring."""
    k, _length = _kf_dims(dims, "KF25 (DN25)")
    rb = k["bore"] / 2.0
    metal = _union("Ring", _ring("Centering ring", rb, rb + 2.8, 6.0,
                                 z=-3.0),
                   _ring("Lip", rb + 2.8, rb + 5.0, 1.2, z=-0.6))
    return _union("KF centering ring",
                  _paint(metal, "#d4d7dc", name="Aluminium"),
                  _paint(_torus("O-ring", rb + 5.2, 2.4), "#151515",
                         "Rubber", name="Viton"))


def build_kf_blank(dims):
    k, _length = _kf_dims(dims, "KF25 (DN25)")
    t = k["thickness"]
    return _union("KF blank flange", _kf_flange_solid(k, "Blank"),
                  _cyl("Grip", 5.0, 6.0, z=t, segments=32))


def build_kf_cross(dims):
    k, length = _kf_dims(dims, "KF25 (DN25)")
    return kf_fitting(k, ["+X", "-X", "+Z", "-Z"], "KF cross",
                      length or max(40.0, k["flange_od"] / 2.0 + 12.0))


KF_REDUCERS = {"KF25 → KF16": ("KF25 (DN25)", "KF16 (DN16)"),
               "KF40 → KF25": ("KF40 (DN40)", "KF25 (DN25)"),
               "KF40 → KF16": ("KF40 (DN40)", "KF16 (DN16)"),
               "KF50 → KF40": ("KF50 (DN50)", "KF40 (DN40)")}


def build_kf_reducer(dims):
    a, b = _pair(KF_REDUCERS, dims, "KF40 → KF25")
    big, small = dict(KF_SIZES[a]), dict(KF_SIZES[b])
    tb, ts = big["thickness"], small["thickness"]
    length = float(dims.get("length") or tb + ts + 30.0)
    cone = max(length - tb - ts, 4.0)
    body = _union("Reducer body",
                  _face_down(_kf_flange_head(big, "Large flange"), tb),
                  _cyl("Cone", big["tube_od"] / 2.0, cone, z=tb,
                       r2=small["tube_od"] / 2.0),
                  _move(_kf_flange_head(small, "Small flange"),
                        z=tb + cone))
    return _group("difference", "KF reducer", body,
                  _cyl("Large bore", big["bore"] / 2.0, tb + 1.1, z=-1.0),
                  _cyl("Cone bore", big["bore"] / 2.0, cone, z=tb,
                       r2=small["bore"] / 2.0),
                  _cyl("Small bore", small["bore"] / 2.0, ts + 1.5,
                       z=tb + cone - 0.5))


def build_kf_hose(dims):
    """A flexible KF bellows hose: clamp heads at both ends."""
    k, length = _kf_dims(dims, "KF25 (DN25)")
    t = k["thickness"]
    length = length or 250.0
    rb, rt = k["bore"] / 2.0, k["tube_od"] / 2.0
    span = max(length - 2 * t - 8.0, 10.0)

    def head(z, down):
        solid = _kf_flange_head(k, "Clamp head")
        solid = _face_down(solid, t) if down else solid
        return _move(_group("difference", "Hose end", solid,
                            _cyl("Bore", rb, t + 2.0, z=-1.0)), z=z)
    return _union("KF bellows hose", head(0.0, True),
                  _ring("Cuff", rb, rt, 4.0, z=t),
                  _move(bellows(rb, (rt - rb) + rt * 0.15, span,
                                max(int(span / 3.5), 4)), z=t + 4.0),
                  _ring("Cuff", rb, rt, 4.0, z=t + 4.0 + span),
                  head(length - t, False))


# ── registration ────────────────────────────────────────────────────

def _spec(label, build, sizes, fields=()):
    return dict(label=label, category=CATEGORY, sizes=sizes,
                fields=list(fields), build=build)


def _cf_subset(*names):
    return {n: dict(CF_SIZES[n]) for n in names}


def _named(table, **extra):
    return {name: dict(extra) for name in table}


_CF_ONLY = [f for f in _CF_FIELDS if f[0] != "port_length"]
_KF_ONLY = [f for f in _KF_FIELDS if f[0] != "port_length"]

PARTS = {
    "cf_cross5": _spec("CF 5-way cross", build_cross5, dict(CF_SIZES),
                       _CF_FIELDS),
    "cf_cross6": _spec("CF 6-way cross", build_cross6, dict(CF_SIZES),
                       _CF_FIELDS),
    "cf_cube": _spec("CF cube (6 sealing faces)", build_cube,
                     _cf_subset("CF40 (DN40)", "CF63 (DN63)",
                                "CF100 (DN100)"), _CF_ONLY),
    "cf_reducer_zero": _spec("CF zero-length reducer", build_zero_reducer,
                             _named(REDUCERS)),
    "cf_reducer_conical": _spec("CF conical reducer nipple", build_conical,
                                _named(REDUCERS, length=110.0),
                                [("length", "Length")]),
    "cf_viewport": _spec("CF viewport (glass window)", build_viewport,
                         _cf_subset("CF16 (DN16)", "CF40 (DN40)",
                                    "CF63 (DN63)", "CF100 (DN100)"),
                         _CF_ONLY),
    "cf_bellows": _spec("CF flexible bellows", build_bellows_nipple,
                        _cf_subset("CF16 (DN16)", "CF40 (DN40)",
                                   "CF63 (DN63)", "CF100 (DN100)"),
                        _CF_FIELDS),
    "cf_kf_adapter": _spec("CF → KF adapter", build_cf_kf,
                           _named(ADAPTERS, length=60.0),
                           [("length", "Length")]),
    "chamber_sphere": _spec("Spherical chamber (multi-port)",
                            build_sphere_chamber, SPHERE_SIZES,
                            [("radius", "Radius"), ("wall", "Wall")]),
    "chamber_cylinder": _spec("Cylindrical chamber (with ports)",
                              build_cylinder_chamber, CYL_SIZES,
                              [("height", "Height")]),
    "gauge_ion": _spec("Ion gauge (nude Bayard–Alpert)", build_ion_gauge,
                       ION_SIZES),
    "gauge_pirani": _spec("Active Pirani gauge", build_pirani,
                          {"KF16": dict(KF_SIZES["KF16 (DN16)"]),
                           "KF25": dict(KF_SIZES["KF25 (DN25)"])}),
    "gauge_manometer": _spec("Capacitance manometer", build_manometer,
                             {"KF16": dict(KF_SIZES["KF16 (DN16)"]),
                              "KF25": dict(KF_SIZES["KF25 (DN25)"])}),
    "rga": _spec("Residual gas analyser (quadrupole)", build_rga,
                 RGA_SIZES),
    "pump_ion": _spec("Ion pump (diode)", build_ion_pump, IONPUMP_SIZES),
    "pump_tsp": _spec("Titanium sublimation pump", build_tsp,
                      _cf_subset("CF40 (DN40)", "CF63 (DN63)")),
    "pump_cryo": _spec("Cryopump", build_cryopump, CRYO_SIZES),
    "pump_diaphragm": _spec("Diaphragm pump (dry)", build_diaphragm,
                            {"Standard": {}}),
    "valve_leak": _spec("Leak valve (variable)", build_leak_valve,
                        LEAK_SIZES),
    "wobble_stick": _spec("Wobble stick (pincer grip)", build_wobble,
                          WOBBLE_SIZES),
    "transfer_arm": _spec("Magnetic transfer arm", build_transfer_arm,
                          TRANSFER_SIZES),
    "linear_shift": _spec("Linear shift (bellows)", build_linear_shift,
                          LINEAR_SIZES),
    "kf_clamp": _spec("KF clamp (wing nut)", build_kf_clamp,
                      dict(KF_SIZES), _KF_ONLY),
    "kf_centering_ring": _spec("KF centering ring + O-ring",
                               build_centering_ring, dict(KF_SIZES),
                               _KF_ONLY),
    "kf_blank": _spec("KF blank flange", build_kf_blank, dict(KF_SIZES),
                      _KF_ONLY),
    "kf_cross": _spec("KF cross (4 ports)", build_kf_cross, dict(KF_SIZES),
                      _KF_FIELDS),
    "kf_reducer": _spec("KF reducer", build_kf_reducer,
                        _named(KF_REDUCERS, length=45.0),
                        [("length", "Length")]),
    "kf_hose": _spec("KF bellows hose", build_kf_hose, dict(KF_SIZES),
                     [("port_length", "Hose length")] + _KF_ONLY),
}
