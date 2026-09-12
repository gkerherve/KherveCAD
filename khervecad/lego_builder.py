"""Library ▸ Lego Builder… — assemble bricks by clicking in the 3D view.

A small non-modal panel picks the piece (brick, plate or tile), its size
in studs, its colour and a quarter turn; Build arms the 3D view's pick
mode on the current build and keeps it armed:

- click the top of a piece (or of a stud): the new piece drops there,
  centred on the stud under the click, and comes to rest on the highest
  piece beneath its footprint — it stacks the way real bricks do;
- click a side: it goes beside that face, on the same layer (on top of
  whatever is already there, if that spot is taken);
- in Erase mode a click takes the clicked piece away.

Every piece is a Group whose placement (x, y, z) is its corner on the
stud grid and whose params carry ``lego`` = {kind, nx, ny, h, colour}:
the build knows its own bricks, a piece moves by editing its x/y/z,
and the .kcad keeps it all. After each change the studs another piece
covers are left out, so a big build stays light. The build is an
ordinary Object ("Lego build", started on a 16 x 16 baseplate), and
each click is one Ctrl+Z.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtGui import QColor, QIcon, QPixmap
from PyQt5.QtWidgets import (QComboBox, QDialog, QFormLayout, QHBoxLayout,
                             QLabel, QPushButton, QRadioButton, QSpinBox,
                             QVBoxLayout)

from . import mesh
from .library_lego import (BASEPLATE_H, BRICK_H, COLORS, PITCH, PLATE_H,
                           brick, colour)
from .model import CadNode

BUILD_NAME = "Lego build"
#: piece kind -> its height
KINDS = {"Brick": BRICK_H, "Plate": PLATE_H, "Tile": PLATE_H,
         "Baseplate": BASEPLATE_H}
#: stud facets in a build: round enough, light enough for many bricks
SEG = 16


# ---------------------------------------------------------------- pieces

def meta(node):
    """The ``lego`` record of a placed piece, or None."""
    rec = node.params.get("lego") if node.type == "union" else None
    return rec if isinstance(rec, dict) else None


def pieces(build):
    return [n for n in build.children if meta(n) is not None]


def grid(node):
    """(i, j) stud column of a piece's corner."""
    return (int(round(float(node.params.get("x", 0.0)) / PITCH)),
            int(round(float(node.params.get("y", 0.0)) / PITCH)))


def _geometry(kind, nx, ny, colour_name, studs=True):
    geo = brick(nx, ny, KINDS[kind],
                studs=False if kind == "Tile" else studs,
                hollow=False, seg=SEG, round_=True,
                name=f"{kind} {nx}x{ny}")
    return colour(geo, colour_name)


def piece_node(kind, nx, ny, colour_name, i, j, z):
    """One placed piece: a Group at its grid corner holding the part,
    built at the origin, in its colour."""
    group = CadNode("union", f"{kind} {nx}x{ny}, {colour_name}", dict(
        x=i * PITCH, y=j * PITCH, z=round(z, 4),
        lego=dict(kind=kind, nx=nx, ny=ny, h=KINDS[kind],
                  colour=colour_name)))
    group.add(_geometry(kind, nx, ny, colour_name))
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


def collides(build, i, j, nx, ny, z, h):
    for p in pieces(build):
        pz = float(p.params.get("z", 0.0))
        if _overlaps(p, i, j, nx, ny) and pz < z + h - 1e-6 \
                and z < pz + meta(p)["h"] - 1e-6:
            return True
    return False


def target(build, desc, clicked, kind, nx, ny, offset=(0.0, 0.0, 0.0)):
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
    if collides(build, i, j, nx, ny, z, KINDS[kind]):
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
        if m["kind"] == "Tile":
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
    """The build to add to: the selected Object if it holds pieces, else
    the first Object called "Lego build", else None."""
    for node in (selected or []):
        while node is not None and node.type != "component":
            node = node.parent
        if node is not None and pieces(node):
            return node
    for node in model.root.walk():
        if node.type == "component" and node.name == BUILD_NAME:
            return node
    return None


def new_build(model):
    """A fresh build in Main: an Object holding a green 16 x 16
    baseplate to click on."""
    plate = piece_node("Baseplate", 16, 16, "Green", 0, 0, 0.0)
    # a holder of its own: enclosing the plate itself turned the plate's
    # group into the Object, and the build lost its baseplate
    holder = CadNode("union", BUILD_NAME)
    holder.add(plate)
    model.root.add(holder)
    model.structure_changed.emit()
    comp = model.enclose_as_part(holder, BUILD_NAME)
    if plate.parent is not comp:          # whichever way it was wrapped
        plate.parent.remove(plate)
        comp.add(plate)
        for n in list(comp.children):
            if n is not plate and n.type == "union" and not n.children:
                comp.remove(n)
    refresh_studs(comp)
    model.structure_changed.emit()
    return comp


# ------------------------------------------------------------------ panel

def _swatch(hexcol):
    pix = QPixmap(14, 14)
    pix.fill(QColor(hexcol))
    return QIcon(pix)


class LegoBuilder(QDialog):
    """The non-modal Lego Builder panel."""

    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.model = window.model
        self.build = None
        self.building = False
        self.setWindowTitle("Lego Builder")
        self.setModal(False)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.kind = QComboBox()
        self.kind.addItems(["Brick", "Plate", "Tile"])
        form.addRow("Piece:", self.kind)
        size = QHBoxLayout()
        self.nx, self.ny = QSpinBox(), QSpinBox()
        for box, value in ((self.nx, 2), (self.ny, 4)):
            box.setRange(1, 16)
            box.setValue(value)
            size.addWidget(box)
        size.insertWidget(1, QLabel("×"))
        turn = QPushButton("Turn 90°")
        turn.setToolTip("Swap the two sizes: the piece turns a quarter")
        turn.clicked.connect(self.turn)
        size.addWidget(turn)
        form.addRow("Studs:", size)
        self.colour = QComboBox()
        for name, hexcol in COLORS.items():
            self.colour.addItem(_swatch(hexcol), name)
        self.colour.setCurrentText("Red")
        form.addRow("Colour:", self.colour)
        mode = QHBoxLayout()
        self.place_mode = QRadioButton("Place")
        self.erase_mode = QRadioButton("Erase")
        self.place_mode.setChecked(True)
        mode.addWidget(self.place_mode)
        mode.addWidget(self.erase_mode)
        form.addRow("Click to:", mode)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        self.go = QPushButton("Build")
        self.go.setCheckable(True)
        self.go.toggled.connect(self.set_building)
        fresh = QPushButton("New build")
        fresh.clicked.connect(self.start_new)
        buttons.addWidget(self.go)
        buttons.addWidget(fresh)
        layout.addLayout(buttons)
        self.status = QLabel("Click Build, then click in the 3D view.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        for w in (self.kind, self.colour):
            w.currentTextChanged.connect(lambda _t: self._rearm())
        for w in (self.nx, self.ny):
            w.valueChanged.connect(lambda _v: self._rearm())
        self.place_mode.toggled.connect(lambda _on: self._rearm())

    # -------------------------------------------------------------- state
    def spec(self):
        return (self.kind.currentText(), self.nx.value(), self.ny.value(),
                self.colour.currentText())

    def turn(self):
        nx, ny = self.nx.value(), self.ny.value()
        self.nx.setValue(ny)
        self.ny.setValue(nx)

    def start_new(self):
        self.build = new_build(self.model)
        self.window_.builder.tree.select_nodes([self.build])
        if not self.go.isChecked():
            self.go.setChecked(True)
        else:
            self._rearm()

    def set_building(self, on):
        self.building = bool(on)
        view = self.window_.view3d
        if not on:
            if view._pick_cb is not None:
                view.cancel_pick()
            self.status.setText("Stopped. Click Build to go on.")
            return
        selected = self.window_.builder.active_tree().selected_nodes()
        self.build = find_build(self.model, selected) or \
            new_build(self.model)
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
        kind, nx, ny, name = self.spec()
        erase = self.erase_mode.isChecked()
        banner = ("Lego Builder: click a piece to take it away · Esc to "
                  "stop" if erase else
                  f"Lego Builder: click a top to stack a {kind} {nx}x{ny} "
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
            kind, nx, ny, name = self.spec()
            spot = target(self.build, desc, key, kind, nx, ny,
                          self._offset())
            if spot is None:
                self.window_.statusBar().showMessage(
                    "Click the top or a side of a piece.", 3000)
            else:
                i, j, z = spot
                self.build.add(piece_node(kind, nx, ny, name, i, j, z))
                refresh_studs(self.build)
                self.model.structure_changed.emit()
        self._arm()

    def closeEvent(self, event):
        self.go.setChecked(False)
        super().closeEvent(event)


def open_builder(window):
    """Show the (one) Lego Builder panel."""
    panel = getattr(window, "_lego_builder", None)
    if panel is None:
        panel = window._lego_builder = LegoBuilder(window)
    panel.show()
    panel.raise_()
    return panel
