"""The Protein Builder's programs: a `protein.Protein` as OpenSCAD
(Qt-free but `apply`, which is the Compound Builder's).

Styles:

- **cartoon** — the backbone as a ribbon through the CA atoms (a
  Catmull-Rom spline, `SAMPLES` rings a residue): alpha helices a flat
  ribbon wound round the helix, strands a flat ribbon ending in an
  arrow, everything else a round tube. The ribbon's width follows the
  peptide plane (the C=O direction, flipped wherever it would twist
  back), which is what lays a helix ribbon along its axis and a strand
  ribbon in its sheet. Each stretch of one colour is ONE closed
  polyhedron (rings joined index to index and capped), so
  the preview is exact and nothing is baked;
- **cartoon_sticks** — the cartoon plus every side chain as sticks;
- **trace** — a round tube through the CA atoms only;
- **ball_and_stick**, **sticks**, **space_filling** — every atom, as the
  Compound Builder draws a molecule, but written as ONE for-loop per
  (colour, radius) over coordinate rows, so a 2,000-atom protein is a
  few dozen nodes rather than thousands.

Colours: ``structure`` (helix, strand, coil), ``chain``, ``rainbow`` (N
to C terminus, blue to red), ``residue`` (hydrophobic, aromatic, polar,
positive, negative, special), ``hydropathy`` (Kyte-Doolittle, blue to
orange) and ``element`` (atom styles). Ligands (non-water HETATM
groups) are drawn ball and stick in element colours next to a cartoon.

Everything is in NANOMETRES, like the molecules.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import colorsys
import math

from . import molecule as mol
from . import molecule_build as mb
from . import protein as P
from .crystal import ELEMENTS

NM = mb.NM
STYLES = ("cartoon", "cartoon_sticks", "trace", "ball_and_stick",
          "sticks", "space_filling")
COLOURS = ("structure", "chain", "rainbow", "residue", "hydropathy",
           "element")
BUDGET = 800_000

SS_COLOURS = {"H": "#e0457b", "G": "#e0457b", "E": "#f2c230",
              "C": "#b8bcc4"}
CHAIN_COLOURS = ("#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#76b7b2",
                 "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac")
CLASS_COLOURS = {"hydrophobic": "#d9a441", "aromatic": "#9b6fd1",
                 "polar": "#4fb39a", "positive": "#3b6fe0",
                 "negative": "#e0453b", "special": "#9aa0a8"}
UNKNOWN_COLOUR = "#9aa0a8"

#: half width, half thickness of the cartoon's cross-section, Å
COIL = (0.35, 0.35)
HELIX = (1.4, 0.28)
STRAND = (1.2, 0.28)
ARROW = 2.1                         # half width at the arrow's base
TIP = 0.35
SAMPLES = 6                         # rings a residue (even: a ring at
RING = 8                            # every half residue); points a ring
GAP = 4.3                           # CA-CA farther than this: chain break
BALL = 0.25                         # atom styles: x vdW radius
STICK = 0.15


class BuildError(mb.BuildError):
    """A protein that cannot be built; says what to do."""


# ---------------------------------------------------------------- text
_n = mb._n


def _hex(r, g, b) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v * 255))))
                                   for v in (r, g, b))


def _rainbow(t: float) -> str:
    return _hex(*colorsys.hsv_to_rgb(0.667 * (1.0 - t), 0.75, 0.92))


def _hydropathy(v: float) -> str:
    t = max(-1.0, min(1.0, v / 4.5))
    white = (0.95, 0.95, 0.95)
    end = (0.93, 0.55, 0.15) if t > 0 else (0.25, 0.45, 0.85)
    k = abs(t)
    return _hex(*(white[c] + (end[c] - white[c]) * k for c in range(3)))


def residue_colours(p: P.Protein, scheme: str) -> dict:
    """{residue key: colour} for every amino-acid residue."""
    out = {}
    chains = p.chains()
    by_chain = {}
    for r in p.residues():
        if r.is_amino:
            by_chain.setdefault(r.chain, []).append(r)
    for chain, res in by_chain.items():
        n = len(res)
        for i, r in enumerate(res):
            if scheme == "chain" or scheme == "element":
                c = CHAIN_COLOURS[chains.index(chain) % len(CHAIN_COLOURS)]
            elif scheme == "rainbow":
                c = _rainbow(i / max(1, n - 1))
            elif scheme == "residue":
                c = CLASS_COLOURS.get(P.RESIDUE_CLASS.get(r.letter),
                                      UNKNOWN_COLOUR)
            elif scheme == "hydropathy":
                c = _hydropathy(P.HYDROPATHY.get(r.letter, 0.0))
            else:
                c = SS_COLOURS[p.secondary.get(r.key, "C")]
            out[r.key] = c
    return out


# ------------------------------------------------------------- cartoon
def _catmull(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return tuple(0.5 * (2 * p1[c] + (-p0[c] + p2[c]) * t
                        + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t2
                        + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t3)
                 for c in range(3))


def chain_runs(p: P.Protein, chains=None) -> list:
    """Unbroken stretches of amino-acid residues with a CA, per chain."""
    runs, current, last = [], [], None
    for r in p.residues():
        if not r.is_amino or (chains and r.chain not in chains):
            continue
        ca = p.atoms[r.atoms["CA"]].xyz
        if current and (r.chain != current[-1].chain
                        or math.dist(ca, last) > GAP):
            runs.append(current)
            current = []
        current.append(r)
        last = ca
    if current:
        runs.append(current)
    return [run for run in runs if len(run) >= 2]


def _shape(ss, i, u, trace):
    """(half width, half thickness) of residue *i* at spline position
    *u* (residue units)."""
    if trace:
        return COIL
    s = ss[i]
    if s in "HG":
        return HELIX
    if s == "E":
        if i + 1 >= len(ss) or ss[i + 1] != "E":        # the arrow
            k = max(0.0, min(1.0, u - (i - 0.5)))
            return (ARROW + (TIP - ARROW) * k, STRAND[1])
        return STRAND
    return COIL


def ribbon(p: P.Protein, run, colours: dict, trace=False,
           samples=SAMPLES, ring=RING) -> list:
    """[(colour, (points, faces))] for one unbroken run: closed tubes
    (Å, faces counter-clockwise), one per stretch of one colour."""
    ss = ["C" if trace else p.secondary.get(r.key, "C") for r in run]
    for i, s in enumerate(ss):                 # a lone helix residue
        if s in "HG" and (i == 0 or ss[i - 1] not in "HG") and \
                (i + 1 >= len(ss) or ss[i + 1] not in "HG"):
            ss[i] = "C"
    ca = [p.atoms[r.atoms["CA"]].xyz for r in run]
    n = len(ca)
    # width directions from the peptide planes, kept from flipping
    widths, prev = [], None
    for i, r in enumerate(run):
        t = P._unit(P._sub(ca[min(i + 1, n - 1)], ca[max(i - 1, 0)]))
        if "O" in r.atoms and "C" in r.atoms:
            w = P._sub(p.atoms[r.atoms["O"]].xyz, p.atoms[r.atoms["C"]].xyz)
        elif 0 < i < n - 1:
            mid = P._mul(P._add(ca[i - 1], ca[i + 1]), 0.5)
            w = P._sub(ca[i], mid)
        else:
            w = P._cross(t, (0.0, 0.0, 1.0))
        w = P._sub(w, P._mul(t, P._dot(w, t)))
        if P._dot(w, w) < 1e-9:
            w = prev or P._cross(t, (1.0, 0.0, 0.0))
        w = P._unit(w)
        if prev is not None and P._dot(w, prev) < 0:
            w = P._mul(w, -1.0)
        widths.append(w)
        prev = w
    ext = [ca[0]] + ca + [ca[-1]]
    # rings: (u, residue, position, tangent, width dir, shape, colour)
    rings = []
    total = (n - 1) * samples
    for k in range(total + 1):
        u = k / samples
        i = min(int(u), n - 2)
        t = u - i
        pos = _catmull(ext[i], ext[i + 1], ext[i + 2], ext[i + 3], t)
        a = _catmull(ext[i], ext[i + 1], ext[i + 2], ext[i + 3],
                     max(0.0, t - 0.01))
        b = _catmull(ext[i], ext[i + 1], ext[i + 2], ext[i + 3],
                     min(1.0, t + 0.01))
        tan = P._unit(P._sub(b, a))
        wd = P._add(P._mul(widths[i], 1 - t), P._mul(widths[i + 1], t))
        wd = P._sub(wd, P._mul(tan, P._dot(wd, tan)))
        wd = P._unit(wd) if P._dot(wd, wd) > 1e-9 else widths[i]
        owners = [int(math.floor(u + 0.5))]
        if k % samples == samples // 2 and k < total:
            owners = [i, i + 1]                   # a half residue: a seam
        for j, r in enumerate(owners):
            r = min(r, n - 1)
            rings.append((u, r, pos, tan, wd, _shape(ss, r, u, trace),
                          colours.get(run[r].key, UNKNOWN_COLOUR),
                          j == 1))
    pieces, current = [], []
    for item in rings:
        seam = item[7]
        if current and seam:
            last = current[-1]
            if item[6] != last[6]:
                pieces.append(current)
                current = [item]
                continue
            if item[5] == last[5]:
                continue                          # nothing changes here
        current.append(item)
    if current:
        pieces.append(current)
    out = []
    for piece in pieces:
        if len(piece) < 2:
            continue
        out.append((piece[0][6], _tube(piece, ring)))
    return out


def _tube(piece, m):
    """(points, faces) of one closed tube: a ring of *m* points a ring,
    a centre point capping each end; faces counter-clockwise from
    outside (turned by the signed volume)."""
    points = []
    for _u, _r, pos, tan, wd, (hw, ht), _c, _s in piece:
        bn = P._cross(tan, wd)
        for j in range(m):
            a = 2 * math.pi * j / m
            ca_, sa = math.cos(a), math.sin(a)
            points.append(tuple(pos[c] + wd[c] * hw * ca_ + bn[c] * ht * sa
                                for c in range(3)))
    rings = len(piece)
    faces = []
    for k in range(rings - 1):
        for j in range(m):
            a, b = k * m + j, k * m + (j + 1) % m
            faces.append((a, b, b + m))
            faces.append((a, b + m, a + m))
    for k, flip in ((0, True), (rings - 1, False)):
        centre = len(points)
        points.append(piece[k][2])
        for j in range(m):
            a, b = k * m + j, k * m + (j + 1) % m
            faces.append((centre, b, a) if flip else (centre, a, b))
    vol = sum(P._dot(points[f[0]], P._cross(points[f[1]], points[f[2]]))
              for f in faces)
    if vol < 0:
        faces = [(f[0], f[2], f[1]) for f in faces]
    return points, faces


def _polyhedron(parts, label) -> str:
    """One OpenSCAD polyhedron from several closed (points, faces) parts
    (disjoint shells), faces turned clockwise from outside."""
    pts, faces, base = [], [], 0
    for points, fs in parts:
        pts += points
        faces += [(f[0] + base, f[2] + base, f[1] + base) for f in fs]
        base += len(points)
    text = ", ".join("[" + ", ".join(_n(v * NM) for v in q) + "]"
                     for q in pts)
    ftext = ", ".join(f"[{a}, {b}, {c}]" for a, b, c in faces)
    return f"polyhedron(points = [{text}], faces = [{ftext}]);  // {label}"


# --------------------------------------------------------------- atoms
def _bond_rows(p, bonds, colour_of, radius_fn=None):
    """{colour: [row]} of half-bond sticks, rows [x, y, z, tilt, turn,
    length] in nm."""
    groups = {}
    for i, j in bonds:
        a, b = p.atoms[i].xyz, p.atoms[j].xyz
        mid = tuple((a[c] + b[c]) / 2 for c in range(3))
        for start, end, k in ((a, mid, i), (mid, b, j)):
            d = P._sub(end, start)
            length = math.sqrt(P._dot(d, d))
            if length < 1e-6:
                continue
            tilt = math.degrees(math.acos(max(-1.0, min(1.0,
                                                         d[2] / length))))
            turn = math.degrees(math.atan2(d[1], d[0]))
            groups.setdefault(colour_of(k), []).append(
                [start[0] * NM, start[1] * NM, start[2] * NM, tilt, turn,
                 length * NM])
    return groups


def _loop(var, rows, body, label) -> list:
    text = ", ".join("[" + ", ".join(_n(v) for v in row) + "]"
                     for row in rows)
    return [f"for ({var} = [{text}])  // {label}", "  " + body]


def atom_lines(p, indices, bonds, style, colour_of, fn):
    """(lines, triangles) of the atoms *indices* and *bonds* between
    them, one loop per (colour, radius) and per stick colour."""
    lines, tris = [], 0
    per_ball, per_stick = mb._tris("sphere", fn), mb._tris("cylinder", fn)
    balls = {}
    for k in indices:
        a = p.atoms[k]
        if style == "space_filling":
            r = mol.vdw(a.element)
        elif style == "sticks":
            r = STICK
        else:
            r = BALL * mol.vdw(a.element)
        balls.setdefault((colour_of(k), round(r * NM, 4)), []).append(
            [a.x * NM, a.y * NM, a.z * NM])
    for (colour, r), rows in balls.items():
        lines.append(f'color("{colour}") {{')
        lines += ["  " + ln for ln in _loop(
            "p", rows, "translate([p[0], p[1], p[2]]) "
            f"sphere(r = {_n(r)}, $fn = {fn});",
            f"{len(rows)} atoms")]
        lines.append("}")
        tris += per_ball * len(rows)
    if style != "space_filling" and bonds:
        radius = STICK * NM
        for colour, rows in _bond_rows(p, bonds, colour_of).items():
            lines.append(f'color("{colour}") {{')
            lines += ["  " + ln for ln in _loop(
                "b", rows,
                "translate([b[0], b[1], b[2]]) rotate([0, b[3], b[4]]) "
                f"cylinder(h = b[5], r = {_n(radius)}, $fn = {fn});",
                f"{len(rows)} half bonds")]
            lines.append("}")
            tris += per_stick * len(rows)
    return lines, tris


# ------------------------------------------------------------- program
def _chains(value):
    if not value:
        return None
    if isinstance(value, str):
        value = [c for c in value.replace(",", " ").split() if c]
    return {str(c) for c in value}


def protein_program(p: P.Protein, style="cartoon", colour="",
                    chains=None, ligands=True, water=False, fn=10,
                    detail=SAMPLES, name=""):
    """(program, stats) for one protein, centred on the origin."""
    if style not in STYLES:
        raise BuildError(f"style is one of {', '.join(STYLES)}.")
    colour = colour or ("element" if style in ("ball_and_stick", "sticks",
                                               "space_filling")
                        else "structure")
    if colour not in COLOURS:
        raise BuildError(f"colour is one of {', '.join(COLOURS)}.")
    want = _chains(chains)
    if want and not want & set(p.chains()):
        raise BuildError(f"No chain {', '.join(sorted(want))}; this "
                         f"structure has {', '.join(p.chains())}.")
    detail = max(2, int(detail) // 2 * 2)
    res_colour = residue_colours(p, colour)
    residues = [r for r in p.residues()
                if not want or r.chain in want]
    amino = [r for r in residues if r.is_amino]
    hetero = [r for r in residues if not r.is_amino
              and (water or not r.is_water)
              and (ligands or r.is_water)]
    keep = [k for r in residues for k in r.atoms.values()]
    if not keep:
        raise BuildError("Nothing to draw.")
    centre = [sum(getattr(p.atoms[k], c) for k in keep) / len(keep)
              for c in "xyz"]
    title = name or p.name
    groups, tris = [], 0

    def element_or_residue(k):
        a = p.atoms[k]
        if colour == "element" or a.residue_key not in res_colour:
            return ELEMENTS.get(a.element, (0, UNKNOWN_COLOUR))[1]
        return res_colour[a.residue_key]

    def side_colour(k):
        a = p.atoms[k]
        if a.element == "C" and a.residue_key in res_colour:
            return res_colour[a.residue_key]
        return ELEMENTS.get(a.element, (0, UNKNOWN_COLOUR))[1]

    # everything is drawn about the centre
    shifted = P.Protein(p.name, [P.Atom(a.name, a.element, a.resname,
                                        a.chain, a.resseq, a.icode,
                                        a.x - centre[0], a.y - centre[1],
                                        a.z - centre[2], a.hetero)
                                 for a in p.atoms],
                        p.bonds, p.secondary, p.source)
    bonds_of = {}
    for i, j in p.bonds:
        bonds_of.setdefault(p.atoms[i].residue_key, []).append((i, j))
        if p.atoms[j].residue_key != p.atoms[i].residue_key:
            bonds_of.setdefault(p.atoms[j].residue_key, []).append((i, j))
    ribbons = 0
    if style in ("cartoon", "cartoon_sticks", "trace"):
        for run in chain_runs(shifted, want):
            lines = []
            by_colour = {}
            for c, part in ribbon(shifted, run, res_colour,
                                  style == "trace", detail):
                by_colour.setdefault(c, []).append(part)
            for c, parts in by_colour.items():
                lines.append(f'color("{c}") ' + _polyhedron(parts,
                                                            "Backbone"))
                tris += sum(len(f) for _pts, f in parts)
                ribbons += len(parts)
            label = f"Chain {run[0].chain} {run[0].resseq}-{run[-1].resseq}"
            groups.append((label, lines))
        if style == "cartoon_sticks":
            backbone = {"N", "C", "O", "OXT"}
            for chain in (want or p.chains()):
                idx = [k for r in amino if r.chain == chain
                       for nm, k in r.atoms.items()
                       if nm not in backbone]
                side = set(idx)
                bonds = [(i, j) for i, j in p.bonds
                         if i in side and j in side]
                if not idx:
                    continue
                lines, t = atom_lines(shifted, [k for k in idx
                                                if p.atoms[k].name != "CA"],
                                      bonds, "sticks", side_colour, fn)
                tris += t
                groups.append((f"Side chains {chain}", lines))
    else:
        for chain in (want or p.chains()):
            res = [r for r in amino if r.chain == chain]
            if not res:
                continue
            idx = {k for r in res for k in r.atoms.values()}
            bonds = [(i, j) for i, j in p.bonds if i in idx and j in idx]
            lines, t = atom_lines(shifted, sorted(idx), bonds, style,
                                  element_or_residue, fn)
            tris += t
            groups.append((f"Chain {chain}", lines))
    if hetero:
        idx = {k for r in hetero for k in r.atoms.values()}
        bonds = [(i, j) for i, j in p.bonds if i in idx and j in idx]
        het_style = style if style in ("ball_and_stick", "sticks",
                                       "space_filling") else "ball_and_stick"
        lines, t = atom_lines(
            shifted, sorted(idx), bonds, het_style,
            lambda k: ELEMENTS.get(p.atoms[k].element,
                                   (0, UNKNOWN_COLOUR))[1], fn)
        tris += t
        names = sorted({r.resname for r in hetero})
        groups.append(("Ligands " + " ".join(names[:6]), lines))
    if tris > BUDGET:
        raise BuildError(f"About {tris:,} triangles (the limit is "
                         f"{BUDGET:,}): draw it as a cartoon or trace, "
                         "pick fewer chains or lower the segments.")
    ident = mb._ident(title)
    body = []
    for label, lines in groups:
        body.append(f"union() {{  // {mb._label(label)}")
        body += ["  " + ln for ln in lines]
        body.append("}")
    summary = p.summary()
    seqs = [f"chain {c}: {len(s)} residues" for c, s in
            summary["chains"].items() if not want or c in want]
    code = ("\n".join([f"// {mb._label(title)}",
                       f"// {p.source or 'protein'}; " + "; ".join(seqs),
                       f"// {style.replace('_', ' ')}, coloured by "
                       f"{colour}. UNITS: nanometres. Built by KherveCAD's "
                       "Protein Builder."]) + "\n\n"
            + mb._module(ident, body)
            + f"\n{ident}();  // {mb._label(title)}\n")
    stats = dict(summary)
    stats.update({"name": title, "style": style, "colour": colour,
                  "segments": fn, "triangles": tris, "ribbons": ribbons, "unit": "nm",
                  "drawn_residues": len(amino),
                  "drawn_ligand_atoms": sum(len(r.atoms) for r in hetero)})
    if p.source == "built":
        stats["clashes"] = P.clashes(p)
    return code, stats


# ------------------------------------------------------------- presets
#: key -> (name, sequence, secondary structure, what it shows)
PRESETS = {
    "alpha_helix": ("Alpha helix (poly-alanine)", "A" * 20, "helix",
                    "3.6 residues a turn, 5.4 Å pitch"),
    "helix_310": ("3-10 helix", "A" * 15, "G",
                  "tighter than alpha: 3 residues a turn"),
    "beta_strand": ("Beta strand (poly-valine)", "V" * 12, "strand",
                    "side chains alternate either face"),
    "beta_hairpin": ("Beta hairpin (Trpzip2)", "SWTWENGKWTWK",
                     "CEEEETTEEEEC", "two strands and a tight turn"),
    "polyproline": ("Polyproline II helix", "P" * 15, "P",
                    "left-handed, 3 residues a turn"),
    "collagen_strand": ("Collagen strand (Gly-Pro-Pro)", "GPP" * 8, "P",
                        "one chain of the triple helix"),
    "melittin": ("Melittin (bee venom)", "GIGAVLKVLTTGLPALISWIKRKRQQ",
                 "C" + "H" * 24 + "C", "a 26-residue helix"),
    "magainin2": ("Magainin 2 (frog skin)", "GIGKFLHSAKKFGKAFVGEIMNS",
                  "helix", "an amphipathic antimicrobial helix"),
    "gcn4_zipper": ("GCN4 leucine zipper (one helix)",
                    "RMKQLEDKVEELLSKNYHLENEVARLKKLVGER", "helix",
                    "leucines every seventh residue"),
    "amyloid_beta": ("Amyloid beta 1-42 (extended)",
                     "DAEFRHDSGYEVHHQKLVFFAEDVGSNKGAIIGLMVGGVVIA", "strand",
                     "the Alzheimer's peptide, stretched out"),
}


def preset(key: str) -> P.Protein:
    try:
        name, seq, ss, _note = PRESETS[key]
    except KeyError:
        raise BuildError(f"No preset '{key}'; the presets are "
                         f"{', '.join(PRESETS)}.")
    return P.build_peptide(seq, ss, name=name)


# ----------------------------------------------------------------- MCP
def resolve(params: dict, opener=None) -> P.Protein:
    """The protein a build_protein call names."""
    try:
        if params.get("preset"):
            return preset(str(params["preset"]))
        if params.get("sequence"):
            return P.build_peptide(str(params["sequence"]),
                                   params.get("secondary") or "helix",
                                   name=str(params.get("name") or ""),
                                   phi_psi=params.get("phi_psi"))
        if params.get("pdb_id") or params.get("uniprot"):
            return P.fetch(str(params.get("pdb_id") or ""),
                           str(params.get("uniprot") or ""), opener)
        if params.get("path"):
            return P.read_structure(str(params["path"]),
                                    str(params.get("name") or ""))
        if params.get("pdb_text"):
            return P.parse_text(str(params["pdb_text"]),
                                str(params.get("name") or ""))
    except P.ProteinError as exc:
        raise BuildError(str(exc))
    raise BuildError("Give a preset, a sequence, a pdb_id, a uniprot "
                     "accession, a path or pdb_text.")


def list_proteins(_params: dict) -> dict:
    return {
        "presets": [{"key": k, "name": v[0], "sequence": v[1],
                     "secondary": v[2], "shows": v[3]}
                    for k, v in PRESETS.items()],
        "secondary_letters": P.SECONDARY_NAMES,
        "styles": list(STYLES), "colours": list(COLOURS),
        "amino_acids": {k: P.ONE_TO_THREE[k] for k in sorted(P.SIDE)},
        "units": "nm",
        "notes": ("A sequence is built with ideal geometry on the (phi, "
                  "psi) of each secondary-structure letter; it is not "
                  "folded. For a real fold give pdb_id (RCSB) or uniprot "
                  "(AlphaFold)."),
    }


def build_protein(window, params: dict, opener=None) -> dict:
    p = resolve(params, opener)
    fn = int(params.get("segments", 10))
    if not 4 <= fn <= 64:
        raise BuildError("segments runs from 4 to 64.")
    code, stats = protein_program(
        p, str(params.get("style") or "cartoon"),
        str(params.get("colour") or params.get("color") or ""),
        params.get("chains"), bool(params.get("ligands", True)),
        bool(params.get("water", False)), fn,
        int(params.get("detail", SAMPLES)), str(params.get("name") or ""))
    if params.get("dry_run"):
        stats["dry_run"] = True
        return stats
    return mb.apply(window, code, stats, fn)
