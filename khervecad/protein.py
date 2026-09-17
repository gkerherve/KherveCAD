"""Proteins (Qt-free): chains built from a sequence, or read from the
Protein Data Bank.

Two ways in, one `Protein` out (heavy atoms, bonds, secondary structure):

- **Built** — `build_peptide(sequence, secondary)`: every residue from
  its ideal internal coordinates (Engh & Huber bond lengths and angles,
  planar trans peptide bonds) placed one atom at a time by NeRF, the
  backbone turned by the (phi, psi) of its secondary-structure letter —
  H alpha helix, G 3-10 helix, E beta strand, P polyproline II, T beta
  turn (two between strands make a hairpin), L left-handed, C coil —
  and each side chain on the first rotamer of a short list that clears
  what is already placed. This is geometry, not folding: a helix or a
  hairpin comes out right, but a mixed string is a chain of those
  pieces with no tertiary packing (`clashes` counts the atoms that ended
  up on top of each other).
- **Read** — `parse_pdb` / `parse_mmcif`: a structure from a file, from
  RCSB by its four-character ID or from the AlphaFold database by a
  UniProt accession (`fetch`, cached; the opener is injectable so the
  tests stay offline). Secondary structure comes from the file's
  HELIX/SHEET or struct_conf/struct_sheet_range records, else from the
  CA geometry (`assign_secondary`, P-SEA-like distance criteria). Bonds
  come from distances (covalent radii), so ligands and disulfides need
  no dictionary.

Hydrogens are left out (X-ray files have none, and they would double the
atom count for no visible gain). Coordinates are Å.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import os
import re
import tempfile
from dataclasses import dataclass, field

from .crystal import ELEMENTS

# ------------------------------------------------------------- residues
#: three-letter -> one-letter
THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
    "MSE": "M", "SEC": "U", "PYL": "O", "HSD": "H", "HSE": "H",
    "HID": "H", "HIE": "H", "HIP": "H", "CYX": "C",
}
ONE_TO_THREE = {v: k for k, v in list(THREE_TO_ONE.items())[:20]}

#: residue names that are water
WATER = {"HOH", "WAT", "DOD", "H2O", "TIP", "TIP3", "SOL"}

#: residue class, for the "residue" colouring
RESIDUE_CLASS = {
    "A": "hydrophobic", "V": "hydrophobic", "L": "hydrophobic",
    "I": "hydrophobic", "M": "hydrophobic", "F": "aromatic",
    "W": "aromatic", "Y": "aromatic", "P": "special", "G": "special",
    "C": "special", "S": "polar", "T": "polar", "N": "polar",
    "Q": "polar", "H": "positive", "K": "positive", "R": "positive",
    "D": "negative", "E": "negative",
}

#: Kyte-Doolittle hydropathy
HYDROPATHY = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5, "Q": -3.5,
    "E": -3.5, "G": -0.4, "H": -3.2, "I": 4.5, "L": 3.8, "K": -3.9,
    "M": 1.9, "F": 2.8, "P": -1.6, "S": -0.8, "T": -0.7, "W": -0.9,
    "Y": -1.3, "V": 4.2,
}

#: (phi, psi) by secondary-structure letter
PHI_PSI = {
    "H": (-57.0, -47.0),       # alpha helix
    "G": (-49.0, -26.0),       # 3-10 helix
    "E": (-120.0, 130.0),      # beta strand
    "P": (-75.0, 145.0),       # polyproline II
    "L": (60.0, 45.0),         # left-handed helix region
    "C": (-70.0, 140.0),       # coil
}
#: a run of T: a two-residue hairpin turn, searched on a grid so the E
#: strands (-120, 130) either side pair up — cross-strand CA 3.8-5.4 Å,
#: alternating like a real hairpin — without the side chains colliding
#: (the textbook type I' angles open the strands 10 Å apart when every
#: strand residue shares one (phi, psi))
TURN = ((-30.0, 90.0), (135.0, -60.0))
SECONDARY_NAMES = {"H": "alpha helix", "G": "3-10 helix",
                   "E": "beta strand", "P": "polyproline II",
                   "L": "left-handed", "T": "beta turn",
                   "C": "coil"}

# backbone (Engh & Huber 1991)
N_CA, CA_C, C_N, C_O = 1.458, 1.525, 1.329, 1.231
ANG_N_CA_C, ANG_CA_C_N, ANG_C_N_CA, ANG_CA_C_O = 111.2, 116.2, 121.7, 120.5
OMEGA = 180.0
CB_TORSION = -122.6            # C-N-CA-CB for an L residue

#: side chains: (atom, element, a, b, c, bond, angle, torsion) — the
#: atom is bonded to c at *bond* Å, angle b-c-atom, torsion a-b-c-atom;
#: a torsion "chi1".."chi4" (+ offset) reads the residue's rotamer
SIDE = {
    "A": [],
    "G": [],
    "S": [("OG", "O", "N", "CA", "CB", 1.417, 110.8, "chi1")],
    "C": [("SG", "S", "N", "CA", "CB", 1.808, 113.8, "chi1")],
    "V": [("CG1", "C", "N", "CA", "CB", 1.527, 110.7, "chi1"),
          ("CG2", "C", "N", "CA", "CB", 1.527, 110.4, "chi1+120")],
    "T": [("OG1", "O", "N", "CA", "CB", 1.433, 109.2, "chi1"),
          ("CG2", "C", "N", "CA", "CB", 1.521, 111.1, "chi1-120")],
    "L": [("CG", "C", "N", "CA", "CB", 1.530, 116.1, "chi1"),
          ("CD1", "C", "CA", "CB", "CG", 1.524, 110.3, "chi2"),
          ("CD2", "C", "CA", "CB", "CG", 1.525, 110.6, "chi2+120")],
    "I": [("CG1", "C", "N", "CA", "CB", 1.530, 110.4, "chi1"),
          ("CG2", "C", "N", "CA", "CB", 1.527, 110.5, "chi1-120"),
          ("CD1", "C", "CA", "CB", "CG1", 1.520, 113.8, "chi2")],
    "M": [("CG", "C", "N", "CA", "CB", 1.520, 114.1, "chi1"),
          ("SD", "S", "CA", "CB", "CG", 1.807, 112.7, "chi2"),
          ("CE", "C", "CB", "CG", "SD", 1.789, 100.9, "chi3")],
    "P": [("CG", "C", "N", "CA", "CB", 1.495, 104.5, "chi1"),
          ("CD", "C", "CA", "CB", "CG", 1.502, 105.5, "chi2")],
    "F": [("CG", "C", "N", "CA", "CB", 1.502, 113.8, "chi1"),
          ("CD1", "C", "CA", "CB", "CG", 1.384, 120.7, "chi2"),
          ("CD2", "C", "CA", "CB", "CG", 1.384, 120.7, "chi2+180"),
          ("CE1", "C", "CB", "CG", "CD1", 1.382, 120.7, "180"),
          ("CE2", "C", "CB", "CG", "CD2", 1.382, 120.7, "180"),
          ("CZ", "C", "CG", "CD1", "CE1", 1.382, 120.0, "0")],
    "Y": [("CG", "C", "N", "CA", "CB", 1.512, 113.9, "chi1"),
          ("CD1", "C", "CA", "CB", "CG", 1.389, 120.8, "chi2"),
          ("CD2", "C", "CA", "CB", "CG", 1.389, 120.8, "chi2+180"),
          ("CE1", "C", "CB", "CG", "CD1", 1.382, 121.2, "180"),
          ("CE2", "C", "CB", "CG", "CD2", 1.382, 121.2, "180"),
          ("CZ", "C", "CG", "CD1", "CE1", 1.378, 119.6, "0"),
          ("OH", "O", "CD1", "CE1", "CZ", 1.376, 119.9, "180")],
    "W": [("CG", "C", "N", "CA", "CB", 1.498, 113.6, "chi1"),
          ("CD1", "C", "CA", "CB", "CG", 1.365, 126.9, "chi2"),
          ("CD2", "C", "CA", "CB", "CG", 1.433, 126.6, "chi2+180"),
          ("NE1", "N", "CB", "CG", "CD1", 1.374, 110.2, "180"),
          ("CE2", "C", "CB", "CG", "CD2", 1.409, 107.2, "180"),
          ("CE3", "C", "CB", "CG", "CD2", 1.398, 133.9, "0"),
          ("CZ2", "C", "CG", "CD2", "CE2", 1.394, 122.4, "180"),
          ("CZ3", "C", "CG", "CD2", "CE3", 1.382, 118.7, "180"),
          ("CH2", "C", "CD2", "CE2", "CZ2", 1.368, 117.5, "0")],
    "H": [("CG", "C", "N", "CA", "CB", 1.497, 113.7, "chi1"),
          ("ND1", "N", "CA", "CB", "CG", 1.378, 122.7, "chi2"),
          ("CD2", "C", "CA", "CB", "CG", 1.356, 131.0, "chi2+180"),
          ("CE1", "C", "CB", "CG", "ND1", 1.321, 109.0, "180"),
          ("NE2", "N", "CB", "CG", "CD2", 1.374, 107.2, "180")],
    "D": [("CG", "C", "N", "CA", "CB", 1.516, 112.6, "chi1"),
          ("OD1", "O", "CA", "CB", "CG", 1.249, 118.4, "chi2"),
          ("OD2", "O", "CA", "CB", "CG", 1.249, 118.4, "chi2+180")],
    "N": [("CG", "C", "N", "CA", "CB", 1.516, 112.6, "chi1"),
          ("OD1", "O", "CA", "CB", "CG", 1.231, 120.8, "chi2"),
          ("ND2", "N", "CA", "CB", "CG", 1.328, 116.4, "chi2+180")],
    "E": [("CG", "C", "N", "CA", "CB", 1.520, 114.1, "chi1"),
          ("CD", "C", "CA", "CB", "CG", 1.516, 112.6, "chi2"),
          ("OE1", "O", "CB", "CG", "CD", 1.249, 118.4, "chi3"),
          ("OE2", "O", "CB", "CG", "CD", 1.249, 118.4, "chi3+180")],
    "Q": [("CG", "C", "N", "CA", "CB", 1.520, 114.1, "chi1"),
          ("CD", "C", "CA", "CB", "CG", 1.516, 112.6, "chi2"),
          ("OE1", "O", "CB", "CG", "CD", 1.231, 120.8, "chi3"),
          ("NE2", "N", "CB", "CG", "CD", 1.328, 116.4, "chi3+180")],
    "K": [("CG", "C", "N", "CA", "CB", 1.520, 114.1, "chi1"),
          ("CD", "C", "CA", "CB", "CG", 1.520, 111.3, "chi2"),
          ("CE", "C", "CB", "CG", "CD", 1.520, 111.3, "chi3"),
          ("NZ", "N", "CG", "CD", "CE", 1.489, 111.9, "chi4")],
    "R": [("CG", "C", "N", "CA", "CB", 1.520, 114.1, "chi1"),
          ("CD", "C", "CA", "CB", "CG", 1.520, 111.3, "chi2"),
          ("NE", "N", "CB", "CG", "CD", 1.460, 112.0, "chi3"),
          ("CZ", "C", "CG", "CD", "NE", 1.329, 124.2, "chi4"),
          ("NH1", "N", "CD", "NE", "CZ", 1.326, 120.0, "0"),
          ("NH2", "N", "CD", "NE", "CZ", 1.326, 120.0, "180")],
}
#: bonds that close a side-chain ring
RING_CLOSURES = {
    "P": [("CD", "N")], "F": [("CE2", "CZ")], "Y": [("CE2", "CZ")],
    "W": [("NE1", "CE2"), ("CZ3", "CH2")], "H": [("CE1", "NE2")],
}
#: rotamers (chi1..chi4) each residue may take, commonest first; the
#: builder keeps the first that touches nothing already placed
ROTAMERS = {
    "S": [(65,), (-65,), (180,)],
    "C": [(-65,), (180,), (65,)],
    "T": [(60,), (-60,), (180,)],
    "V": [(175,), (-60,), (65,)],
    "L": [(-65, 175), (180, 65), (-85, 65), (180, 180)],
    "I": [(-65, 170), (-57, -60), (60, 170), (180, 170)],
    "M": [(-65, 180, 180), (-65, -65, -70), (180, 180, 75),
          (180, 65, 75)],
    "P": [(30, -35)],
    "F": [(-65, 95), (180, 80), (62, 90), (-65, -30)],
    "Y": [(-65, 95), (180, 80), (62, 90), (-65, -30)],
    "W": [(-65, 95), (-65, -5), (180, -105), (180, 90), (62, -90)],
    "H": [(-65, -70), (-65, 80), (180, -80), (180, 80), (62, -75)],
    "D": [(-65, -20), (180, 10), (62, 10), (-65, 60)],
    "N": [(-65, -40), (-65, 120), (180, -20), (62, -10)],
    "E": [(-65, 180, -10), (180, 180, 10), (-65, -65, -40),
          (62, 180, 20)],
    "Q": [(-65, 180, -40), (180, 180, 60), (-65, -65, -40),
          (62, 180, 20)],
    "K": [(-65, 180, 180, 180), (180, 180, 180, 180),
          (-65, -65, 180, 180), (62, 180, 180, 180)],
    "R": [(-65, 180, 180, 180), (180, 180, 180, 180),
          (-65, -65, 180, 85), (62, 180, 180, 180)],
}
#: side-chain atoms nearer than this to another residue's atom clash
ROTAMER_CLEARANCE = 3.0

MAX_RESIDUES = 2000


class ProteinError(ValueError):
    """A sequence or structure that cannot be used; says why."""


# ---------------------------------------------------------------- data
@dataclass
class Atom:
    name: str
    element: str
    resname: str
    chain: str
    resseq: int
    icode: str
    x: float
    y: float
    z: float
    hetero: bool = False

    @property
    def xyz(self):
        return (self.x, self.y, self.z)

    @property
    def residue_key(self):
        return (self.chain, self.resseq, self.icode)


@dataclass
class Residue:
    chain: str
    resseq: int
    icode: str
    resname: str
    atoms: dict                       # atom name -> index
    hetero: bool = False

    @property
    def key(self):
        return (self.chain, self.resseq, self.icode)

    @property
    def letter(self) -> str:
        return THREE_TO_ONE.get(self.resname, "X")

    @property
    def is_amino(self) -> bool:
        return self.resname in THREE_TO_ONE and "CA" in self.atoms

    @property
    def is_water(self) -> bool:
        return self.resname in WATER


@dataclass
class Protein:
    name: str
    atoms: list = field(default_factory=list)       # [Atom]
    bonds: list = field(default_factory=list)       # [(i, j)]
    secondary: dict = field(default_factory=dict)   # residue key -> H/E
    source: str = ""

    def residues(self) -> list:
        out, index = [], {}
        for i, a in enumerate(self.atoms):
            k = a.residue_key
            r = index.get(k)
            if r is None:
                r = index[k] = Residue(a.chain, a.resseq, a.icode,
                                       a.resname, {}, a.hetero)
                out.append(r)
            r.atoms.setdefault(a.name, i)
        return out

    def chains(self) -> list:
        seen = []
        for a in self.atoms:
            if a.chain not in seen:
                seen.append(a.chain)
        return seen

    def sequence(self, chain: str | None = None) -> str:
        return "".join(r.letter for r in self.residues()
                       if r.is_amino and (chain is None or r.chain == chain))

    @property
    def mass(self) -> float:
        return sum(ELEMENTS.get(a.element, (0, 0, 12.0))[2]
                   for a in self.atoms)

    def summary(self) -> dict:
        res = self.residues()
        amino = [r for r in res if r.is_amino]
        ss = [self.secondary.get(r.key, "C") for r in amino]
        return {
            "name": self.name, "source": self.source,
            "chains": {c: self.sequence(c) for c in self.chains()
                       if self.sequence(c)},
            "residues": len(amino),
            "ligands": sorted({r.resname for r in res if not r.is_amino
                               and not r.is_water}),
            "waters": sum(1 for r in res if r.is_water),
            "atoms": len(self.atoms), "bonds": len(self.bonds),
            "helix_residues": sum(1 for s in ss if s in "HG"),
            "strand_residues": sum(1 for s in ss if s == "E"),
            "mass_kda": round(self.mass / 1000.0, 2),
        }


# ------------------------------------------------------------- vectors
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _unit(v):
    n = math.sqrt(_dot(v, v))
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-12 else (1.0, 0.0, 0.0)


def place(a, b, c, bond, angle, torsion):
    """NeRF: the atom bonded to *c* at *bond* Å, angle b-c-d *angle*
    degrees, torsion a-b-c-d *torsion* degrees."""
    th, ph = math.radians(angle), math.radians(torsion)
    bc = _unit(_sub(c, b))
    n = _unit(_cross(_sub(b, a), bc))
    m = _cross(n, bc)
    dx = -bond * math.cos(th)
    dy = bond * math.sin(th) * math.cos(ph)
    dz = bond * math.sin(th) * math.sin(ph)
    return _add(c, _add(_mul(bc, dx), _add(_mul(m, dy), _mul(n, dz))))


def torsion(a, b, c, d) -> float:
    """Dihedral a-b-c-d, degrees."""
    b0, b1, b2 = _sub(a, b), _sub(c, b), _sub(d, c)
    b1u = _unit(b1)
    v = _sub(b0, _mul(b1u, _dot(b0, b1u)))
    w = _sub(b2, _mul(b1u, _dot(b2, b1u)))
    x = _dot(v, w)
    y = _dot(_cross(b1u, v), w)
    return math.degrees(math.atan2(y, x))


# ------------------------------------------------------------ building
def clean_sequence(text: str) -> str:
    """One-letter codes; FASTA headers, spaces, digits and a trailing *
    are dropped. ProteinError on anything else."""
    lines = [ln for ln in str(text).splitlines()
             if not ln.lstrip().startswith(">")]
    seq = re.sub(r"[\s\d*\-]", "", "".join(lines)).upper()
    bad = sorted({ch for ch in seq if ch not in SIDE})
    if bad:
        raise ProteinError(f"Not an amino-acid letter: {', '.join(bad)} "
                           "(use the 20 one-letter codes).")
    if not seq:
        raise ProteinError("An empty sequence.")
    if len(seq) > MAX_RESIDUES:
        raise ProteinError(f"{len(seq)} residues: the builder takes up to "
                           f"{MAX_RESIDUES}.")
    return seq


def clean_secondary(text, n: int) -> str:
    """A secondary-structure string of length *n*: a word (helix, strand,
    polyproline, coil) fills it, a letter string is padded with coil."""
    words = {"helix": "H", "alpha": "H", "alpha_helix": "H", "3-10": "G",
             "strand": "E", "beta": "E", "sheet": "E", "extended": "E",
             "polyproline": "P", "ppii": "P", "coil": "C", "loop": "C"}
    t = str(text or "helix").strip()
    if t.lower() in words:
        return words[t.lower()] * n
    s = re.sub(r"\s", "", t).upper().replace("-", "C").replace(".", "C")
    bad = sorted({ch for ch in s if ch not in PHI_PSI and ch != "T"})
    if bad:
        raise ProteinError(f"Secondary structure letters are "
                           f"{''.join(SECONDARY_NAMES)} (not "
                           f"{', '.join(bad)}).")
    if len(s) > n:
        raise ProteinError(f"The secondary structure has {len(s)} letters "
                           f"for {n} residues.")
    return s + "C" * (n - len(s))


def _chi(expr: str, chis) -> float:
    m = re.match(r"^chi(\d)([+-]\d+(?:\.\d*)?)?$", expr)
    if not m:
        return float(expr)
    k = int(m.group(1)) - 1
    base = chis[k] if k < len(chis) else 180.0
    return base + (float(m.group(2)) if m.group(2) else 0.0)


class _Grid:
    """Points in 3 Å cells, for the rotamer search."""

    def __init__(self, cell=3.0):
        self.cell, self.cells = cell, {}

    def _key(self, p):
        c = self.cell
        return (int(math.floor(p[0] / c)), int(math.floor(p[1] / c)),
                int(math.floor(p[2] / c)))

    def add(self, p, tag):
        self.cells.setdefault(self._key(p), []).append((p, tag))

    def hits(self, p, reach, skip):
        kx, ky, kz = self._key(p)
        r2, n = reach * reach, 0
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for q, tag in self.cells.get((kx + dx, ky + dy,
                                                  kz + dz), ()):
                        if tag in skip:
                            continue
                        if ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2
                                + (p[2] - q[2]) ** 2) < r2:
                            n += 1
        return n


def turn_angles(ss: str, i: int):
    """(phi, psi) of residue *i*: a run of T steps through `TURN` (two
    T between E strands make a hairpin), other letters their own."""
    letter = ss[i]
    if letter != "T":
        return PHI_PSI[letter]
    k = 0
    while i - k - 1 >= 0 and ss[i - k - 1] == "T":
        k += 1
    return TURN[k % len(TURN)]


def build_peptide(sequence: str, secondary="helix", name: str = "",
                  phi_psi=None, chain: str = "A") -> Protein:
    """A chain from its sequence: ideal geometry, (phi, psi) per residue
    from *secondary* (a word or a letter string) unless *phi_psi* rows
    are given; then each side chain on the first rotamer of its list
    that clears everything placed so far."""
    seq = clean_sequence(sequence)
    n = len(seq)
    ss = clean_secondary(secondary, n)
    angles = []
    for i in range(n):
        if phi_psi and i < len(phi_psi) and phi_psi[i] is not None:
            angles.append((float(phi_psi[i][0]), float(phi_psi[i][1])))
            continue
        phi, psi = turn_angles(ss, i)
        if seq[i] == "P" and phi < 0:
            phi = -65.0                      # the ring fixes proline's phi
        angles.append((phi, psi))
    atoms, bonds = [], []

    def add(resi, atom_name, element, xyz):
        atoms.append(Atom(atom_name, element, ONE_TO_THREE[seq[resi]],
                          chain, resi + 1, "", *xyz))
        return len(atoms) - 1

    # backbone first, so side chains can see the whole chain
    backbone, prev, prev_c = [], None, None
    for i, aa in enumerate(seq):
        phi, psi = angles[i]
        if prev is None:
            n_pos = (0.0, 0.0, 0.0)
            ca_pos = (N_CA, 0.0, 0.0)
            ang = math.radians(180.0 - ANG_N_CA_C)
            c_pos = (N_CA + CA_C * math.cos(ang), CA_C * math.sin(ang), 0.0)
        else:
            pn, pca, pc = prev
            n_pos = place(pn, pca, pc, C_N, ANG_CA_C_N, angles[i - 1][1])
            ca_pos = place(pca, pc, n_pos, N_CA, ANG_C_N_CA, OMEGA)
            c_pos = place(pc, n_pos, ca_pos, CA_C, ANG_N_CA_C, phi)
        # carbonyl O anti to the next N (torsion N-CA-C-O = psi + 180)
        o_pos = place(n_pos, ca_pos, c_pos, C_O, ANG_CA_C_O, psi + 180.0)
        pos = {"N": n_pos, "CA": ca_pos, "C": c_pos, "O": o_pos}
        if aa != "G":
            pos["CB"] = place(c_pos, n_pos, ca_pos, 1.530, 110.5,
                              CB_TORSION)
        backbone.append(pos)
        prev = (n_pos, ca_pos, c_pos)
    grid = _Grid()
    for i, pos in enumerate(backbone):
        for p in pos.values():
            grid.add(p, i)
    residues = []
    for i, aa in enumerate(seq):
        pos = dict(backbone[i])
        chosen, fewest = {}, None
        for chis in ROTAMERS.get(aa, [()]):
            trial = dict(pos)
            for atom_name, _el, ra, rb, rc, bond, ang, tor in SIDE[aa]:
                trial[atom_name] = place(trial[ra], trial[rb], trial[rc],
                                         bond, ang, _chi(tor, chis))
            skip = {i, i - 1, i + 1} if aa == "P" else {i}
            bumps = sum(grid.hits(trial[a[0]], ROTAMER_CLEARANCE, skip)
                        for a in SIDE[aa])
            if fewest is None or bumps < fewest:
                chosen, fewest = trial, bumps
            if bumps == 0:
                break
        for atom_name, *_rest in SIDE[aa]:
            grid.add(chosen[atom_name], i)
        residues.append(chosen or pos)
    for i, aa in enumerate(seq):
        pos = residues[i]
        idx = {}
        for atom_name, el in (("N", "N"), ("CA", "C"), ("C", "C"),
                              ("O", "O")):
            idx[atom_name] = add(i, atom_name, el, pos[atom_name])
        bonds += [(idx["N"], idx["CA"]), (idx["CA"], idx["C"]),
                  (idx["C"], idx["O"])]
        if prev_c is not None:
            bonds.append((prev_c, idx["N"]))
        if i == n - 1:
            oxt = place(pos["N"], pos["CA"], pos["C"], 1.25, 117.0,
                        angles[i][1])
            bonds.append((idx["C"], add(i, "OXT", "O", oxt)))
        if aa != "G":
            idx["CB"] = add(i, "CB", "C", pos["CB"])
            bonds.append((idx["CA"], idx["CB"]))
            for atom_name, el, _ra, _rb, rc, *_rest in SIDE[aa]:
                idx[atom_name] = add(i, atom_name, el, pos[atom_name])
                bonds.append((idx[rc], idx[atom_name]))
            for x, y in RING_CLOSURES.get(aa, ()):
                bonds.append((idx[x], idx[y]))
        prev_c = idx["C"]
    centre = [sum(getattr(a, c) for a in atoms) / len(atoms) for c in "xyz"]
    for a in atoms:
        a.x -= centre[0]
        a.y -= centre[1]
        a.z -= centre[2]
    return Protein(name=name or f"Peptide {seq[:12]}"
                   + ("…" if n > 12 else ""),
                   atoms=atoms, bonds=bonds,
                   secondary={(chain, i + 1, ""): s
                              for i, s in enumerate(ss) if s in "HGE"},
                   source="built")


def clashes(p: Protein, limit: float = 2.2) -> int:
    """Atom pairs closer than *limit* Å that are neither bonded nor
    bonded to a common atom — two pieces of chain on top of each
    other."""
    near = set()
    nbrs = [set() for _ in p.atoms]
    for i, j in p.bonds:
        nbrs[i].add(j)
        nbrs[j].add(i)
    count = 0
    for i, j in _pairs_within(p.atoms, limit):
        if j in nbrs[i] or nbrs[i] & nbrs[j]:
            continue
        key = (min(i, j), max(i, j))
        if key not in near:
            near.add(key)
            count += 1
    return count


def _pairs_within(atoms, reach):
    """Index pairs (i < j) closer than *reach* Å, through a grid."""
    cell = max(reach, 1e-3)
    grid = {}
    for i, a in enumerate(atoms):
        grid.setdefault((int(math.floor(a.x / cell)),
                         int(math.floor(a.y / cell)),
                         int(math.floor(a.z / cell))), []).append(i)
    r2 = reach * reach
    for (gx, gy, gz), members in grid.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    other = grid.get((gx + dx, gy + dy, gz + dz))
                    if not other:
                        continue
                    for i in members:
                        a = atoms[i]
                        for j in other:
                            if j <= i:
                                continue
                            b = atoms[j]
                            d2 = ((a.x - b.x) ** 2 + (a.y - b.y) ** 2
                                  + (a.z - b.z) ** 2)
                            if d2 < r2:
                                yield i, j


def distance_bonds(atoms) -> list:
    """Bonds by covalent radii (+0.45 Å), never between alternate
    conformers' duplicates, never to water."""
    out = []
    for i, j in _pairs_within(atoms, 2.4):
        a, b = atoms[i], atoms[j]
        if a.resname in WATER or b.resname in WATER:
            continue
        ra = ELEMENTS.get(a.element, (0.77,))[0]
        rb = ELEMENTS.get(b.element, (0.77,))[0]
        d = math.dist(a.xyz, b.xyz)
        if 0.4 < d < ra + rb + 0.45:
            out.append((i, j))
    return out


# ------------------------------------------------------------- reading
def _element(name: str, given: str, resname: str) -> str:
    g = given.strip()
    if g:
        e = g[0].upper() + g[1:].lower()
        if e in ELEMENTS:
            return e
    letters = re.sub(r"[^A-Za-z]", "", name)
    if resname in THREE_TO_ONE or resname in WATER:
        return letters[:1].upper() or "C"
    two = letters[:2].capitalize()
    return two if two in ELEMENTS and len(letters) >= 2 and \
        two not in ("Ca", "Cd", "Ne", "Nb", "Hg", "Ho") else \
        (letters[:1].upper() or "C")


def parse_pdb(text: str, name: str = "", model: int = 1) -> Protein:
    """A structure from PDB-format text: the first model (or *model*),
    altloc blank or A only, HELIX/SHEET for secondary structure."""
    atoms, helix, sheet, title = [], [], [], ""
    current, want = 1, int(model)
    for line in text.splitlines():
        rec = line[:6]
        if rec == "MODEL ":
            try:
                current = int(line[10:14])
            except ValueError:
                current += 0
        elif rec in ("ATOM  ", "HETATM") and current == want:
            alt = line[16:17]
            if alt not in (" ", "", "A", "1"):
                continue
            try:
                x, y, z = (float(line[30:38]), float(line[38:46]),
                           float(line[46:54]))
                resseq = int(line[22:26])
            except ValueError:
                continue
            atom_name = line[12:16].strip()
            resname = line[17:20].strip()
            element = _element(atom_name, line[76:78] if len(line) > 76
                               else "", resname)
            if element == "H" or element == "D":
                continue
            atoms.append(Atom(atom_name, element, resname,
                              line[21:22].strip() or "A", resseq,
                              line[26:27].strip(), x, y, z,
                              rec == "HETATM"))
        elif rec == "HELIX ":
            try:
                helix.append((line[19:20].strip() or "A", int(line[21:25]),
                              int(line[33:37])))
            except ValueError:
                pass
        elif rec == "SHEET ":
            try:
                sheet.append((line[21:22].strip() or "A", int(line[22:26]),
                              int(line[33:37])))
            except ValueError:
                pass
        elif rec == "TITLE " and not title:
            title = line[10:].strip()
    return _finish(atoms, helix, sheet, name or title.title()[:60])


def _cif_tokens(text: str):
    """mmCIF tokens: quoted strings, ;-delimited text fields, words."""
    lines = text.splitlines()
    i = 0
    word = re.compile(r"""'(?:[^']|'(?!\s|$))*'|"(?:[^"]|"(?!\s|$))*"|\S+""")
    while i < len(lines):
        line = lines[i]
        if line.startswith(";"):
            block = [line[1:]]
            i += 1
            while i < len(lines) and not lines[i].startswith(";"):
                block.append(lines[i])
                i += 1
            i += 1
            yield "\n".join(block).strip()
            continue
        for m in word.finditer(line):
            tok = m.group()
            if tok.startswith("#"):
                break
            if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "'\"":
                tok = tok[1:-1]
            yield tok
        i += 1


def cif_tables(text: str) -> dict:
    """{category: [ {item: value} ]} for every loop and key-value pair."""
    tables = {}
    toks = list(_cif_tokens(text))
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.lower() == "loop_":
            i += 1
            items = []
            while i < len(toks) and toks[i].startswith("_"):
                items.append(toks[i])
                i += 1
            values = []
            while i < len(toks) and not toks[i].startswith("_") and \
                    toks[i].lower() != "loop_" and \
                    not toks[i].lower().startswith("data_"):
                values.append(toks[i])
                i += 1
            if not items:
                continue
            cat = items[0].split(".")[0]
            keys = [it.split(".", 1)[-1] for it in items]
            rows = tables.setdefault(cat, [])
            for k in range(0, len(values) - len(keys) + 1, len(keys)):
                rows.append(dict(zip(keys, values[k:k + len(keys)])))
        elif t.startswith("_") and "." in t and i + 1 < len(toks):
            cat, key = t.split(".", 1)
            rows = tables.setdefault(cat, [{}])
            rows[0][key] = toks[i + 1]
            i += 2
        else:
            i += 1
    return tables


def parse_mmcif(text: str, name: str = "", model: int = 1) -> Protein:
    """A structure from mmCIF text (author chain and residue numbers)."""
    tables = cif_tables(text)
    atoms = []
    for row in tables.get("_atom_site", []):
        try:
            if int(row.get("pdbx_PDB_model_num", "1") or 1) != int(model):
                continue
        except ValueError:
            pass
        if row.get("label_alt_id", ".") not in (".", "?", "A", "1"):
            continue
        element = _element(row.get("auth_atom_id", row.get("label_atom_id",
                                                           "C")),
                           row.get("type_symbol", ""),
                           row.get("auth_comp_id", ""))
        if element in ("H", "D"):
            continue
        try:
            resseq = int(row.get("auth_seq_id") or row.get("label_seq_id"))
            x, y, z = (float(row["Cartn_x"]), float(row["Cartn_y"]),
                       float(row["Cartn_z"]))
        except (KeyError, TypeError, ValueError):
            continue
        icode = row.get("pdbx_PDB_ins_code", "?")
        atoms.append(Atom(
            row.get("auth_atom_id") or row.get("label_atom_id", "X"),
            element, row.get("auth_comp_id") or row.get("label_comp_id", ""),
            row.get("auth_asym_id") or row.get("label_asym_id", "A"),
            resseq, "" if icode in ("?", ".") else icode, x, y, z,
            row.get("group_PDB") == "HETATM"))

    def ranges(cat, want=None):
        out = []
        for row in tables.get(cat, []):
            if want and not row.get("conf_type_id", "").startswith(want):
                continue
            try:
                out.append((row.get("beg_auth_asym_id", "A"),
                            int(row["beg_auth_seq_id"]),
                            int(row["end_auth_seq_id"])))
            except (KeyError, ValueError):
                continue
        return out

    title = ""
    for row in tables.get("_struct", []):
        title = row.get("title", "")
    if not name:
        entry = tables.get("_entry", [{}])[0].get("id", "")
        name = (title.title()[:60] or entry)
    return _finish(atoms, ranges("_struct_conf", "HELX"),
                   ranges("_struct_sheet_range"), name)


def _finish(atoms, helix, sheet, name) -> Protein:
    if not atoms:
        raise ProteinError("No atoms in that structure.")
    p = Protein(name=name or "Protein", atoms=atoms,
                bonds=distance_bonds(atoms), source="file")
    for letter, ranges in (("H", helix), ("E", sheet)):
        for chain, a, b in ranges:
            for r in range(min(a, b), max(a, b) + 1):
                p.secondary[(chain, r, "")] = letter
    if not helix and not sheet:
        p.secondary = assign_secondary(p)
    return p


def to_pdb(p: Protein) -> str:
    """PDB-format text: HELIX and SHEET records from the secondary
    structure, then every atom (HETATM for hetero groups), TER per chain
    — what PyMOL, ChimeraX or a docking tool reads."""
    lines = [f"TITLE     {p.name[:70]}"]
    runs = []
    for r in p.residues():
        s = p.secondary.get(r.key, "C")
        if runs and runs[-1][0] == s and runs[-1][1] == r.chain and \
                r.resseq == runs[-1][3] + 1:
            runs[-1][3] = r.resseq
            runs[-1][5] = r.resname
        else:
            runs.append([s, r.chain, r.resseq, r.resseq, r.resname,
                         r.resname])
    helices = [x for x in runs if x[0] in "HG"]
    for k, (s, ch, a, b, ra, rb) in enumerate(helices, 1):
        lines.append(f"HELIX  {k:>3} {k:>3} {ra:>3} {ch}{a:>5}  {rb:>3} "
                     f"{ch}{b:>5} {1 if s == 'H' else 5:>2}"
                     f"{'':31}{b - a + 1:>5}")
    for k, (s, ch, a, b, ra, rb) in enumerate(
            [x for x in runs if x[0] == "E"], 1):
        lines.append(f"SHEET  {k:>3} S{k:<2} 1 {ra:>3} {ch}{a:>4}  {rb:>3} "
                     f"{ch}{b:>4}  0")
    serial, last_chain = 0, None
    for a in p.atoms:
        if last_chain is not None and a.chain != last_chain:
            serial += 1
            lines.append(f"TER   {serial:>5}")
        serial += 1
        name = a.name if len(a.name) == 4 or len(a.element) == 2 \
            else " " + a.name
        lines.append(
            f"{'HETATM' if a.hetero else 'ATOM  '}{serial % 100000:>5} "
            f"{name:<4} {a.resname:>3} {a.chain[:1]}{a.resseq:>4}"
            f"{a.icode[:1] or ' '}   {a.x:8.3f}{a.y:8.3f}{a.z:8.3f}"
            f"{1.0:6.2f}{0.0:6.2f}          {a.element.upper():>2}")
        last_chain = a.chain
    lines += [f"TER   {serial + 1:>5}", "END"]
    return "\n".join(lines) + "\n"


def read_structure(path: str, name: str = "") -> Protein:
    """A PDB or mmCIF file (.pdb, .ent, .cif, .mmcif; .gz too)."""
    import gzip
    opener = gzip.open if path.endswith(".gz") else open
    try:
        with opener(path, "rt", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as exc:
        raise ProteinError(f"Cannot read {path}: {exc}")
    stem = os.path.basename(path).split(".")[0]
    return parse_text(text, name or stem)


def parse_text(text: str, name: str = "") -> Protein:
    if re.search(r"^_atom_site\.", text, re.M):
        return parse_mmcif(text, name)
    return parse_pdb(text, name)


# ------------------------------------------------- secondary structure
def assign_secondary(p: Protein) -> dict:
    """Helix and strand from CA distances alone (P-SEA-like): i..i+4 is
    helical when d(i,i+2), d(i,i+3), d(i,i+4) sit at 5.5, 5.3, 6.4 Å;
    extended when at 6.7, 9.9, 12.4 Å and a CA of another stretch lies
    within 5.5 Å (a partner strand). Runs shorter than 4 (helix) or 3
    (strand) are dropped."""
    out = {}
    by_chain = {}
    for r in p.residues():
        if r.is_amino:
            by_chain.setdefault(r.chain, []).append(r)
    for chain, res in by_chain.items():
        ca = [p.atoms[r.atoms["CA"]].xyz for r in res]
        n = len(ca)
        ss = ["C"] * n

        def d(i, j):
            return math.dist(ca[i], ca[j])

        for i in range(n - 4):
            if abs(d(i, i + 2) - 5.5) < 0.5 and abs(d(i, i + 3) - 5.3) < \
                    0.5 and abs(d(i, i + 4) - 6.4) < 0.6:
                for k in range(i, i + 5):
                    ss[k] = "H"
        ext = [False] * n
        for i in range(n - 4):
            if abs(d(i, i + 2) - 6.7) < 0.6 and abs(d(i, i + 3) - 9.9) < \
                    0.9 and abs(d(i, i + 4) - 12.4) < 1.1:
                for k in range(i, i + 5):
                    ext[k] = True
        for i in range(n):
            if ext[i] and ss[i] == "C" and any(
                    ext[j] and abs(i - j) > 3 and d(i, j) < 5.5
                    for j in range(n)):
                ss[i] = "E"
        for letter, shortest in (("H", 4), ("E", 3)):
            i = 0
            while i < n:
                if ss[i] != letter:
                    i += 1
                    continue
                j = i
                while j < n and ss[j] == letter:
                    j += 1
                if j - i < shortest:
                    for k in range(i, j):
                        ss[k] = "C"
                i = j
        for r, s in zip(res, ss):
            if s != "C":
                out[r.key] = s
    return out


# ------------------------------------------------------------- fetching
RCSB_URL = "https://files.rcsb.org/download/{id}.cif"
ALPHAFOLD_API = "https://alphafold.ebi.ac.uk/api/prediction/{id}"


def cache_dir() -> str:
    path = os.path.join(tempfile.gettempdir(), "khervecad_proteins")
    os.makedirs(path, exist_ok=True)
    return path


def _download(url: str, opener=None) -> bytes:
    import urllib.request
    if opener is None:
        from .geo import urlopen as opener
    req = urllib.request.Request(url, headers={"User-Agent": "KherveCAD"})
    try:
        with opener(req, timeout=60) as resp:
            return resp.read()
    except Exception as exc:                          # noqa: BLE001
        raise ProteinError(f"Could not download {url}: {exc}")


def fetch(pdb_id: str = "", uniprot: str = "", opener=None) -> Protein:
    """A structure from RCSB (*pdb_id*, e.g. 1CRN) or the AlphaFold
    database (*uniprot*, e.g. P69905), cached in the temp folder."""
    import json
    if pdb_id:
        ident = pdb_id.strip().upper()
        if not re.fullmatch(r"[0-9][A-Z0-9]{3}", ident):
            raise ProteinError(f"'{pdb_id}' is not a PDB ID (four "
                               "characters, a digit first: 1CRN, 4HHB).")
        path = os.path.join(cache_dir(), f"{ident}.cif")
        if not os.path.exists(path):
            data = _download(RCSB_URL.format(id=ident), opener)
            with open(path, "wb") as fh:
                fh.write(data)
        p = read_structure(path, "")
        p.source = f"PDB {ident}"
        if not p.name or p.name == ident:
            p.name = f"PDB {ident}"
        return p
    if uniprot:
        ident = uniprot.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{6,10}", ident):
            raise ProteinError(f"'{uniprot}' is not a UniProt accession "
                               "(e.g. P69905).")
        cached = [os.path.join(cache_dir(), f"AF-{ident}{ext}")
                  for ext in (".pdb", ".cif")]
        path = next((c for c in cached if os.path.exists(c)), None)
        if path is None:
            meta = _download(ALPHAFOLD_API.format(id=ident), opener)
            try:
                entry = json.loads(meta.decode("utf-8"))[0]
                url = entry.get("pdbUrl") or entry["cifUrl"]
            except (ValueError, KeyError, IndexError, TypeError):
                raise ProteinError(f"AlphaFold has no model for {ident}.")
            data = _download(url, opener)
            path = os.path.join(cache_dir(), f"AF-{ident}"
                                + (".cif" if url.endswith(".cif")
                                   else ".pdb"))
            with open(path, "wb") as fh:
                fh.write(data)
        p = read_structure(path, "")
        p.source = f"AlphaFold {ident}"
        p.name = f"AlphaFold {ident}"
        return p
    raise ProteinError("Give a PDB ID or a UniProt accession.")
