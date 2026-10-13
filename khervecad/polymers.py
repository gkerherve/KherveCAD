"""Polymers (Qt-free): a repeat unit written as SMILES, repeated n times.

A repeat unit is a SMILES fragment whose first atom takes the previous
unit's last atom as a neighbour and whose last atom bonds to the next
unit — ``CC`` for polyethylene, ``CC(Cl)`` for PVC. `chain_smiles`
concatenates n of them between two end caps (hydrogen unless a preset says
otherwise, e.g. a methyl on silicone), and the ordinary SMILES builder
does the rest, so a polymer is just a long molecule: editable, savable,
exportable.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import molecule as smiles

ADDITION = "Addition polymers (vinyl)"
DIENES = "Dienes, rubbers & conjugated"
ETHERS = "Polyethers & acetals"
CONDENSATION = "Polyesters, amides & urethanes"
SPECIALTY = "Silicones, aromatics & conducting"
CATEGORIES = (ADDITION, DIENES, ETHERS, CONDENSATION, SPECIALTY)

#: key -> (name, repeat unit, default n, category, (head cap, tail cap))
PRESETS = {
    "polyethylene": ("Polyethylene (PE)", "CC", 8, ADDITION, ("", "")),
    "polypropylene": ("Polypropylene (PP)", "CC(C)", 6, ADDITION, ("", "")),
    "polyisobutylene": ("Polyisobutylene (PIB)", "CC(C)(C)", 5, ADDITION,
                        ("", "")),
    "pvc": ("Poly(vinyl chloride) (PVC)", "CC(Cl)", 6, ADDITION, ("", "")),
    "pvdc": ("Poly(vinylidene chloride) (PVDC)", "CC(Cl)(Cl)", 4, ADDITION,
             ("", "")),
    "pvf": ("Poly(vinyl fluoride) (PVF)", "CC(F)", 6, ADDITION, ("", "")),
    "pvdf": ("Poly(vinylidene fluoride) (PVDF)", "CC(F)(F)", 5, ADDITION,
             ("", "")),
    "ptfe": ("Polytetrafluoroethylene (PTFE)", "C(F)(F)C(F)(F)", 4,
             ADDITION, ("", "")),
    "polystyrene": ("Polystyrene (PS)", "CC(c1ccccc1)", 4, ADDITION,
                    ("", "")),
    "pva": ("Poly(vinyl alcohol) (PVA)", "CC(O)", 6, ADDITION, ("", "")),
    "pvac": ("Poly(vinyl acetate) (PVAc)", "CC(OC(C)=O)", 4, ADDITION,
             ("", "")),
    "pmma": ("Poly(methyl methacrylate) (PMMA)", "CC(C)(C(=O)OC)", 4,
             ADDITION, ("", "")),
    "pma": ("Poly(methyl acrylate)", "CC(C(=O)OC)", 4, ADDITION, ("", "")),
    "paa": ("Poly(acrylic acid) (PAA)", "CC(C(=O)O)", 5, ADDITION, ("", "")),
    "pam": ("Polyacrylamide", "CC(C(N)=O)", 5, ADDITION, ("", "")),
    "pan": ("Polyacrylonitrile (PAN)", "CC(C#N)", 6, ADDITION, ("", "")),
    "pvp": ("Poly(vinylpyrrolidone) (PVP)", "CC(N1CCCC1=O)", 3, ADDITION,
            ("", "")),
    "polybutadiene": ("Polybutadiene", "CC=CC", 4, DIENES, ("", "")),
    "polyisoprene": ("Polyisoprene (natural rubber)", "CC(C)=CC", 4, DIENES,
                     ("", "")),
    "polychloroprene": ("Polychloroprene (neoprene)", "CC(Cl)=CC", 4, DIENES,
                        ("", "")),
    "polyacetylene": ("Polyacetylene", "C=C", 8, DIENES, ("", "")),
    "pom": ("Polyoxymethylene (POM, acetal)", "CO", 10, ETHERS, ("", "")),
    "peo": ("Poly(ethylene oxide) (PEO / PEG)", "CCO", 8, ETHERS, ("", "")),
    "ppo": ("Poly(propylene oxide) (PPO)", "CC(C)O", 6, ETHERS, ("", "")),
    "ptmeg": ("Poly(tetrahydrofuran) (PTMEG)", "CCCCO", 4, ETHERS, ("", "")),
    "pet": ("Poly(ethylene terephthalate) (PET)",
            "C(=O)c1ccc(cc1)C(=O)OCCO", 2, CONDENSATION, ("", "")),
    "pla": ("Polylactic acid (PLA)", "OC(C)C(=O)", 5, CONDENSATION,
            ("", "")),
    "pga": ("Polyglycolic acid (PGA)", "OCC(=O)", 6, CONDENSATION, ("", "")),
    "pcl": ("Polycaprolactone (PCL)", "OCCCCCC(=O)", 3, CONDENSATION,
            ("", "")),
    "phb": ("Poly(3-hydroxybutyrate) (PHB)", "OC(C)CC(=O)", 4, CONDENSATION,
            ("", "")),
    "nylon6": ("Nylon 6", "NCCCCCC(=O)", 3, CONDENSATION, ("", "")),
    "nylon66": ("Nylon 6,6", "NCCCCCCNC(=O)CCCCC(=O)", 2, CONDENSATION,
                ("", "")),
    "kevlar": ("Kevlar (poly-paraphenylene terephthalamide)",
               "C(=O)c1ccc(cc1)C(=O)Nc1ccc(cc1)N", 2, CONDENSATION,
               ("", "")),
    "polyurethane": ("Polyurethane (hexamethylene / butanediol)",
                     "C(=O)NCCCCCCNC(=O)OCCCCO", 2, CONDENSATION, ("", "")),
    "polycarbonate": ("Polycarbonate (bisphenol A)",
                      "c1ccc(cc1)C(C)(C)c1ccc(cc1)OC(=O)O", 2,
                      CONDENSATION, ("", "")),
    "pdms": ("Polydimethylsiloxane (silicone, PDMS)", "[Si](C)(C)O", 5,
             SPECIALTY, ("C", "C")),
    "polyphenylene": ("Poly(para-phenylene)", "c1ccc(cc1)", 5, SPECIALTY,
                      ("", "")),
    "polythiophene": ("Polythiophene", "c1ccc(s1)", 4, SPECIALTY, ("", "")),
    "polypyrrole": ("Polypyrrole", "c1ccc([nH]1)", 4, SPECIALTY, ("", "")),
    "polyaniline": ("Polyaniline (leucoemeraldine)", "Nc1ccc(cc1)", 4,
                    SPECIALTY, ("", "")),
}


class PolymerError(ValueError):
    """A polymer that cannot be built; says what to change."""


def chain_smiles(unit, n, head="", tail=""):
    """SMILES of *n* repeat units between the two end caps."""
    unit = unit.strip()
    if not unit:
        raise PolymerError("Give a repeat unit as SMILES, e.g. CC(Cl).")
    if "." in unit:
        raise PolymerError("A repeat unit is one connected fragment.")
    if not 1 <= int(n) <= 200:
        raise PolymerError("The number of repeat units runs from 1 to 200.")
    return head + unit * int(n) + tail


def preset(key):
    """(name, unit, default n, category, caps) or KeyError."""
    return PRESETS[key]


def max_units(unit, head="", tail=""):
    """The most repeat units that still fit in a built molecule."""
    one = _atoms(chain_smiles(unit, 1, head, tail))
    two = _atoms(chain_smiles(unit, 2, head, tail))
    per = max(1, two - one)
    return max(1, (smiles.MAX_ATOMS - (one - per)) // per)


def _atoms(text):
    atoms, bonds = smiles.parse_smiles(text)
    return len(smiles.add_hydrogens(atoms, bonds)[0])


def build_chain(unit, n, head="", tail=""):
    """The polymer as a `smiles.Compound`. Raises `PolymerError`."""
    text = chain_smiles(unit, n, head, tail)
    try:
        if _atoms(text) > smiles.MAX_ATOMS:
            raise PolymerError(
                f"{n} units is more than the builder takes "
                f"({smiles.MAX_ATOMS} atoms): at most "
                f"{max_units(unit, head, tail)} for this unit.")
        return smiles.from_smiles(text)
    except smiles.SmilesError as exc:
        raise PolymerError(f"Repeat unit '{unit}': {exc}")


def formula_of_chain(unit, n, head="", tail=""):
    return smiles.from_smiles(chain_smiles(unit, n, head, tail)).formula
