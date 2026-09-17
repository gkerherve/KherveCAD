"""Every body of `solar_data` as a detailed globe (Qt-free):
`build_body(key, diameter_mm, fine)` returns one union — base sphere
(flattened to the body's polar radius, or an ellipsoid for an
irregular moon), then its features from `solar_surface`: Earth's map,
Mars' albedo regions, volcanoes, Valles Marineris and caps, Jupiter's
belts and the Great Red Spot, Saturn's rings, Uranus' and Neptune's
rings, the Moon's maria, craters and Tycho's rays, Io's volcano rings,
Europa's lineae, Iapetus' dark face and ridge, Enceladus' tiger
stripes, Titan's haze… Everything stands on the sphere, so the preview
is exact and each feature keeps its colour. Positions are IAU
latitude / east longitude, so a synchronous moon's 0° meridian faces
its planet. Not a survey: the features are the ones a reader
recognises, placed and sized from the published figures.

*fine* False (the orrery) drops the seeded crater scatters, the lines
and the finest patches and samples the Earth map every other cell.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import random

from . import solar_data as D
from . import solar_maps as M
from . import solar_surface as S
from .model import CadNode


class _Globe:
    """The body's radius in mm plus conversions for its features."""

    def __init__(self, body, diameter, fine):
        self.body = body
        self.r = float(diameter) / 2          # equatorial, mm
        self.k = self.r / body["radius"]      # mm per km
        self.fine = fine
        a, b, c = body["radii"]
        self.flat = c / a
        self.irregular = abs(b - a) > 1e-9
        self.parts = []

    def deg(self, km):
        return S.deg_of(km, self.body["radius"])

    def add(self, node):
        if node is not None:
            self.parts.append(node)

    # ---- features on the sphere (radius self.r) --------------------
    def base(self, colour=None, material="Plastic"):
        b = self.body
        if self.irregular:
            radii = [v * self.k for v in b["radii"]]
            self.add(S.ellipsoid(b["label"], radii, colour or b["colour"],
                                 material))
        else:
            self.add(S.sphere(b["label"], self.r, colour or b["colour"],
                              material))

    def bands(self, table, material="Plastic", lift=1.0):
        self.add(S.bands(self.body["label"] + " bands", self.r, table,
                         material, lift))

    def cap(self, lat, colour, lift=1.003):
        north = lat > 0
        name = ("North" if north else "South") + " polar cap"
        self.add(S.band(name, self.r, lat, 90.0 if north else -90.0,
                        colour, lift=lift))

    def patch(self, name, lat, lon, ns, ew, colour, bulge=0.005):
        self.add(S.patch(name, self.r, lat, lon, ns, ew, colour, bulge))

    def crater(self, name, lat, lon, km, colour, rim=None):
        self.add(S.crater(name, self.r, lat, lon, self.deg(km), colour,
                          rim=rim))

    def mountain(self, name, lat, lon, base_km, height, colour):
        self.add(S.mountain(name, self.r, lat, lon, self.deg(base_km),
                            height * self.r, colour))

    def line(self, name, start, end, width, colour, step=8.0):
        if self.fine:
            self.add(S.arc_line(name, self.r, start, end, width * self.r,
                                colour, step_deg=step))

    def scatter(self, count, seed, km_min, km_max, colour, lat_max=90.0):
        """Seeded random craters, the cratered look of an old surface
        (fine detail only)."""
        if not self.fine:
            return
        rng = random.Random(seed)
        node = CadNode("union", "Craters")
        for i in range(count):
            lat = math.degrees(math.asin(rng.uniform(-1, 1)))
            lat = max(-lat_max, min(lat_max, lat))
            lon = rng.uniform(-180, 180)
            km = rng.uniform(km_min, km_max)
            node.add(S.crater(f"Crater {i + 1}", self.r, lat, lon,
                              self.deg(km), colour))
        self.add(node)

    def haze(self, factor, colour, alpha):
        self.add(S.haze("Atmosphere", self.r * factor, colour, alpha))

    def rings(self, spans_km, thickness=0.004):
        self.add(S.rings(self.body["label"] + " rings",
                         [(a * self.k, b * self.k, c, al)
                          for a, b, c, al in spans_km],
                         thickness * self.r))

    def pole_stripe(self, name, offset_deg, half_len_deg, width, colour,
                    south=True, step=5.0):
        """A straight streak across the polar region, *offset_deg*
        beside the pole (Enceladus' tiger stripes)."""
        if not self.fine:
            return
        pts = []
        n = max(int(2 * half_len_deg / step), 1)
        for i in range(n + 1):
            x = -half_len_deg + 2 * half_len_deg * i / n
            rho = math.hypot(x, offset_deg)
            phi = math.degrees(math.atan2(offset_deg, x))
            pts.append(((-90.0 + rho) if south else (90.0 - rho), phi))
        node = CadNode("union", name)
        for i in range(n):
            node.add(S.arc_line(f"{name} {i + 1}", self.r, pts[i],
                                pts[i + 1], width * self.r, colour,
                                step_deg=step))
        self.add(node)

    def build(self):
        node = CadNode("union", self.body["label"])
        for part in self.parts:
            node.add(part)
        return S.flatten(node, self.flat) if not self.irregular else node


# ---------------------------------------------------------- the bodies

def _sun(g):
    g.base(material="Emissive")
    for i, (lat, lon) in enumerate([(-18, 40), (12, -70), (-8, 150),
                                    (22, -150)]):
        g.patch(f"Sunspot group {i + 1}", lat, lon, 4, 7, "#b8621a",
                bulge=0.002)
    if g.fine:
        g.haze(1.06, "#ffe6a0", 0.15)


def _mercury(g):
    g.base()
    g.patch("Caloris basin floor", 30.5, -170.2, 34, 40, "#a19b93",
            bulge=0.002)
    g.crater("Caloris basin", 30.5, -170.2, 1550, "#78736c")
    g.crater("Rembrandt", -33, 88, 715, "#7a756e")
    g.crater("Beethoven", -20.8, -124, 630, "#7a756e")
    g.crater("Tolstoj", -16, -164, 390, "#7a756e")
    for i, (lat, lon) in enumerate([(-45, 60), (10, 20), (55, -60)]):
        g.patch(f"Dark plain {i + 1}", lat, lon, 20, 35, "#767069",
                bulge=0.002)
    g.scatter(22, 1, 120, 320, "#a09a92")


def _venus(g):
    g.base()
    g.bands([(90, 60, "#e9d4a4"), (60, 40, "#e0c894"), (40, 22, "#ead6aa"),
             (22, 8, "#dfc48e"), (8, -8, "#ecd9ae"), (-8, -22, "#dfc48e"),
             (-22, -40, "#ead6aa"), (-40, -60, "#e0c894"),
             (-60, -90, "#e9d4a4")], lift=1.0)
    g.parts.pop(0)                       # the bands are the globe
    for i, (lat, lon) in enumerate([(30, 0), (-30, 120), (10, -110)]):
        g.patch(f"Cloud vortex {i + 1}", lat, lon, 12, 40, "#f0dfb6",
                bulge=0.002)


def _earth(g):
    g.base(M.EARTH_OCEAN)
    g.add(S.map_shells("Land", g.r, M.EARTH, M.EARTH_PALETTE,
                       skip=1 if g.fine else 2))
    g.haze(1.03, "#9ec5ff", 0.16)


def _mars(g):
    g.base()
    dark = "#7b4423"
    for name, lat, lon, ns, ew in [
            ("Syrtis Major", 10, 70, 20, 26), ("Sinus Meridiani", -3, 3,
                                                8, 22),
            ("Mare Erythraeum", -25, -25, 18, 40), ("Solis Lacus", -26, -90,
                                                    12, 18),
            ("Mare Sirenum", -30, -160, 14, 50), ("Mare Cimmerium", -20,
                                                  -140, 14, 40),
            ("Mare Tyrrhenum", -20, 105, 15, 30), ("Mare Acidalium", 45,
                                                   -30, 20, 35),
            ("Aurorae Sinus", -12, -50, 10, 20), ("Sabaeus Sinus", -8, 20,
                                                  8, 25)]:
        g.patch(name, lat, lon, ns, ew, dark, bulge=0.002)
    g.patch("Utopia Planitia", 45, 110, 15, 40, "#a5522a", bulge=0.002)
    g.patch("Hellas Planitia", -42, 70, 22, 30, "#d99a68", bulge=0.002)
    g.patch("Arabia Terra", 20, 20, 18, 30, "#d08a55", bulge=0.002)
    g.line("Valles Marineris", (-14, -95), (-8, -40), 0.006, "#5a2e15")
    g.mountain("Olympus Mons", 18.65, -134, 600, 0.03, "#cd7a45")
    g.mountain("Ascraeus Mons", 11.8, -104, 400, 0.02, "#cd7a45")
    g.mountain("Pavonis Mons", 0.8, -113, 400, 0.02, "#cd7a45")
    g.mountain("Arsia Mons", -8.3, -121, 400, 0.02, "#cd7a45")
    g.mountain("Elysium Mons", 25, 147, 240, 0.015, "#cd7a45")
    for name, lat, lon, km in [("Huygens", -14, 55.6, 470),
                               ("Schiaparelli", -2.7, 16.7, 460),
                               ("Cassini", 23.4, 32.1, 415),
                               ("Antoniadi", 21.5, 61, 380),
                               ("Newton", -40.8, -158, 300),
                               ("Herschel", -14.5, 130, 300),
                               ("Lyot", 50.5, 29.3, 236)]:
        g.crater(name, lat, lon, km, "#d38a5c")
    g.cap(82, "#f4f3ef")
    g.cap(-86, "#f4f3ef")


def _jupiter(g):
    g.bands([(90, 55, "#a99680"), (55, 45, "#cbb99f"), (45, 36, "#b0957a"),
             (36, 31, "#dccbb1"), (31, 24, "#a88c6e"), (24, 18, "#e3d5bb"),
             (18, 7, "#9c6b4b"), (7, -7, "#efe3cb"), (-7, -21, "#a5714f"),
             (-21, -27, "#e0d1b6"), (-27, -33, "#ab8f72"),
             (-33, -42, "#d5c4a8"), (-42, -52, "#b3987b"),
             (-52, -90, "#a99680")])
    g.patch("Great Red Spot", -22, -30, 12, 22, "#c65a3c", bulge=0.004)
    for i, lon in enumerate((60, 95, 130)):
        g.patch(f"White oval {i + 1}", -33, lon, 4, 7, "#f2ebdc",
                bulge=0.002)


def _saturn(g):
    g.bands([(90, 72, "#cbbd94"), (72, 55, "#ddcda2"), (55, 40, "#d3c092"),
             (40, 25, "#e5d4a9"), (25, 12, "#dcc99c"), (12, -12, "#ead9b0"),
             (-12, -25, "#dcc99c"), (-25, -40, "#e5d4a9"),
             (-40, -55, "#d3c092"), (-55, -72, "#ddcda2"),
             (-72, -90, "#cbbd94")])
    g.rings([(74658, 92000, "#8f8470", 0.55), (92000, 117580, "#d6c49e",
                                                1.0),
             (122170, 136775, "#c4b38a", 0.9), (139800, 140500, "#cdbf9f",
                                                 0.6)])


def _uranus(g):
    g.base()
    g.cap(60, "#b6e3e8", lift=1.002)
    g.cap(-60, "#b6e3e8", lift=1.002)
    g.rings([(a - 130, a + 130, "#5b5b5b", 0.75)
             for a in (41837, 42234, 42571, 44718, 45661, 47176, 47627,
                       48300)]
            + [(50900, 51400, "#6a6a6a", 0.85)], thickness=0.003)


def _neptune(g):
    g.base()
    g.cap(50, "#4867cf", lift=1.002)
    g.add(S.band("South band", g.r, -30, -45, "#2f4bb3", lift=1.002))
    g.patch("Great Dark Spot", -20, 30, 8, 16, "#223a8f", bulge=0.004)
    g.patch("Scooter", -42, 40, 3, 6, "#e8ecf8", bulge=0.003)
    g.rings([(41900, 42900, "#6a6f80", 0.35), (53100, 53400, "#7a7f90", 0.5),
             (62800, 63100, "#8a8fa0", 0.6)], thickness=0.003)


def _pluto(g):
    g.base()
    g.patch("Tombaugh Regio, west lobe", 20, 170, 32, 26, "#efe6d6",
            bulge=0.003)
    g.patch("Tombaugh Regio, east lobe", 14, -165, 26, 22, "#efe6d6",
            bulge=0.003)
    g.patch("Cthulhu Macula", -5, 120, 28, 70, "#5a3a2c", bulge=0.002)
    g.patch("Belton Regio", -5, 30, 22, 40, "#6b4534", bulge=0.002)
    g.cap(62, "#d8c4a8", lift=1.002)


def _ceres(g):
    g.base()
    g.patch("Occator bright spot", 20, -121, 3, 3, "#f2f2f0", bulge=0.008)
    g.mountain("Ahuna Mons", -10, -44, 20, 0.02, "#a4a19c")
    g.crater("Kerwan", -11, 124, 280, "#a09d98")
    g.scatter(14, 3, 40, 120, "#a5a29d")


def _haumea(g):
    g.base()
    g.rings([(2250, 2320, "#7a7a7a", 0.6)], thickness=0.01)


def _makemake(g):
    g.base()
    for i, (lat, lon) in enumerate([(20, 30), (-25, -100)]):
        g.patch(f"Dark region {i + 1}", lat, lon, 14, 24, "#8c5d48",
                bulge=0.002)


def _eris(g):
    g.base()


# ---------------------------------------------------------------- moons

def _moon(g):
    g.base()
    mare = "#66625e"
    for name, lat, lon, ns, ew in [
            ("Mare Imbrium", 33, -16, 36, 40), ("Mare Serenitatis", 28,
                                                18, 23, 24),
            ("Mare Tranquillitatis", 8, 31, 26, 30),
            ("Mare Fecunditatis", -8, 51, 30, 26),
            ("Mare Nectaris", -15, 35, 12, 12), ("Mare Crisium", 17, 59,
                                                 16, 20),
            ("Mare Nubium", -21, -17, 22, 24), ("Mare Humorum", -24, -39,
                                                13, 14),
            ("Oceanus Procellarum", 18, -57, 70, 45),
            ("Mare Frigoris", 56, 1, 8, 55), ("Mare Vaporum", 13, 3, 8, 9),
            ("Mare Cognitum", -10, -23, 12, 12),
            ("Mare Moscoviense", 27, 148, 9, 10),
            ("Mare Orientale", -19, -93, 11, 11),
            ("Mare Smythii", 1, 87, 12, 12), ("Mare Marginis", 13, 86,
                                              12, 12),
            ("Mare Humboldtianum", 57, 81, 9, 12),
            ("Mare Ingenii", -34, 163, 10, 10)]:
        g.patch(name, lat, lon, ns, ew, mare, bulge=0.002)
    rim = "#b5b1ab"
    for name, lat, lon, km in [
            ("Tycho", -43.3, -11.4, 86), ("Copernicus", 9.6, -20.1, 93),
            ("Kepler", 8.1, -38, 32), ("Aristarchus", 23.7, -47.4, 40),
            ("Plato", 51.6, -9.4, 101), ("Clavius", -58.4, -14.4, 225),
            ("Grimaldi", -5.5, -68.3, 170), ("Langrenus", -8.9, 61.1, 132),
            ("Petavius", -25.1, 60.4, 177), ("Theophilus", -11.4, 26.4,
                                             100),
            ("Archimedes", 29.7, -4, 83), ("Eratosthenes", 14.5, -11.3,
                                           58),
            ("Ptolemaeus", -9.3, -1.9, 153), ("Alphonsus", -13.4, -2.8,
                                              119),
            ("Arzachel", -18.2, -1.9, 97), ("Schickard", -44.3, -55.3,
                                            227),
            ("Posidonius", 31.8, 29.9, 95), ("Cleomedes", 27.7, 55.5, 126),
            ("Endymion", 53.6, 56.5, 125), ("Tsiolkovskiy", -20.4, 129.1,
                                            185),
            ("Hertzsprung", 1.5, -129, 570), ("Korolev", -4, -157.4, 437),
            ("Apollo", -36.1, -151.8, 537), ("Mendeleev", 5.7, 140.9, 313),
            ("Schrodinger", -75, 132.4, 312), ("Bailly", -66.5, -69.1,
                                               303)]:
        if g.fine or km >= 150:
            g.crater(name, lat, lon, km, rim)
    for i, end in enumerate([(-10, 10), (-25, -45), (-70, 20),
                             (-30, 25), (-58, -40), (-15, -30)]):
        g.line(f"Tycho ray {i + 1}", (-43.3, -11.4), end, 0.004, "#bdb9b3")
    g.scatter(18, 5, 60, 140, "#adaaa4")


def _phobos(g):
    g.base()
    a, b, c = (v * g.k for v in g.body["radii"])
    # Stickney at 1° N 49° W: the ellipsoid's radius that way
    lat, lon = 1.0, -49.0
    d = S.point(1.0, lat, lon)
    rr = 1 / math.sqrt((d[0] / a) ** 2 + (d[1] / b) ** 2 + (d[2] / c) ** 2)
    g.add(S.crater("Stickney", rr, lat, lon, g.deg(9.0), "#5c534b"))


def _deimos(g):
    g.base()


def _io(g):
    g.base()
    g.cap(62, "#b79a45", lift=1.002)
    g.cap(-62, "#b79a45", lift=1.002)
    for name, lat, lon, ns, ew in [("Loki Patera", 13, -51, 6, 8),
                                   ("Babbar Patera", -40, -88, 6, 8),
                                   ("Prometheus", -2, 153, 4, 4),
                                   ("Amaterasu Patera", 38, -52, 4, 5)]:
        g.patch(name, lat, lon, ns, ew, "#3e2e1e", bulge=0.002)
    g.crater("Pele plume ring", -18, -105, 1200, "#b5432c", rim=0.02 * g.r)
    for i, (lat, lon, ns, ew) in enumerate([(10, 40, 10, 15),
                                            (-30, -160, 12, 20),
                                            (20, 100, 8, 12)]):
        g.patch(f"Sulphur dioxide frost {i + 1}", lat, lon, ns, ew,
                "#f2eee0", bulge=0.002)


def _europa(g):
    g.base()
    line = "#8f5a3c"
    for i, (a, b) in enumerate([((-40, -30), (30, 60)),
                                ((10, -120), (-25, -20)),
                                ((50, 100), (-10, 170)),
                                ((-30, 120), (35, -170)),
                                ((-60, 0), (10, 60)), ((20, -60), (60, 20))]):
        g.line(f"Linea {i + 1}", a, b, 0.004, line)
    g.patch("Conamara Chaos", 10, -87, 8, 10, "#b8946f", bulge=0.002)
    g.patch("Thera Macula", -47, -180, 8, 10, "#b8946f", bulge=0.002)
    g.crater("Tyre", 34, -146, 140, "#a37a58")
    g.crater("Callanish", -16, -26, 100, "#a37a58")


def _ganymede(g):
    g.base()
    dark = "#5f5248"
    for name, lat, lon, ns, ew in [("Galileo Regio", 35, 145, 36, 40),
                                   ("Marius Regio", 8, -170, 30, 25),
                                   ("Perrine Regio", 37, -30, 15, 25),
                                   ("Nicholson Regio", -25, -25, 30, 40),
                                   ("Barnard Regio", -22, 10, 20, 25)]:
        g.patch(name, lat, lon, ns, ew, dark, bulge=0.002)
    g.cap(65, "#c9c2b6", lift=1.002)
    g.cap(-65, "#c9c2b6", lift=1.002)
    g.crater("Osiris", -38, -166, 107, "#d6cfc4")
    g.crater("Tros", 11, -27, 94, "#d6cfc4")
    g.scatter(10, 7, 60, 110, "#c2b9ad")


def _callisto(g):
    g.base()
    bright = "#8f857a"
    for i, d in enumerate((5, 10, 15, 20)):
        g.add(S.crater(f"Valhalla ring {i + 1}", g.r, 14, -56, d, bright,
                       rim=0.004 * g.r))
    for i, d in enumerate((4, 8, 12)):
        g.add(S.crater(f"Asgard ring {i + 1}", g.r, 30, -140, d, bright,
                       rim=0.004 * g.r))
    g.scatter(28, 9, 60, 160, "#8a8078")


def _amalthea(g):
    g.base()


def _mimas(g):
    g.base()
    g.crater("Herschel", 0, -111, 139, "#b5b2ad")
    g.mountain("Herschel central peak", 0, -111, 30, 0.03, "#b5b2ad")
    g.scatter(20, 11, 20, 45, "#b9b6b1")


def _enceladus(g):
    g.base(material="Plastic")
    for i, off in enumerate((-12.0, -4.0, 4.0, 12.0)):
        g.pole_stripe(f"Tiger stripe {i + 1}", off, 15.0, 0.004, "#9fc2e0")


def _tethys(g):
    g.base()
    g.crater("Odysseus", 32.8, -128.9, 445, "#c9c5be")
    g.line("Ithaca Chasma", (-55, 20), (55, 0), 0.005, "#b9b4ab")
    g.scatter(15, 13, 40, 110, "#c9c5be")


def _dione(g):
    g.base()
    for i, (a, b) in enumerate([((-40, -110), (40, -70)),
                                ((-30, -95), (35, -60)),
                                ((-50, -80), (20, -50)),
                                ((-10, -120), (50, -85))]):
        g.line(f"Wispy cliff {i + 1}", a, b, 0.003, "#f0eeea")
    g.crater("Amata", 7, -84, 240, "#bcb6ae")
    g.crater("Aeneas", 26, -47, 155, "#bcb6ae")
    g.scatter(12, 15, 40, 100, "#bcb6ae")


def _rhea(g):
    g.base()
    g.crater("Tirawa", 34.2, -151.7, 360, "#b6b0a8")
    g.crater("Mamaldi", -17, -175, 480, "#b6b0a8")
    for i, (a, b) in enumerate([((-30, -100), (40, -60)),
                                ((-45, -85), (30, -40))]):
        g.line(f"Wispy cliff {i + 1}", a, b, 0.003, "#e6e2dc")
    g.scatter(24, 17, 50, 130, "#b6b0a8")


def _titan(g):
    g.base()
    dune = "#7c4f22"
    g.patch("Shangri-La", -10, -165, 25, 60, dune, bulge=0.002)
    g.patch("Belet", -5, 105, 20, 50, dune, bulge=0.002)
    g.patch("Fensal-Aztlan", 5, -20, 15, 50, dune, bulge=0.002)
    g.patch("Xanadu", -15, -100, 25, 40, "#e2b26a", bulge=0.002)
    g.patch("Kraken Mare", 68, 50, 12, 30, "#3b4a5b", bulge=0.002)
    g.patch("Ligeia Mare", 78, 112, 6, 12, "#3b4a5b", bulge=0.002)
    g.haze(1.05, "#e8a94a", 0.28)


def _hyperion(g):
    g.base()


def _iapetus(g):
    g.base()
    dark = "#3d2a1c"
    zone = S._revolve("Cassini Regio", S._arc(g.r * 1.002, -52.0, 52.0),
                      angle=170.0)
    rot = CadNode("rotate", "Cassini Regio", dict(x=0.0, y=0.0, z=-175.0))
    rot.add(S.col("Cassini Regio", dark, zone))
    g.add(rot)
    ridge = S._revolve("Equatorial ridge", S._arc(g.r * 1.026, -2.0, 2.0)
                       + [(0.0, g.r * 0.03), (0.0, -g.r * 0.03)],
                       angle=150.0)
    rot = CadNode("rotate", "Equatorial ridge", dict(x=0.0, y=0.0,
                                                     z=-165.0))
    rot.add(S.col("Equatorial ridge", "#4a3626", ridge))
    g.add(rot)
    g.scatter(12, 19, 60, 200, "#c9c3b9", lat_max=70)


def _miranda(g):
    g.base()
    for name, lat, lon, ns, ew in [("Arden Corona", -15, -40, 30, 30),
                                   ("Inverness Corona", -70, -20, 25, 25),
                                   ("Elsinore Corona", -20, 100, 30, 30)]:
        g.patch(name, lat, lon, ns, ew, "#8f8c88", bulge=0.002)
    g.line("Verona Rupes", (-45, -25), (-35, -5), 0.005, "#e5e3e0")


def _ariel(g):
    g.base()
    for i, (a, b) in enumerate([((-30, -100), (20, -40)),
                                ((-50, -20), (10, 30)),
                                ((0, 60), (40, 130))]):
        g.line(f"Chasma {i + 1}", a, b, 0.004, "#9d9a96")
    g.scatter(10, 21, 30, 70, "#d0cecb")


def _umbriel(g):
    g.base()
    g.crater("Wunda", 8, -86, 131, "#d9d5cf", rim=0.012 * g.r)
    g.crater("Vuver", -4, 49, 98, "#8a8784")
    g.scatter(12, 23, 40, 100, "#7f7c79")


def _titania(g):
    g.base()
    g.line("Messina Chasma", (-45, 10), (-20, 60), 0.005, "#7f756c")
    g.crater("Gertrude", -16, -73, 326, "#b9ada3")
    g.scatter(10, 25, 40, 120, "#b9ada3")


def _oberon(g):
    g.base()
    g.crater("Hamlet", -46, -44.4, 206, "#aba09a")
    g.patch("Hamlet floor", -46, -44.4, 8, 10, "#6d6560", bulge=0.001)
    g.line("Mommur Chasma", (-10, -80), (30, -30), 0.004, "#7d746d")
    g.scatter(15, 27, 50, 150, "#aba09a")


def _triton(g):
    g.base()
    g.add(S.band("South polar cap", g.r, -90, -15, "#e9c9c0", lift=1.002))
    for i, (lat, lon) in enumerate([(20, 20), (35, -40), (10, 80),
                                    (30, 140)]):
        g.patch(f"Cantaloupe terrain {i + 1}", lat, lon, 14, 20, "#c7b6a8",
                bulge=0.002)
    for i, lon in enumerate((-30, 10, 50, 100)):
        g.line(f"Geyser streak {i + 1}", (-52, lon), (-40, lon + 12),
               0.003, "#7d6b62")


def _proteus(g):
    g.base()


def _charon(g):
    g.base()
    g.cap(70, "#6c3b2c")
    g.patch("Vulcan Planum", -25, 0, 40, 70, "#aca19a", bulge=0.001)


def _dysnomia(g):
    g.base()


BUILDERS = {
    "sun": _sun, "mercury": _mercury, "venus": _venus, "earth": _earth,
    "mars": _mars, "jupiter": _jupiter, "saturn": _saturn,
    "uranus": _uranus, "neptune": _neptune, "pluto": _pluto,
    "ceres": _ceres, "haumea": _haumea, "makemake": _makemake,
    "eris": _eris, "moon": _moon, "phobos": _phobos, "deimos": _deimos,
    "io": _io, "europa": _europa, "ganymede": _ganymede,
    "callisto": _callisto, "amalthea": _amalthea, "mimas": _mimas,
    "enceladus": _enceladus, "tethys": _tethys, "dione": _dione,
    "rhea": _rhea, "titan": _titan, "hyperion": _hyperion,
    "iapetus": _iapetus, "miranda": _miranda, "ariel": _ariel,
    "umbriel": _umbriel, "titania": _titania, "oberon": _oberon,
    "triton": _triton, "proteus": _proteus, "charon": _charon,
    "dysnomia": _dysnomia,
}


def build_body(key: str, diameter: float, fine: bool = True) -> CadNode:
    """*key*'s globe, *diameter* mm across its equator (the longest
    axis of an irregular moon), as one union named after the body."""
    body = D.BY_KEY[key]
    g = _Globe(body, diameter, fine)
    BUILDERS[key](g)
    return g.build()
