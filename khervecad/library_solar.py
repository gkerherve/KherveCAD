"""The Solar System in the Library (Science ▸ Solar System): every
planet, dwarf planet and notable moon of `solar_data` as a Part
Library globe (`solar_bodies`), and orreries that RUN — the whole
Solar System, the inner planets, and each planet with its moons —
driven by a Customizer slider of days since J2000, the way the
Mechanisms & motion library drives a crank.

An orrery is real OpenSCAD: every body is an Object whose own
variables solve its Kepler orbit (mean anomaly -> equation of the
centre -> distance and longitude, inclined at the node), so the
program reads `translate([px, py, pz]) rotate([0, tilt, pole])` over a
globe Object that spins on `rz`. Sliders: days, Earth's diameter (the
rest scale with it, compressed by `size_compression`), the Sun's, the
radius of Earth's orbit, `compression` (1 = true spacing, 0.5 =
square-root, or Neptune is thirty Earth orbits out), how far moons
stand from their planet and the smallest moon drawn. Time is real —
Earth laps the Sun in 365.256 days, the Moon in 27.3 — and Greenwich
faces the Sun at day 0. Inserting one ADDS it (`library_motion.place`)
with its variables prefixed, so two orreries coexist.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import solar_bodies, solar_data as D
from .model import CadNode

CATEGORY_PLANETS = "Planets"
CATEGORY_MOONS = "Moons"
CATEGORY_SYSTEMS = "Solar System models"

#: the printed-model scale offered beside the fixed diameters
SCALE = 250_000_000
#: the globes of an orrery are built at this diameter, then scaled
REF = 20.0

MOON_BASE = {"saturn": 2.3}          # outside the rings


def _sizes(body):
    sizes = {"Ø 30 mm": dict(d=30.0), "Ø 60 mm": dict(d=60.0),
             "Ø 120 mm": dict(d=120.0)}
    to_scale = 2 * body["radius"] / SCALE * 1e6
    if to_scale >= 0.8:
        sizes[f"To scale, 1:{SCALE:,} ({to_scale:.3g} mm)".replace(
            ",", " ")] = dict(d=round(to_scale, 3))
    return sizes


def _body_part(body):
    label = D.planet_label(body)
    if body["kind"] == "dwarf":
        label += " (dwarf planet)"
    elif body["kind"] == "star":
        label = "The Sun"
    return dict(
        label=label,
        category=CATEGORY_MOONS if body["kind"] == "moon"
        else CATEGORY_PLANETS,
        sizes=_sizes(body), fields=[("d", "Diameter")],
        build=lambda dims, key=body["key"]: solar_bodies.build_body(
            key, float(dims.get("d", 60.0)), fine=True),
        note=body["note"])


PARTS = {f"body_{b['key']}": _body_part(b) for b in D.BODIES}


# --------------------------------------------------------------- orreries

#: the moons an orrery of the whole system shows
ORRERY_MOONS = ["moon", "phobos", "deimos", "io", "europa", "ganymede",
                "callisto", "mimas", "enceladus", "tethys", "dione", "rhea",
                "titan", "iapetus", "miranda", "ariel", "umbriel", "titania",
                "oberon", "triton", "charon"]


def _assign(name, value, options="", description="", group=""):
    params = dict(variable=name, value=str(value))
    if options:
        params["options"] = options
    if description:
        params["description"] = description
    if group:
        params["group"] = group
    return CadNode("assign", f"{name} =", params)


def _component(name, *children, **placement):
    node = CadNode("component", name, dict(
        x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0, color="", alpha=1.0))
    for key, value in placement.items():
        node.params[key] = value
    for child in children:
        node.add(child)
    return node


def _translate(name, x, y, z, *children):
    node = CadNode("translate", name, dict(x=x, y=y, z=z))
    for child in children:
        node.add(child)
    return node


def _rotate(name, x, y, z, *children):
    node = CadNode("rotate", name, dict(x=x, y=y, z=z))
    for child in children:
        node.add(child)
    return node


def _globe(body, size_expr, spin_expr):
    """The body's globe as an Object spinning on *spin_expr*, scaled
    from REF to *size_expr* mm. The globe reads no variable at all, so
    its mesh is cached once and a tick only re-places it; the scale
    stands outside because a nested module is hoisted to the top of
    the program, where its planet's locals are out of reach."""
    globe = _component(f"{body['label']} globe",
                       solar_bodies.build_body(body["key"], REF, fine=False),
                       rz=spin_expr)
    scale = CadNode("scale", "Size", dict(x=f"{size_expr} / {REF:g}",
                                          y=f"{size_expr} / {REF:g}",
                                          z=f"{size_expr} / {REF:g}"))
    scale.add(globe)
    return scale


def _size_expr(body, p, reference):
    """Diameter expression: the body's true ratio to Earth, compressed
    by the size slider; a moon never smaller than min_moon."""
    ratio = body["radius"] / D.EARTH_RADIUS_KM
    expr = (f"pow({ratio:.6g}, {p}_size_compression) * {reference}")
    if body["kind"] == "moon":
        return f"max({expr}, {p}_min_moon)"
    return expr


def _spin_expr(body, p):
    return f"{body['phase']:.3f} + 360 * {p}_days / {body['rotation']:.5f}"


def _moon_node(moon, parent, p, parent_size, size_reference):
    """A moon Object inside its planet's tilted frame: it circles in
    the equatorial plane at a compressed distance and keeps its 0°
    meridian towards the planet (synchronous rotation). *parent_size*
    is the planet's diameter as an expression of the globals only —
    the module is hoisted, so it cannot read the planet's own."""
    ratio = moon["a"] / parent["radius"]
    base = MOON_BASE.get(parent["key"], 1.0)
    period = moon["period"]
    children = [
        _assign("angle", f"{moon['phase']:.3f} + 360 * {p}_days / "
                         f"{period:.5f}"),
        _assign("planet", parent_size),
        _assign("size", _size_expr(moon, p, size_reference)),
        _assign("dist", f"planet / 2 * ({base:g} + 0.5 * "
                        f"{p}_moon_spread * {math.log(ratio):.4f}) + "
                        f"size / 2"),
        _translate("Orbit position", "dist * cos(angle)",
                   "dist * sin(angle)", 0.0,
                   _globe(moon, "size", "angle + 180")),
    ]
    return _component(moon["label"], *children)


def _planet_node(body, moons, p, size_reference, at_origin=False):
    """A planet (or dwarf planet) Object: its Kepler position, tilt and
    spin, its globe and its moons."""
    children = []
    if not at_origin:
        dist = f"{p}_orbit * pow(r, {p}_compression)"
        for name, expr in D.orbit_expressions(body, f"{p}_days", dist):
            children.append(_assign(name, expr))
    size = (f"{p}_planet_size" if at_origin
            else _size_expr(body, p, size_reference))
    children.append(_assign("size", size))
    children.append(_assign("spin", _spin_expr(body, p)))
    inside = [_globe(body, "size", "spin")]
    for moon in moons:
        inside.append(_moon_node(moon, body, p, size, size_reference))
    tilted = _rotate("Axis", 0.0, body["tilt"], body["pole_lon"], *inside)
    if at_origin:
        children.append(tilted)
    else:
        children.append(_translate("Orbit position", "px", "py", "pz",
                                   tilted))
    return _component(body["label"], *children)


def _sun_node(p):
    sun = D.BY_KEY["sun"]
    return _component("Sun", _assign("spin", _spin_expr(sun, p)),
                      _globe(sun, f"{p}_sun_size", "spin"))


def _orbits_node(bodies, p):
    """Every orbit as a ring of dots computed by the same formula as
    the planets (so it follows the compression sliders), cached since
    it never reads the days."""
    node = _component("Orbits")
    for body in bodies:
        e = body["e"]
        loop = CadNode("for_loop", f"{body['label']} orbit", dict(
            variable="k", start=0.0, end=356.0, step=4.0, values=""))
        for name, expr in [
                ("r", f"{body['a'] * (1 - e * e):.5f} / (1 + {e:.5f} * "
                      "cos(k))"),
                ("dist", f"{p}_orbit * pow(r, {p}_compression)"),
                ("u", f"k + {body['peri'] - body['node']:.3f}"),
                ("px", f"dist * (cos({body['node']:.3f}) * cos(u) - "
                       f"sin({body['node']:.3f}) * sin(u) * "
                       f"cos({body['inc']:.3f}))"),
                ("py", f"dist * (sin({body['node']:.3f}) * cos(u) + "
                       f"cos({body['node']:.3f}) * sin(u) * "
                       f"cos({body['inc']:.3f}))"),
                ("pz", f"dist * sin(u) * sin({body['inc']:.3f})")]:
            loop.add(_assign(name, expr))
        dot = CadNode("cube", "Dot", dict(x="px", y="py", z="pz",
                                          width=0.6, depth=0.6, height=0.6,
                                          center=True))
        loop.add(dot)
        node.add(loop)
    wrap = CadNode("color", "Orbits", dict(color="#8a8f96", alpha=1.0,
                                           material="Matte"))
    for child in list(node.children):
        node.remove(child)
        wrap.add(child)
    node.add(wrap)
    return node


def _system_variables(system, p):
    label = SYSTEMS[system]["label"]
    time_group, layout = f"{label} · Time", f"{label} · Layout"
    spec = SYSTEMS[system]
    out = [_assign(f"{p}_days", "0", f"0:{spec['step']:g}:{spec['span']:g}",
                   "Days since 1 January 2000 — press play to run it",
                   time_group)]
    if spec["kind"] == "sun":
        out += [
            _assign(f"{p}_earth_size", spec["earth"], "2:1:60",
                    "Earth's diameter, mm; every other body scales with it",
                    layout),
            _assign(f"{p}_sun_size", spec["sun"], "10:5:200",
                    "The Sun's diameter, mm (to scale it would be 109 "
                    "Earths)", layout),
            _assign(f"{p}_orbit", spec["orbit"], "30:10:800",
                    "Radius of Earth's orbit, mm", layout),
            _assign(f"{p}_compression", spec["compression"], "0.25:0.05:1",
                    "Orbit spacing: 1 keeps the true proportions, 0.5 "
                    "packs the outer planets in", layout),
            _assign(f"{p}_size_compression", spec["size_compression"],
                    "0.3:0.05:1",
                    "Body sizes: 1 keeps the true proportions to Earth, "
                    "0.5 tames Jupiter", layout),
        ]
    else:
        out += [
            _assign(f"{p}_planet_size", spec["planet"], "10:5:200",
                    "The planet's diameter, mm; its moons scale with it",
                    layout),
            _assign(f"{p}_size_compression", spec["size_compression"],
                    "0.3:0.05:1",
                    "Moon sizes: 1 keeps the true proportions, lower "
                    "makes the small ones visible", layout),
        ]
    out += [
        _assign(f"{p}_moon_spread", "1", "0.3:0.1:4",
                "How far the moons stand from their planet", layout),
        _assign(f"{p}_min_moon", "1", "0.3:0.1:6",
                "The smallest moon drawn, mm across", layout),
    ]
    return out


def system_root(system: str, prefix: str = None) -> CadNode:
    """The orrery as a root: its variables, then its Objects."""
    spec = SYSTEMS[system]
    p = prefix or spec["prefix"]
    root = CadNode("root")
    for node in _system_variables(system, p):
        root.add(node)
    if spec["kind"] == "sun":
        planets = [D.BY_KEY[k] for k in spec["bodies"]]
        moons = spec["moons"]
        root.add(_sun_node(p))
        root.add(_orbits_node(planets, p))
        for planet in planets:
            root.add(_planet_node(
                planet, [m for m in D.moons_of(planet["key"])
                         if m["key"] in moons], p, f"{p}_earth_size"))
    else:
        planet = D.BY_KEY[spec["planet_key"]]
        reference = (f"({p}_planet_size * "
                     f"{D.EARTH_RADIUS_KM / planet['radius']:.6g})")
        root.add(_planet_node(planet, D.moons_of(planet["key"]), p,
                              reference, at_origin=True))
    return root


def _planet_system(key):
    body = D.BY_KEY[key]
    moons = D.moons_of(key)
    longest = max(abs(m["period"]) for m in moons)
    return dict(label=f"{body['label']} & its moons", prefix=key,
                kind="planet", planet_key=key, planet="60",
                size_compression="0.6", step=round(longest / 400, 2),
                span=math.ceil(longest * 2))


SYSTEMS = {
    "solar_system": dict(
        label="Solar System orrery", prefix="solar", kind="sun",
        bodies=[b["key"] for b in D.PLANETS] + ["pluto"],
        moons=ORRERY_MOONS, earth="10", sun="40", orbit="120",
        compression="0.5", size_compression="0.5", step=1, span=7300),
    "solar_inner": dict(
        label="Inner Solar System (Mercury to Mars)", prefix="inner",
        kind="sun", bodies=["mercury", "venus", "earth", "mars"],
        moons=["moon", "phobos", "deimos"], earth="20", sun="60",
        orbit="150", compression="0.8", size_compression="0.8", step=1,
        span=730),
    "solar_dwarfs": dict(
        label="Dwarf planets with the outer planets", prefix="dwarfs",
        kind="sun",
        bodies=["jupiter", "saturn", "uranus", "neptune", "ceres",
                "pluto", "haumea", "makemake", "eris"],
        moons=["charon", "dysnomia"], earth="12", sun="30", orbit="60",
        compression="0.5", size_compression="0.6", step=10, span=100_000),
}
for _key in ("earth", "mars", "jupiter", "saturn", "uranus", "neptune",
             "pluto"):
    SYSTEMS[f"system_{_key}"] = _planet_system(_key)


def build_system(system: str) -> CadNode:
    """The orrery as ONE node (the dialog's preview and the tests): its
    variables followed by its parts, the way `library_motion.build`
    does it."""
    root = system_root(system)
    group = CadNode("union", SYSTEMS[system]["label"])
    for node in list(root.children):
        root.remove(node)
        if node.type == "component":
            node.type = "union"
            for key in ("x", "y", "z", "rx", "ry", "rz"):
                node.params.pop(key, None)
        group.add(node)
    return group


def insert_system(system: str, model, dims=None):
    """Add the orrery to *model*: its variables as globals (Customizer
    sliders), its Objects beside what is there. Returns the Objects."""
    from . import library_motion
    prefix = library_motion.free_prefix(model, SYSTEMS[system]["prefix"])
    return library_motion.place(model, system_root(system, prefix))


PARTS.update({
    sid: dict(label=spec["label"], category=CATEGORY_SYSTEMS,
              sizes={"Standard": {}}, fields=[],
              build=lambda dims, sid=sid: build_system(sid),
              insert=lambda model, dims, sid=sid: insert_system(sid, model,
                                                                dims),
              insert_note="Added as Objects beside the model, driven by "
                          "annotated document variables (prefixed, see "
                          "get_code): the days slider runs the orbits; "
                          "change them with set_params on the assign "
                          "nodes or the Customizer panel.")
    for sid, spec in SYSTEMS.items()
})
