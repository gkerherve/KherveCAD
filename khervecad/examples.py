"""Ready-made example models for the Examples menu.

Each entry builds a complete document tree (a fresh ``root`` node) that
replaces the current document, so a new user can load something real and
take it apart. The examples double as a tour of the app: variables and
expressions, booleans, the part library, and Masters with Linked copies.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from .model import CadNode, DocumentModel


def _root(*children) -> CadNode:
    root = CadNode("root")
    for child in children:
        root.add(child)
    return root


def _var(name, value) -> CadNode:
    return CadNode("assign", f"{name} =",
                   dict(variable=name, value=str(value)))


def _cyl(name, **params) -> CadNode:
    p = dict(x=0.0, y=0.0, z=0.0, height=10.0, radius_bottom=5.0,
             radius_top=5.0, segments=64, center=False)
    p.update(params)
    return CadNode("cylinder", name, p)


# ---------------------------------------------------------------- builders

def parametric_box() -> CadNode:
    """A hollow, open-topped box driven entirely by variables — edit
    ``w``, ``d``, ``h`` or ``wall`` in the Variables tab and the whole
    part follows."""
    outer = CadNode("cube", "Outer shell",
                    dict(width="w", depth="d", height="h", center=False))
    cavity = CadNode("cube", "Cavity",
                     dict(x="wall", y="wall", z="wall",
                          width="w - 2 * wall", depth="d - 2 * wall",
                          height="h", center=False))
    box = CadNode("difference", "Hollow box")
    box.add(outer)
    box.add(cavity)
    return _root(_var("w", 60), _var("d", 40), _var("h", 30),
                 _var("wall", 2), box)


def l_bracket() -> CadNode:
    """A right-angle mounting bracket: two plates unioned, then two
    fixing holes drilled through the base — the classic boolean idiom."""
    base = CadNode("cube", "Base plate",
                   dict(width=60, depth=40, height=6))
    wall = CadNode("cube", "Upright",
                   dict(width=60, depth=6, height=40))
    body = CadNode("union", "Bracket body")
    body.add(base)
    body.add(wall)
    hole1 = _cyl("Hole 1", x=15, y=22, z=-1, height=8,
                 radius_bottom=3.2, radius_top=3.2, segments=32)
    hole2 = _cyl("Hole 2", x=45, y=22, z=-1, height=8,
                 radius_bottom=3.2, radius_top=3.2, segments=32)
    bracket = CadNode("difference", "L-bracket")
    bracket.add(body)
    bracket.add(hole1)
    bracket.add(hole2)
    return _root(bracket)


def bolt_circle() -> CadNode:
    """A Masters demo: one M6 bolt lives in the Masters store, and a
    for-loop drops eight Linked copies of it around a flange disc. Edit
    the master and every bolt in the ring updates."""
    from .library import default_part
    bolt = default_part("bolt_hex")
    bolt.name = "Bolt"
    masters = CadNode("masters", "Masters")
    masters.add(bolt)

    disc = _cyl("Flange disc", height=6, radius_bottom=42, radius_top=42,
                segments=96)
    ring = CadNode("for_loop", "Bolt ring",
                   dict(variable="i", start=0, end=5, step=1, values=""))
    ref = CadNode("reference", "Copy of Bolt",
                  dict(ref="Bolt", x="30 * cos(i * 60)",
                       y="30 * sin(i * 60)", z=6,
                       rx=0.0, ry=0.0, rz=0.0))
    ring.add(ref)
    return _root(masters, disc, ring)


def vacuum_starter() -> CadNode:
    """An assembly starter from the part library: a CF tee with a turbo
    pump hung below it — drag the parts in the 2D assembly view or edit
    them in the tree."""
    from .library import default_part
    tee = default_part("cf_tee")
    turbo = default_part("turbo")
    mount = CadNode("translate", "Turbo position", dict(x=0, y=0, z=-170))
    mount.add(turbo)
    return _root(tee, mount)


def desk_setup() -> CadNode:
    """A furniture scene: a table with a monitor and a chair, each a
    coloured library part — a quick way to block out a room."""
    from .library import default_part
    table = default_part("room_table")
    monitor = default_part("room_monitor")
    mon_pos = CadNode("translate", "Monitor position",
                      dict(x=0, y=0, z=740))
    mon_pos.add(monitor)
    chair = default_part("room_chair")
    chair_pos = CadNode("translate", "Chair position",
                        dict(x=0, y=-520, z=0))
    chair_pos.add(chair)
    return _root(table, mon_pos, chair_pos)


#: (menu label, category, builder) — grouped in the Examples menu.
EXAMPLES = [
    ("Parametric box", "Mechanical", parametric_box),
    ("L-bracket with holes", "Mechanical", l_bracket),
    ("Bolt circle (Masters demo)", "Mechanical", bolt_circle),
    ("Vacuum starter (CF tee + turbo)", "Vacuum", vacuum_starter),
    ("Desk setup", "Room", desk_setup),
]


def load_example(model: DocumentModel, build) -> None:
    """Replace the document with the example built by *build*."""
    model.root = build()
    model.structure_changed.emit()
