"""The standard crystal library of the Crystal Builder (Qt-free).

Thirty-two structures chemists and materials scientists reach for
first, in five families, each with its room-temperature lattice
parameters, every atom of the conventional cell, the coordination
polyhedra worth drawing and — for the tests — its density and nearest
distance, so a slipped coordinate cannot hide. Structure prototypes
(FCC, diamond, rock salt, wurtzite, rutile…) are written once and
instanced per element.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from .crystal import Crystal

METALS, SEMI, SALTS, OXIDES, CARBON = (
    "Metals", "Semiconductors", "Ionic salts", "Oxides",
    "Carbon & nitrides")
#: the order the dialog lists them in
CATEGORIES = (METALS, SEMI, SALTS, OXIDES, CARBON)

_FCC = [(0.0, 0.0, 0.0), (0.0, 0.5, 0.5), (0.5, 0.0, 0.5), (0.5, 0.5, 0.0)]
_SRC = "room-temperature lattice parameters; X-ray density"


def _shift(sites, d):
    return [tuple((s[i] + d[i]) % 1.0 for i in range(3)) for s in sites]


def _put(element, sites):
    return [(element, *s) for s in sites]


def _cubic(key, name, formula, category, group, a, atoms, density, bonds,
           polyhedra=None):
    return Crystal(key, name, formula, category, "cubic", group, a, a, a,
                   atoms=atoms, polyhedra=polyhedra, density=density,
                   bonds=bonds, source=_SRC)


def _hexagonal(key, name, formula, category, group, a, c, atoms, density,
               bonds, polyhedra=None, system="hexagonal"):
    return Crystal(key, name, formula, category, system, group, a, a, c,
                   gamma=120.0, atoms=atoms, polyhedra=polyhedra,
                   density=density, bonds=bonds, source=_SRC)


def _poly(centre, ligand, cutoff, sites=None):
    return {"centre": centre, "ligand": ligand, "cutoff": cutoff,
            "sites": sites}


# ------------------------------------------------------------ prototypes
def fcc(key, name, el, a, density, nn):
    return _cubic(key, name, el, METALS, "Fm-3m (225), FCC", a,
                  _put(el, _FCC), density, [(el, el, nn)])


def bcc(key, name, el, a, density, nn):
    return _cubic(key, name, el, METALS, "Im-3m (229), BCC", a,
                  _put(el, [(0, 0, 0), (0.5, 0.5, 0.5)]), density,
                  [(el, el, nn)])


def hcp(key, name, el, a, c, density, nn):
    return _hexagonal(key, name, el, METALS, "P6_3/mmc (194), HCP", a, c,
                      _put(el, [(1 / 3, 2 / 3, 0.25), (2 / 3, 1 / 3, 0.75)]),
                      density, [(el, el, nn)])


def diamond(key, name, el, a, density, nn, category=SEMI):
    atoms = _put(el, _FCC) + _put(el, _shift(_FCC, (0.25, 0.25, 0.25)))
    # one sublattice as centres: corner-sharing tetrahedra, as in zinc
    # blende (every atom as a centre would overlap them)
    return _cubic(key, name, el, category, "Fd-3m (227), diamond", a,
                  atoms, density, [(el, el, nn)],
                  _poly(el, el, nn * 1.1, sites=list(range(4))))


def zinc_blende(key, name, formula, cation, anion, a, density, nn):
    atoms = _put(cation, _FCC) + _put(anion,
                                      _shift(_FCC, (0.25, 0.25, 0.25)))
    return _cubic(key, name, formula, SEMI, "F-43m (216), zinc blende", a,
                  atoms, density, [(cation, anion, nn)],
                  _poly(cation, anion, nn * 1.1))


def rock_salt(key, name, formula, cation, anion, a, density, nn,
              category=SALTS):
    atoms = _put(cation, _FCC) + _put(anion, _shift(_FCC, (0.5, 0.0, 0.0)))
    return _cubic(key, name, formula, category, "Fm-3m (225), rock salt",
                  a, atoms, density, [(cation, anion, nn)],
                  _poly(cation, anion, nn * 1.1))


def fluorite(key, name, formula, cation, anion, a, density, nn,
             category=SALTS):
    atoms = (_put(cation, _FCC)
             + _put(anion, _shift(_FCC, (0.25, 0.25, 0.25)))
             + _put(anion, _shift(_FCC, (0.75, 0.75, 0.75))))
    return _cubic(key, name, formula, category, "Fm-3m (225), fluorite",
                  a, atoms, density, [(cation, anion, nn)],
                  _poly(cation, anion, nn * 1.1))


def wurtzite(key, name, formula, cation, anion, a, c, u, density, nn,
             category=SEMI):
    atoms = (_put(cation, [(1 / 3, 2 / 3, 0.0), (2 / 3, 1 / 3, 0.5)])
             + _put(anion, [(1 / 3, 2 / 3, u), (2 / 3, 1 / 3, 0.5 + u)]))
    return _hexagonal(key, name, formula, category, "P6_3mc (186), "
                      "wurtzite", a, c, atoms, density, [(cation, anion, nn)],
                      _poly(cation, anion, nn * 1.1))


def rutile(key, name, formula, metal, a, c, u, density, nn):
    atoms = (_put(metal, [(0, 0, 0), (0.5, 0.5, 0.5)])
             + _put("O", [(u, u, 0), (1 - u, 1 - u, 0),
                          (0.5 + u, 0.5 - u, 0.5), (0.5 - u, 0.5 + u, 0.5)]))
    return Crystal(key, name, formula, OXIDES, "tetragonal",
                   "P4_2/mnm (136), rutile", a, a, c, atoms=atoms,
                   polyhedra=_poly(metal, "O", 2.2), density=density,
                   bonds=[(metal, "O", nn)], source=_SRC)


def _quartz():
    """alpha-quartz, P3_2 21: Si 3a (x, 0, 2/3), O 6c — the general
    positions applied to the asymmetric unit (Levien et al. 1980)."""
    def orbit(p):
        x, y, z = p
        out = []
        for q in ((x, y, z), (-y, x - y, z + 2 / 3), (-x + y, -x, z + 1 / 3),
                  (y, x, -z), (x - y, -y, -z + 1 / 3),
                  (-x, -x + y, -z + 2 / 3)):
            q = tuple(round(v % 1.0, 6) % 1.0 for v in q)
            if not any(max(min(abs(u - v), 1 - abs(u - v))
                           for u, v in zip(q, r)) < 1e-4 for r in out):
                out.append(q)
        return out
    atoms = (_put("Si", orbit((0.4697, 0.0, 2 / 3)))
             + _put("O", orbit((0.4135, 0.2669, 0.1191 + 2 / 3))))
    return _hexagonal("quartz", "SiO2 alpha-quartz", "SiO2", OXIDES,
                      "P3_2 21 (154)", 4.9134, 5.4052, atoms, 2.649,
                      [("Si", "O", 1.605)], _poly("Si", "O", 1.8),
                      system="trigonal")


def _anatase():
    a, c, z = 3.7845, 9.5143, 0.2081
    ti = [(0, 0, 0), (0.5, 0.5, 0.5), (0, 0.5, 0.25), (0.5, 0, 0.75)]
    o = [(0, 0, z), (0, 0, -z), (0.5, 0.5, 0.5 + z), (0.5, 0.5, 0.5 - z),
         (0, 0.5, 0.25 + z), (0, 0.5, 0.25 - z), (0.5, 0, 0.75 + z),
         (0.5, 0, 0.75 - z)]
    atoms = _put("Ti", ti) + _put("O", _shift(o, (0, 0, 0)))
    return Crystal("anatase", "TiO2 anatase", "TiO2", OXIDES, "tetragonal",
                   "I4_1/amd (141)", a, a, c, atoms=atoms,
                   polyhedra=_poly("Ti", "O", 2.1), density=3.893,
                   bonds=[("Ti", "O", 1.934)], source=_SRC)


def _perovskite():
    atoms = (_put("Sr", [(0, 0, 0)]) + _put("Ti", [(0.5, 0.5, 0.5)])
             + _put("O", [(0.5, 0.5, 0), (0.5, 0, 0.5), (0, 0.5, 0.5)]))
    return _cubic("srtio3", "SrTiO3 perovskite", "SrTiO3", OXIDES,
                  "Pm-3m (221), perovskite", 3.905, atoms, 5.117,
                  [("Ti", "O", 1.9525)], _poly("Ti", "O", 2.1))


def _cscl():
    atoms = _put("Cs", [(0, 0, 0)]) + _put("Cl", [(0.5, 0.5, 0.5)])
    return _cubic("cscl", "CsCl caesium chloride", "CsCl", SALTS,
                  "Pm-3m (221), CsCl", 4.123, atoms, 3.988,
                  [("Cs", "Cl", 3.571)], _poly("Cs", "Cl", 3.8))


def _graphite():
    atoms = _put("C", [(0, 0, 0.25), (0, 0, 0.75), (1 / 3, 2 / 3, 0.25),
                       (2 / 3, 1 / 3, 0.75)])
    return _hexagonal("graphite", "Graphite", "C", CARBON,
                      "P6_3/mmc (194), graphite", 2.464, 6.711, atoms,
                      2.261, [("C", "C", 1.4226)])


def _hbn():
    atoms = (_put("B", [(1 / 3, 2 / 3, 0.25), (2 / 3, 1 / 3, 0.75)])
             + _put("N", [(2 / 3, 1 / 3, 0.25), (1 / 3, 2 / 3, 0.75)]))
    return _hexagonal("hbn", "h-BN hexagonal boron nitride", "BN", CARBON,
                      "P6_3/mmc (194), h-BN", 2.504, 6.661, atoms, 2.279,
                      [("B", "N", 1.4457)])


def _po():
    return _cubic("po", "Polonium (simple cubic)", "Po", METALS,
                  "Pm-3m (221), simple cubic", 3.359, _put("Po", [(0, 0, 0)]),
                  9.156, [("Po", "Po", 3.359)])


_ALL = [
    fcc("cu", "Copper", "Cu", 3.6149, 8.935, 2.556),
    fcc("al", "Aluminium", "Al", 4.0495, 2.699, 2.863),
    fcc("au", "Gold", "Au", 4.0782, 19.29, 2.884),
    fcc("ag", "Silver", "Ag", 4.0853, 10.50, 2.889),
    fcc("ni", "Nickel", "Ni", 3.5240, 8.908, 2.492),
    fcc("pt", "Platinum", "Pt", 3.9242, 21.44, 2.775),
    bcc("fe", "Iron (alpha)", "Fe", 2.8665, 7.874, 2.482),
    bcc("w", "Tungsten", "W", 3.1652, 19.25, 2.741),
    _po(),
    hcp("mg", "Magnesium", "Mg", 3.2094, 5.2108, 1.737, 3.197),
    hcp("ti", "Titanium (alpha)", "Ti", 2.9508, 4.6855, 4.499, 2.896),
    hcp("zn", "Zinc", "Zn", 2.6649, 4.9468, 7.136, 2.665),
    diamond("si", "Silicon", "Si", 5.4310, 2.329, 2.352),
    diamond("ge", "Germanium", "Ge", 5.6579, 5.327, 2.450),
    zinc_blende("gaas", "GaAs gallium arsenide", "GaAs", "Ga", "As",
                5.6533, 5.318, 2.448),
    zinc_blende("zns", "ZnS zinc blende (sphalerite)", "ZnS", "Zn", "S",
                5.4093, 4.089, 2.342),
    zinc_blende("sic", "3C-SiC silicon carbide", "SiC", "Si", "C",
                4.3596, 3.214, 1.888),
    wurtzite("gan", "GaN gallium nitride", "GaN", "Ga", "N",
             3.189, 5.185, 0.377, 6.09, 1.946),
    rock_salt("nacl", "NaCl rock salt", "NaCl", "Na", "Cl", 5.6402, 2.163,
              2.820),
    _cscl(),
    fluorite("caf2", "CaF2 fluorite", "CaF2", "Ca", "F", 5.4626, 3.181,
             2.365),
    rock_salt("mgo", "MgO periclase", "MgO", "Mg", "O", 4.2112, 3.585,
              2.106, category=OXIDES),
    wurtzite("zno", "ZnO zincite", "ZnO", "Zn", "O", 3.2495, 5.2069, 0.3819,
             5.675, 1.974, category=OXIDES),
    rutile("rutile", "TiO2 rutile", "TiO2", "Ti", 4.5937, 2.9587, 0.30478,
           4.249, 1.948),
    _anatase(),
    rutile("sno2", "SnO2 cassiterite", "SnO2", "Sn", 4.7374, 3.1864,
           0.3056, 7.00, 2.052),
    fluorite("ceo2", "CeO2 ceria", "CeO2", "Ce", "O", 5.411, 7.216, 2.343,
             category=OXIDES),
    _perovskite(),
    _quartz(),
    diamond("diamond", "Diamond", "C", 3.5668, 3.516, 1.5445,
            category=CARBON),
    _graphite(),
    _hbn(),
]

#: key -> Crystal, in the order the families list them
LIBRARY = {c.key: c for cat in CATEGORIES for c in _ALL
           if c.category == cat}


def get(key: str) -> Crystal:
    """The library crystal *key* (case-insensitive); KeyError names the
    choices."""
    crystal = LIBRARY.get(str(key).strip().lower())
    if crystal is None:
        raise KeyError(f"No crystal '{key}'. Choices: "
                       + ", ".join(LIBRARY))
    return crystal
