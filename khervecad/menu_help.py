"""Hover help for every menu item (the card in the main window's corner).

Menu items come from three places: commands with a hand-written entry
(`tooltips.TIPS`, or `COMMANDS` here, keyed by the item's label), Library
parts (their action's data is "part:<id>") and example documents
("example:<category>|<label>"). `resolve(action)` gives the HTML for any
of them, so no menu item is ever without help; a test walks the menus
and fails on the one that is.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import re

from . import language, tooltips

#: (category prefix, what a part of it is) — first match wins; {label}
CATEGORY = [
    ("Molecules: Polymers", "A chain of {label} repeat units in 3D, drawn "
     "ball and stick with atoms coloured by element."),
    ("Molecules: Proteins", "{label}: every heavy atom of the peptide "
     "built in 3D, as a coloured cartoon with its side chains."),
    ("Molecules: Fullerenes", "{label} as a 3D cage of carbon atoms."),
    ("Molecules: Medicines", "The molecule of {label}, a medicine, in 3D "
     "ball and stick (atoms coloured by element)."),
    ("Molecules:", "The molecule {label} in 3D, ball and stick, atoms "
     "coloured by element, at true bond lengths and angles."),
    ("Surfaces:", "A slab of {label} cut along that crystal face: the "
     "atoms of the top layers, ball and stick, in nanometres."),
    ("Crystals (unit cells)", "The conventional unit cell of {label}: "
     "every atom, the bonds and the coordination polyhedra, in nm."),
    ("Crystals (supercells)", "{label} repeated into a block of unit "
     "cells — pick 2×2×2 up to 6×6×6 in the Part Library."),
    ("Crystals (nanotubes)", "A carbon nanotube — {label}; choose its "
     "chirality, length and walls in the Part Library."),
    ("Crystals (custom)", "{label}: a crystal structure you added, as a "
     "unit cell or slab."),
    ("MOFs", "{label}: a metal-organic framework cell, with its "
     "zirconium clusters and linkers."),
    ("Vacuum", "{label}: a vacuum-system part (CF/KF flanges, fittings, "
     "pumps, gauges) at real dimensions, in stainless steel."),
    ("Fasteners", "{label}: a standard fastener at ISO dimensions — real "
     "threads where it has them. Pick the size (M3–M20) in the dialog."),
    ("Brackets", "{label}: a printable or machinable bracket or fixing."),
    ("Tools", "{label}: a hand tool built from its real parts, so you "
     "can colour, mate or explode them apart."),
    ("Mechanisms & motion", "{label}: a working mechanism driven by a "
     "slider in the Customizer — press its ▶ to watch it move."),
    ("Motion & motors", "{label}: a motion component (motor, rail, "
     "pulley, bearing) at its published dimensions."),
    ("Electronics boards", "{label}: a circuit board at its maker's "
     "outline, with its connectors."),
    ("Electronic components", "{label}: an electronic component at true "
     "size, leads down from z = 0."),
    ("Electronics lab", "{label}: bench or instrument for an electronics "
     "lab."),
    ("RPi enclosures", "{label}: a printable Raspberry Pi 5 case, one "
     "colour per Object. It previews empty until OpenSCAD renders it."),
    ("Server racks", "{label}: a 19-inch rack."),
    ("Air conditioning", "{label}: air-conditioning equipment."),
    ("Printed joints", "{label}: a joint that prints without supports; "
     "clearances are tuned for FDM printers."),
    ("Printed organisers", "{label}: a printable organiser (Gridfinity "
     "style, 42 mm pitch)."),
    ("Enclosures", "{label}: a printable enclosure."),
    ("Prusa", "{label}, modelled from scratch."),
    ("Test parts", "{label}: a test print that needs no supports and "
     "sits flat on the bed."),
    ("Printables", "{label}: a ready-to-print model."),
    ("Bag clips", "{label}: a printable bag clip design."),
    ("Washing machine trays", "{label}: a drip tray for a washing "
     "machine."),
    ("Finished houses", "{label}: a complete furnished house; each "
     "floor lands as its own Object and the House Builder edits it."),
    ("Finished labs", "{label}: a complete furnished laboratory you can "
     "edit in the House Builder."),
    ("Finished commercial", "{label}: a commercial building or fitting."),
    ("Home furniture", "{label}: a piece of furniture at real size, "
     "front facing -Y, standing on z = 0."),
    ("Room & furniture", "{label}: furniture or a fitting at real size."),
    ("Tables", "{label}: a table at real size."),
    ("Bookshelves", "{label}: a bookshelf."),
    ("Doors", "{label}: a door with its frame."),
    ("Appliances", "{label}: a household appliance at real size."),
    ("Ceiling lights", "{label}: a ceiling light."),
    ("Porches", "{label}: an entrance porch; the House Builder can put "
     "it against a facade."),
    ("Houses", "{label}: a house design."),
    ("Buildings", "{label}: an outside-only building for streets and "
     "cities — pick Small, Standard or Large and the wall look."),
    ("Landmarks", "{label}: a famous structure from its published "
     "dimensions, at true size."),
    ("Skyscrapers", "{label}: a skyscraper from its published "
     "dimensions."),
    ("Bridges", "{label}: a famous bridge from its published "
     "dimensions."),
    ("Park & sport", "{label}: parkland or sports-ground piece at real "
     "size."),
    ("Lighting & signals", "{label}: street furniture — lamps, traffic "
     "lights, signs."),
    ("Sport: stadiums", "{label}: a whole stadium in one click; size = "
     "the sport, colour = the seats."),
    ("Sport:", "{label}: sports equipment or a pitch at regulation "
     "size."),
    ("Sport", "{label}: a saved sports facility."),
    ("Gym", "{label}: gym equipment or room."),
    ("Swimming", "{label}: a pool or aquatics piece."),
    ("Grown trees", "{label}: a tree grown branch by branch — pick Young, "
     "Mature or Old, a seed and the season."),
    ("Trees", "{label}: a tree grown branch by branch — pick its age, a "
     "seed and the season."),
    ("Leaves", "{label}: a detailed leaf, with veins, in summer, autumn "
     "or spring colour."),
    ("Stones", "{label}: a stone or rock, different every seed."),
    ("Flowers", "{label}: a flower built from petals."),
    ("Landscape", "{label}: a terrain block with grass, rock and snow "
     "by height."),
    ("Garden", "{label}: a garden piece."),
    ("Pots", "{label}: a plant pot — pick the colour and size."),
    ("Chemistry", "{label}: laboratory glassware or bench equipment; "
     "glass is translucent, and you can set a liquid level."),
    ("Lab equipment", "{label}: laboratory equipment."),
    ("Solar System models", "{label}: an orrery driven by a days slider "
     "— press ▶ in the Customizer."),
    ("Planets", "{label}: a planet with its real features; the "
     "document scale is set for you."),
    ("Moons", "{label}: a moon with its real features."),
    ("Lego Technic", "{label}: a Lego Technic piece."),
    ("Lego sets", "{label}: a whole Lego model from bricks, as one "
     "Object."),
    ("Lego builds", "{label}: a Lego model you built."),
    ("Lego", "{label}: a Lego piece at real dimensions (8 mm pitch) — "
     "it snaps stud to stud."),
    ("Cartoon animals", "{label}: a chibi toy animal, about 10 cm."),
    ("Monsters", "{label}: a creature that can be sent walking into "
     "PlanetCraft."),
    ("Characters", "{label}: a character figure."),
    ("Minecraft", "{label}: a Minecraft character or mob in block "
     "pixels."),
    ("Cars", "{label}: a car at its published dimensions — the Car "
     "Builder changes paint and wheels."),
    ("Vehicles", "{label}: a vehicle model."),
    ("Playing cards", "{label}: a playing card with raised ink."),
    ("Kitchen & tableware", "{label}: tableware or kitchenware, hollow "
     "and at real size."),
    ("Musical instruments", "{label}: an instrument tuned by its "
     "physics (bar lengths, frets, pipe lengths)."),
    ("Generative", "{label}: a generated pattern — seeded, so a new seed "
     "gives a new design."),
    ("Games", "{label}: a game piece."),
    ("Art", "{label}: an artwork."),
    ("Custom objects", "A starting point for your own object made of "
     "shapes."),
    ("Robot arms", "{label}: a robot arm with joints you can pose."),
    ("My library", "{label}: a part you (or an assistant) saved in My "
     "Library."),
]

EXAMPLE = {
    "Learn": "A step-by-step tutorial model: it teaches one OpenSCAD "
             "technique with a small, annotated tree.",
    "Mechanical": "An engineering technique example built from parametric "
                  "parts.",
    "Projects": "A finished part from the \"Mastering OpenSCAD in 10 "
                "projects\" course, rebuilt natively.",
    "Showcase": "A showcase model that shows what the tree can do.",
    "Flowers": "A procedural flower.",
    "Trees": "A procedural tree.",
    "Lego": "A Lego model built from bricks.",
    "Vacuum": "A vacuum-system starter assembly.",
    "Room": "A desk set-up to start a scene from.",
}


def _card(title, what, steps=(), tip=None):
    parts = [f"<b>{title}</b>",
             f"<p style='margin:4px 0 0 0'>{what}</p>"]
    if steps:
        items = "".join(f"<li>{s}</li>" for s in steps)
        parts.append("<p style='margin:6px 0 0 0'><b>"
                     f"{language.tr('How to use')}</b></p>"
                     f"<ol style='margin:2px 0 0 0'>{items}</ol>")
    if tip:
        parts.append("<p style='margin:4px 0 0 0; color:#8a8a8a'><i>"
                     f"{language.tr('Tip:')}</i> {tip}</p>")
    return (f"<table width='{tooltips.WIDTH}' cellspacing='0' "
            f"cellpadding='0'><tr><td>{''.join(parts)}</td></tr></table>")


def _esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;")


def part_help(pid):
    """The card for Library part *pid*, or None if it is unknown."""
    from .library import PARTS
    spec = PARTS.get(pid)
    if spec is None:
        return None
    label = _esc(spec["label"])
    category = spec.get("category", "")
    what = spec.get("description") or spec.get("note")
    if not what:
        what = next((t for prefix, t in CATEGORY
                     if category.startswith(prefix)), None)
        what = (what or "{label}: a ready-made part.").format(label=label)
    else:
        what = _esc(what)
    steps = ["Click to add it to your document as one Object "
             "(Main tab), at its default size."]
    sizes = [k for k in spec.get("sizes", {})]
    if len(sizes) > 1:
        shown = ", ".join(_esc(s) for s in sizes[:4])
        more = " …" if len(sizes) > 4 else ""
        steps.append(f"Other sizes ({shown}{more}) and options are in "
                     "Library ▸ Part Library… (Ctrl+L).")
    if spec.get("colors"):
        steps.append("Pick its colour in the Part Library.")
    steps.append("Select it in the tree to move, rotate, colour or edit "
                 "it — an Object's construction opens in the Object tab.")
    tip = spec.get("insert_note") or None
    return _card(label, what, steps, tip)


def example_help(token):
    """Card for an example document; *token* = "<category>|<label>"."""
    category, _sep, label = token.partition("|")
    from .examples import EXAMPLES
    doc = ""
    for lab, cat, build in EXAMPLES:
        if lab == label and cat == category:
            doc = (build.__doc__ or "").strip().split("\n\n")[0]
            doc = " ".join(doc.split())
    what = _esc(doc) if doc else EXAMPLE.get(category, "An example model.")
    return _card(
        _esc(label), what,
        ["Click to open it. It REPLACES the document in the window — "
         "save yours first if you want to keep it.",
         "Open the Main tab and the Variables tab to see how it is "
         "built; change a value and watch the model follow."],
        "Ctrl+Z brings your own document back.")


EXAMPLE_NOTE_TEXT = "Opens as a document, in place of yours"


def _norm(text):
    text = re.sub(r"&(?=\w)", "", str(text)).replace("&&", "&")
    text = text.split("\t")[0].replace("…", "").replace("...", "")
    return re.sub(r"\s+", " ", text).strip().lower()


from .menu_help_commands import COMMANDS as _RAW  # noqa: E402


COMMANDS = {_norm(k): v for k, v in _RAW.items()}
COMMANDS[_norm(EXAMPLE_NOTE_TEXT)] = (
    "Examples", "The models below open as documents and REPLACE the "
    "one in the window.", ["Save your own work first.",
                           "Ctrl+Z brings it back."], None)


def resolve(action):
    """HTML help for a menu *action*, or None when nothing is known."""
    data = action.data()
    if isinstance(data, str):
        if data.startswith("part:"):
            return part_help(data[5:])
        if data.startswith("example:"):
            return example_help(data[8:])
    label = _norm(action.text())
    entry = COMMANDS.get(label)
    if entry is None:
        m = re.fullmatch(r"(distance|at) (\d+) ?%", label)
        if m:
            entry = (action.text().replace("&", ""),
                     "Sets the exploded-view distance." if m.group(1) ==
                     "distance" else "Puts the cut plane here, as a "
                     "percentage of the model.", [], None)
    if entry is not None:
        title, what, steps, tip = entry
        return _card(title, what, [language.tr(s) for s in steps], tip)
    return None
