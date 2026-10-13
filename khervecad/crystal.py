"""Crystal structures for the Crystal Builder (Qt-free).

A `Crystal` is a lattice — a, b, c in ångström and α, β, γ in degrees,
any of the seven crystal systems — plus EVERY atom of its conventional
cell as fractional coordinates. Writing the cell out atom by atom,
instead of an asymmetric unit plus a space-group table, keeps each
entry checkable by eye and needs no symmetry engine; the library's
tests pin every entry to its published density and nearest-neighbour
distance, which catches a missing atom or a slipped coordinate at once.

The lattice follows the crystallographic convention: a along x, b in
the xy plane, c completing a right-handed cell. Lengths here are
ÅNGSTRÖM (the unit papers give); the builder writes nanometres. Atom
sizes are the covalent radii of Cordero et al., Dalton Trans. 2008 —
what "the size of the atom" meant in the quartz models — and colours
VESTA's default scheme (`VESTA_COLOURS`, the viewer most papers'
structure pictures come from); the Jmol/CPK colours stay in
`ELEMENTS` for `colour(el, "jmol")`.

A crystal may name its coordination polyhedra — a centre element, the
ligand element and a cut-off: SiO4 tetrahedra in quartz, TiO6
octahedra in rutile. `polyhedra_sites` finds each centre's ligands
through the periodic images and `polyhedron` turns them into an
OpenSCAD polyhedron (the convex hull, faces clockwise from outside).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .geom3d import convex_hull

#: g/mol per Å^3 -> g/cm^3 is 1 / (N_A x 1e-24 cm^3) = 1 / 0.602214076
AVOGADRO_CM3 = 0.602214076

#: symbol -> (covalent radius Å [Cordero 2008], Jmol colour, atomic mass)
ELEMENTS = {
    "H": (0.31, "#FFFFFF", 1.008), "He": (0.28, "#D9FFFF", 4.0026),
    "Li": (1.28, "#CC80FF", 6.94), "Be": (0.96, "#C2FF00", 9.0122),
    "B": (0.84, "#FFB5B5", 10.81), "C": (0.76, "#909090", 12.011),
    "N": (0.71, "#3050F8", 14.007), "O": (0.66, "#FF0D0D", 15.999),
    "F": (0.57, "#90E050", 18.998), "Ne": (0.58, "#B3E3F5", 20.180),
    "Na": (1.66, "#AB5CF2", 22.990), "Mg": (1.41, "#8AFF00", 24.305),
    "Al": (1.21, "#BFA6A6", 26.982), "Si": (1.11, "#F0C8A0", 28.085),
    "P": (1.07, "#FF8000", 30.974), "S": (1.05, "#FFFF30", 32.06),
    "Cl": (1.02, "#1FF01F", 35.45), "Ar": (1.06, "#80D1E3", 39.948),
    "K": (2.03, "#8F40D4", 39.098), "Ca": (1.76, "#3DFF00", 40.078),
    "Sc": (1.70, "#E6E6E6", 44.956), "Ti": (1.60, "#BFC2C7", 47.867),
    "V": (1.53, "#A6A6AB", 50.942), "Cr": (1.39, "#8A99C7", 51.996),
    "Mn": (1.39, "#9C7AC7", 54.938), "Fe": (1.32, "#E06633", 55.845),
    "Co": (1.26, "#F090A0", 58.933), "Ni": (1.24, "#50D050", 58.693),
    "Cu": (1.32, "#C88033", 63.546), "Zn": (1.22, "#7D80B0", 65.38),
    "Ga": (1.22, "#C28F8F", 69.723), "Ge": (1.20, "#668F8F", 72.630),
    "As": (1.19, "#BD80E3", 74.922), "Se": (1.20, "#FFA100", 78.971),
    "Br": (1.20, "#A62929", 79.904), "Kr": (1.16, "#5CB8D1", 83.798),
    "Rb": (2.20, "#702EB0", 85.468), "Sr": (1.95, "#00FF00", 87.62),
    "Y": (1.90, "#94FFFF", 88.906), "Zr": (1.75, "#94E0E0", 91.224),
    "Nb": (1.64, "#73C2C9", 92.906), "Mo": (1.54, "#54B5B5", 95.95),
    "Ru": (1.46, "#248F8F", 101.07), "Rh": (1.42, "#0A7D8C", 102.91),
    "Pd": (1.39, "#006985", 106.42), "Ag": (1.45, "#C0C0C0", 107.87),
    "Cd": (1.44, "#FFD98F", 112.41), "In": (1.42, "#A67573", 114.82),
    "Sn": (1.39, "#668080", 118.71), "Sb": (1.39, "#9E63B5", 121.76),
    "Te": (1.38, "#D47A00", 127.60), "I": (1.39, "#940094", 126.90),
    "Xe": (1.40, "#429EB0", 131.29), "Cs": (2.44, "#57178F", 132.91),
    "Ba": (2.15, "#00C900", 137.33), "La": (2.07, "#70D4FF", 138.91),
    "Ce": (2.04, "#FFFFC7", 140.12), "Hf": (1.75, "#4DC2FF", 178.49),
    "Ta": (1.70, "#4DA6FF", 180.95), "W": (1.62, "#2194D6", 183.84),
    "Re": (1.51, "#267DAB", 186.21), "Os": (1.44, "#266696", 190.23),
    "Ir": (1.41, "#175487", 192.22), "Pt": (1.36, "#D0D0E0", 195.08),
    "Au": (1.36, "#FFD123", 196.97), "Hg": (1.32, "#B8B8D0", 200.59),
    "Tl": (1.45, "#A6544D", 204.38), "Pb": (1.46, "#575961", 207.2),
    "Bi": (1.48, "#9E4FB5", 208.98), "Po": (1.40, "#AB5C00", 208.98),
    "Th": (2.06, "#00BAFF", 232.04), "U": (1.96, "#008FFF", 238.03),
}

#: ligand count -> the polyhedron's name
SHAPE_NAMES = {3: "triangles", 4: "tetrahedra", 5: "bipyramids",
               6: "octahedra", 8: "cubes", 12: "cuboctahedra"}


def radius(element: str) -> float:
    """Covalent radius, Å."""
    return ELEMENTS[element][0]


#: VESTA's default element colours (its elements.ini); an element it
#: does not list here falls back to the Jmol colour
VESTA_COLOURS = {
    "H": "#FFCCCC", "He": "#FCE8CE", "Li": "#86DF73", "Be": "#5ED77B",
    "B": "#1FA20F", "C": "#814929", "N": "#B0B9E6", "O": "#FE0300",
    "F": "#B0B9E6", "Ne": "#FE37B5", "Na": "#F9DC3C", "Mg": "#FB7B15",
    "Al": "#81B2D6", "Si": "#1B3BFA", "P": "#C09CC2", "S": "#FFFA00",
    "Cl": "#31FC02", "Ar": "#CFFEC4", "K": "#A121F6", "Ca": "#5A96BD",
    "Sc": "#B563AB", "Ti": "#78CAFF", "V": "#E51900", "Cr": "#00009E",
    "Mn": "#A8089E", "Fe": "#B57100", "Co": "#0000AF", "Ni": "#B7BBBD",
    "Cu": "#2247DC", "Zn": "#8F8F81", "Ga": "#9EE373", "Ge": "#7E6EA6",
    "As": "#74D057", "Se": "#9AEF0F", "Br": "#7E3102", "Kr": "#FAC1F3",
    "Rb": "#FF0099", "Sr": "#00FF27", "Y": "#67988E", "Zr": "#00FF00",
    "Nb": "#4CB276", "Mo": "#B386AF", "Ru": "#CFCFCF", "Rh": "#CDD1AB",
    "Pd": "#C1C3B8", "Ag": "#B7BBBD", "Cd": "#F31FDC", "In": "#D780BB",
    "Sn": "#9A8EB9", "Sb": "#D8831D", "Te": "#ADA251", "I": "#8E1F8A",
    "Xe": "#9AA1F8", "Cs": "#0EFEB9", "Ba": "#1EEF2C", "La": "#5AC449",
    "Ce": "#D1FC06", "Hf": "#B4B359", "Ta": "#B79A56", "W": "#8E8A80",
    "Re": "#B3B18E", "Os": "#C9B179", "Ir": "#C9CF73", "Pt": "#CBC5BE",
    "Au": "#FEB338", "Hg": "#D3B7CB", "Tl": "#95896C", "Pb": "#52535B",
    "Bi": "#D230F8", "Po": "#0000FF", "U": "#7A8CA6",
}
#: the colour scheme crystal pictures use: "vesta" or "jmol"
SCHEME = "vesta"


def colour(element: str, scheme: str | None = None) -> str:
    if (scheme or SCHEME) == "vesta" and element in VESTA_COLOURS:
        return VESTA_COLOURS[element]
    return ELEMENTS[element][1]


#: two atoms are bonded within this many times their covalent radii
BOND_TOLERANCE = 1.15


def bonded(el1: str, el2: str, d: float) -> bool:
    return 1e-6 < d <= BOND_TOLERANCE * (radius(el1) + radius(el2))


def _clean(value: float) -> float:
    """cos 90° is 6e-17, not 0 — and a zero keeps the program short."""
    return 0.0 if abs(value) < 1e-12 else value


@dataclass
class Crystal:
    """One crystal structure (lengths in Å, angles in degrees)."""
    key: str
    name: str
    formula: str
    category: str
    system: str
    space_group: str
    a: float
    b: float
    c: float
    alpha: float = 90.0
    beta: float = 90.0
    gamma: float = 90.0
    #: every atom of the conventional cell: (element, fx, fy, fz)
    atoms: list = field(default_factory=list)
    #: {"centre", "ligand", "cutoff" (Å), "sites" (atom indices) or None}
    polyhedra: dict | None = None
    #: reference density g/cm^3 and nearest distances [(el, el, Å)]
    density: float | None = None
    bonds: list = field(default_factory=list)
    source: str = ""
    #: explicit bond cutoffs {(el, el) sorted: max length Å}
    cutoffs: dict = field(default_factory=dict)

    # ------------------------------------------------------- geometry
    def vectors(self):
        """Lattice vectors a1, a2, a3 in Å."""
        al, be, ga = (math.radians(x) for x in (self.alpha, self.beta,
                                                self.gamma))
        ca, cb = _clean(math.cos(al)), _clean(math.cos(be))
        cg, sg = _clean(math.cos(ga)), math.sin(ga)
        x3 = self.c * cb
        y3 = _clean(self.c * (ca - cb * cg) / sg)
        z3 = math.sqrt(max(self.c ** 2 - x3 * x3 - y3 * y3, 0.0))
        return ((self.a, 0.0, 0.0),
                (_clean(self.b * cg), self.b * sg, 0.0),
                (_clean(x3), y3, z3))

    def cart(self, f):
        """Fractional -> Cartesian (Å)."""
        v1, v2, v3 = self.vectors()
        return tuple(f[0] * v1[i] + f[1] * v2[i] + f[2] * v3[i]
                     for i in range(3))

    def volume(self) -> float:
        v1, v2, v3 = self.vectors()
        cx = (v2[1] * v3[2] - v2[2] * v3[1], v2[2] * v3[0] - v2[0] * v3[2],
              v2[0] * v3[1] - v2[1] * v3[0])
        return abs(v1[0] * cx[0] + v1[1] * cx[1] + v1[2] * cx[2])

    def mass(self) -> float:
        """g/mol of one conventional cell."""
        return sum(ELEMENTS[el][2] for el, *_f in self.atoms)

    def computed_density(self) -> float:
        return self.mass() / (self.volume() * AVOGADRO_CM3)

    def composition(self) -> dict:
        counts = {}
        for el, *_f in self.atoms:
            counts[el] = counts.get(el, 0) + 1
        return counts

    def _images(self, f, reach):
        r = range(-reach, reach + 1)
        for i in r:
            for j in r:
                for k in r:
                    yield self.cart((f[0] + i, f[1] + j, f[2] + k))

    def nearest(self, el1: str, el2: str) -> float:
        """Shortest el1-el2 distance through the periodic images, Å."""
        best = math.inf
        for e1, *f1 in self.atoms:
            if e1 != el1:
                continue
            p = self.cart(f1)
            for e2, *f2 in self.atoms:
                if e2 != el2:
                    continue
                for q in self._images(f2, 1):
                    d = math.dist(p, q)
                    if 1e-6 < d < best:
                        best = d
        return best

    # ------------------------------------------------------ polyhedra
    def polyhedra_sites(self):
        """[(atom index, centre xyz, [ligand xyz])] for every centre in
        the cell; ligands may lie in neighbouring cells (Å)."""
        spec = self.polyhedra
        if not spec:
            return []
        sites = spec.get("sites")
        out = []
        for idx, (el, *f) in enumerate(self.atoms):
            if el != spec["centre"] or (sites is not None
                                        and idx not in sites):
                continue
            p = self.cart(f)
            ligands = [q for e, *g in self.atoms if e == spec["ligand"]
                       for q in self._images(g, 2)
                       if 1e-6 < math.dist(p, q) <= spec["cutoff"]]
            out.append((idx, p, ligands))
        return out

    def polyhedra_label(self) -> str:
        """"SiO4 tetrahedra" — or "" when the crystal has none."""
        sites = self.polyhedra_sites()
        if not sites:
            return ""
        n = len(sites[0][2])
        spec = self.polyhedra
        return (f"{spec['centre']}{spec['ligand']}{n} "
                f"{SHAPE_NAMES.get(n, 'polyhedra')}")

    # -------------------------------------------------------- listing
    def summary(self) -> dict:
        """What list_crystals reports — lengths in nm."""
        return {
            "key": self.key, "name": self.name, "formula": self.formula,
            "category": self.category, "system": self.system,
            "space_group": self.space_group,
            "a_nm": round(self.a / 10, 5), "b_nm": round(self.b / 10, 5),
            "c_nm": round(self.c / 10, 5), "alpha": self.alpha,
            "beta": self.beta, "gamma": self.gamma,
            "atoms_per_cell": len(self.atoms),
            "composition": self.composition(),
            "density_g_cm3": round(self.computed_density(), 3),
            "polyhedra": self.polyhedra_label() or None,
            "source": self.source,
        }


def polyhedron(ligands, digits: int = 5):
    """OpenSCAD ``(points, faces)`` of the convex hull of *ligands*
    (faces clockwise seen from outside); ``([], [])`` when they span no
    volume (a flat CO3, a linear pair)."""
    index, points, faces = {}, [], []
    for tri in convex_hull(ligands):          # counter-clockwise, outward
        ids = []
        for v in tri:
            key = tuple(round(x, digits) for x in v)
            if key not in index:
                index[key] = len(points)
                points.append(list(key))
            ids.append(index[key])
        if len(set(ids)) == 3:
            faces.append([ids[0], ids[2], ids[1]])
    return points, faces


def custom(spec: dict) -> Crystal:
    """A crystal from a plain dict — what an assistant passes when the
    library lacks one: ``{"name", "a", "b", "c", "alpha", "beta",
    "gamma", "atoms": [[el, fx, fy, fz], ...], "polyhedra": {"centre",
    "ligand", "cutoff"}, "units": "angstrom" | "nm"}``. Raises
    ValueError with the reason."""
    if not isinstance(spec, dict):
        raise ValueError("A custom crystal is an object with a, b, c, "
                         "angles and atoms.")
    units = str(spec.get("units", "angstrom")).lower()
    if units not in ("angstrom", "a", "å", "nm", "nanometre", "nanometer"):
        raise ValueError("custom units are 'angstrom' or 'nm'.")
    to_a = 10.0 if units.startswith("n") else 1.0
    try:
        a = float(spec["a"]) * to_a
        b = float(spec.get("b", spec["a"])) * to_a
        c = float(spec.get("c", spec["a"])) * to_a
        angles = [float(spec.get(k, 90.0))
                  for k in ("alpha", "beta", "gamma")]
    except (KeyError, TypeError, ValueError):
        raise ValueError("A custom crystal needs a number 'a' (and 'b', "
                         "'c' if they differ).")
    if min(a, b, c) <= 0 or not all(0 < x < 180 for x in angles):
        raise ValueError("Cell lengths must be positive and angles "
                         "between 0 and 180 degrees.")
    atoms = []
    for row in spec.get("atoms") or []:
        if not isinstance(row, (list, tuple)) or len(row) != 4:
            raise ValueError("Each atom is [element, fx, fy, fz] "
                             "(fractional coordinates).")
        el = str(row[0]).strip().capitalize()
        if el not in ELEMENTS:
            raise ValueError(f"Unknown element '{row[0]}'.")
        atoms.append((el, *(float(x) % 1.0 for x in row[1:])))
    if not atoms:
        raise ValueError("A custom crystal needs at least one atom.")
    poly = spec.get("polyhedra")
    if poly:
        try:
            poly = {"centre": str(poly["centre"]).capitalize(),
                    "ligand": str(poly["ligand"]).capitalize(),
                    "cutoff": float(poly["cutoff"]) * to_a,
                    "sites": None}
        except (KeyError, TypeError, ValueError):
            raise ValueError("polyhedra is {centre, ligand, cutoff}.")
    name = str(spec.get("name") or "Custom crystal")
    crystal = Crystal(
        key="custom", name=name, formula=str(spec.get("formula") or name),
        category="Custom", system=str(spec.get("system") or "custom"),
        space_group=str(spec.get("space_group") or "?"),
        a=a, b=b, c=c, alpha=angles[0], beta=angles[1], gamma=angles[2],
        atoms=atoms, polyhedra=poly or None,
        source=str(spec.get("source") or "given by the user"))
    if crystal.volume() < 1e-6:
        raise ValueError("Those angles give a flat cell.")
    return crystal
