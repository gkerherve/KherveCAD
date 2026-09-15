"""The compound library of the Compound Builder (Qt-free).

Common chemical compounds as name + SMILES, in families. Formulas,
masses and 3D shapes are COMPUTED (molecule.py) rather than typed, so a
library entry is one line that cannot disagree with itself; the tests
build every one and check its formula, its bond lengths and that no
two atoms clash. An assistant reaches the same list through
list_molecules and builds anything else from SMILES.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from .molecule import from_smiles

GASES = "Gases & simple molecules"
INORGANIC = "Inorganic acids, bases & ions"
SHAPES = "Molecular shapes (VSEPR)"
HYDROCARBONS = "Hydrocarbons"
OXYGEN = "Alcohols, ethers & carbonyls"
ACIDS = "Acids & esters"
NITROGEN = "Nitrogen compounds & solvents"
BIO = "Biomolecules & drugs"
CATEGORIES = (GASES, INORGANIC, SHAPES, HYDROCARBONS, OXYGEN, ACIDS,
              NITROGEN, BIO)

#: key -> (name, SMILES, category, formula it must give)
COMPOUNDS = {
    # gases & simple molecules
    "hydrogen": ("Hydrogen", "[H][H]", GASES, "H2"),
    "oxygen": ("Oxygen", "O=O", GASES, "O2"),
    "nitrogen": ("Nitrogen", "N#N", GASES, "N2"),
    "water": ("Water", "O", GASES, "H2O"),
    "carbon_dioxide": ("Carbon dioxide", "O=C=O", GASES, "CO2"),
    "carbon_monoxide": ("Carbon monoxide", "[C-]#[O+]", GASES, "CO"),
    "ozone": ("Ozone", "[O-][O+]=O", GASES, "O3"),
    "ammonia": ("Ammonia", "N", GASES, "H3N"),
    "methane": ("Methane", "C", GASES, "CH4"),
    "hydrogen_chloride": ("Hydrogen chloride", "Cl", GASES, "ClH"),
    "hydrogen_sulfide": ("Hydrogen sulfide", "S", GASES, "H2S"),
    "hydrogen_cyanide": ("Hydrogen cyanide", "C#N", GASES, "CHN"),
    "sulfur_dioxide": ("Sulfur dioxide", "O=S=O", GASES, "O2S"),
    "hydrogen_peroxide": ("Hydrogen peroxide", "OO", GASES, "H2O2"),
    # inorganic acids, bases & ions
    "sulfuric_acid": ("Sulfuric acid", "OS(=O)(=O)O", INORGANIC, "H2O4S"),
    "nitric_acid": ("Nitric acid", "O[N+](=O)[O-]", INORGANIC, "HNO3"),
    "phosphoric_acid": ("Phosphoric acid", "OP(=O)(O)O", INORGANIC,
                        "H3O4P"),
    "carbonic_acid": ("Carbonic acid", "OC(=O)O", INORGANIC, "CH2O3"),
    "hydroxide": ("Hydroxide ion", "[OH-]", INORGANIC, "HO-"),
    "hydronium": ("Hydronium ion", "[OH3+]", INORGANIC, "H3O+"),
    "ammonium": ("Ammonium ion", "[NH4+]", INORGANIC, "H4N+"),
    "sulfate": ("Sulfate ion", "[O-]S(=O)(=O)[O-]", INORGANIC, "O4S 2-"),
    "nitrate": ("Nitrate ion", "[O-][N+](=O)[O-]", INORGANIC, "NO3-"),
    "carbonate": ("Carbonate ion", "[O-]C(=O)[O-]", INORGANIC, "CO3 2-"),
    "sodium_chloride": ("Sodium chloride (ion pair)", "[Na+].[Cl-]",
                        INORGANIC, "ClNa"),
    # molecular shapes
    "boron_trifluoride": ("Boron trifluoride", "FB(F)F", SHAPES, "BF3"),
    "carbon_tetrachloride": ("Carbon tetrachloride", "ClC(Cl)(Cl)Cl",
                             SHAPES, "CCl4"),
    "phosphorus_pentachloride": ("Phosphorus pentachloride",
                                 "ClP(Cl)(Cl)(Cl)Cl", SHAPES, "Cl5P"),
    "sulfur_hexafluoride": ("Sulfur hexafluoride", "FS(F)(F)(F)(F)F",
                            SHAPES, "F6S"),
    "xenon_tetrafluoride": ("Xenon tetrafluoride", "F[Xe](F)(F)F", SHAPES,
                            "F4Xe"),
    "silane": ("Silane", "[SiH4]", SHAPES, "H4Si"),
    # hydrocarbons
    "ethane": ("Ethane", "CC", HYDROCARBONS, "C2H6"),
    "propane": ("Propane", "CCC", HYDROCARBONS, "C3H8"),
    "butane": ("Butane", "CCCC", HYDROCARBONS, "C4H10"),
    "isobutane": ("Isobutane", "CC(C)C", HYDROCARBONS, "C4H10"),
    "hexane": ("Hexane", "CCCCCC", HYDROCARBONS, "C6H14"),
    "octane": ("Octane", "CCCCCCCC", HYDROCARBONS, "C8H18"),
    "ethylene": ("Ethylene", "C=C", HYDROCARBONS, "C2H4"),
    "propene": ("Propene", "CC=C", HYDROCARBONS, "C3H6"),
    "acetylene": ("Acetylene", "C#C", HYDROCARBONS, "C2H2"),
    "cyclohexane": ("Cyclohexane", "C1CCCCC1", HYDROCARBONS, "C6H12"),
    "benzene": ("Benzene", "c1ccccc1", HYDROCARBONS, "C6H6"),
    "toluene": ("Toluene", "Cc1ccccc1", HYDROCARBONS, "C7H8"),
    "styrene": ("Styrene", "C=Cc1ccccc1", HYDROCARBONS, "C8H8"),
    "naphthalene": ("Naphthalene", "c1ccc2ccccc2c1", HYDROCARBONS,
                    "C10H8"),
    # alcohols, ethers & carbonyls
    "methanol": ("Methanol", "CO", OXYGEN, "CH4O"),
    "ethanol": ("Ethanol", "CCO", OXYGEN, "C2H6O"),
    "isopropanol": ("Isopropanol", "CC(C)O", OXYGEN, "C3H8O"),
    "ethylene_glycol": ("Ethylene glycol", "OCCO", OXYGEN, "C2H6O2"),
    "glycerol": ("Glycerol", "OCC(O)CO", OXYGEN, "C3H8O3"),
    "diethyl_ether": ("Diethyl ether", "CCOCC", OXYGEN, "C4H10O"),
    "formaldehyde": ("Formaldehyde", "C=O", OXYGEN, "CH2O"),
    "acetaldehyde": ("Acetaldehyde", "CC=O", OXYGEN, "C2H4O"),
    "acetone": ("Acetone", "CC(C)=O", OXYGEN, "C3H6O"),
    "phenol": ("Phenol", "Oc1ccccc1", OXYGEN, "C6H6O"),
    # acids & esters
    "formic_acid": ("Formic acid", "OC=O", ACIDS, "CH2O2"),
    "acetic_acid": ("Acetic acid", "CC(=O)O", ACIDS, "C2H4O2"),
    "lactic_acid": ("Lactic acid", "CC(O)C(=O)O", ACIDS, "C3H6O3"),
    "citric_acid": ("Citric acid", "OC(=O)CC(O)(CC(=O)O)C(=O)O", ACIDS,
                    "C6H8O7"),
    "benzoic_acid": ("Benzoic acid", "OC(=O)c1ccccc1", ACIDS, "C7H6O2"),
    "ethyl_acetate": ("Ethyl acetate", "CCOC(C)=O", ACIDS, "C4H8O2"),
    # nitrogen compounds & solvents
    "methylamine": ("Methylamine", "CN", NITROGEN, "CH5N"),
    "urea": ("Urea", "NC(N)=O", NITROGEN, "CH4N2O"),
    "aniline": ("Aniline", "Nc1ccccc1", NITROGEN, "C6H7N"),
    "pyridine": ("Pyridine", "c1ccncc1", NITROGEN, "C5H5N"),
    "acetonitrile": ("Acetonitrile", "CC#N", NITROGEN, "C2H3N"),
    "nitrobenzene": ("Nitrobenzene", "O=[N+]([O-])c1ccccc1", NITROGEN,
                     "C6H5NO2"),
    "dmso": ("Dimethyl sulfoxide (DMSO)", "CS(C)=O", NITROGEN, "C2H6OS"),
    "dmf": ("Dimethylformamide (DMF)", "CN(C)C=O", NITROGEN, "C3H7NO"),
    "dichloromethane": ("Dichloromethane", "ClCCl", NITROGEN, "CH2Cl2"),
    "chloroform": ("Chloroform", "ClC(Cl)Cl", NITROGEN, "CHCl3"),
    "thf": ("Tetrahydrofuran (THF)", "C1CCOC1", NITROGEN, "C4H8O"),
    # biomolecules & drugs
    "glycine": ("Glycine", "NCC(=O)O", BIO, "C2H5NO2"),
    "alanine": ("Alanine", "CC(N)C(=O)O", BIO, "C3H7NO2"),
    "glucose": ("Glucose (beta-D-glucopyranose)", "OCC1OC(O)C(O)C(O)C1O",
                BIO, "C6H12O6"),
    "adenine": ("Adenine", "Nc1ncnc2[nH]cnc12", BIO, "C5H5N5"),
    "caffeine": ("Caffeine", "Cn1cnc2c1c(=O)n(C)c(=O)n2C", BIO,
                 "C8H10N4O2"),
    "aspirin": ("Aspirin", "CC(=O)Oc1ccccc1C(=O)O", BIO, "C9H8O4"),
    "paracetamol": ("Paracetamol", "CC(=O)Nc1ccc(O)cc1", BIO, "C8H9NO2"),
    "vanillin": ("Vanillin", "COc1cc(C=O)ccc1O", BIO, "C8H8O3"),
}


def get(key: str):
    """The library molecule *key* (3D, cached); KeyError names the
    choices."""
    k = str(key).strip().lower().replace(" ", "_")
    if k not in COMPOUNDS:
        by_name = {v[0].lower(): kk for kk, v in COMPOUNDS.items()}
        k = by_name.get(str(key).strip().lower(), k)
    if k not in COMPOUNDS:
        raise KeyError(f"No compound '{key}'. Choices: "
                       + ", ".join(COMPOUNDS))
    name, smiles, category, _formula = COMPOUNDS[k]
    return from_smiles(smiles, name=name, key=k, category=category)


def by_formula(formula: str):
    """Library keys whose molecule has this formula (order as listed)."""
    from .molecule import formula_counts, hill_formula
    try:
        want = hill_formula(formula_counts(formula))
    except ValueError:
        return []
    return [k for k, (_n, _s, _c, f) in COMPOUNDS.items()
            if hill_formula(formula_counts(f.split(" ")[0].rstrip("+-")))
            == want]
