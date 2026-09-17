"""A UHV chamber as data (Qt-free): a body (sphere, cylinder or cube), its
orientation, a mu-metal liner, the bench it stands on and a list of CF or
KF ports. Each port is aimed at a FOCAL POINT on the chamber's axis (the
manipulator axis, chamber z; `focus` mm from the centre, so a tall
chamber can hold a preparation level and an analysis level) from a polar
angle θ (0° = up the axis) and an azimuth φ (0° = +X), and carries an
accessory — a viewport, gauges, a sputter gun, LEED, an analyser, an
X-ray source or monochromator, a manipulator, a transfer arm… — in the
size row `variant`, turned `spin` degrees about the port axis.

`build(spec)` turns it into one assembly: the chamber and everything on
it turned by (rx, ry, rz) about the centre, lifted to `beam_height`
above the floor, on a level bench (`chamber_bench`). `problems(spec)`
finds ports whose tubes or flanges collide, in 3D. `PRESETS` holds a
preparation chamber, an XPS analysis chamber, a two-level chamber and a
load lock. The Chamber Designer (`chamber_dialog`) edits a spec; a spec
is plain JSON.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import copy
import math

from .chamber_bench import KINDS as BENCHES
from .chamber_bench import SEAT, build_bench
from .library import (CF_SIZES, KF_SIZES, _bolt_holes, _cyl,
                      _kf_flange_head, build_part, cf_flange_solid)
from .library_uhv import MU_METAL, mu_metal_liner
from .library_vacuum import (STEEL, _cube, _group, _move, _object, _paint,
                             _turn, _union)
from .model import CadNode

BODIES = ("sphere", "cylinder", "cube")
FLANGES = list(CF_SIZES) + list(KF_SIZES)

#: accessory key -> (label, part id or None, flange family)
ACCESSORIES = {
    "open": ("Open port", None, "any"),
    "blank": ("Blank flange", "blank", "any"),
    "viewport": ("Viewport", "cf_viewport", "CF"),
    "ion_gauge": ("Ion gauge (nude)", "gauge_ion", "CF"),
    "gauge_head": ("Ion gauge head (nipple)", "gauge_head", "CF"),
    "rga": ("RGA (quadrupole)", "rga_detailed", "CF"),
    "sputter_gun": ("Sputter ion gun", "sputter_gun", "CF"),
    "evaporator": ("e-beam evaporator", "evaporator", "CF"),
    "leed": ("LEED optics", "leed", "CF"),
    "analyser": ("Hemispherical analyser", "analyser_lens", "CF"),
    "xray": ("X-ray source, twin anode", "xray_twin", "CF"),
    "mono": ("X-ray monochromator", "xray_mono", "CF"),
    "manipulator": ("Manipulator: Omniax style", "manip_omniax", "CF"),
    "manipulator_cryo": ("Manipulator: Omniax style + LN2", "manip_omniax",
                         "CF"),
    "manipulator_transax": ("Manipulator: Transax style", "manip_transax",
                            "CF"),
    "manipulator_hpt": ("Manipulator: HPT style", "manip_hpt", "CF"),
    "manipulator_uhvd": ("Manipulator: UHV Design style XYZT", "manip_uhvd",
                         "CF"),
    "transfer_flag": ("Transfer arm (flag fork)", "transfer_arm_detailed",
                      "CF"),
    "transfer_pts": ("Transfer arm (PTS bayonet)", "transfer_arm_detailed",
                     "CF"),
    "carousel": ("Sample carousel", "sample_carousel", "CF"),
    "wobble": ("Wobble stick", "wobble_stick", "CF"),
    "door": ("Fast-entry door", "fast_entry", "CF"),
    "kf_blank": ("KF blank", "kf_blank", "KF"),
    "pirani": ("Pirani gauge", "gauge_pirani", "KF"),
}

#: which size row a port starts from, per accessory (else the first)
_SIZE_ROW = {
    "manipulator": "Omniax style Z100, CF100 base, flag head",
    "manipulator_cryo": "Omniax style Z300, CF100 base, LN2 flag head",
    "transfer_flag": "Travel 600 mm, flag fork, port aligner (CF40)",
    "transfer_pts": "Travel 600 mm, PTS bayonet, port aligner (CF63)",
}

#: a tool that must not reach the sample stops this short of it (mm)
_STANDOFF = {"wobble": 30.0, "rga": 60.0}


def family(flange: str) -> str:
    return "KF" if str(flange) in KF_SIZES else "CF"


def flange_row(flange: str) -> dict:
    return dict(KF_SIZES.get(flange) or CF_SIZES[flange])


def port(name, flange, theta, phi, length, accessory="blank", focus=0.0,
         spin=0.0, variant=""):
    return dict(name=name, flange=flange, theta=float(theta),
                phi=float(phi), length=float(length), accessory=accessory,
                focus=float(focus), spin=float(spin), variant=variant)


def new_spec(name="UHV chamber", body="sphere", radius=150.0):
    return dict(name=name, body=body, radius=float(radius), height=300.0,
                wall=4.0, liner=False, liner_gap=10.0, liner_thickness=1.5,
                rx=0.0, ry=0.0, rz=0.0, beam_height=1100.0, bench="frame",
                bench_width=0.0, bench_depth=0.0, ports=[])


def variants(accessory) -> list:
    """The size rows a port's accessory can be built in."""
    from .library import PARTS
    pid = ACCESSORIES.get(accessory, (None, None))[1]
    if pid in (None, "blank", "cf_viewport", "kf_blank", "gauge_pirani"):
        return []
    return list((PARTS.get(pid) or {}).get("sizes") or {})


def normalise(spec: dict) -> dict:
    """*spec* with every key present and sane (a loaded file may be
    missing some, or come from before benches and focal points)."""
    out = new_spec()
    out.update({k: v for k, v in dict(spec).items() if k != "ports"})
    if "bench" not in spec and "stand" in spec:
        out["bench"] = "frame" if spec["stand"] else "none"
    out.pop("stand", None)
    if out["body"] not in BODIES:
        out["body"] = "sphere"
    if out["bench"] not in BENCHES:
        out["bench"] = "frame"
    for key in ("radius", "height", "wall", "liner_gap",
                "liner_thickness"):
        out[key] = max(float(out[key]), 0.5)
    for key in ("rx", "ry", "rz", "beam_height", "bench_width",
                "bench_depth"):
        out[key] = float(out[key])
    out["ports"] = []
    for i, p in enumerate(spec.get("ports") or []):
        q = port(f"Port {i + 1}", "CF40 (DN40)", 90.0, 0.0,
                 out["radius"] + 60.0)
        q.update(p)
        if q["flange"] not in FLANGES:
            q["flange"] = "CF40 (DN40)"
        if q["accessory"] not in ACCESSORIES:
            q["accessory"] = "blank"
        if q["variant"] and q["variant"] not in variants(q["accessory"]):
            q["variant"] = ""
        q["theta"] = min(max(float(q["theta"]), 0.0), 180.0)
        q["phi"] = float(q["phi"]) % 360.0
        q["length"] = max(float(q["length"]), 10.0)
        q["focus"] = float(q["focus"])
        q["spin"] = float(q["spin"]) % 360.0
        out["ports"].append(q)
    return out


# ── port geometry ───────────────────────────────────────────────────

def direction(theta, phi):
    t, f = math.radians(theta), math.radians(phi)
    return (math.sin(t) * math.cos(f), math.sin(t) * math.sin(f),
            math.cos(t))


def half_height(spec) -> float:
    return spec["height"] / 2.0 if spec["body"] == "cylinder" \
        else spec["radius"]


def wall_distance(spec, p) -> float:
    """How far from its focal point a port's axis leaves the body's outer
    surface."""
    R, f = spec["radius"], p.get("focus", 0.0)
    dx, dy, dz = direction(p["theta"], p["phi"])
    if spec["body"] == "sphere":
        b, c = f * dz, f * f - R * R
        return -b + math.sqrt(max(b * b - c, 0.0))
    hits = []
    H = half_height(spec)
    if abs(dz) > 1e-9:
        hits.append(((H if dz > 0 else -H) - f) / dz)
    if spec["body"] == "cylinder":
        radial = math.hypot(dx, dy)
        if radial > 1e-9:
            hits.append(R / radial)
    else:
        hits += [R / abs(c) for c in (dx, dy) if abs(c) > 1e-9]
    hits = [h for h in hits if h > 0]
    return min(hits) if hits else R


def min_length(spec, p) -> float:
    """The shortest port that still clears the body: its flange outside
    the wall with a little tube between."""
    row = flange_row(p["flange"])
    return round(wall_distance(spec, p) + row["thickness"] + 15.0, 1)


def angle_between(a, b) -> float:
    da, db = direction(a["theta"], a["phi"]), direction(b["theta"], b["phi"])
    dot = max(min(sum(x * y for x, y in zip(da, db)), 1.0), -1.0)
    return math.degrees(math.acos(dot))


def half_angle(p) -> float:
    """The half-angle a port's flange subtends from its focal point."""
    row = flange_row(p["flange"])
    inner = max(p["length"] - row["thickness"], 1.0)
    return math.degrees(math.atan2(row["flange_od"] / 2.0, inner))


def _cylinders(spec, p):
    """The port's tube and flange as (origin, axis, s0, s1, radius)."""
    row = flange_row(p["flange"])
    o, d = (0.0, 0.0, p["focus"]), direction(p["theta"], p["phi"])
    L, t = p["length"], row["thickness"]
    w = wall_distance(spec, p)
    return [(o, d, w + 1.0, L - t, row["tube_od"] / 2.0),
            (o, d, L - t, L, row["flange_od"] / 2.0)]


def _basis(d):
    a = (1.0, 0.0, 0.0) if abs(d[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = (d[1] * a[2] - d[2] * a[1], d[2] * a[0] - d[0] * a[2],
         d[0] * a[1] - d[1] * a[0])
    n = math.sqrt(sum(c * c for c in u))
    u = tuple(c / n for c in u)
    v = (d[1] * u[2] - d[2] * u[1], d[2] * u[0] - d[0] * u[2],
         d[0] * u[1] - d[1] * u[0])
    return u, v


def _samples(cyl, step=8.0, around=12):
    o, d, s0, s1, r = cyl
    if s1 <= s0:
        return []
    u, v = _basis(d)
    n = max(int(math.ceil((s1 - s0) / step)), 1)
    pts = []
    for i in range(n + 1):
        s = s0 + (s1 - s0) * i / n
        c = tuple(o[k] + d[k] * s for k in range(3))
        pts.append(c)
        for j in range(around):
            a = 2.0 * math.pi * j / around
            pts.append(tuple(c[k] + r * 0.97 * (math.cos(a) * u[k]
                                                 + math.sin(a) * v[k])
                             for k in range(3)))
    return pts


def _inside(pt, cyl):
    o, d, s0, s1, r = cyl
    w = [pt[k] - o[k] for k in range(3)]
    s = sum(w[k] * d[k] for k in range(3))
    if s < s0 or s > s1:
        return False
    radial = [w[k] - s * d[k] for k in range(3)]
    return sum(c * c for c in radial) < r * r


def _overlap(a, b):
    return (any(_inside(pt, b) for pt in _samples(a))
            or any(_inside(pt, a) for pt in _samples(b)))


def problems(spec) -> list:
    """[(message, {port indices})] for the ports: tubes or flanges that
    collide (checked in 3D, focal points and all), ports too short to
    clear the body, focal points outside it, accessories on the wrong
    flange family."""
    ports = spec["ports"]
    out = []
    cyls = [_cylinders(spec, p) for p in ports]
    inner = half_height(spec) - spec["wall"] - 5.0
    for i, a in enumerate(ports):
        if abs(a["focus"]) > inner:
            out.append((f"{a['name']}: focal point {a['focus']:g} mm is "
                        "outside the chamber", {i}))
        if a["length"] < min_length(spec, a) - 0.05:
            out.append((f"{a['name']}: too short to clear the chamber "
                        f"(at least {min_length(spec, a):g} mm)", {i}))
        fam = ACCESSORIES[a["accessory"]][2]
        if fam != "any" and fam != family(a["flange"]):
            out.append((f"{a['name']}: {ACCESSORIES[a['accessory']][0]} "
                        f"needs a {fam} flange", {i}))
        for j in range(i + 1, len(ports)):
            b = ports[j]
            if angle_between(a, b) > 150.0 and a["focus"] == b["focus"]:
                continue
            hit = [(pa, pb) for pa in range(2) for pb in range(2)
                   if _overlap(cyls[i][pa], cyls[j][pb])]
            if hit:
                what = "flanges" if (1, 1) in hit else "ports"
                out.append((f"{a['name']} and {b['name']} {what} collide",
                            {i, j}))
    return out


def clashes(spec) -> list:
    """The messages of `problems`."""
    return [msg for msg, _ports in problems(spec)]


# ── orientation ─────────────────────────────────────────────────────

def rotation(rx, ry, rz):
    """OpenSCAD's rotate([rx, ry, rz]) as a 3x3 matrix (x, then y, then
    z)."""
    cx, sx = math.cos(math.radians(rx)), math.sin(math.radians(rx))
    cy, sy = math.cos(math.radians(ry)), math.sin(math.radians(ry))
    cz, sz = math.cos(math.radians(rz)), math.sin(math.radians(rz))
    Rx = ((1, 0, 0), (0, cx, -sx), (0, sx, cx))
    Ry = ((cy, 0, sy), (0, 1, 0), (-sy, 0, cy))
    Rz = ((cz, -sz, 0), (sz, cz, 0), (0, 0, 1))

    def mul(A, B):
        return tuple(tuple(sum(A[i][k] * B[k][j] for k in range(3))
                           for j in range(3)) for i in range(3))
    return mul(Rz, mul(Ry, Rx))


def body_extent(spec):
    """(lowest z, widest xy) of the turned body about its centre."""
    R, H = spec["radius"], half_height(spec)
    if spec["body"] == "sphere":
        return -R, R
    M = rotation(spec["rx"], spec["ry"], spec["rz"])
    if spec["body"] == "cylinder":
        pts = [(R * math.cos(a), R * math.sin(a), z)
               for a in (2 * math.pi * k / 36 for k in range(36))
               for z in (-H, H)]
    else:
        pts = [(sx * R, sy * R, sz * R) for sx in (-1, 1) for sy in (-1, 1)
               for sz in (-1, 1)]
    turned = [tuple(sum(M[i][k] * p[k] for k in range(3)) for i in range(3))
              for p in pts]
    return (min(p[2] for p in turned),
            max(max(abs(p[0]), abs(p[1])) for p in turned))


# ── geometry ────────────────────────────────────────────────────────

def _aim(node, p, name):
    """*node* built along +Z, spun about it, turned onto the port axis
    and moved to the port's focal point."""
    if p.get("spin"):
        node = _turn(node, z=p["spin"], name=f"{name} spin")
    aimed = _turn(node, 0.0, float(p["theta"]), float(p["phi"]), name=name)
    return _move(aimed, z=p["focus"], name=f"{name} focus") \
        if p.get("focus") else aimed


def _port_geometry(spec, p):
    """(solid, cut) of one port along +Z: the tube from inside the wall to
    the flange, the flange (sealing face at *length*), the bore and bolt
    holes."""
    row = flange_row(p["flange"])
    L, t = p["length"], row["thickness"]
    start = max(wall_distance(spec, p) - spec["wall"] * 3.0 - 20.0, 0.0)
    tube = max(L - t - start, 0.5) + 0.1
    solid = _union("Port", _cyl("Tube", row["tube_od"] / 2.0, tube,
                                z=start, segments=64))
    cut = _union("Port cut", _cyl("Bore", row["bore"] / 2.0,
                                  L - start + 10.0, z=start - 8.0,
                                  segments=64))
    if family(p["flange"]) == "KF":
        solid.add(_move(_kf_flange_head(row, "KF flange"), z=L - t))
    else:
        solid.add(_move(cf_flange_solid(row, 0.0, "CF flange"), z=L - t))
        cut.add(_bolt_holes(row, z=L - t - 1.0, height=t + 2.0))
    return solid, cut


def _body_solids(spec):
    """(outer solid, inner void) of the chamber body."""
    R, w, H = spec["radius"], spec["wall"], spec["height"]
    if spec["body"] == "sphere":
        return (CadNode("sphere", "Chamber shell", dict(
                    x=0.0, y=0.0, z=0.0, radius=R, segments=128)),
                CadNode("sphere", "Chamber void", dict(
                    x=0.0, y=0.0, z=0.0, radius=R - w, segments=128)))
    if spec["body"] == "cylinder":
        return (_cyl("Chamber wall", R, H, z=-H / 2.0, segments=128),
                _cyl("Chamber void", R - w, H - 2 * w, z=-H / 2.0 + w,
                     segments=128))
    return (_cube("Chamber block", 2 * R, 2 * R, 2 * R, z=-R),
            _cube("Chamber void", 2 * (R - w), 2 * (R - w), 2 * (R - w),
                  z=-R + w))


def accessory_dims(p) -> dict:
    """The dims an accessory is built from on port *p*: its size row (the
    port's variant) with the port's flange as the mount and the port
    length as the reach."""
    from .library import PARTS
    key = p["accessory"]
    pid = ACCESSORIES[key][1]
    row = flange_row(p["flange"])
    if pid in ("cf_viewport", "kf_blank"):
        return dict(row, _size=p["flange"])
    sizes = PARTS[pid].get("sizes") or {}
    size = p.get("variant") if p.get("variant") in sizes else \
        _SIZE_ROW.get(key) if _SIZE_ROW.get(key) in sizes else \
        next(iter(sizes), "")
    dims = dict(sizes.get(size, {}), _size=size)
    if pid == "gauge_pirani":
        return dict(row, _size=size)
    if "mount" in dims:
        dims["mount"] = p["flange"]
    reach = p["length"] - _STANDOFF.get(key, 0.0)
    if "reach" in dims:
        dims["reach"] = reach
    if pid == "rga_detailed":
        dims["probe"] = min(float(dims["probe"]), max(reach - 60.0, 60.0))
    if pid == "transfer_arm_detailed":
        dims["travel"] = max(float(dims.get("travel", 600.0)), reach)
    return dims


def _accessory(p):
    pid = ACCESSORIES[p["accessory"]][1]
    if pid is None:
        return None
    row = flange_row(p["flange"])
    if pid == "blank":
        node = build_part("kf_blank" if family(p["flange"]) == "KF"
                          else "cf_blank", dict(row))
    else:
        node = build_part(pid, accessory_dims(p))
    face = CadNode("translate", f"{p['name']} face",
                   dict(x=0.0, y=0.0, z=float(p["length"])))
    face.add(node)
    return face


def _openings(spec):
    return [(p["theta"], p["phi"], flange_row(p["flange"])["tube_od"] + 4.0,
             p["focus"]) for p in spec["ports"]]


def build(spec) -> CadNode:
    """The whole system: the chamber (ported body, mu-metal liner, one
    Object per accessory) turned and lifted to the beam height, and the
    bench under it."""
    spec = normalise(spec)
    body_solid, void = _body_solids(spec)
    body = CadNode("difference", "Chamber")
    outer = _union("Chamber body", body_solid)
    body.add(outer)
    body.add(void)
    for p in spec["ports"]:
        solid, cut = _port_geometry(spec, p)
        outer.add(_aim(solid, p, p["name"]))
        body.add(_aim(cut, p, f"{p['name']} bore"))
    objects = [_object("Chamber", _paint(body, STEEL))]
    if spec["liner"]:
        r = spec["radius"] - spec["wall"] - spec["liner_gap"]
        if spec["body"] == "sphere":
            liner = mu_metal_liner(r, spec["liner_thickness"],
                                   _openings(spec))
        else:
            liner = _box_liner(spec, r, _openings(spec))
        objects.append(_object("Mu-metal liner", _paint(liner, MU_METAL)))
    for p in spec["ports"]:
        acc = _accessory(p)
        if acc is None:
            continue
        label = ACCESSORIES[p["accessory"]][0].split(": ")[-1]
        objects.append(_object(f"{p['name']}: {label}",
                               _aim(acc, p, p["name"])))
    assembly = _union("Chamber and ports", *objects)
    if spec["rx"] or spec["ry"] or spec["rz"]:
        assembly = _turn(assembly, spec["rx"], spec["ry"], spec["rz"],
                         name="Chamber orientation")
    lifted = _move(assembly, z=spec["beam_height"], name="Beam height")
    parts = [lifted]
    low, wide = body_extent(spec)
    z0 = spec["beam_height"]
    seat = (z0 - spec["radius"] * math.sqrt(1.0 - SEAT * SEAT)
            if spec["body"] == "sphere" else z0 + low)
    bench = build_bench(spec["bench"], z0, z0 + low, wide,
                        spec["bench_width"], spec["bench_depth"], seat)
    if bench is not None:
        parts.append(bench)
    return _union(spec["name"], *parts)


def objects_of(node, depth=2):
    """The Objects of a built system: the chamber's and the bench's."""
    out = []
    for n in node.walk():
        if n.type == "component" and not any(
                a.type == "component" for a in _ancestors(n, node)):
            out.append(n)
    return out


def _ancestors(n, stop):
    p = n.parent
    while p is not None and p is not stop:
        yield p
        p = p.parent


def _box_liner(spec, r, openings):
    """A liner for a cylinder or cube: the body shape shrunk by the gap,
    as a thin shell with the port openings cut."""
    t = spec["liner_thickness"]
    g = spec["wall"] + spec["liner_gap"]
    if spec["body"] == "cylinder":
        H = spec["height"] - 2 * g
        outer = _cyl("Liner", r, H, z=-H / 2.0, segments=128)
        inner = _cyl("Liner void", r - t, H - 2 * t, z=-H / 2.0 + t,
                     segments=128)
    else:
        outer = _cube("Liner", 2 * r, 2 * r, 2 * r, z=-r)
        inner = _cube("Liner void", 2 * (r - t), 2 * (r - t), 2 * (r - t),
                      z=-r + t)
    part = _group("difference", "Mu-metal liner", outer, inner)
    reach = spec["radius"] * 2.0 + spec["height"]
    for theta, phi, d, focus in openings:
        part.add(_aim(_cyl("Port opening", d / 2.0, reach, segments=48),
                      dict(theta=theta, phi=phi, focus=focus), "Opening"))
    return part


def apply(model, spec) -> CadNode:
    """Add the built system to *model* (one undo step)."""
    node = build(spec)
    model.root.add(node)
    model.structure_changed.emit()
    return node


# ── presets ─────────────────────────────────────────────────────────

def _prep():
    s = new_spec("Preparation chamber", "sphere", 150.0)
    s["ports"] = [
        port("Manipulator", "CF63 (DN63)", 0.0, 0.0, 420.0,
             "manipulator_transax", variant="Transax style Z300, CF63 "
             "base, PTS head"),
        port("Transfer arm", "CF63 (DN63)", 90.0, 180.0, 230.0,
             "transfer_pts"),
        port("LEED", "CF100 (DN100)", 90.0, 0.0, 260.0, "leed"),
        port("Sputter gun", "CF40 (DN40)", 45.0, 90.0, 230.0,
             "sputter_gun"),
        port("Evaporator", "CF40 (DN40)", 45.0, 270.0, 230.0,
             "evaporator"),
        port("Ion gauge", "CF40 (DN40)", 90.0, 90.0, 220.0, "gauge_head"),
        port("Viewport", "CF63 (DN63)", 60.0, 225.0, 230.0, "viewport"),
        port("RGA", "CF40 (DN40)", 90.0, 270.0, 220.0, "rga"),
        port("Ion pump", "CF100 (DN100)", 180.0, 0.0, 260.0, "blank"),
        port("Gas leak", "CF16 (DN16)", 120.0, 135.0, 200.0, "blank"),
        port("Roughing", "KF25 (DN25)", 120.0, 45.0, 200.0, "kf_blank"),
    ]
    return s


def _analysis():
    """XPS: the monochromator at the magic angle (54.7°) to the analyser
    axis, the twin-anode source beside it, the cooled manipulator above."""
    s = new_spec("XPS analysis chamber", "sphere", 170.0)
    s.update(liner=True, liner_gap=10.0, liner_thickness=1.5, bench="rack")
    s["ports"] = [
        port("Manipulator", "CF100 (DN100)", 0.0, 0.0, 440.0,
             "manipulator_cryo"),
        port("Analyser", "CF100 (DN100)", 90.0, 0.0, 260.0, "analyser"),
        port("Monochromator", "CF63 (DN63)", 90.0, 305.3, 250.0, "mono",
             spin=90.0),
        port("X-ray source", "CF40 (DN40)", 55.0, 135.0, 250.0, "xray"),
        port("Transfer arm", "CF40 (DN40)", 90.0, 180.0, 260.0,
             "transfer_flag"),
        port("Flood gun / UV lamp", "CF40 (DN40)", 90.0, 125.0, 250.0,
             "blank"),
        port("Ion gauge", "CF40 (DN40)", 90.0, 90.0, 240.0, "ion_gauge"),
        port("Viewport", "CF63 (DN63)", 125.0, 225.0, 250.0, "viewport"),
        port("Sputter gun", "CF40 (DN40)", 55.0, 45.0, 250.0,
             "sputter_gun"),
        port("Pumping", "CF160 (DN160)", 180.0, 0.0, 300.0, "blank"),
    ]
    return s


def _two_level():
    """A tall cylinder: preparation tools aimed at an upper focal point,
    analysis at a lower one, the manipulator's long Z carrying the sample
    between them."""
    s = new_spec("Two-level prep + analysis chamber", "cylinder", 160.0)
    s.update(height=620.0, wall=4.0, liner=True, bench="castors",
             beam_height=1250.0)
    up, down = 170.0, -140.0
    s["ports"] = [
        port("Manipulator", "CF160 (DN160)", 0.0, 0.0, 520.0,
             "manipulator", focus=down, variant="Omniax style Z600, CF160 "
             "base, motorised, PTS head"),
        port("Sputter gun", "CF40 (DN40)", 55.0, 90.0, 230.0, "sputter_gun",
             focus=up),
        port("LEED", "CF100 (DN100)", 90.0, 0.0, 250.0, "leed", focus=up),
        port("Evaporator", "CF40 (DN40)", 90.0, 240.0, 230.0, "evaporator",
             focus=up),
        port("Transfer arm", "CF63 (DN63)", 90.0, 180.0, 240.0,
             "transfer_pts", focus=up),
        port("Analyser", "CF100 (DN100)", 90.0, 0.0, 250.0, "analyser",
             focus=down),
        port("X-ray source", "CF40 (DN40)", 90.0, 305.3, 240.0, "xray",
             focus=down),
        port("RGA", "CF40 (DN40)", 90.0, 150.0, 230.0, "rga", focus=down),
        port("Ion gauge", "CF40 (DN40)", 90.0, 90.0, 220.0, "gauge_head",
             focus=down),
        port("Pumping", "CF160 (DN160)", 180.0, 0.0, 380.0, "blank",
             focus=down),
    ]
    return s


def _load_lock():
    s = new_spec("Load lock", "cylinder", 76.0)
    s.update(height=220.0, wall=3.0, bench="table", beam_height=1000.0)
    s["ports"] = [
        port("Fast-entry door", "CF100 (DN100)", 0.0, 0.0, 150.0, "door"),
        port("Carousel", "CF40 (DN40)", 180.0, 0.0, 150.0, "carousel"),
        port("Transfer arm", "CF40 (DN40)", 90.0, 180.0, 130.0,
             "transfer_flag", variant="Travel 300 mm, flag fork (CF40)"),
        port("To prep (gate valve)", "CF63 (DN63)", 90.0, 0.0, 130.0,
             "open"),
        port("Turbo", "CF63 (DN63)", 90.0, 90.0, 130.0, "blank"),
        port("Pirani", "KF16 (DN16)", 90.0, 270.0, 120.0, "pirani"),
    ]
    return s


def _cube6():
    s = new_spec("CF cube chamber", "cube", 60.0)
    s.update(wall=10.0, bench="none", beam_height=0.0)
    s["ports"] = [port(n, "CF63 (DN63)", th, ph, 95.0, "blank")
                  for n, th, ph in (("Top", 0, 0), ("Bottom", 180, 0),
                                    ("+X", 90, 0), ("-X", 90, 180),
                                    ("+Y", 90, 90), ("-Y", 90, 270))]
    return s


PRESETS = {"Preparation chamber (LEED, sputter, evaporator)": _prep,
           "XPS analysis chamber (analyser, monochromator, mu-metal)":
               _analysis,
           "Two-level chamber (prep above, analysis below)": _two_level,
           "Load lock (fast entry, carousel)": _load_lock,
           "CF cube (6 ports)": _cube6,
           "Empty sphere": lambda: new_spec()}


def preset(name) -> dict:
    return normalise(copy.deepcopy(PRESETS[name]()))
