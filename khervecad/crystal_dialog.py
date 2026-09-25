"""Library ▸ Crystal Builder… — atoms, unit cell, supercell, particle.

A non-modal panel over `crystal_build`: pick a crystal from the library
(grouped by family, with its space group, cell, density and polyhedra
shown), choose what to build — the unit cell, a supercell, a particle,
all three side by side, or a SCATTER of particles over an area — and
how the cells are drawn (atoms at covalent radii, coordination
polyhedra, or both), the particle's shape and size in nanometres and
what fills it (cells, or N x N x N blocks of cells). Every change
re-counts the build: cells, atoms, polyhedra and triangles, and a build
the 3D view could not draw says so and what to change instead of
building. Build adds the Objects to Main as one undo step; the
Variables tab then reshapes them.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from dataclasses import replace

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog,
                             QDoubleSpinBox, QFormLayout, QHBoxLayout,
                             QLabel, QMessageBox, QPushButton, QSpinBox,
                             QVBoxLayout)

from . import crystal_build as cb
from . import language
from .crystal_library import CATEGORIES, LIBRARY

BUILD_CHOICES = (("Unit cell, supercell and particle", "hierarchy"),
                 ("Unit cell", "unit_cell"), ("Supercell", "supercell"),
                 ("Particle", "particle"),
                 ("Scatter particles over an area", "scatter"))
REP_CHOICES = (("Automatic", "auto"), ("Atoms", "atoms"),
               ("Polyhedra", "polyhedra"), ("Atoms and polyhedra", "both"))
FILL_CHOICES = (("Automatic", "auto"), ("Atoms", "atoms"),
                ("Polyhedra", "polyhedra"), ("Blocks of cells", "blocks"))


def _combo(choices):
    box = QComboBox()
    for label, value in choices:
        box.addItem(language.tr(label), value)
    return box


def _spin(lo, hi, value, step=1.0, decimals=2, suffix=""):
    box = QDoubleSpinBox()
    box.setRange(lo, hi)
    box.setDecimals(decimals)
    box.setSingleStep(step)
    box.setValue(value)
    box.setSuffix(suffix)
    return box


class CrystalBuilder(QDialog):
    """The non-modal Crystal Builder panel."""

    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setWindowTitle(language.tr("Crystal Builder"))
        self.setModal(False)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.crystal = QComboBox()
        for cat in CATEGORIES:
            members = [c for c in LIBRARY.values() if c.category == cat]
            if not members:
                continue
            self.crystal.addItem(f"— {cat} —")
            item = self.crystal.model().item(self.crystal.count() - 1)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            for c in members:
                self.crystal.addItem(f"   {c.name}", c.key)
        self.crystal.setCurrentIndex(self.crystal.findData("quartz"))
        form.addRow(language.tr("Crystal:"), self.crystal)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow(self.info)
        self.build = _combo(BUILD_CHOICES)
        form.addRow(language.tr("Build:"), self.build)
        self.rep = _combo(REP_CHOICES)
        self.rep.setToolTip(language.tr(
            "How a cell is drawn: its atoms (covalent radii), its "
            "coordination polyhedra (SiO4 tetrahedra…, ~10x "
            "lighter), or both"))
        form.addRow(language.tr("Cells show:"), self.rep)
        counts = QHBoxLayout()
        self.counts = []
        for _axis in "abc":
            box = QSpinBox()
            box.setRange(1, 60)
            box.setValue(4)
            counts.addWidget(box)
            self.counts.append(box)
        form.addRow(language.tr("Supercell (a × b × c):"), counts)
        self.shape = QComboBox()
        for key in cb.SHAPES:
            self.shape.addItem(
                language.tr(key.replace("_", " ").capitalize()), key)
        form.addRow(language.tr("Particle shape:"), self.shape)
        self.size = _spin(0.5, 10000, 10.0, 1.0, 2, " nm")
        self.size_label = QLabel(language.tr("Diameter:"))
        form.addRow(self.size_label, self.size)
        self.height = _spin(0.5, 10000, 10.0, 1.0, 2, " nm")
        form.addRow(language.tr("Height:"), self.height)
        edges = QHBoxLayout()
        self.edges = [_spin(0.5, 10000, v, 1.0, 2, " nm")
                      for v in (10.0, 10.0, 10.0)]
        for box in self.edges:
            edges.addWidget(box)
        form.addRow(language.tr("Box (x, y, z):"), edges)
        self.fill = _combo(FILL_CHOICES)
        self.fill.setToolTip(language.tr(
            "What fills the particle: every cell (as atoms or "
            "polyhedra) or blocks of N × N × N cells. Automatic "
            "keeps cells while the view can draw them, blocks "
            "beyond"))
        form.addRow(language.tr("Particle made of:"), self.fill)
        self.block = QSpinBox()
        self.block.setRange(1, 1000)
        self.block.setValue(10)
        self.block.setSuffix(" " + language.tr("cells per edge"))
        form.addRow(language.tr("Block:"), self.block)
        self.gap = _spin(0.0, 0.45, 0.03, 0.01, 2)
        form.addRow(language.tr("Gap between blocks:"), self.gap)
        # ---- scatter
        self.count = QSpinBox()
        self.count.setRange(1, 500)
        self.count.setValue(12)
        self.count.setSuffix(" " + language.tr("particles"))
        form.addRow(language.tr("Scatter:"), self.count)
        area = QHBoxLayout()
        self.area = [_spin(1.0, 100000, 100.0, 10.0, 1, " nm")
                     for _ in range(2)]
        for box in self.area:
            area.addWidget(box)
        form.addRow(language.tr("Over an area (x, y):"), area)
        self.min_gap = _spin(0.0, 1000.0, 1.0, 0.5, 2, " nm")
        form.addRow(language.tr("Smallest gap:"), self.min_gap)
        self.seed = QSpinBox()
        self.seed.setRange(1, 99999)
        self.seed.setValue(1)
        self.seed.setToolTip(
            language.tr("The same seed gives the same arrangement"))
        form.addRow(language.tr("Arrangement seed:"), self.seed)
        self.substrate = QCheckBox(language.tr("Draw a substrate under "
                                               "them"))
        self.substrate.setChecked(True)
        form.addRow(self.substrate)
        self.random_turn = QCheckBox(
            language.tr("Turn each particle at random"))
        self.random_turn.setChecked(True)
        form.addRow(self.random_turn)
        # ---- common
        self.atom_scale = _spin(0.05, 3.0, 1.0, 0.05, 2,
                                " " + language.tr("× covalent radius"))
        form.addRow(language.tr("Atom size:"), self.atom_scale)
        self.cell_box = QCheckBox(language.tr("Draw the lattice boxes"))
        self.cell_box.setChecked(True)
        form.addRow(self.cell_box)
        layout.addLayout(form)
        self.estimate = QLabel()
        self.estimate.setWordWrap(True)
        layout.addWidget(self.estimate)
        buttons = QHBoxLayout()
        self.go = QPushButton(language.tr("Build"))
        self.go.setDefault(True)
        self.go.clicked.connect(self.build_now)
        close = QPushButton(language.tr("Close"))
        close.clicked.connect(self.close)
        buttons.addStretch(1)
        buttons.addWidget(self.go)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._refresh)
        for widget in ([self.crystal, self.build, self.rep, self.shape,
                        self.fill] + self.counts
                       + [self.size, self.height, self.block, self.gap,
                          self.atom_scale, self.count, self.min_gap,
                          self.seed] + self.edges + self.area):
            signal = (widget.currentIndexChanged
                      if isinstance(widget, QComboBox)
                      else widget.valueChanged)
            signal.connect(self._timer.start)
        for check in (self.cell_box, self.substrate, self.random_turn):
            check.toggled.connect(self._timer.start)
        self._refresh()

    # ------------------------------------------------------------ state
    def crystal_obj(self):
        return LIBRARY.get(self.crystal.currentData() or "quartz")

    def spec(self) -> cb.Spec:
        return cb.Spec(
            crystal=self.crystal_obj(), build=self.build.currentData(),
            representation=self.rep.currentData(),
            supercell=tuple(b.value() for b in self.counts),
            shape=self.shape.currentData(), size=self.size.value(),
            height=self.height.value(),
            box=tuple(b.value() for b in self.edges),
            fill=self.fill.currentData(), block=self.block.value(),
            gap=self.gap.value(), atom_scale=self.atom_scale.value(),
            cell_box=self.cell_box.isChecked(),
            count=self.count.value(),
            area=tuple(b.value() for b in self.area),
            seed=self.seed.value(), min_gap=self.min_gap.value(),
            substrate=self.substrate.isChecked(),
            random_turn=self.random_turn.isChecked())

    def _refresh(self):
        c = self.crystal_obj()
        build, shape = self.build.currentData(), self.shape.currentData()
        particle = build in ("particle", "hierarchy", "scatter")
        scatter = build == "scatter"
        for widget in [self.shape, self.size, self.fill, self.block,
                       self.gap]:
            widget.setEnabled(particle)
        for box in self.counts:
            box.setEnabled(build == "supercell")
        self.height.setEnabled(particle and shape in ("cylinder",
                                                      "hexagonal_prism"))
        for box in self.edges:
            box.setEnabled(particle and shape == "box")
        self.size.setEnabled(particle and shape != "box")
        label = cb.SHAPES[shape].split(";")[0].split(" (")[0].capitalize()
        self.size_label.setText(language.tr(label) + ":")
        for widget in ([self.count, self.min_gap, self.seed,
                        self.substrate, self.random_turn] + self.area):
            widget.setEnabled(scatter)
        summary = c.summary()
        comp = " ".join(f"{el}{n}" for el, n in summary["composition"]
                        .items())
        self.info.setText(language.tr(
            "<b>{formula}</b> — {space_group}, {system}<br>a = {a} nm, "
            "b = {b} nm, c = {c} nm; α = {alpha:g}°, β = {beta:g}°, "
            "γ = {gamma:g}°<br>{count} atoms per cell ({comp}), "
            "{density} g/cm³").format(
                formula=c.formula, space_group=c.space_group,
                system=c.system, a=summary['a_nm'], b=summary['b_nm'],
                c=summary['c_nm'], alpha=c.alpha, beta=c.beta,
                gamma=c.gamma, count=len(c.atoms), comp=comp,
                density=summary['density_g_cm3'])
            + (language.tr("; {polyhedra}").format(
                polyhedra=summary['polyhedra'])
               if summary["polyhedra"] else ""))
        try:
            _code, stats = cb.program(replace(self.spec(), prefix="x"))
        except cb.BuildError as exc:
            self.estimate.setText(
                f"<span style='color:#c0392b'>{exc}</span>")
            self.go.setEnabled(False)
            return
        self.go.setEnabled(True)
        self.estimate.setText(describe(stats))

    # ------------------------------------------------------------ build
    def build_now(self):
        try:
            stats = cb.apply(self.window_, self.spec())
        except cb.BuildError as exc:
            QMessageBox.warning(self, language.tr("Crystal Builder"),
                                str(exc))
            return
        names = ", ".join(o["name"] for o in stats.get("objects", []))
        self.window_.statusBar().showMessage(
            language.tr("Built {names} — {triangles:,} triangles.").format(
                names=names, triangles=stats['triangles'])
            + " " + " ".join(stats.get("notes", [])), 12000)
        self._refresh()


def describe(stats: dict) -> str:
    """The estimate line: what each level holds and what it costs."""
    rows = []
    scatter = stats.get("scatter")
    if scatter:
        rows.append(language.tr(
            "Scatter: {particles} particles over {x:g} × {y:g} nm").format(
                particles=scatter['particles'], x=scatter['area_nm'][0],
                y=scatter['area_nm'][1]))
    part = stats.get("particle")
    if part:
        if part.get("blocks"):
            what = language.tr(
                "{blocks:,} blocks of {block_cells}³ cells "
                "({cells:,} cells)").format(
                    blocks=part['blocks'], block_cells=part['block_cells'],
                    cells=part['cells'])
        else:
            what = language.tr("{cells:,} cells").format(
                cells=part['cells'])
            if part.get("polyhedra"):
                what += ", " + language.tr(
                    "{count:,} polyhedra").format(count=part['polyhedra'])
            if part.get("atoms"):
                what += ", " + language.tr(
                    "{count:,} atoms").format(count=part['atoms'])
        label = (language.tr("Each particle") if scatter
                else language.tr("Particle"))
        rows.append(f"{label}: {what}"
                    + ("" if part.get("exact_count", True)
                       else " " + language.tr("(about)")))
    sc = stats.get("supercell")
    if sc:
        rows.append(language.tr("Supercell: {counts} = {cells:,} "
                                "cells").format(
            counts='×'.join(map(str, sc['counts'])), cells=sc['cells']))
    uc = stats.get("unit_cell")
    if uc:
        text = language.tr("Unit cell: {count} atoms").format(
            count=uc['atoms_per_cell'])
        if uc["polyhedra"]:
            text += ", " + language.tr("{count} polyhedra").format(
                count=uc['polyhedra'])
        rows.append(text)
    rows.append(language.tr(
        "≈ {triangles:,} triangles in the 3D view").format(
            triangles=stats['triangles']))
    rows += [f"<i>{n}</i>" for n in stats.get("notes", [])]
    return "<br>".join(rows)


def open_builder(window):
    """Show the (one) Crystal Builder panel."""
    panel = getattr(window, "_crystal_builder", None)
    if panel is None:
        panel = window._crystal_builder = CrystalBuilder(window)
    panel.show()
    panel.raise_()
    return panel
