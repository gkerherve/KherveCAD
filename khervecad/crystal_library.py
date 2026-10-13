"""The standard crystal library (Qt-free).

Over a hundred structures chemists and materials scientists reach for
first, in six families, each with its room-temperature lattice
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

import math

from .crystal import Crystal

METALS, SEMI, SALTS, OXIDES, CARBON, LAYERED = (
    "Metals", "Semiconductors", "Ionic salts", "Oxides",
    "Carbon & nitrides", "Layered materials")
#: the order the tree lists them in
CATEGORIES = (METALS, SEMI, SALTS, OXIDES, CARBON, LAYERED)

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

# ------------------------------------------------------- more structures
def _cscl_type(key, name, formula, cation, anion, a, category=SALTS):
    atoms = _put(cation, [(0, 0, 0)]) + _put(anion, [(0.5, 0.5, 0.5)])
    return _cubic(key, name, formula, category, "Pm-3m (221), CsCl", a,
                  atoms, None, [(cation, anion, a * math.sqrt(3) / 2)],
                  _poly(cation, anion, a * 0.95))


def _perovskite_type(key, name, formula, a, a_site, b_site):
    atoms = (_put(a_site, [(0, 0, 0)]) + _put(b_site, [(0.5, 0.5, 0.5)])
             + _put("O", [(0.5, 0.5, 0), (0.5, 0, 0.5), (0, 0.5, 0.5)]))
    return _cubic(key, name, formula, OXIDES, "Pm-3m (221), perovskite", a,
                  atoms, None, [(b_site, "O", a / 2)],
                  _poly(b_site, "O", a * 0.55))


def _cuprite():
    a = 4.2696
    atoms = (_put("O", [(0, 0, 0), (0.5, 0.5, 0.5)])
             + _put("Cu", [(0.25, 0.25, 0.25), (0.75, 0.75, 0.25),
                           (0.75, 0.25, 0.75), (0.25, 0.75, 0.75)]))
    return _cubic("cu2o", "Cu2O cuprite", "Cu2O", OXIDES,
                  "Pn-3m (224), cuprite", a, atoms, 6.10,
                  [("Cu", "O", a * math.sqrt(3) / 4)])


def _corundum():
    """alpha-Al2O3, R-3c (hexagonal axes): Al 12c (0, 0, z), O 18e
    (x, 0, 1/4), each with the rhombohedral centring."""
    z, x = 0.3523, 0.3064
    al = [(0, 0, z), (0, 0, -z + 0.5), (0, 0, -z), (0, 0, z + 0.5)]
    o = [(x, 0, 0.25), (0, x, 0.25), (-x, -x, 0.25),
         (-x, 0, 0.75), (0, -x, 0.75), (x, x, 0.75)]
    cent = [(0, 0, 0), (2 / 3, 1 / 3, 1 / 3), (1 / 3, 2 / 3, 2 / 3)]

    def orbit(points):
        out = []
        for p in points:
            for t in cent:
                q = tuple(round((p[i] + t[i]) % 1.0, 6) % 1.0
                          for i in range(3))
                if q not in out:
                    out.append(q)
        return out
    return _hexagonal("corundum", "Al2O3 corundum (sapphire)", "Al2O3", OXIDES,
                      "R-3c (167), corundum", 4.7570, 12.9877,
                      _put("Al", orbit(al)) + _put("O", orbit(o)), 3.987,
                      [("Al", "O", 1.855)], _poly("Al", "O", 2.1),
                      system="trigonal")


def _mos2(key, name, formula, metal, a, c, z=0.621):
    atoms = (_put(metal, [(1 / 3, 2 / 3, 0.25), (2 / 3, 1 / 3, 0.75)])
             + _put("S", [(1 / 3, 2 / 3, z), (2 / 3, 1 / 3, z + 0.5),
                          (2 / 3, 1 / 3, 1 - z), (1 / 3, 2 / 3, 0.5 - z)]))
    return _hexagonal(key, name, formula, LAYERED,
                      "P6_3/mmc (194), 2H-MoS2", a, c, atoms, None,
                      [(metal, "S", 2.41)], _poly(metal, "S", 2.6))


def _more():
    out = []
    # FCC metals
    for key, name, el, a, nn in (
            ("pd", "Palladium", "Pd", 3.8907, 2.751),
            ("rh", "Rhodium", "Rh", 3.8034, 2.689),
            ("ir", "Iridium", "Ir", 3.8392, 2.715),
            ("pb", "Lead", "Pb", 4.9508, 3.501),
            ("ca", "Calcium", "Ca", 5.5884, 3.951),
            ("sr", "Strontium", "Sr", 6.0849, 4.303)):
        out.append(fcc(key, name, el, a, None, nn))
    # BCC metals
    for key, name, el, a in (
            ("cr", "Chromium", "Cr", 2.8839), ("mo", "Molybdenum", "Mo", 3.1470),
            ("v", "Vanadium", "V", 3.0274), ("nb", "Niobium", "Nb", 3.3008),
            ("ta", "Tantalum", "Ta", 3.3013), ("li", "Lithium", "Li", 3.4910),
            ("na", "Sodium", "Na", 4.2906), ("k", "Potassium", "K", 5.3280),
            ("ba", "Barium", "Ba", 5.0280), ("rb", "Rubidium", "Rb", 5.5850),
            ("cs", "Caesium", "Cs", 6.0450)):
        out.append(bcc(key, name, el, a, None, a * math.sqrt(3) / 2))
    # HCP metals
    for key, name, el, a, c, nn in (
            ("co", "Cobalt", "Co", 2.5071, 4.0695, 2.506),
            ("zr", "Zirconium", "Zr", 3.2316, 5.1475, 3.179),
            ("cd", "Cadmium", "Cd", 2.9793, 5.6181, 2.979),
            ("be", "Beryllium", "Be", 2.2856, 3.5832, 2.226),
            ("ru", "Ruthenium", "Ru", 2.7058, 4.2811, 2.650),
            ("os", "Osmium", "Os", 2.7344, 4.3173, 2.675),
            ("re", "Rhenium", "Re", 2.7610, 4.4560, 2.741),
            ("hf", "Hafnium", "Hf", 3.1946, 5.0511, 3.127),
            ("sc", "Scandium", "Sc", 3.3090, 5.2730, 3.212),
            ("y", "Yttrium", "Y", 3.6474, 5.7306, 3.550)):
        out.append(hcp(key, name, el, a, c, None, nn))
    # tetrahedral semiconductors
    out.append(diamond("sn", "Tin (alpha, grey)", "Sn", 6.4892, None, 2.810))
    for key, name, formula, cat, an, a in (
            ("gap", "GaP gallium phosphide", "GaP", "Ga", "P", 5.4505),
            ("inp", "InP indium phosphide", "InP", "In", "P", 5.8687),
            ("inas", "InAs indium arsenide", "InAs", "In", "As", 6.0583),
            ("insb", "InSb indium antimonide", "InSb", "In", "Sb", 6.4794),
            ("gasb", "GaSb gallium antimonide", "GaSb", "Ga", "Sb", 6.0959),
            ("alas", "AlAs aluminium arsenide", "AlAs", "Al", "As", 5.6611),
            ("alp", "AlP aluminium phosphide", "AlP", "Al", "P", 5.4635),
            ("znse", "ZnSe zinc selenide", "ZnSe", "Zn", "Se", 5.6676),
            ("znte", "ZnTe zinc telluride", "ZnTe", "Zn", "Te", 6.1010),
            ("cdte", "CdTe cadmium telluride", "CdTe", "Cd", "Te", 6.4820),
            ("cbn", "c-BN cubic boron nitride", "BN", "B", "N", 3.6157)):
        out.append(zinc_blende(key, name, formula, cat, an, a, None,
                               a * math.sqrt(3) / 4))
    for key, name, formula, cat, an, a, c, u in (
            ("aln", "AlN aluminium nitride", "AlN", "Al", "N", 3.111, 4.978,
             0.382),
            ("beo", "BeO bromellite", "BeO", "Be", "O", 2.698, 4.380, 0.378),
            ("cds", "CdS greenockite", "CdS", "Cd", "S", 4.136, 6.713, 0.376),
            ("cdse", "CdSe", "CdSe", "Cd", "Se", 4.300, 7.010, 0.376),
            ("zns_w", "ZnS wurtzite", "ZnS", "Zn", "S", 3.811, 6.234, 0.375),
            ("inn", "InN indium nitride", "InN", "In", "N", 3.545, 5.703,
             0.379)):
        out.append(wurtzite(key, name, formula, cat, an, a, c, u, None,
                            (u * c)))
    # rock-salt halides, oxides and carbides
    for key, name, formula, c_, an, a, cat in (
            ("lif", "LiF lithium fluoride", "LiF", "Li", "F", 4.0270, SALTS),
            ("naf", "NaF villiaumite", "NaF", "Na", "F", 4.6340, SALTS),
            ("kf", "KF potassium fluoride", "KF", "K", "F", 5.3470, SALTS),
            ("nabr", "NaBr sodium bromide", "NaBr", "Na", "Br", 5.9770, SALTS),
            ("nai", "NaI sodium iodide", "NaI", "Na", "I", 6.4728, SALTS),
            ("kcl", "KCl sylvite", "KCl", "K", "Cl", 6.2931, SALTS),
            ("kbr", "KBr potassium bromide", "KBr", "K", "Br", 6.6000, SALTS),
            ("ki", "KI potassium iodide", "KI", "K", "I", 7.0656, SALTS),
            ("rbcl", "RbCl rubidium chloride", "RbCl", "Rb", "Cl", 6.5810,
             SALTS),
            ("agcl", "AgCl chlorargyrite", "AgCl", "Ag", "Cl", 5.5491, SALTS),
            ("agbr", "AgBr silver bromide", "AgBr", "Ag", "Br", 5.7745, SALTS),
            ("pbs", "PbS galena", "PbS", "Pb", "S", 5.9362, SEMI),
            ("pbte", "PbTe altaite", "PbTe", "Pb", "Te", 6.4620, SEMI),
            ("tic", "TiC titanium carbide", "TiC", "Ti", "C", 4.3273, CARBON),
            ("tin", "TiN titanium nitride", "TiN", "Ti", "N", 4.2417, CARBON),
            ("nio", "NiO bunsenite", "NiO", "Ni", "O", 4.1771, OXIDES),
            ("coo", "CoO", "CoO", "Co", "O", 4.2612, OXIDES),
            ("feo", "FeO wüstite", "FeO", "Fe", "O", 4.3260, OXIDES),
            ("mno", "MnO manganosite", "MnO", "Mn", "O", 4.4445, OXIDES),
            ("cao", "CaO lime", "CaO", "Ca", "O", 4.8105, OXIDES),
            ("sro", "SrO", "SrO", "Sr", "O", 5.1600, OXIDES),
            ("bao", "BaO", "BaO", "Ba", "O", 5.5391, OXIDES),
            ("cdo", "CdO monteponite", "CdO", "Cd", "O", 4.6953, OXIDES)):
        out.append(rock_salt(key, name, formula, c_, an, a, None, a / 2,
                             category=cat))
    out.append(_cscl_type("csbr", "CsBr caesium bromide", "CsBr", "Cs", "Br",
                          4.2860))
    out.append(_cscl_type("csi", "CsI caesium iodide", "CsI", "Cs", "I",
                          4.5667))
    # fluorite and antifluorite
    for key, name, formula, c_, an, a, cat in (
            ("zro2", "ZrO2 cubic zirconia", "ZrO2", "Zr", "O", 5.090, OXIDES),
            ("uo2", "UO2 uraninite", "UO2", "U", "O", 5.4704, OXIDES),
            ("tho2", "ThO2 thorianite", "ThO2", "Th", "O", 5.5970, OXIDES),
            ("srf2", "SrF2 strontium fluoride", "SrF2", "Sr", "F", 5.7996,
             SALTS),
            ("baf2", "BaF2 barium fluoride", "BaF2", "Ba", "F", 6.2001, SALTS),
            ("cdf2", "CdF2 cadmium fluoride", "CdF2", "Cd", "F", 5.3880,
             SALTS),
            ("pbf2", "PbF2 lead fluoride", "PbF2", "Pb", "F", 5.9400, SALTS),
            ("li2o", "Li2O lithium oxide (antifluorite)", "Li2O", "O", "Li",
             4.6114, OXIDES),
            ("na2o", "Na2O sodium oxide (antifluorite)", "Na2O", "O", "Na",
             5.5490, OXIDES)):
        out.append(fluorite(key, name, formula, c_, an, a, None,
                            a * math.sqrt(3) / 4, category=cat))
    # rutile-type
    for key, name, formula, metal, a, c, u in (
            ("mgf2", "MgF2 sellaite", "MgF2", "Mg", 4.621, 3.052, 0.303),
            ("ruo2", "RuO2", "RuO2", "Ru", 4.4994, 3.1071, 0.3053),
            ("mno2", "MnO2 pyrolusite", "MnO2", "Mn", 4.398, 2.874, 0.302),
            ("vo2", "VO2 (rutile phase)", "VO2", "V", 4.5546, 2.8514, 0.3001)):
        crystal = rutile(key, name, formula, metal, a, c, u, None, 1.95)
        anion = "O"
        if metal == "Mg":
            anion = "F"
            crystal.atoms = [(("F" if e == "O" else e), *f)
                             for e, *f in crystal.atoms]
            crystal.polyhedra = _poly("Mg", "F", 2.2)
        crystal.bonds = [(metal, anion, round(crystal.nearest(metal, anion),
                                              3))]
        out.append(crystal)
    # cubic perovskites, cuprite, corundum, layered dichalcogenides
    out.append(_perovskite_type("batio3", "BaTiO3 (cubic perovskite)",
                                "BaTiO3", 4.0000, "Ba", "Ti"))
    out.append(_perovskite_type("ktao3", "KTaO3 potassium tantalate",
                                "KTaO3", 3.9885, "K", "Ta"))
    out.append(_perovskite_type("srzro3", "SrZrO3 (cubic perovskite)",
                                "SrZrO3", 4.1010, "Sr", "Zr"))
    out.append(_cuprite())
    out.append(_corundum())
    out.append(_mos2("mos2", "MoS2 molybdenite (2H)", "MoS2", "Mo", 3.160,
                     12.294))
    out.append(_mos2("ws2", "WS2 tungstenite (2H)", "WS2", "W", 3.153,
                     12.323))
    return out


_ALL += _more()


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
