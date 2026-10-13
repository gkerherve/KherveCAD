"""The MCP `chemistry` tool: the Chemistry Builder's scene, driven by an
assistant (the same scene the window shows — `chem_dialog.scene_of`).

One tool, one `action` each call: load (compound / SMILES, crystal,
surface with whole polyhedra, CIF, reaction), measure (2 / 3 / 4 atoms),
edit (add, bond, delete, move, element), dope, adsorb / move_adsorbate /
remove_adsorbate, properties, state, export (XYZ / PDB / CIF / MOL /
SDF) and build (into the document; a reaction as a film the Customizer
plays). Atom indices are 0-based, positions in ångström.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from . import chem_adsorb as ad
from . import chem_scene as cs
from .crystal_build import BuildError

ACTIONS = ("load", "state", "measure", "edit", "dope", "adsorb",
           "move_adsorbate", "remove_adsorbate", "properties", "export",
           "build")
#: atoms listed in full by `state` (beyond, a count and the formula)
LIST_ATOMS = 400


def _panel(window):
    from . import chem_dialog
    return chem_dialog.open_builder(window, show=False)


def _summary(scene):
    out = {"name": scene.name, "kind": scene.kind,
           "formula": scene.formula(), "atoms": len(scene.atoms),
           "bonds": len(scene.bonds),
           "adsorbates": [dict(g) for g in scene.groups]}
    return out


def run(window, params: dict) -> dict:
    action = params.get("action")
    if action not in ACTIONS:
        raise BuildError(f"action is one of {', '.join(ACTIONS)}.")
    panel = _panel(window)
    scene = panel.canvas.scene
    if action == "load":
        src = params.get("source", "compound")
        if src == "reaction":
            panel.load_reaction(str(params.get("equation", "")))
            if panel.film is None:
                raise BuildError(panel.status.text() or "No reaction.")
            return {**_summary(panel.canvas.scene),
                    "equation": panel.equation}
        if src == "compound":
            new = cs.compound_scene(str(params.get("compound", "")))
        elif src == "crystal":
            new = cs.crystal_scene(str(params.get("crystal", "")),
                                   params.get("cells", [1, 1, 1]),
                                   params.get("dope"),
                                   int(params.get("seed", 7)))
        elif src == "surface":
            new = cs.surface_scene(str(params.get("crystal", "")),
                                   str(params.get("miller", "111")),
                                   params.get("repeat"),
                                   int(params.get("layers", 3)),
                                   params.get("termination"),
                                   params.get("dope"),
                                   int(params.get("seed", 7)),
                                   bool(params.get("complete", False)))
        elif src == "cif":
            new = cs.cif_scene(str(params.get("path", "")),
                               params.get("cells", [1, 1, 1]))
        else:
            raise BuildError("source is compound, crystal, surface, cif or "
                             "reaction.")
        panel.load_scene(new)
        return _summary(new)
    if action == "state":
        out = _summary(scene)
        if len(scene.atoms) <= LIST_ATOMS:
            out["atom_list"] = [[i, a[0], round(a[1], 3), round(a[2], 3),
                                 round(a[3], 3)]
                                for i, a in enumerate(scene.atoms)]
            out["bond_list"] = [list(b) for b in scene.bonds]
        return out
    if action == "measure":
        atoms = [int(i) for i in params.get("atoms", [])]
        if any(not 0 <= i < len(scene.atoms) for i in atoms):
            raise BuildError("An atom index is out of range.")
        result = cs.measure(scene, atoms)
        panel.canvas.measures.append((atoms, result))
        panel.measures.insertItem(0, result["text"])
        panel.canvas.update()
        return {k: (round(v, 4) if isinstance(v, float) else v)
                for k, v in result.items()}
    if action == "properties":
        return {"properties": [[k, v] for k, v in cs.properties(scene)]}
    if action == "export":
        from . import chem_io
        return chem_io.export(scene, str(params.get("path", "")),
                              params.get("format"))
    if action == "build":
        from . import chem_dialog
        return chem_dialog.build(window, scene, panel.film, panel.equation,
                                 params.get("style", "ball_and_stick"),
                                 bool(params.get("cell_box", True)))
    # ---- edits: one undo step in the builder each
    panel._snapshot()
    if action == "edit":
        op = params.get("op")
        if op == "add":
            if params.get("bond_to") is not None and \
                    params.get("position") is None:
                i = cs.place_bonded(scene, str(params.get("element", "C")),
                                    int(params["bond_to"]))
            else:
                i = cs.add_atom(scene, str(params.get("element", "C")),
                                params.get("position", [0, 0, 0]),
                                params.get("bond_to"))
            out = {"added": i}
        elif op == "delete":
            cs.delete_atoms(scene, [int(i) for i in params.get("atoms", [])])
            out = {"deleted": params.get("atoms", [])}
        elif op == "bond":
            a = params.get("atoms", [])
            if len(a) != 2:
                raise BuildError("bond takes two atoms.")
            cs.add_bond(scene, int(a[0]), int(a[1]),
                        int(params.get("order", 1)))
            out = {"bonded": a}
        elif op == "unbond":
            a = params.get("atoms", [])
            cs.delete_bond(scene, int(a[0]), int(a[1]))
            out = {"unbonded": a}
        elif op == "move":
            a = params.get("atoms", [])
            cs.move_atom(scene, int(a[0]), params.get("position"))
            out = {"moved": a[0]}
        elif op == "element":
            for i in params.get("atoms", []):
                cs.set_element(scene, int(i), str(params.get("element")))
            out = {"changed": params.get("atoms", [])}
        elif op == "find_bonds":
            cs.auto_bonds(scene)
            out = {"bonds": len(scene.bonds)}
        else:
            raise BuildError("op is add, delete, bond, unbond, move, "
                             "element or find_bonds.")
    elif action == "dope":
        out = {"substituted": cs.dope(scene, params.get("rule"),
                                      int(params.get("seed", 7)))}
    elif action == "adsorb":
        molecule = cs.compound_scene(str(params.get("compound", "")))
        gi = ad.add(scene, molecule, name=params.get("name"),
                    height=float(params.get("height", 2.4)),
                    dx=float(params.get("x", 0.0)),
                    dy=float(params.get("y", 0.0)),
                    mode=str(params.get("mode", "flat")),
                    spin=float(params.get("spin", 0.0)),
                    auto=params.get("x") is None and params.get("y") is None)
        out = {"group": gi, **ad.pose(scene, gi)}
    elif action == "move_adsorbate":
        gi = int(params.get("group", 0))
        if not 0 <= gi < len(scene.groups):
            raise BuildError("No such adsorbate group.")
        ad.place(scene, gi, params.get("x"), params.get("y"),
                 params.get("height"))
        ad.rotate(scene, gi, float(params.get("rx", 0)),
                  float(params.get("ry", 0)), float(params.get("rz", 0)))
        out = {"group": gi, **ad.pose(scene, gi)}
    else:                                       # remove_adsorbate
        gi = int(params.get("group", 0))
        if not 0 <= gi < len(scene.groups):
            raise BuildError("No such adsorbate group.")
        ad.remove(scene, gi)
        out = {"removed": gi}
    panel._refresh()
    return {**out, **_summary(scene)}
