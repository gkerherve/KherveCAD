"""A UHV chamber as data (Qt-free): a body (sphere, cylinder or cube), a
mu-metal liner, a stand and a list of CF or KF ports, each aimed at the
sample (the chamber centre) from a polar angle θ (0° = straight up) and
an azimuth φ (0° = +X), carrying an accessory — a viewport, an ion
gauge, a sputter gun, LEED, an analyser, a manipulator, a transfer arm…

`build(spec)` turns it into one assembly of Objects; `clashes(spec)`
finds ports whose flanges would collide; `PRESETS` holds a preparation
chamber, an XPS analysis chamber and a load lock to start from. The
Chamber Designer (`chamber_dialog`) edits a spec; a spec is plain JSON.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import copy
import math

from .library import (CF_SIZES, KF_SIZES, _bolt_holes, _cyl,
                      _kf_flange_head, build_part, cf_flange_solid)
from .library_uhv import MU_METAL, mu_metal_liner
from .library_vacuum import (STEEL, _cube, _group, _move, _object, _paint,
                             _ring, _turn, _union)
from .model import CadNode

BODIES = ("sphere", "cylinder", "cube")
FLANGES = list(CF_SIZES) + list(KF_SIZES)

#: accessory key -> (label, part id or None, flange family, dims(flange,
#: reach)). A part id of None is an open port or a built-in blank.
ACCESSORIES = {
    "open": ("Open port", None, "any"),
    "blank": ("Blank flange", "blank", "any"),
    "viewport": ("Viewport", "cf_viewport", "CF"),
    "ion_gauge": ("Ion gauge (nude)", "gauge_ion", "CF"),
    "gauge_head": ("Ion gauge head (nipple)", "gauge_head", "CF"),
    "sputter_gun": ("Sputter ion gun", "sputter_gun", "CF"),
    "leed": ("LEED optics", "leed", "CF"),
    "analyser": ("Hemispherical analyser", "analyser_lens", "CF"),
    "xray": ("X-ray source", "xray_source", "CF"),
    "evaporator": ("e-beam evaporator", "evaporator", "CF"),
    "manipulator": ("XYZT manipulator", "manipulator_xyzt", "CF"),
    "manipulator_cryo": ("XYZT manipulator + LN2", "manipulator_xyzt",
                         "CF"),
    "transfer_flag": ("Transfer arm (flag)", "transfer_sample", "CF"),
    "transfer_pts": ("Transfer arm (PTS)", "transfer_sample", "CF"),
    "carousel": ("Sample carousel", "sample_carousel", "CF"),
    "wobble": ("Wobble stick", "wobble_stick", "CF"),
    "rga": ("RGA (quadrupole)", "rga", "CF"),
    "door": ("Fast-entry door", "fast_entry", "CF"),
    "kf_blank": ("KF blank", "kf_blank", "KF"),
    "pirani": ("Pirani gauge", "gauge_pirani", "KF"),
}

#: which size row of a part to start from, per accessory
_SIZE_ROW = {
    "manipulator": "XYZT, Z 100 mm, flag head (CF63)",
    "manipulator_cryo": "XYZT, Z 200 mm, flag head + LN2 (CF100)",
    "transfer_flag": "Travel 600 mm, flag fork (CF40)",
    "transfer_pts": "Travel 600 mm, PTS bayonet (CF40)",
}

#: a sample-reaching tool stops this short of the centre (mm)
_STANDOFF = {"manipulator": 0.0, "manipulator_cryo": 0.0,
             "transfer_flag": 0.0, "transfer_pts": 0.0, "carousel": 0.0,
             "wobble": 30.0, "rga": 60.0, "ion_gauge": 0.0}


def family(flange: str) -> str:
    return "KF" if str(flange) in KF_SIZES else "CF"


def flange_row(flange: str) -> dict:
    return dict(KF_SIZES.get(flange) or CF_SIZES[flange])


def port(name, flange, theta, phi, length, accessory="blank"):
    return dict(name=name, flange=flange, theta=float(theta),
                phi=float(phi), length=float(length), accessory=accessory)


def new_spec(name="UHV chamber", body="sphere", radius=150.0):
    return dict(name=name, body=body, radius=float(radius), height=300.0,
                wall=4.0, liner=False, liner_gap=10.0, liner_thickness=1.5,
                stand=True, ports=[])


def normalise(spec: dict) -> dict:
    """*spec* with every key present and sane (a loaded file may be
    missing some)."""
    out = new_spec()
    out.update({k: v for k, v in dict(spec).items() if k != "ports"})
    if out["body"] not in BODIES:
        out["body"] = "sphere"
    for key in ("radius", "height", "wall", "liner_gap",
                "liner_thickness"):
        out[key] = max(float(out[key]), 0.5)
    out["ports"] = []
    for i, p in enumerate(spec.get("ports") or []):
        q = port(f"Port {i + 1}", "CF40 (DN40)", 90.0, 0.0,
                 out["radius"] + 60.0)
        q.update(p)
        if q["flange"] not in FLANGES:
            q["flange"] = "CF40 (DN40)"
        if q["accessory"] not in ACCESSORIES:
            q["accessory"] = "blank"
        q["theta"] = min(max(float(q["theta"]), 0.0), 180.0)
        q["phi"] = float(q["phi"]) % 360.0
        q["length"] = max(float(q["length"]), 10.0)
        out["ports"].append(q)
    return out


def direction(theta, phi):
    t, f = math.radians(theta), math.radians(phi)
    return (math.sin(t) * math.cos(f), math.sin(t) * math.sin(f),
            math.cos(t))


def wall_distance(spec, theta, phi) -> float:
    """How far from the centre the port axis leaves the body's outer
    surface."""
    R = spec["radius"]
    if spec["body"] == "sphere":
        return R
    dx, dy, dz = direction(theta, phi)
    if spec["body"] == "cylinder":
        H = spec["height"] / 2.0
        radial = math.hypot(dx, dy)
        hits = []
        if radial > 1e-9:
            hits.append(R / radial)
        if abs(dz) > 1e-9:
            hits.append(H / abs(dz))
        return min(hits)
    hits = [R / abs(c) for c in (dx, dy, dz) if abs(c) > 1e-9]
    return min(hits)


def min_length(spec, p) -> float:
    """The shortest port that still clears the body: its flange must sit
    outside the wall with a little tube between."""
    row = flange_row(p["flange"])
    return round(wall_distance(spec, p["theta"], p["phi"])
                 + row["thickness"] + 15.0, 1)


def angle_between(a, b) -> float:
    da, db = direction(a["theta"], a["phi"]), direction(b["theta"], b["phi"])
    dot = max(min(sum(x * y for x, y in zip(da, db)), 1.0), -1.0)
    return math.degrees(math.acos(dot))


def half_angle(p) -> float:
    """The half-angle a port's flange subtends from the centre."""
    row = flange_row(p["flange"])
    inner = max(p["length"] - row["thickness"], 1.0)
    return math.degrees(math.atan2(row["flange_od"] / 2.0, inner))


def problems(spec) -> list:
    """[(message, {port indices})] for the ports: flanges that overlap,
    ports too short to clear the body, accessories on the wrong flange
    family."""
    ports = spec["ports"]
    out = []
    for i, a in enumerate(ports):
        if a["length"] < min_length(spec, a) - 0.05:
            out.append((f"{a['name']}: too short to clear the chamber "
                        f"(at least {min_length(spec, a):g} mm)", {i}))
        fam = ACCESSORIES[a["accessory"]][2]
        if fam != "any" and fam != family(a["flange"]):
            out.append((f"{a['name']}: {ACCESSORIES[a['accessory']][0]} "
                        f"needs a {fam} flange", {i}))
        for j in range(i + 1, len(ports)):
            b = ports[j]
            gap = angle_between(a, b) - half_angle(a) - half_angle(b)
            if gap < 0:
                out.append((f"{a['name']} and {b['name']} flanges overlap "
                            f"({-gap:.0f}° too close)", {i, j}))
    return out


def clashes(spec) -> list:
    """The messages of `problems`."""
    return [msg for msg, _ports in problems(spec)]


# ── geometry ────────────────────────────────────────────────────────

def _aim(node, theta, phi, name):
    """*node* built along +Z, turned onto the port axis."""
    return _turn(node, 0.0, float(theta), float(phi), name=name)


def _port_geometry(spec, p):
    """(solid, cut) of one port along +Z: the tube from inside the wall to
    the flange, the flange (sealing face at *length*), the bore and bolt
    holes."""
    row = flange_row(p["flange"])
    L, t = p["length"], row["thickness"]
    start = max(wall_distance(spec, p["theta"], p["phi"])
                - spec["wall"] * 3.0 - 20.0, 0.0)
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


def _stand(spec):
    R = spec["radius"]
    bottom = R if spec["body"] != "cylinder" else spec["height"] / 2.0
    foot = -bottom - R * 0.9 - 150.0
    legs = []
    for k in range(4 if spec["body"] == "cube" else 3):
        a = math.radians(30.0 + 360.0 * k / (4 if spec["body"] == "cube"
                                             else 3))
        x, y = R * 1.25 * math.cos(a), R * 1.25 * math.sin(a)
        legs += [_cyl("Leg", 14.0, -foot - bottom * 0.2, x=x, y=y, z=foot,
                      segments=24),
                 _cyl("Foot", 30.0, 8.0, x=x, y=y, z=foot, segments=32)]
        legs.append(_move(_turn(_cube("Cradle arm", 16.0, 16.0,
                                      R * 1.25, x=-8.0, y=-8.0), y=-90.0),
                          x, y, -bottom * 0.2))
    legs.append(_ring("Cradle ring", R * 1.25 - 12.0, R * 1.25 + 12.0,
                      16.0, z=-bottom * 0.2 - 8.0))
    legs.append(_ring("Brace", R * 1.25 - 8.0, R * 1.25 + 8.0, 10.0,
                      z=foot + 120.0))
    return _union("Stand", *legs)


def accessory_dims(p) -> dict:
    """The dims an accessory is built from on port *p*: its size row with
    the port's flange as the mount and the port length as the reach."""
    from .library import PARTS
    key = p["accessory"]
    pid = ACCESSORIES[key][1]
    row = flange_row(p["flange"])
    if pid == "cf_viewport":
        return dict(row, _size=p["flange"])
    if pid == "kf_blank":
        return dict(row, _size=p["flange"])
    sizes = PARTS[pid].get("sizes") or {}
    size = _SIZE_ROW.get(key) or next(iter(sizes), "")
    dims = dict(sizes.get(size, {}), _size=size)
    dims.pop("port", None)
    if "mount" in dims or pid in ("gauge_ion",):
        dims["mount"] = p["flange"]
    if pid in ("gauge_pirani",):
        return dict(row, _size=size)
    reach = p["length"] - _STANDOFF.get(key, 0.0)
    for k in ("reach",):
        if k in dims:
            dims[k] = reach
    if pid == "wobble_stick":
        dims["reach"] = reach - 20.0
    if pid == "rga":
        dims["probe"] = max(reach - 40.0, 40.0)
    if pid == "transfer_sample":
        dims["travel"] = max(float(dims.get("travel", 600.0)), reach)
    return dims


def _accessory(p):
    key = p["accessory"]
    pid = ACCESSORIES[key][1]
    if pid is None:
        return None
    row = flange_row(p["flange"])
    if pid == "blank":
        if family(p["flange"]) == "KF":
            node = build_part("kf_blank", dict(row))
        else:
            node = build_part("cf_blank", dict(row))
    else:
        node = build_part(pid, accessory_dims(p))
    face = CadNode("translate", f"{p['name']} face",
                   dict(x=0.0, y=0.0, z=float(p["length"])))
    face.add(node)
    return face


def build(spec) -> CadNode:
    """The chamber as a union of Objects: the ported body, the mu-metal
    liner, the stand and one Object per accessory, all on their ports."""
    spec = normalise(spec)
    body_solid, void = _body_solids(spec)
    body = CadNode("difference", "Chamber")
    outer = _union("Chamber body", body_solid)
    body.add(outer)
    body.add(void)
    for p in spec["ports"]:
        solid, cut = _port_geometry(spec, p)
        outer.add(_aim(solid, p["theta"], p["phi"], p["name"]))
        body.add(_aim(cut, p["theta"], p["phi"], f"{p['name']} bore"))
    objects = [_object("Chamber", _paint(body, STEEL))]
    if spec["liner"]:
        r = spec["radius"] - spec["wall"] - spec["liner_gap"]
        openings = [(p["theta"], p["phi"],
                     flange_row(p["flange"])["tube_od"] + 4.0)
                    for p in spec["ports"]]
        if spec["body"] == "sphere":
            liner = mu_metal_liner(r, spec["liner_thickness"], openings)
        else:
            liner = _box_liner(spec, r, openings)
        objects.append(_object("Mu-metal liner", _paint(liner, MU_METAL)))
    if spec["stand"]:
        objects.append(_object("Stand", _paint(_stand(spec), "#5f646c")))
    for p in spec["ports"]:
        acc = _accessory(p)
        if acc is None:
            continue
        label = ACCESSORIES[p["accessory"]][0]
        objects.append(_object(f"{p['name']}: {label}",
                               _aim(acc, p["theta"], p["phi"], p["name"])))
    return _union(spec["name"], *objects)


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
    for theta, phi, d in openings:
        part.add(_aim(_cyl("Port opening", d / 2.0, reach, segments=48),
                      theta, phi, "Opening"))
    return part


def apply(model, spec) -> CadNode:
    """Add the built chamber to *model* (one undo step)."""
    node = build(spec)
    model.root.add(node)
    model.structure_changed.emit()
    return node


# ── presets ─────────────────────────────────────────────────────────

def _prep():
    s = new_spec("Preparation chamber", "sphere", 150.0)
    s.update(liner=False, wall=4.0)
    s["ports"] = [
        port("Manipulator", "CF100 (DN100)", 0.0, 0.0, 400.0,
             "manipulator"),
        port("Transfer arm", "CF40 (DN40)", 90.0, 180.0, 230.0,
             "transfer_flag"),
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
    s = new_spec("XPS analysis chamber", "sphere", 170.0)
    s.update(liner=True, liner_gap=10.0, liner_thickness=1.5, wall=4.0)
    s["ports"] = [
        port("Manipulator", "CF100 (DN100)", 0.0, 0.0, 420.0,
             "manipulator_cryo"),
        port("Analyser", "CF100 (DN100)", 90.0, 0.0, 260.0, "analyser"),
        port("X-ray source", "CF40 (DN40)", 35.0, 180.0, 250.0, "xray"),
        port("Transfer arm", "CF40 (DN40)", 90.0, 180.0, 260.0,
             "transfer_flag"),
        port("Flood gun / UV lamp", "CF40 (DN40)", 90.0, 125.0, 250.0,
             "blank"),
        port("Ion gauge", "CF40 (DN40)", 90.0, 270.0, 240.0, "ion_gauge"),
        port("Viewport", "CF63 (DN63)", 90.0, 90.0, 250.0, "viewport"),
        port("Sputter gun", "CF40 (DN40)", 55.0, 300.0, 250.0,
             "sputter_gun"),
        port("Pumping", "CF160 (DN160)", 180.0, 0.0, 300.0, "blank"),
    ]
    return s


def _load_lock():
    s = new_spec("Load lock", "cylinder", 76.0)
    s.update(height=220.0, wall=3.0, stand=False)
    s["ports"] = [
        port("Fast-entry door", "CF100 (DN100)", 0.0, 0.0, 150.0, "door"),
        port("Carousel", "CF40 (DN40)", 180.0, 0.0, 150.0, "carousel"),
        port("Transfer arm", "CF40 (DN40)", 90.0, 180.0, 130.0,
             "transfer_flag"),
        port("To prep (gate valve)", "CF63 (DN63)", 90.0, 0.0, 130.0,
             "open"),
        port("Turbo", "CF63 (DN63)", 90.0, 90.0, 130.0, "blank"),
        port("Pirani", "KF16 (DN16)", 90.0, 270.0, 120.0, "pirani"),
    ]
    return s


def _cube6():
    s = new_spec("CF cube chamber", "cube", 60.0)
    s.update(wall=10.0, stand=False)
    s["ports"] = [port(n, "CF63 (DN63)", th, ph, 95.0, "blank")
                  for n, th, ph in (("Top", 0, 0), ("Bottom", 180, 0),
                                    ("+X", 90, 0), ("-X", 90, 180),
                                    ("+Y", 90, 90), ("-Y", 90, 270))]
    return s


PRESETS = {"Preparation chamber (LEED, sputter, evaporator)": _prep,
           "XPS analysis chamber (analyser, X-rays, mu-metal)": _analysis,
           "Load lock (fast entry, carousel)": _load_lock,
           "CF cube (6 ports)": _cube6,
           "Empty sphere": lambda: new_spec()}


def preset(name) -> dict:
    return normalise(copy.deepcopy(PRESETS[name]()))
