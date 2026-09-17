"""The Solar System's bodies as data (Qt-free): the Sun, the eight
planets, five dwarf planets and the notable moons — real equatorial and
polar radii (km), axial tilt and where the pole leans, sidereal rotation
(days, negative when retrograde), and the orbit (semi-major axis,
period, eccentricity, inclination, node, longitude of perihelion and
mean longitude at the J2000 epoch, from the JPL approximate elements),
plus the colour each body reads as. `position` runs the same Kepler
formula the orrery writes as OpenSCAD expressions, so the tests can
check the program against Python.

Good enough for a model, not an ephemeris: orbits are Keplerian
ellipses fixed at J2000, moons circle in their planet's equatorial
plane, and the spin phase is right for the Earth only (Greenwich faces
the Sun at the epoch, noon on 1 January 2000).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

AU_KM = 149_597_870.7
EARTH_RADIUS_KM = 6378.137

#: kind -> how the Library groups it
KINDS = {"star": "Sun", "planet": "Planet", "dwarf": "Dwarf planet",
         "moon": "Moon"}


def _body(key, label, kind, radius, colour, *, polar=None, radii=None,
          tilt=0.0, pole_lon=0.0, rotation=1.0, parent=None, a=0.0,
          period=0.0, e=0.0, inc=0.0, node=0.0, peri=0.0, L0=0.0,
          phase=0.0, note=""):
    """One body. *radius* is the equatorial radius in km (*polar*
    defaults to it; *radii* (a, b, c) for an irregular moon overrides
    both), *a* is in AU for what orbits the Sun and km for a moon,
    *period* in days (negative = retrograde orbit), *rotation* the
    sidereal spin in days (negative = retrograde; a moon's default is
    synchronous), *tilt* the obliquity in degrees and *pole_lon* the
    ecliptic longitude the north pole leans towards."""
    if radii is None:
        radii = (radius, radius, polar if polar is not None else radius)
    if kind == "moon" and rotation == 1.0:
        rotation = abs(period)
    return dict(key=key, label=label, kind=kind, radius=float(radius),
                radii=tuple(float(v) for v in radii), colour=colour,
                tilt=float(tilt), pole_lon=float(pole_lon),
                rotation=float(rotation), parent=parent, a=float(a),
                period=float(period), e=float(e), inc=float(inc),
                node=float(node), peri=float(peri), L0=float(L0),
                phase=float(phase), note=note)


BODIES = [
    _body("sun", "Sun", "star", 695_700, "#ffc94d", rotation=25.38,
          note="A G-type star; 109 Earths across."),
    # ------------------------------------------------------- planets
    _body("mercury", "Mercury", "planet", 2439.7, "#8c8880", tilt=0.03,
          rotation=58.646, a=0.38710, period=87.969, e=0.20563,
          inc=7.005, node=48.331, peri=77.456, L0=252.251,
          note="Cratered, airless; a 3:2 spin-orbit resonance."),
    _body("venus", "Venus", "planet", 6051.8, "#e6cf9d", tilt=2.64,
          rotation=-243.025, a=0.72333, period=224.701, e=0.00677,
          inc=3.395, node=76.680, peri=131.564, L0=181.979,
          note="Hidden under sulphuric-acid clouds; spins backwards."),
    _body("earth", "Earth", "planet", EARTH_RADIUS_KM, "#1f4f9c",
          polar=6356.752, tilt=23.44, pole_lon=90.0, rotation=0.99727,
          a=1.0, period=365.256, e=0.01671, inc=0.0, node=0.0,
          peri=102.937, L0=100.464, phase=190.46,
          note="Oceans, continents and polar caps at 5° resolution."),
    _body("mars", "Mars", "planet", 3396.2, "#c1642f", polar=3376.2,
          tilt=25.19, pole_lon=352.9, rotation=1.02596, a=1.52368,
          period=686.980, e=0.09339, inc=1.850, node=49.558,
          peri=336.041, L0=355.453,
          note="Rust deserts, dark albedo regions, Olympus Mons, "
               "Valles Marineris and two polar caps."),
    _body("jupiter", "Jupiter", "planet", 71_492, "#c9a678", polar=66_854,
          tilt=3.13, pole_lon=248.0, rotation=0.41354, a=5.2026,
          period=4332.59, e=0.04839, inc=1.303, node=100.474,
          peri=14.728, L0=34.396,
          note="Belts and zones, the Great Red Spot; 11 Earths across."),
    _body("saturn", "Saturn", "planet", 60_268, "#e3cfa0", polar=54_364,
          tilt=26.73, pole_lon=79.5, rotation=0.44401, a=9.5549,
          period=10_759.22, e=0.05386, inc=2.489, node=113.666,
          peri=92.599, L0=49.954,
          note="The C, B and A rings with the Cassini Division; the "
               "most flattened planet."),
    _body("uranus", "Uranus", "planet", 25_559, "#a9dbe3", polar=24_973,
          tilt=97.77, pole_lon=77.6, rotation=0.71833, a=19.2184,
          period=30_688.5, e=0.04726, inc=0.773, node=74.006,
          peri=170.954, L0=313.238,
          note="Rolls on its side; thin dark rings; five big moons "
               "orbit over its poles."),
    _body("neptune", "Neptune", "planet", 24_764, "#3d5cc8", polar=24_341,
          tilt=28.32, pole_lon=319.0, rotation=0.67125, a=30.1104,
          period=60_182.0, e=0.00859, inc=1.770, node=131.784,
          peri=44.965, L0=304.880,
          note="Deep blue with the Great Dark Spot and faint ring arcs."),
    # ------------------------------------------------- dwarf planets
    _body("pluto", "Pluto", "dwarf", 1188.3, "#c9a88a", tilt=112.8,
          pole_lon=137.0, rotation=6.3872, a=39.482, period=90_560.0,
          e=0.2488, inc=17.16, node=110.299, peri=224.07, L0=238.93,
          note="Tombaugh Regio, the bright heart, beside the dark "
               "Cthulhu Macula."),
    _body("ceres", "Ceres", "dwarf", 482.0, "#8e8b86", polar=446.0,
          tilt=4.0, rotation=0.3781, a=2.7675, period=1681.6, e=0.0758,
          inc=10.59, node=80.3, peri=153.9, L0=160.0,
          note="The largest body of the asteroid belt, with Occator's "
               "bright spots."),
    _body("haumea", "Haumea", "dwarf", 1050.0, "#eceef2",
          radii=(1050.0, 840.0, 537.0), rotation=0.1631, a=43.1,
          period=103_700.0, e=0.196, inc=28.2, node=122.2, peri=1.2,
          L0=201.0,
          note="An egg spinning in under four hours, with a ring."),
    _body("makemake", "Makemake", "dwarf", 715.0, "#b9836a",
          rotation=0.9511, a=45.4, period=111_900.0, e=0.161, inc=29.0,
          node=79.4, peri=14.2, L0=174.0,
          note="Reddish methane ice in the Kuiper belt."),
    _body("eris", "Eris", "dwarf", 1163.0, "#dfe3e8", rotation=1.08,
          a=67.86, period=203_830.0, e=0.4361, inc=44.04, node=35.95,
          peri=187.5, L0=27.5,
          note="More massive than Pluto, three times farther out."),
    # ----------------------------------------------------------- moons
    _body("moon", "Moon", "moon", 1737.4, "#9e9a94", parent="earth",
          a=384_400, period=27.3217, inc=5.145, phase=128.3,
          note="Maria, Tycho's rays and the great craters; the far side "
               "nearly bare."),
    _body("phobos", "Phobos", "moon", 13.0, "#6f645b", parent="mars",
          radii=(13.0, 11.4, 9.1), a=9376, period=0.31891,
          note="A potato 27 km long with the Stickney crater."),
    _body("deimos", "Deimos", "moon", 7.8, "#7b7169", parent="mars",
          radii=(7.8, 6.1, 5.2), a=23_463, period=1.26244,
          note="Mars' smaller, smoother outer moon."),
    _body("io", "Io", "moon", 1821.6, "#d8b74c", parent="jupiter",
          a=421_800, period=1.76914,
          note="Sulphur yellows and volcano rings: the most active "
               "body in the Solar System."),
    _body("europa", "Europa", "moon", 1560.8, "#d9cdb6", parent="jupiter",
          a=671_100, period=3.55118,
          note="An ice shell crossed by brown lineae over an ocean."),
    _body("ganymede", "Ganymede", "moon", 2634.1, "#9c8f7e",
          parent="jupiter", a=1_070_400, period=7.15455,
          note="The largest moon, bigger than Mercury; dark Galileo "
               "Regio on bright grooved terrain."),
    _body("callisto", "Callisto", "moon", 2410.3, "#625850",
          parent="jupiter", a=1_882_700, period=16.6890,
          note="Dark and saturated with craters; the Valhalla rings."),
    _body("amalthea", "Amalthea", "moon", 125.0, "#9b4a2f",
          parent="jupiter", radii=(125.0, 73.0, 64.0), a=181_400,
          period=0.49818, note="A red, irregular inner moon."),
    _body("mimas", "Mimas", "moon", 198.2, "#c8c6c2", parent="saturn",
          a=185_540, period=0.94242,
          note="The Herschel crater, a third of the moon across."),
    _body("enceladus", "Enceladus", "moon", 252.1, "#f2f4f6",
          parent="saturn", a=238_040, period=1.37022,
          note="Fresh ice and the four tiger stripes venting at the "
               "south pole."),
    _body("tethys", "Tethys", "moon", 531.0, "#dcd9d3", parent="saturn",
          a=294_670, period=1.88780,
          note="Odysseus, a crater 450 km wide, and Ithaca Chasma."),
    _body("dione", "Dione", "moon", 561.4, "#cfcac3", parent="saturn",
          a=377_420, period=2.73692,
          note="Wispy bright cliffs across the trailing hemisphere."),
    _body("rhea", "Rhea", "moon", 763.5, "#c6c1ba", parent="saturn",
          a=527_070, period=4.51750,
          note="Saturn's second largest moon, heavily cratered."),
    _body("titan", "Titan", "moon", 2574.7, "#d4912f", parent="saturn",
          a=1_221_870, period=15.9454,
          note="Orange haze over dark dune fields; the only moon with "
               "a thick atmosphere."),
    _body("hyperion", "Hyperion", "moon", 180.0, "#a89a8a",
          parent="saturn", radii=(180.0, 133.0, 103.0), a=1_481_000,
          period=21.2766, rotation=13.0,
          note="A sponge-like irregular moon tumbling chaotically."),
    _body("iapetus", "Iapetus", "moon", 734.5, "#d8d2c8", parent="saturn",
          a=3_560_840, period=79.3215,
          note="Two-toned — a dark leading face, bright trailing — with "
               "an equatorial ridge."),
    _body("miranda", "Miranda", "moon", 235.8, "#bdbbb8", parent="uranus",
          a=129_900, period=1.41348,
          note="Jumbled terrain and Verona Rupes, a 20 km cliff."),
    _body("ariel", "Ariel", "moon", 578.9, "#c4c2bf", parent="uranus",
          a=190_900, period=2.52038, note="The brightest Uranian moon."),
    _body("umbriel", "Umbriel", "moon", 584.7, "#6f6c69", parent="uranus",
          a=266_000, period=4.14418,
          note="Dark, with the bright ring of Wunda at its edge."),
    _body("titania", "Titania", "moon", 788.4, "#a89c92", parent="uranus",
          a=436_300, period=8.70587,
          note="The largest moon of Uranus, cut by long canyons."),
    _body("oberon", "Oberon", "moon", 761.4, "#9a8f86", parent="uranus",
          a=583_500, period=13.4632,
          note="Outermost of the big five, old and cratered."),
    _body("triton", "Triton", "moon", 1353.4, "#d5c8be", parent="neptune",
          a=354_760, period=-5.87685,
          note="Orbits backwards; a pink south polar cap of nitrogen "
               "ice with geysers."),
    _body("proteus", "Proteus", "moon", 218.0, "#6b6664", parent="neptune",
          radii=(218.0, 208.0, 201.0), a=117_650, period=1.12231,
          note="A dark, boxy inner moon."),
    _body("charon", "Charon", "moon", 606.0, "#b5aaa2", parent="pluto",
          a=19_591, period=6.38723,
          note="Half Pluto's size; Mordor Macula, a dark red pole."),
    _body("dysnomia", "Dysnomia", "moon", 350.0, "#8a8580", parent="eris",
          a=37_300, period=15.786, note="Eris' dark moon."),
]

BY_KEY = {b["key"]: b for b in BODIES}
PLANETS = [b for b in BODIES if b["kind"] == "planet"]
DWARFS = [b for b in BODIES if b["kind"] == "dwarf"]
MOONS = [b for b in BODIES if b["kind"] == "moon"]


def moons_of(key: str) -> list:
    return [m for m in MOONS if m["parent"] == key]


def planet_label(body: dict) -> str:
    """"Io (Jupiter)" for a moon, the plain name otherwise."""
    if body["kind"] == "moon":
        return f"{body['label']} ({BY_KEY[body['parent']]['label']})"
    return body["label"]


# --------------------------------------------------------------- orbits

def centre_coeffs(e: float):
    """The equation of the centre to third order, in degrees: true
    anomaly = M + c1 sin M + c2 sin 2M + c3 sin 3M."""
    deg = 180.0 / math.pi
    return ((2 * e - e ** 3 / 4) * deg, 1.25 * e * e * deg,
            13.0 / 12.0 * e ** 3 * deg)


def orbit_expressions(body: dict, days: str, dist: str) -> list:
    """(name, expression) pairs, in order, giving a Sun-orbiting body's
    position: mean anomaly, true anomaly, distance (*dist* is an
    expression of the AU distance ``r``, e.g. ``orbit * pow(r,
    compression)``), argument of latitude and px/py/pz in OpenSCAD
    syntax, exactly what `position` computes in Python."""
    c1, c2, c3 = centre_coeffs(body["e"])
    e = body["e"]
    return [
        ("M", f"{body['L0'] - body['peri']:.3f} + 360 * {days} / "
              f"{body['period']:.3f}"),
        ("nu", f"M + {c1:.4f} * sin(M) + {c2:.4f} * sin(2 * M) + "
               f"{c3:.4f} * sin(3 * M)"),
        ("r", f"{body['a'] * (1 - e * e):.5f} / (1 + {e:.5f} * cos(nu))"),
        ("dist", dist),
        ("u", f"nu + {body['peri'] - body['node']:.3f}"),
        ("px", f"dist * (cos({body['node']:.3f}) * cos(u) - "
               f"sin({body['node']:.3f}) * sin(u) * cos({body['inc']:.3f}))"),
        ("py", f"dist * (sin({body['node']:.3f}) * cos(u) + "
               f"cos({body['node']:.3f}) * sin(u) * cos({body['inc']:.3f}))"),
        ("pz", f"dist * sin(u) * sin({body['inc']:.3f})"),
    ]


def position(body: dict, days: float, scale=lambda r: r):
    """Heliocentric (x, y, z) of *body* *days* after J2000 in the
    ecliptic frame, the distance mapped through *scale* (identity =
    AU). The Python twin of `orbit_expressions`."""
    c1, c2, c3 = centre_coeffs(body["e"])
    e = body["e"]
    M = math.radians(body["L0"] - body["peri"] + 360 * days / body["period"])
    nu = M + math.radians(c1 * math.sin(M) + c2 * math.sin(2 * M)
                          + c3 * math.sin(3 * M))
    r = body["a"] * (1 - e * e) / (1 + e * math.cos(nu))
    dist = scale(r)
    u = nu + math.radians(body["peri"] - body["node"])
    node, inc = math.radians(body["node"]), math.radians(body["inc"])
    return (dist * (math.cos(node) * math.cos(u)
                    - math.sin(node) * math.sin(u) * math.cos(inc)),
            dist * (math.sin(node) * math.cos(u)
                    + math.cos(node) * math.sin(u) * math.cos(inc)),
            dist * math.sin(u) * math.sin(inc))


def spin(body: dict, days: float) -> float:
    """Degrees the body has turned about its pole since J2000."""
    return (body["phase"] + 360.0 * days / body["rotation"]) % 360.0
