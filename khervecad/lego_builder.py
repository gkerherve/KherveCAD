"""Library ▸ Lego Builder… — assemble a Lego build level by level.

The window has three parts: a palette of every piece (bricks, plates
and tiles of any size, and every piece of the Library's Lego menu —
slopes, arches, windows, round pieces, Technic…), a colour and a quarter
turn; a LEVEL, one plate apart; and the plan of that level
(lego_plan.py), the stud grid seen from above, where a left click puts
the piece and a right click takes one away. Cells already filled at that
level are grey, studs to build on are circles, and the chosen piece
follows the cursor green where it fits and red where it does not — it
must not run into anything and must hold on to studs beneath, a piece
above, or the ground (`can_place`). The 3D view shows the build grow.

A toolbar goes with the plan: the click TOOLS down its left edge —
Select (outline a piece; arrows move it, R turns, Delete removes), Move
(drag it), Rotate (a quarter about its corner), Add piece, Erase — and
Turn / Copy / Delete, level ▼▲ and Zoom in / out / Fit across the top;
the wheel zooms, the middle button pans. Every move goes through
`replace_piece` (the piece rebuilt where it stood in the tree, checked
by `can_place` with itself ignored).

The baseplate (16 to 96 studs a side, `BASEPLATE_SIZES`) lives in an
Object of its own beside the build (`BASE_KEY`, `base_object`), its
studs one nested loop of 8-sided cylinders and never culled: its mesh
then never changes, so a click on a 96 x 96 plate costs ~0.3 s, not the
1.5 s it took to re-tessellate and re-project 9216 studs each time.

"Click in 3D view" keeps the older way too: clicking the top of a piece
drops the new one there on the highest top beneath it, a side sets it
beside that face, and in Erase mode a click takes a piece away.

Every piece is a Group whose placement (x, y, z, rz) puts its corner on
the stud grid and whose params carry ``lego`` = {kind, nx, ny, h, colour,
i, j} (+ part and turn for a Library piece): the build knows its own
bricks and the .kcad keeps it all. After each change the studs another
piece covers are left out of bricks and plates, so a big build stays
light. The build is an ordinary Object ("Lego build", started on a
16 x 16 baseplate), and each click is one Ctrl+Z.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QPixmap
from PyQt5.QtWidgets import (QAction, QActionGroup, QComboBox, QDialog,
                             QFormLayout, QHBoxLayout, QLabel, QPushButton,
                             QSpinBox, QToolBar, QTreeWidget,
                             QTreeWidgetItem, QTreeWidgetItemIterator,
                             QVBoxLayout)

from . import icons, mesh
from .library_lego import (BASEPLATE_H, BRICK_H, COLORS, PITCH, PLATE_H,
                           brick, colour)
from . import library_lego_parts as parts_lib
from .model import CadNode

BUILD_NAME = "Lego build"
#: piece kind -> its height
KINDS = {"Brick": BRICK_H, "Plate": PLATE_H, "Tile": PLATE_H,
         "Baseplate": BASEPLATE_H}
#: stud facets in a build: round enough, light enough for many bricks
SEG = 16
#: a baseplate with more studs than this gets plain 8-sided studs,
#: which the document's $fn leaves alone (`model.keeps_segments`): a
#: 16-sided stud became 45-sided and a 32 x 32 plate ~280k triangles
BIG_PLATE = 0
#: the baseplate sizes the builder offers, in studs a side
BASEPLATE_SIZES = (16, 24, 32, 48, 64, 96)


# ---------------------------------------------------------------- pieces

def meta(node):
    """The ``lego`` record of a placed piece, or None."""
    rec = node.params.get("lego") if node.type == "union" else None
    return rec if isinstance(rec, dict) else None


#: a build's param naming the Object that holds its baseplate
BASE_KEY = "lego_base"


def base_object(build):
    """The Object beside *build* holding its baseplate, or None (a build
    made before the baseplate moved out keeps it among its pieces)."""
    name = build.params.get(BASE_KEY)
    if not name or build.parent is None:
        return None
    for n in build.parent.children:
        if n is not build and n.type == "component" and n.name == name:
            return n
    return None


def pieces(build):
    """Every placed piece of *build*: its own and its baseplate's."""
    own = [n for n in build.children if meta(n) is not None]
    base = base_object(build)
    if base is None:
        return own
    return [n for n in base.children if meta(n) is not None] + own


def grid(node):
    """(i, j) stud column of a piece's corner (its turned footprint's
    lowest corner)."""
    m = meta(node) or {}
    if "i" in m and "j" in m:
        return int(m["i"]), int(m["j"])
    return (int(round(float(node.params.get("x", 0.0)) / PITCH)),
            int(round(float(node.params.get("y", 0.0)) / PITCH)))


def part_shape(part, turn=0):
    """(nx, ny, h) of a library piece turned *turn* quarters."""
    nx, ny, h = parts_lib.shape(part)
    return (ny, nx, h) if turn % 2 else (nx, ny, h)


def _baseplate(nx, ny, colour_name):
    """A builder baseplate: the slab and ONE nested loop of plain
    8-sided studs (a node per stud made the part's cache key walk
    18k nodes on every change of a 96 x 96 plate)."""
    from .library_lego import GAP, STUD_H, STUD_R
    plate = CadNode("union", f"Baseplate {nx}x{ny}")
    plate.add(CadNode("cube", "Body", dict(
        x=GAP, y=GAP, z=0.0, width=nx * PITCH - 2 * GAP,
        depth=ny * PITCH - 2 * GAP, height=BASEPLATE_H, center=False)))
    rows = CadNode("for_loop", "Stud rows", dict(
        variable="i", start=0.0, end=float(nx - 1), step=1.0, values=""))
    cols = CadNode("for_loop", "Studs", dict(
        variable="j", start=0.0, end=float(ny - 1), step=1.0, values=""))
    cols.add(CadNode("cylinder", "Stud", dict(
        x=f"(i + 0.5) * {PITCH:g}", y=f"(j + 0.5) * {PITCH:g}",
        z=BASEPLATE_H, height=STUD_H, radius_bottom=STUD_R,
        radius_top=STUD_R, segments=8, center=False)))
    rows.add(cols)
    plate.add(rows)
    return colour(plate, colour_name)


def _geometry(kind, nx, ny, colour_name, studs=True, part=None):
    if part is not None:
        return colour(parts_lib._MAKERS[part](n=part), colour_name)
    if kind == "Baseplate":
        return _baseplate(nx, ny, colour_name)
    big = kind == "Baseplate" and nx * ny > BIG_PLATE
    geo = brick(nx, ny, KINDS[kind],
                studs=False if kind == "Tile" else studs,
                hollow=False, seg=8 if big else SEG, round_=not big,
                name=f"{kind} {nx}x{ny}")
    return colour(geo, colour_name)


#: where the origin of a piece built at (0, 0) lands, in studs, after
#: `turn` quarter turns about it, so its footprint starts at (i, j)
_TURN_SHIFT = {0: lambda nx, ny: (0, 0), 1: lambda nx, ny: (ny, 0),
               2: lambda nx, ny: (nx, ny), 3: lambda nx, ny: (0, nx)}


def piece_node(kind, nx, ny, colour_name, i, j, z, part=None, turn=0):
    """One placed piece: a Group at its grid corner holding the part,
    built at the origin, in its colour. *part* is a Library piece's
    label ("Slope 45° 2 × 2"), turned *turn* quarters; the footprint
    (nx, ny) is then its own."""
    turn = int(turn) % 4
    if part is None:
        h, label = KINDS[kind], f"{kind} {nx}x{ny}"
        dx = dy = 0
        rec = dict(kind=kind, nx=nx, ny=ny, h=h, colour=colour_name)
    else:
        bx, by, h = parts_lib.shape(part)
        nx, ny, _h = part_shape(part, turn)
        dx, dy = _TURN_SHIFT[turn](bx, by)
        label = part
        rec = dict(kind="Part", part=part, nx=nx, ny=ny, h=h,
                   colour=colour_name, turn=turn)
    rec.update(i=int(i), j=int(j))
    group = CadNode("union", f"{label}, {colour_name}", dict(
        x=(i + dx) * PITCH, y=(j + dy) * PITCH, z=round(z, 4),
        rz=90.0 * turn, lego=rec))
    group.add(_geometry(kind, nx, ny, colour_name, part=part))
    return group


def _overlaps(node, i, j, nx, ny):
    m = meta(node)
    pi, pj = grid(node)
    return pi < i + nx and i < pi + m["nx"] and pj < j + ny and j < pj + m["ny"]


def drop_z(build, i, j, nx, ny):
    """Where a piece with this footprint comes to rest: on the highest
    top beneath it (0 on empty ground)."""
    top = 0.0
    for p in pieces(build):
        if _overlaps(p, i, j, nx, ny):
            top = max(top, float(p.params.get("z", 0.0)) + meta(p)["h"])
    return top


def collides(build, i, j, nx, ny, z, h, ignore=None):
    for p in pieces(build):
        if p is ignore:
            continue
        pz = float(p.params.get("z", 0.0))
        if _overlaps(p, i, j, nx, ny) and pz < z + h - 1e-6 \
                and z < pz + meta(p)["h"] - 1e-6:
            return True
    return False


def ground(build):
    """Where level 0 stands: on a baseplate lying at z = 0, else 0."""
    tops = [float(p.params.get("z", 0.0)) + meta(p)["h"]
            for p in pieces(build) if meta(p)["h"] < PLATE_H - 1e-6
            and abs(float(p.params.get("z", 0.0))) < 1e-6]
    return max(tops) if tops else 0.0


def level_z(build, level):
    """The height of plan level *level* (one plate a level)."""
    return round(ground(build) + level * PLATE_H, 4)


def level_of(build, z):
    return int(round((z - ground(build)) / PLATE_H))


def layer(build, z):
    """What the plan shows at height *z*: {cell: (piece, starts_here)}
    for every cell a piece fills at that height, and {cell: piece} for
    the cells whose top is exactly *z* (studs to build on)."""
    filled, support = {}, {}
    for p in pieces(build):
        m, (pi, pj) = meta(p), grid(p)
        pz = float(p.params.get("z", 0.0))
        cells = [(pi + a, pj + b) for a in range(m["nx"])
                 for b in range(m["ny"])]
        if pz - 1e-6 <= z < pz + m["h"] - 1e-6:
            for c in cells:
                filled[c] = (p, abs(pz - z) < 1e-6)
        elif abs(pz + m["h"] - z) < 1e-6:
            for c in cells:
                support[c] = p
    return filled, support


def beneath(build, z):
    """{cell: the highest piece whose top is below *z*} — what the plan
    tints faintly under empty air."""
    best = {}
    for p in pieces(build):
        m, (pi, pj) = meta(p), grid(p)
        top = float(p.params.get("z", 0.0)) + m["h"]
        if top > z - 1e-6:
            continue
        for a in range(m["nx"]):
            for b in range(m["ny"]):
                c = (pi + a, pj + b)
                if c not in best or top > best[c][0]:
                    best[c] = (top, p)
    return {c: p for c, (_t, p) in best.items()}


def can_place(build, i, j, nx, ny, z, h, ignore=None):
    """(True, "") when a piece fits at (i, j, z), else (False, why): it
    must not run into another and must hold on to something — studs
    beneath, a piece on top, or the ground. *ignore* is a piece being
    moved, which is not in its own way."""
    if collides(build, i, j, nx, ny, z, h, ignore):
        return False, "Something is already there."
    if z <= ground(build) + 1e-6:
        return True, ""
    for p in pieces(build):
        if p is ignore:
            continue
        pz = float(p.params.get("z", 0.0))
        if _overlaps(p, i, j, nx, ny) and (
                abs(pz + meta(p)["h"] - z) < 1e-6 or abs(pz - z - h) < 1e-6):
            return True, ""
    return False, "Nothing to hold it: no studs beneath it at this level."


def replace_piece(build, node, i, j, z, turn=0):
    """Put *node* at (i, j, z), *turn* quarters further round (a brick,
    plate or tile turns by swapping its sides). Returns (new node,
    "") — the piece is rebuilt in the same place in the tree — or
    (None, why) when it would not fit there."""
    m = meta(node)
    nx, ny, part = m["nx"], m["ny"], m.get("part")
    new_turn = (int(m.get("turn", 0)) + turn) % 4
    if part is not None:
        nx, ny, _h = part_shape(part, new_turn)
    elif turn % 2:
        nx, ny = ny, nx
    ok, why = can_place(build, i, j, nx, ny, z, m["h"], ignore=node)
    if not ok:
        return None, why
    new = piece_node(m["kind"], nx, ny, m["colour"], i, j, z, part=part,
                     turn=new_turn if part is not None else 0)
    index = build.children.index(node)
    build.remove(node)
    build.add(new, index)
    refresh_studs(build)
    return new, ""


def duplicate_piece(build, node):
    """A copy of *node* beside it: the first free spot to its right,
    behind, left or in front, at the same height. (new, "") or
    (None, why)."""
    m, (i, j) = meta(node), grid(node)
    z = float(node.params.get("z", 0.0))
    for di, dj in ((m["nx"], 0), (0, m["ny"]), (-m["nx"], 0),
                   (0, -m["ny"])):
        if can_place(build, i + di, j + dj, m["nx"], m["ny"], z, m["h"])[0]:
            new = piece_node(m["kind"], m["nx"], m["ny"], m["colour"],
                             i + di, j + dj, z, part=m.get("part"),
                             turn=m.get("turn", 0))
            build.add(new)
            refresh_studs(build)
            return new, ""
    return None, "No room beside it for a copy."


def baseplate_of(build):
    for p in pieces(build):
        if meta(p)["kind"] == "Baseplate" and \
                abs(float(p.params.get("z", 0.0))) < 1e-6:
            return p
    return None


def set_baseplate(build, size, colour_name=None):
    """Give *build* a *size* x *size* baseplate at the origin (replacing
    the one it has). Returns the plate."""
    old = baseplate_of(build)
    colour_name = colour_name or (meta(old)["colour"] if old is not None
                                  else "Green")
    plate = piece_node("Baseplate", size, size, colour_name, 0, 0, 0.0)
    holder = old.parent if old is not None else (base_object(build)
                                                  or build)
    if old is not None:
        index = holder.children.index(old)
        holder.remove(old)
        holder.add(plate, index)
    else:
        holder.add(plate, 0)
    refresh_studs(build)
    return plate


def piece_at(build, i, j, z):
    """The piece filling cell (i, j) at height *z*, or None."""
    return layer(build, z)[0].get((i, j), (None, False))[0]


def target(build, desc, clicked, kind, nx, ny, offset=(0.0, 0.0, 0.0),
           h=None):
    """(i, j, z) for a new piece from a pick *desc* (world point and
    face normal) on the piece *clicked*, or None for an underside.
    *offset* is the build Object's placement in the view."""
    px, py = (desc["point"][0] - offset[0], desc["point"][1] - offset[1])
    n = desc.get("normal") or (0.0, 0.0, 1.0)
    side = max(abs(n[0]), abs(n[1]))
    if n[2] > 0.7 or (abs(n[2]) < 0.3 and side < 0.95):
        # a top — or the round side of a stud, which means "on here"
        ci, cj = math.floor(px / PITCH), math.floor(py / PITCH)
        i, j = ci - (nx - 1) // 2, cj - (ny - 1) // 2
        return i, j, drop_z(build, i, j, nx, ny)
    if abs(n[2]) >= 0.3 or clicked is None or meta(clicked) is None:
        return None                                   # an underside
    ci = math.floor((px + n[0] * PITCH * 0.5) / PITCH)
    cj = math.floor((py + n[1] * PITCH * 0.5) / PITCH)
    if abs(n[0]) >= abs(n[1]):
        i = ci if n[0] > 0 else ci - nx + 1
        j = cj - (ny - 1) // 2
    else:
        j = cj if n[1] > 0 else cj - ny + 1
        i = ci - (nx - 1) // 2
    z = float(clicked.params.get("z", 0.0))
    if collides(build, i, j, nx, ny, z, KINDS.get(kind, h) if h is None
                else h):
        z = drop_z(build, i, j, nx, ny)
    return i, j, z


def refresh_studs(build):
    """Leave out the studs another piece now covers, and put back the
    ones uncovered — a piece is rebuilt only when that changed. Returns
    how many were rebuilt."""
    bottoms = set()
    for p in pieces(build):
        m, (pi, pj) = meta(p), grid(p)
        z = round(float(p.params.get("z", 0.0)), 3)
        for a in range(m["nx"]):
            for b in range(m["ny"]):
                bottoms.add((pi + a, pj + b, z))
    rebuilt = 0
    for p in pieces(build):
        m, (pi, pj) = meta(p), grid(p)
        if m["kind"] not in ("Brick", "Plate"):
            # a tile, a Library piece as made — or the baseplate, whose
            # hidden studs stay so its mesh never changes (and every
            # cache keeps it: 9216 studs re-projected cost 1.5 s a click)
            continue
        top = round(float(p.params.get("z", 0.0)) + m["h"], 3)
        bare = [[a, b] for a in range(m["nx"]) for b in range(m["ny"])
                if (pi + a, pj + b, top) not in bottoms]
        if m.get("bare") == bare:
            continue
        for child in list(p.children):
            p.remove(child)
        p.add(_geometry(m["kind"], m["nx"], m["ny"], m["colour"],
                        studs={(a, b) for a, b in bare}))
        p.params["lego"] = dict(m, bare=bare)
        rebuilt += 1
    return rebuilt


def find_build(model, selected=None):
    """The build to add to: the selected Object if it holds pieces (a
    selected baseplate Object means its build), else the first Object
    called "Lego build", else None."""
    for node in (selected or []):
        while node is not None and node.type != "component":
            node = node.parent
        if node is None:
            continue
        if node.params.get("lego_role") == "baseplate":
            for other in (node.parent.children if node.parent else []):
                if other.type == "component" and \
                        other.params.get(BASE_KEY) == node.name:
                    return other
            continue
        if pieces(node):
            return node
    for node in model.root.walk():
        if node.type == "component" and node.name == BUILD_NAME:
            return node
    return None


def _new_object(model, name, content=None):
    """A new visible Object in Main called *name* (made unique), holding
    *content* if given."""
    # a holder of its own: enclosing a piece itself turned the piece's
    # group into the Object, and the build lost it
    holder = CadNode("union", name)
    if content is not None:
        holder.add(content)
    model.root.add(holder)
    model.structure_changed.emit()
    comp = model.enclose_as_part(holder, name)
    if content is not None and content.parent is not comp:
        content.parent.remove(content)      # whichever way it was wrapped
        comp.add(content)
        for n in list(comp.children):
            if n is not content and n.type == "union" and not n.children:
                comp.remove(n)
    return comp


def new_build(model, size=16):
    """A fresh build in Main: an Object for the pieces beside an Object
    holding a green *size* x *size* baseplate to click on. The plate is
    kept apart so its mesh — the biggest by far — is never rebuilt when
    a piece is placed."""
    plate = piece_node("Baseplate", size, size, "Green", 0, 0, 0.0)
    base = _new_object(model, BUILD_NAME + " baseplate", plate)
    base.params["lego_role"] = "baseplate"
    comp = _new_object(model, BUILD_NAME)
    comp.params[BASE_KEY] = base.name
    comp.params["keep_empty"] = True
    refresh_studs(comp)
    model.structure_changed.emit()
    return comp


# ------------------------------------------------------------------ panel

def _swatch(hexcol):
    pix = QPixmap(14, 14)
    pix.fill(QColor(hexcol))
    return QIcon(pix)


#: the palette's first group: pieces whose size is typed in
BASIC = "Any size"
_PART_ROLE = Qt.UserRole + 1


class LegoBuilder(QDialog):
    """The non-modal Lego Builder: a palette of every piece, a colour,
    a level, and the plan of that level (lego_plan.LegoPlan) to click
    on — the 3D view shows the build grow. Build (in 3D) also lets a
    click on the 3D view place or erase, as before."""

    def __init__(self, window):
        super().__init__(window)
        from .lego_plan import LegoPlan
        self.window_ = window
        self.model = window.model
        self.build = None
        self.building = False
        self.turns = 0
        self.level = 0
        self.tool = "add"
        self.selected = None
        self.setWindowTitle("Lego Builder")
        self.setModal(False)
        self.resize(980, 640)
        outer = QHBoxLayout(self)
        side = QVBoxLayout()
        outer.addLayout(side, 0)
        # ---- palette
        self.palette_tree = QTreeWidget()
        self.palette_tree.setHeaderHidden(True)
        self.palette_tree.setMinimumWidth(250)
        self._fill_palette()
        self.palette_tree.currentItemChanged.connect(
            lambda _a, _b: self._piece_changed())
        side.addWidget(QLabel("<b>1 · Piece</b>"))
        side.addWidget(self.palette_tree, 1)
        form = QFormLayout()
        size = QHBoxLayout()
        self.nx, self.ny = QSpinBox(), QSpinBox()
        for box, value in ((self.nx, 2), (self.ny, 4)):
            box.setRange(1, 16)
            box.setValue(value)
            size.addWidget(box)
        size.insertWidget(1, QLabel("×"))
        form.addRow("Studs:", size)
        turn_row = QHBoxLayout()
        turn = QPushButton("Turn 90° (R)")
        turn.setToolTip("Turn the piece a quarter (R in the plan)")
        turn.clicked.connect(self.turn)
        self.turn_label = QLabel("")
        turn_row.addWidget(turn)
        turn_row.addWidget(self.turn_label, 1)
        form.addRow("Turn:", turn_row)
        self.colour = QComboBox()
        for name, hexcol in COLORS.items():
            self.colour.addItem(_swatch(hexcol), name)
        self.colour.setCurrentText("Red")
        form.addRow("Colour:", self.colour)
        side.addLayout(form)
        # ---- level
        side.addWidget(QLabel("<b>2 · Level (height)</b>"))
        lev = QHBoxLayout()
        self.level_box = QSpinBox()
        self.level_box.setRange(0, 999)
        self.level_box.setToolTip("One level is a plate (3.2 mm); a brick "
                                  "is three")
        self.level_box.valueChanged.connect(self.set_level)
        down = QPushButton("▼ brick")
        up = QPushButton("▲ brick")
        down.clicked.connect(lambda: self.step_level(-3))
        up.clicked.connect(lambda: self.step_level(3))
        lev.addWidget(self.level_box)
        lev.addWidget(down)
        lev.addWidget(up)
        side.addLayout(lev)
        self.level_text = QLabel("")
        side.addWidget(self.level_text)
        top = QPushButton("Go to the top of the build")
        top.clicked.connect(self.to_top)
        side.addWidget(top)
        # ---- build
        side.addWidget(QLabel("<b>3 · Build</b>"))
        base = QHBoxLayout()
        base.addWidget(QLabel("Baseplate:"))
        self.base_size = QComboBox()
        for n in BASEPLATE_SIZES:
            self.base_size.addItem(f"{n} × {n} studs", n)
        self.base_size.setCurrentIndex(BASEPLATE_SIZES.index(32))
        self.base_size.setToolTip("The baseplate of a new build; changing "
                                  "it resizes the current build's plate")
        self.base_size.activated.connect(lambda _i: self.resize_baseplate())
        base.addWidget(self.base_size, 1)
        side.addLayout(base)
        buttons = QHBoxLayout()
        self.go = QPushButton("Click in 3D view")
        self.go.setCheckable(True)
        self.go.setToolTip("Also place / erase by clicking pieces in the "
                           "3D view")
        self.go.toggled.connect(self.set_building)
        fresh = QPushButton("New build")
        fresh.clicked.connect(self.start_new)
        buttons.addWidget(self.go)
        buttons.addWidget(fresh)
        side.addLayout(buttons)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        side.addWidget(self.status)
        # ---- plan
        right = QVBoxLayout()
        outer.addLayout(right, 1)
        self.plan = LegoPlan(self)
        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        tools, actions = self._toolbar()
        right.addWidget(actions)
        right.addWidget(self.hint)
        row = QHBoxLayout()
        row.addWidget(tools)
        row.addWidget(self.plan, 1)
        right.addLayout(row, 1)
        self.plan.clicked.connect(self.place_at)
        self.plan.erase.connect(self.erase_at)
        self.plan.level_step.connect(self.step_level)
        self.plan.turn.connect(self.turn)
        self.plan.hovered.connect(self._ghost)
        for w in (self.colour,):
            w.currentTextChanged.connect(lambda _t: self._changed())
        for w in (self.nx, self.ny):
            w.valueChanged.connect(lambda _v: self._changed())
        self.model.structure_changed.connect(self._model_changed)
        self._piece_changed()
        self._update_level_text()

    # ------------------------------------------------------------ toolbar
    TOOLS = [
        ("select", "mdi.cursor-default-outline", "Select",
         "Click a piece to select it (a piece lower down too: the level "
         "follows it). Arrows move it a stud, Shift+PgUp/PgDn a plate, R "
         "turns, Delete removes, Esc lets go."),
        ("move", "mdi.cursor-move", "Move",
         "Drag a piece to where it should go — green where it fits, red "
         "where it does not."),
        ("rotate", "mdi.rotate-right", "Rotate",
         "Click a piece to turn it a quarter about its corner."),
        ("add", "mdi.toy-brick-plus-outline", "Add piece",
         "Click to put the chosen piece down on this level (R turns it)."),
        ("erase", "mdi.eraser", "Erase",
         "Click a piece on this level to take it away (right click does "
         "that with any tool)."),
    ]
    HINTS = {
        "select": "Select: click a piece · arrows move it · R turns · "
                  "Delete removes · wheel zooms, middle drag pans",
        "move": "Move: drag a piece · wheel zooms, middle drag pans",
        "rotate": "Rotate: click a piece to turn it 90°",
        "add": "Add: click to place · R turns · right click takes away · "
               "Shift+wheel or PgUp/PgDn changes level · grey = filled "
               "here, circles = studs to build on",
        "erase": "Erase: click a piece on this level to take it away",
    }

    def _toolbar(self):
        """(tools, actions): the five click tools stacked down the plan's
        left edge, and the actions and view controls across its top."""
        tools = QToolBar()
        tools.setOrientation(Qt.Vertical)
        tools.setIconSize(QSize(24, 24))
        tools.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        bar = QToolBar()
        bar.setIconSize(QSize(20, 20))
        bar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        group = QActionGroup(self)
        group.setExclusive(True)
        self.tool_actions = {}
        for key, icon, text, tip in self.TOOLS:
            act = QAction(icons.icon(icon), text, self)
            act.setCheckable(True)
            act.setToolTip(f"<b>{text}</b><br>{tip}")
            act.toggled.connect(lambda on, k=key: on and self.set_tool(k))
            group.addAction(act)
            tools.addAction(act)
            self.tool_actions[key] = act
        self.place_mode = self.tool_actions["add"]
        self.erase_mode = self.tool_actions["erase"]

        def action(icon, text, tip, slot):
            act = QAction(icons.icon(icon), text, self)
            act.setToolTip(f"<b>{text}</b><br>{tip}")
            act.triggered.connect(lambda _c=False: slot())
            bar.addAction(act)
            return act
        action("mdi.rotate-left", "Turn", "Turn the selected piece 90° "
               "(R) — or the piece to add", self._turn_any)
        action("mdi.content-copy", "Copy", "Put a copy of the selected "
               "piece beside it", self.duplicate_selected)
        action("mdi.delete-outline", "Delete", "Take the selected piece "
               "away (Delete)", self.delete_selected)
        bar.addSeparator()
        action("mdi.arrow-down-bold-outline", "Level −", "One plate down "
               "(PgDn, Shift+wheel)", lambda: self.step_level(-1))
        action("mdi.arrow-up-bold-outline", "Level +", "One plate up "
               "(PgUp, Shift+wheel)", lambda: self.step_level(1))
        bar.addSeparator()
        action("mdi.magnify-plus-outline", "Zoom in", "Zoom in (wheel, +)",
               lambda: self.plan.zoom_by(1.25))
        action("mdi.magnify-minus-outline", "Zoom out", "Zoom out "
               "(wheel, −)", lambda: self.plan.zoom_by(0.8))
        action("mdi.fit-to-page-outline", "Fit", "Show the whole build",
               self.plan.fit_all)
        self.tool_actions["add"].setChecked(True)
        return tools, bar

    def set_tool(self, key):
        self.tool = key
        if self.tool_actions[key].isChecked() is False:
            self.tool_actions[key].setChecked(True)
        self.hint.setText(self.HINTS[key])
        cursors = {"select": Qt.ArrowCursor, "move": Qt.SizeAllCursor,
                   "rotate": Qt.PointingHandCursor, "add": Qt.CrossCursor,
                   "erase": Qt.ForbiddenCursor}
        self.plan.setCursor(cursors[key])
        self._ghost(None)
        self._changed()

    def _turn_any(self):
        if self.selected is not None and self.tool != "add":
            self.rotate_selected()
        else:
            self.turn()

    # ---------------------------------------------------------- selection
    def select(self, piece):
        """Select *piece* (None lets go); it is outlined on the plan and
        tinted in the 3D view."""
        self.selected = piece
        if piece is not None:
            m = meta(piece)
            where = level_of(self.build, float(piece.params.get("z", 0.0)))
            self.status.setText(f"Selected {m.get('part') or m['kind']} "
                                f"{m['nx']}×{m['ny']}, {m['colour']}, at "
                                f"{grid(piece)} level {where}.")
        self._ghost(None)
        self.plan.update()

    def select_at(self, i, j):
        """Select the piece at (i, j) on this level, else the highest one
        below it (and go to its level). Returns it or None."""
        build = self._live_build()
        if build is None:
            self.select(None)
            return None
        piece = piece_at(build, i, j, self.z())
        if piece is None:
            # the piece whose studs this level stands on, else the
            # highest lower down
            piece = layer(build, self.z())[1].get((i, j)) or \
                beneath(build, self.z()).get((i, j))
            if piece is not None:
                self.set_level(level_of(build,
                                        float(piece.params.get("z", 0.0))))
        self.select(piece)
        return piece

    def _selected_live(self):
        piece = self.selected
        if piece is None or self.build is None \
                or piece not in pieces(self.build):
            self.selected = None
        return self.selected

    def move_selected(self, di, dj, dlevel=0, turn=0):
        """Move the selected piece by (di, dj) studs and *dlevel* plates,
        turning it *turn* quarters. Returns True when it moved."""
        piece = self._selected_live()
        if piece is None:
            self.status.setText("Select a piece first.")
            return False
        if meta(piece)["kind"] == "Baseplate":
            self.status.setText("The baseplate stays (resize it instead).")
            return False
        i, j = grid(piece)
        z = float(piece.params.get("z", 0.0)) + dlevel * PLATE_H
        if z < -1e-6:
            return False
        new, why = replace_piece(self.build, piece, i + di, j + dj, z, turn)
        if new is None:
            self.status.setText(why)
            return False
        if dlevel:
            self.set_level(self.level + dlevel)
        self.model.structure_changed.emit()
        self.select(new)
        return True

    def rotate_selected(self):
        return self.move_selected(0, 0, turn=1)

    def delete_selected(self):
        piece = self._selected_live()
        if piece is None:
            self.status.setText("Select a piece first.")
            return False
        if meta(piece)["kind"] == "Baseplate":
            self.status.setText("The baseplate stays (resize it instead).")
            return False
        self.build.remove(piece)
        refresh_studs(self.build)
        self.select(None)
        self.model.structure_changed.emit()
        self.status.setText("Taken away.")
        return True

    def duplicate_selected(self):
        piece = self._selected_live()
        if piece is None:
            self.status.setText("Select a piece first.")
            return None
        new, why = duplicate_piece(self.build, piece)
        if new is None:
            self.status.setText(why)
            return None
        self.model.structure_changed.emit()
        self.select(new)
        return new

    def resize_baseplate(self, size=None):
        """Give the current build (a new one if there is none) a baseplate
        of the size chosen."""
        size = int(size or self.base_size.currentData())
        if size != self.base_size.currentData():
            self.base_size.setCurrentIndex(BASEPLATE_SIZES.index(size))
        build = self._live_build()
        if build is None:
            self.start_new()
            return
        set_baseplate(build, size)
        self.model.structure_changed.emit()
        self.plan.fit_all()
        self.status.setText(f"Baseplate {size} × {size}.")

    # ------------------------------------------------------------ palette
    def _fill_palette(self):
        tree = self.palette_tree
        basic = QTreeWidgetItem(tree, [BASIC])
        for kind in ("Brick", "Plate", "Tile"):
            item = QTreeWidgetItem(basic, [f"{kind} (size: Studs below)"])
            item.setData(0, Qt.UserRole, kind)
        basic.setExpanded(True)
        groups = {}
        for label, group, _col, _make in parts_lib.ITEMS:
            parent = groups.get(group)
            if parent is None:
                parent = groups[group] = QTreeWidgetItem(tree, [group])
            item = QTreeWidgetItem(parent, [label])
            item.setData(0, Qt.UserRole, "Part")
            item.setData(0, _PART_ROLE, label)
        tree.setCurrentItem(basic.child(0))

    def select_piece(self, label):
        """Choose a piece by kind ("Brick") or Library label."""
        it = QTreeWidgetItemIterator(self.palette_tree)
        while it.value():
            item = it.value()
            if label in (item.data(0, _PART_ROLE), item.data(0, Qt.UserRole)):
                self.palette_tree.setCurrentItem(item)
                return True
            it += 1
        return False

    def _current(self):
        item = self.palette_tree.currentItem()
        kind = item.data(0, Qt.UserRole) if item is not None else None
        if kind is None:
            return "Brick", None
        return kind, item.data(0, _PART_ROLE)

    def _piece_changed(self):
        kind, part = self._current()
        self.nx.setEnabled(part is None)
        self.ny.setEnabled(part is None)
        if part is not None:
            self.turns = 0
            self.colour.setCurrentText(parts_lib.DEFAULT_COLOUR[part])
        self._changed()

    # -------------------------------------------------------------- state
    def spec(self):
        kind, _part = self._current()
        return (kind, *self.footprint()[:2], self.colour.currentText())

    def footprint(self):
        """(nx, ny, h) of the chosen piece as it will be placed."""
        kind, part = self._current()
        if part is not None:
            return part_shape(part, self.turns)
        return self.nx.value(), self.ny.value(), KINDS[kind]

    def colour_name(self):
        return self.colour.currentText()

    def erasing(self):
        return self.tool == "erase"

    def front_side(self):
        _kind, part = self._current()
        if part is None:
            return None
        return ("-Y", "+X", "+Y", "-X")[self.turns % 4]

    def z(self):
        return level_z(self.build, self.level) if self.build is not None \
            else self.level * PLATE_H

    def turn(self):
        _kind, part = self._current()
        if part is not None:
            self.turns = (self.turns + 1) % 4
        else:
            nx, ny = self.nx.value(), self.ny.value()
            self.nx.setValue(ny)
            self.ny.setValue(nx)
        self._changed()

    def _changed(self):
        _kind, part = self._current()
        self.turn_label.setText(f"{90 * self.turns}°, front faces "
                                f"{self.front_side()}" if part else "")
        self._rearm()
        self.plan.update()

    def _ghost(self, corner):
        """Tint in the 3D view the piece the plan's cursor would place,
        else the selected piece, else the window's own selection."""
        view = self.window_.view3d
        if self.build is None:
            return
        node = self._selected_live()
        if corner is not None and self.tool == "add":
            kind, part = self._current()
            nx, ny, _h = self.footprint()
            node = piece_node(kind, nx, ny, self.colour_name(), *corner,
                              self.z(), part=part, turn=self.turns)
        if node is None:
            view.set_highlight_mesh(self.window_._highlight_tris())
            return
        ox, oy, oz = self._offset()
        view.set_highlight_mesh([
            tuple((v[0] + ox, v[1] + oy, v[2] + oz) for v in t)
            for t in mesh.tessellate(node)])

    # -------------------------------------------------------------- level
    def set_level(self, level):
        self.level = max(0, int(level))
        if self.level_box.value() != self.level:
            self.level_box.setValue(self.level)
        self._update_level_text()
        self.plan.update()

    def step_level(self, step):
        self.set_level(self.level + step)

    def to_top(self):
        build = self._live_build()
        if build is None:
            return
        tops = [float(p.params.get("z", 0.0)) + meta(p)["h"]
                for p in pieces(build)]
        self.set_level(level_of(build, max(tops)) if tops else 0)

    def _update_level_text(self):
        bricks, plates = divmod(self.level, 3)
        parts = []
        if bricks:
            parts.append(f"{bricks} brick{'s' if bricks > 1 else ''}")
        if plates:
            parts.append(f"{plates} plate{'s' if plates > 1 else ''}")
        up = " + ".join(parts) or "on the ground"
        self.level_text.setText(f"z = {self.z():g} mm · {up}")

    # -------------------------------------------------------------- build
    def _live_build(self):
        """The build, found again if an undo replaced its node."""
        node = self.build
        while node is not None and node is not self.model.root:
            node = node.parent
        if node is None:
            self.build = find_build(self.model)
        return self.build

    def _model_changed(self):
        self._live_build()
        self._selected_live()
        self._update_level_text()
        self.plan.update()

    def _ensure_build(self):
        if self._live_build() is None:
            selected = self.window_.builder.active_tree().selected_nodes()
            self.build = find_build(self.model, selected) or \
                new_build(self.model, int(self.base_size.currentData()))
        return self.build

    def place_at(self, i, j):
        """Put the chosen piece with its corner at (i, j) on the current
        level (the plan's click); in Erase mode take away what is
        there. Returns the new piece, or None."""
        if self.erasing():
            self.erase_at(i + (self.footprint()[0] - 1) // 2,
                          j + (self.footprint()[1] - 1) // 2)
            return None
        build = self._ensure_build()
        kind, part = self._current()
        nx, ny, h = self.footprint()
        z = self.z()
        ok, why = can_place(build, i, j, nx, ny, z, h)
        if not ok:
            self.status.setText(why)
            return None
        node = piece_node(kind, nx, ny, self.colour_name(), i, j, z,
                          part=part, turn=self.turns)
        build.add(node)
        refresh_studs(build)
        self.model.structure_changed.emit()
        self.status.setText(f"Placed {part or kind} at ({i}, {j}), "
                            f"z = {z:g} mm.")
        return node

    def erase_at(self, i, j):
        build = self._live_build()
        if build is None:
            return False
        piece = piece_at(build, i, j, self.z())
        if piece is None or meta(piece)["kind"] == "Baseplate":
            self.status.setText("Nothing to take away there at this level.")
            return False
        build.remove(piece)
        refresh_studs(build)
        self.model.structure_changed.emit()
        self.status.setText("Taken away.")
        return True

    def start_new(self):
        self.build = new_build(self.model, int(self.base_size.currentData()))
        self.selected = None
        self.plan.fit_all()
        self.set_level(0)
        self.window_.builder.tree.select_nodes([self.build])
        self._rearm()
        self.plan.update()

    def set_building(self, on):
        self.building = bool(on)
        view = self.window_.view3d
        if not on:
            if view._pick_cb is not None:
                view.cancel_pick()
            self.status.setText("3D clicking stopped.")
            return
        self._ensure_build()
        self._arm()

    # --------------------------------------------------------------- pick
    def _offset(self):
        if self.window_.builder.isolated_component() is self.build:
            return (0.0, 0.0, 0.0)                 # shown in its own frame
        p = self.build.params
        return (float(p.get("x", 0.0)), float(p.get("y", 0.0)),
                float(p.get("z", 0.0)))

    def _groups(self):
        ox, oy, oz = self._offset()
        out = []
        for p in pieces(self.build):
            tris = [tuple((v[0] + ox, v[1] + oy, v[2] + oz) for v in t)
                    for t in mesh.tessellate(p)]
            if tris:
                out.append((p, tris))
        return out

    def _arm(self):
        if not self.building or self.build is None:
            return
        kind, part = self._current()
        nx, ny, _h = self.footprint()
        name = self.colour_name()
        erase = self.erase_mode.isChecked()
        what = part or f"{kind} {nx}x{ny}"
        banner = ("Lego Builder: click a piece to take it away · Esc to "
                  "stop" if erase else
                  f"Lego Builder: click a top to stack a {what} "
                  f"({name}), a side to set it beside · Esc to stop")
        self.status.setText(banner.split(": ", 1)[1])
        self.window_.view3d.start_pick(
            self._on_pick, groups=self._groups(), banner=banner,
            labeler=lambda desc, key: "Erase this piece" if erase
            else "Place here")

    def _rearm(self):
        view = self.window_.view3d
        if self.building and view._pick_cb is not None:
            view._pick_cb = None                 # re-arm with the new spec
            view._end_pick_mode()
            self._arm()

    def _on_pick(self, desc, key):
        if desc is None:                            # Esc / right click
            self.go.setChecked(False)
            return
        if self.erase_mode.isChecked():
            if key is not None and meta(key) is not None \
                    and meta(key)["kind"] != "Baseplate":
                key.parent.remove(key)
                refresh_studs(self.build)
                self.model.structure_changed.emit()
        else:
            kind, part = self._current()
            nx, ny, h = self.footprint()
            spot = target(self.build, desc, key, kind, nx, ny,
                          self._offset(), h=h)
            if spot is None:
                self.window_.statusBar().showMessage(
                    "Click the top or a side of a piece.", 3000)
            else:
                i, j, z = spot
                self.build.add(piece_node(kind, nx, ny, self.colour_name(),
                                          i, j, z, part=part,
                                          turn=self.turns))
                refresh_studs(self.build)
                self.set_level(max(0, level_of(self.build, z)))
                self.model.structure_changed.emit()
        self._arm()

    def closeEvent(self, event):
        self.go.setChecked(False)
        self.selected = None
        self._ghost(None)
        super().closeEvent(event)


def open_builder(window):
    """Show the (one) Lego Builder panel, on the selected build if
    there is one."""
    panel = getattr(window, "_lego_builder", None)
    if panel is None:
        panel = window._lego_builder = LegoBuilder(window)
    selected = window.builder.active_tree().selected_nodes()
    found = find_build(window.model, selected)
    if found is not None:
        panel.build = found
    panel.show()
    panel.raise_()
    panel.plan.update()
    return panel
