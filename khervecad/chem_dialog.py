"""Library ▸ Chemistry Builder…: molecules, crystals, surfaces and
reactions built, edited, measured and exported inside KherveCAD.

A non-modal window like the House Builder: the steps down the left
(1 Start from, 2 Edit, 3 Dope, 4 Molecules on the surface, 5 Reaction
film, 6 Properties), the `ChemCanvas` beside them with its view buttons
(Top / Front / Side plans and a free 3D turn) and the measurements list.
Every edit is one undo step (whole-scene snapshots). **Build into
document** draws the structure ball-and-stick in nanometres (a crystal or
slab with its cell box), a reaction as a film the Customizer plays;
**Export…** writes XYZ / PDB / CIF / MOL / SDF. The MCP `chemistry` tool
drives the same scene (`scene_of`).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog,
                             QDoubleSpinBox, QFileDialog, QFormLayout,
                             QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                             QListWidget, QMessageBox, QPushButton,
                             QScrollArea, QSlider, QSpinBox, QSplitter,
                             QStackedWidget, QTableWidget,
                             QTableWidgetItem, QToolButton, QVBoxLayout,
                             QWidget)

from . import chem_adsorb as ad
from . import chem_io
from . import chem_scene as cs
from . import language
from .chem_canvas import TOOLS, VIEWS, ChemCanvas
from .crystal_build import BuildError

SOURCES = (("Compound or SMILES", "compound"), ("Crystal", "crystal"),
           ("Surface", "surface"), ("CIF file", "cif"),
           ("Reaction", "reaction"))
COMMON = ("C", "H", "O", "N", "S", "P", "F", "Cl", "Br", "I", "Si", "B",
          "Li", "Na", "K", "Mg", "Ca", "Al", "Ti", "Fe", "Co", "Ni", "Cu",
          "Zn", "Zr", "Nb", "Mo", "Ag", "Au", "Pt", "Pd")
TOOL_LABELS = {"rotate": "Turn", "select": "Select", "measure": "Measure",
               "add": "Add atom", "bond": "Bond", "move": "Move",
               "delete": "Delete"}
UNDO_DEPTH = 60


def scene_of(window):
    """The builder's scene for *window* (created hidden when needed)."""
    return open_builder(window, show=False).canvas.scene


class ChemistryBuilder(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setWindowTitle(language.tr("Chemistry Builder"))
        self.setModal(False)
        self.resize(1150, 760)
        self._undo, self._redo = [], []
        self.film = None
        self.equation = ""
        root = QHBoxLayout(self)
        split = QSplitter(Qt.Horizontal)
        root.addWidget(split)
        # ---- left: the steps
        steps = QWidget()
        col = QVBoxLayout(steps)
        col.addWidget(self._start_box())
        col.addWidget(self._edit_box())
        col.addWidget(self._dope_box())
        col.addWidget(self._adsorb_box())
        col.addWidget(self._film_box())
        col.addWidget(self._props_box())
        col.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidget(steps)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(360)
        split.addWidget(scroll)
        # ---- right: views, canvas, measurements, actions
        right = QWidget()
        rcol = QVBoxLayout(right)
        bar = QHBoxLayout()
        for name in VIEWS:
            b = QPushButton(language.tr(name))
            b.clicked.connect(lambda _c, n=name: self.canvas.set_view(n))
            bar.addWidget(b)
        fit = QPushButton(language.tr("Fit"))
        fit.clicked.connect(lambda: (self.canvas.fit(), self.canvas.update()))
        bar.addWidget(fit)
        self.labels = QCheckBox(language.tr("Labels"))
        self.labels.toggled.connect(self._labels)
        bar.addWidget(self.labels)
        bar.addStretch(1)
        rcol.addLayout(bar)
        self.canvas = ChemCanvas()
        self.canvas.edited.connect(self._edited)
        self.canvas.measured.connect(self._measured)
        self.canvas.picked.connect(self._picked)
        rcol.addWidget(self.canvas, 1)
        mrow = QHBoxLayout()
        self.measures = QListWidget()
        self.measures.setMaximumHeight(110)
        mrow.addWidget(self.measures, 1)
        clear = QPushButton(language.tr("Clear\nmeasurements"))
        clear.clicked.connect(self._clear_measures)
        mrow.addWidget(clear)
        rcol.addLayout(mrow)
        act = QHBoxLayout()
        self.style = QComboBox()
        for label, key in (("Ball and stick", "ball_and_stick"),
                           ("Space filling", "space_filling"),
                           ("Sticks", "sticks")):
            self.style.addItem(language.tr(label), key)
        act.addWidget(QLabel(language.tr("Draw as:")))
        act.addWidget(self.style)
        self.cell_box = QCheckBox(language.tr("Cell box"))
        self.cell_box.setChecked(True)
        act.addWidget(self.cell_box)
        act.addStretch(1)
        export = QPushButton(language.tr("Export…"))
        export.clicked.connect(self._export)
        act.addWidget(export)
        build = QPushButton(language.tr("Build into document"))
        build.setDefault(True)
        build.clicked.connect(self.build_into_document)
        act.addWidget(build)
        rcol.addLayout(act)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)
        self.load_scene(cs.compound_scene("caffeine"))

    # ------------------------------------------------------ 1. start
    def _start_box(self):
        box = QGroupBox(language.tr("1  Start from"))
        form = QFormLayout(box)
        self.source = QComboBox()
        for label, key in SOURCES:
            self.source.addItem(language.tr(label), key)
        form.addRow(self.source)
        self.pages = QStackedWidget()
        # compound
        self.compound = QLineEdit("caffeine")
        self.compound.setPlaceholderText(language.tr(
            "name, formula or SMILES"))
        self.pages.addWidget(self._page([(None, self.compound)]))
        # crystal
        self.crystal = self._crystal_combo()
        self.reps = [self._spin(1, 30, 1) for _ in range(3)]
        reps = QHBoxLayout()
        for s in self.reps:
            reps.addWidget(s)
        self.pages.addWidget(self._page([("Crystal", self.crystal),
                                         ("Cells a × b × c", reps)]))
        # surface
        self.s_crystal = self._crystal_combo()
        self.miller = QLineEdit("111")
        self.s_rep = [self._spin(1, 20, 4) for _ in range(2)]
        srep = QHBoxLayout()
        for s in self.s_rep:
            srep.addWidget(s)
        self.layers = self._spin(1, 20, 3)
        self.complete = QCheckBox(language.tr("Whole polyhedra at the cut"))
        self.pages.addWidget(self._page([
            ("Crystal", self.s_crystal), ("Face (hkl)", self.miller),
            ("Cells across", srep), ("Layers", self.layers),
            (None, self.complete)]))
        # cif
        self.cif_path = QLineEdit()
        pick = QPushButton(language.tr("Choose…"))
        pick.clicked.connect(self._choose_cif)
        row = QHBoxLayout()
        row.addWidget(self.cif_path, 1)
        row.addWidget(pick)
        self.pages.addWidget(self._page([("CIF", row)]))
        # reaction
        self.reaction = QLineEdit("CH4 + O2 -> CO2 + H2O")
        self.pages.addWidget(self._page([("Equation", self.reaction)]))
        self.source.currentIndexChanged.connect(self._page_shown)
        self._page_shown(0)
        form.addRow(self.pages)
        load = QPushButton(language.tr("Load"))
        load.clicked.connect(self.load_from_form)
        form.addRow(load)
        self.status = QLabel()
        self.status.setWordWrap(True)
        form.addRow(self.status)
        return box

    def _page_shown(self, index):
        """Only the shown page counts for the height (a stack is as tall
        as its tallest page otherwise)."""
        from PyQt5.QtWidgets import QSizePolicy
        for k in range(self.pages.count()):
            self.pages.widget(k).setSizePolicy(
                QSizePolicy.Preferred,
                QSizePolicy.Preferred if k == index else QSizePolicy.Ignored)
        self.pages.setCurrentIndex(index)
        self.pages.adjustSize()

    def _page(self, rows):
        w = QWidget()
        f = QFormLayout(w)
        f.setContentsMargins(0, 0, 0, 0)
        for label, widget in rows:
            if label is None:
                f.addRow(widget)
            else:
                f.addRow(language.tr(label), widget)
        return w

    def _spin(self, lo, hi, v):
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setValue(v)
        return s

    def _dspin(self, lo, hi, v, step=0.1, suffix=""):
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setDecimals(2)
        s.setSingleStep(step)
        s.setValue(v)
        s.setSuffix(suffix)
        return s

    def _crystal_combo(self):
        from .crystal_library import CATEGORIES, LIBRARY
        box = QComboBox()
        for cat in CATEGORIES:
            for c in LIBRARY.values():
                if c.category == cat:
                    box.addItem(f"{c.name}", c.key)
        box.setCurrentIndex(max(0, box.findData("rutile")))
        return box

    def _choose_cif(self):
        path, _ = QFileDialog.getOpenFileName(
            self, language.tr("Open CIF"), "",
            language.tr("Crystal structure (*.cif)"))
        if path:
            self.cif_path.setText(path)

    def load_from_form(self):
        kind = self.source.currentData()
        try:
            if kind == "compound":
                scene = cs.compound_scene(self.compound.text())
            elif kind == "crystal":
                scene = cs.crystal_scene(self.crystal.currentData(),
                                         [s.value() for s in self.reps])
            elif kind == "surface":
                scene = cs.surface_scene(
                    self.s_crystal.currentData(), self.miller.text(),
                    [s.value() for s in self.s_rep], self.layers.value(),
                    complete=self.complete.isChecked())
            elif kind == "cif":
                scene = cs.cif_scene(self.cif_path.text(),
                                     [s.value() for s in self.reps])
            else:
                self.load_reaction(self.reaction.text())
                return
        except (BuildError, ValueError, KeyError) as exc:
            self.status.setText(str(exc))
            return
        self.load_scene(scene)

    def load_scene(self, scene):
        self._stop_film()
        self.film = None
        self.film_box.setEnabled(False)
        self._undo, self._redo = [], []
        self.canvas.set_scene(scene)
        self.measures.clear()
        self.status.setText(language.tr("{n}: {a} atoms, {b} bonds").format(
            n=scene.name, a=len(scene.atoms), b=len(scene.bonds)))
        self._refresh()

    # ------------------------------------------------------- 2. edit
    def _edit_box(self):
        box = QGroupBox(language.tr("2  Edit and measure"))
        col = QVBoxLayout(box)
        grid = QHBoxLayout()
        self.tools = QButtonGroup(self)
        for tool in TOOLS:
            b = QToolButton()
            b.setText(language.tr(TOOL_LABELS[tool]))
            b.setCheckable(True)
            b.setChecked(tool == "rotate")
            b.clicked.connect(lambda _c, t=tool: self.set_tool(t))
            self.tools.addButton(b)
            grid.addWidget(b)
        col.addLayout(grid)
        row = QHBoxLayout()
        row.addWidget(QLabel(language.tr("Element")))
        self.element = QComboBox()
        self.element.setEditable(True)
        self.element.addItems(COMMON)
        self.element.currentTextChanged.connect(self._element)
        row.addWidget(self.element)
        to = QPushButton(language.tr("Set selected"))
        to.setToolTip(language.tr("Change the selected atoms to this "
                                  "element"))
        to.clicked.connect(self._set_selected)
        row.addWidget(to)
        col.addLayout(row)
        row = QHBoxLayout()
        bonds = QPushButton(language.tr("Find bonds"))
        bonds.setToolTip(language.tr("Bond every pair within 1.15 × their "
                                     "covalent radii"))
        bonds.clicked.connect(self._auto_bonds)
        undo = QPushButton(language.tr("Undo"))
        undo.clicked.connect(self.undo)
        redo = QPushButton(language.tr("Redo"))
        redo.clicked.connect(self.redo)
        for b in (bonds, undo, redo):
            row.addWidget(b)
        col.addLayout(row)
        return box

    def set_tool(self, tool):
        self.canvas.set_tool(tool)
        for b in self.tools.buttons():
            b.setChecked(b.text() == language.tr(TOOL_LABELS[tool]))

    def _element(self, text):
        self.canvas.element = text.strip().capitalize() or "C"

    def _labels(self, on):
        self.canvas.labels = on
        self.canvas.update()

    def _snapshot(self):
        self._undo.append(self.canvas.scene.copy())
        del self._undo[:-UNDO_DEPTH]
        self._redo = []

    def _edited(self):
        # the canvas edits in place: its last state was snapshotted before
        self._undo.append(self._before)
        del self._undo[:-UNDO_DEPTH]
        self._redo = []
        self._refresh()

    def _refresh(self):
        self._before = self.canvas.scene.copy()
        self._fill_props()
        self._fill_groups()
        self.canvas.update()

    def undo(self):
        if self._undo:
            self._redo.append(self.canvas.scene.copy())
            self.canvas.scene = self._undo.pop()
            self.canvas.selection = []
            self._refresh()

    def redo(self):
        if self._redo:
            self._undo.append(self.canvas.scene.copy())
            self.canvas.scene = self._redo.pop()
            self._refresh()

    def _set_selected(self):
        if not self.canvas.selection:
            return
        self._snapshot()
        try:
            for i in self.canvas.selection:
                cs.set_element(self.canvas.scene, i, self.element.currentText())
        except BuildError as exc:
            self.status.setText(str(exc))
        self._refresh()

    def _auto_bonds(self):
        self._snapshot()
        cs.auto_bonds(self.canvas.scene)
        self._refresh()

    def _measured(self, result):
        self.measures.insertItem(0, result["text"])
        if result["kind"] in ("distance", "angle"):
            # stays on the drawing too (a torsion the canvas keeps itself)
            self.canvas.measures.append((list(self.canvas.selection),
                                         result))

    def _picked(self):
        sel = self.canvas.selection
        if self.canvas.tool == "measure" and len(sel) == 3:
            return
        if self.canvas.tool == "select" and sel:
            gi = ad.group_of(self.canvas.scene, sel[-1])
            if gi is not None:
                self.groups.setCurrentRow(gi)

    def _clear_measures(self):
        self.measures.clear()
        self.canvas.clear_measures()

    # ------------------------------------------------------- 3. dope
    def _dope_box(self):
        box = QGroupBox(language.tr("3  Dope"))
        form = QFormLayout(box)
        self.dope_rule = QLineEdit("Ti:Zr:0.1")
        self.dope_rule.setToolTip(language.tr(
            "host:dopant:fraction, several separated by commas — "
            "Nb:Mo:0.1 puts Mo on a tenth of the Nb sites"))
        self.seed = self._spin(0, 99999, 7)
        apply_ = QPushButton(language.tr("Dope"))
        apply_.clicked.connect(self._dope)
        form.addRow(language.tr("host:dopant:fraction"), self.dope_rule)
        form.addRow(language.tr("Random seed"), self.seed)
        form.addRow(apply_)
        return box

    def _dope(self):
        self._snapshot()
        try:
            n = cs.dope(self.canvas.scene, self.dope_rule.text(),
                        self.seed.value())
        except BuildError as exc:
            self._undo.pop()
            self.status.setText(str(exc))
            return
        self.status.setText(language.tr("{n} atoms substituted.").format(
            n=n))
        self._refresh()

    # ------------------------------------------- 4. molecules on slab
    def _adsorb_box(self):
        box = QGroupBox(language.tr("4  Molecules on the surface"))
        form = QFormLayout(box)
        self.ads_text = QLineEdit("CO")
        self.ads_mode = QComboBox()
        self.ads_mode.addItems(list(ad.MODES))
        self.ads_height = self._dspin(0.5, 20, 2.4, 0.1, " Å")
        self.ads_spin = self._dspin(-180, 180, 0, 15, "°")
        add = QPushButton(language.tr("Add to the surface"))
        add.clicked.connect(self._add_adsorbate)
        form.addRow(language.tr("Molecule"), self.ads_text)
        form.addRow(language.tr("Lying"), self.ads_mode)
        form.addRow(language.tr("Height"), self.ads_height)
        form.addRow(language.tr("Spin"), self.ads_spin)
        form.addRow(add)
        self.groups = QListWidget()
        self.groups.setMaximumHeight(80)
        self.groups.currentRowChanged.connect(self._group_picked)
        form.addRow(self.groups)
        self.gx = self._dspin(-500, 500, 0, 0.5, " Å")
        self.gy = self._dspin(-500, 500, 0, 0.5, " Å")
        self.gh = self._dspin(0, 50, 2.4, 0.1, " Å")
        for s in (self.gx, self.gy, self.gh):
            s.setKeyboardTracking(False)
            s.valueChanged.connect(self._group_moved)
        form.addRow(language.tr("Centre x"), self.gx)
        form.addRow(language.tr("Centre y"), self.gy)
        form.addRow(language.tr("Height"), self.gh)
        row = QHBoxLayout()
        for label, kw in (("↺ 15°", {"rz": 15}), ("↻ 15°", {"rz": -15}),
                          ("Tilt", {"rx": 15})):
            b = QPushButton(label)
            b.clicked.connect(lambda _c, k=kw: self._group_turn(**k))
            row.addWidget(b)
        rm = QPushButton(language.tr("Remove"))
        rm.clicked.connect(self._group_remove)
        row.addWidget(rm)
        form.addRow(row)
        return box

    def _add_adsorbate(self):
        if self.canvas.scene.kind != "surface":
            self.status.setText(language.tr(
                "Load a surface first (1 Start from ▸ Surface)."))
            return
        try:
            molecule = cs.compound_scene(self.ads_text.text())
            self._snapshot()
            ad.add(self.canvas.scene, molecule, height=self.ads_height.value(),
                   mode=self.ads_mode.currentText(),
                   spin=self.ads_spin.value(), auto=True)
        except BuildError as exc:
            self.status.setText(str(exc))
            return
        self._refresh()
        self.groups.setCurrentRow(self.groups.count() - 1)

    def _fill_groups(self):
        self.groups.blockSignals(True)
        row = self.groups.currentRow()
        self.groups.clear()
        for g in self.canvas.scene.groups:
            self.groups.addItem(g["name"])
        self.groups.setCurrentRow(min(row, self.groups.count() - 1))
        self.groups.blockSignals(False)
        self._group_picked(self.groups.currentRow())

    def _group_picked(self, gi):
        if gi < 0 or gi >= len(self.canvas.scene.groups):
            return
        p = ad.pose(self.canvas.scene, gi)
        for s, v in ((self.gx, p["x"]), (self.gy, p["y"]),
                     (self.gh, p["height"])):
            s.blockSignals(True)
            s.setValue(v)
            s.blockSignals(False)

    def _group_moved(self):
        gi = self.groups.currentRow()
        if gi < 0:
            return
        self._snapshot()
        ad.place(self.canvas.scene, gi, self.gx.value(), self.gy.value(),
                 self.gh.value())
        self._refresh()

    def _group_turn(self, **kw):
        gi = self.groups.currentRow()
        if gi < 0:
            return
        self._snapshot()
        ad.rotate(self.canvas.scene, gi, **kw)
        self._refresh()

    def _group_remove(self):
        gi = self.groups.currentRow()
        if gi < 0:
            return
        self._snapshot()
        ad.remove(self.canvas.scene, gi)
        self._refresh()

    # -------------------------------------------------- 5. the film
    def _film_box(self):
        box = QGroupBox(language.tr("5  Reaction film"))
        col = QVBoxLayout(box)
        self.film_label = QLabel(language.tr(
            "Load a reaction (1 Start from ▸ Reaction) to play it."))
        self.film_label.setWordWrap(True)
        col.addWidget(self.film_label)
        row = QHBoxLayout()
        self.play = QPushButton(language.tr("Play"))
        self.play.setCheckable(True)
        self.play.toggled.connect(self._play)
        self.scrub = QSlider(Qt.Horizontal)
        self.scrub.setRange(0, 200)
        self.scrub.valueChanged.connect(self._scrub)
        row.addWidget(self.play)
        row.addWidget(self.scrub, 1)
        col.addLayout(row)
        self.film_box = box
        box.setEnabled(False)
        return box

    def load_reaction(self, text):
        from . import chem_reaction
        try:
            film, eq = chem_reaction.animation(text)
        except BuildError as exc:
            self.status.setText(str(exc))
            return
        scene = cs.Scene(name=eq, kind="reaction",
                         source={"reaction": text})
        self.load_scene(scene)
        self.film, self.equation = film, eq
        self.film_box.setEnabled(True)
        self.film_label.setText(eq)
        self.scrub.setValue(0)
        self._scrub(0)
        self.canvas.set_view("Front")
        self.canvas.fit()

    def _scrub(self, v):
        if self.film is None:
            return
        p = v / 200.0
        s = self.canvas.scene
        s.atoms = [[el, *self.film.position(i, p)]
                   for i, el in enumerate(self.film.reac.elements)]
        s.bonds = self.film.bonds_at(p)
        self.film_label.setText(f"{self.equation} — "
                                f"{self.film.stage(p)}")
        if not self.canvas.scene.edges and v == 0:
            self.canvas.fit()
        self.canvas.update()

    def _play(self, on):
        if on:
            self._timer.start()
        else:
            self._timer.stop()

    def _stop_film(self):
        if self._timer.isActive():
            self._timer.stop()
        if hasattr(self, "play"):
            self.play.setChecked(False)

    def _tick(self):
        v = self.scrub.value() + 2
        self.scrub.setValue(v if v <= 200 else 0)

    # ---------------------------------------------- 6. properties
    def _props_box(self):
        box = QGroupBox(language.tr("6  Properties"))
        col = QVBoxLayout(box)
        self.props = QTableWidget(0, 2)
        self.props.horizontalHeader().setVisible(False)
        self.props.verticalHeader().setVisible(False)
        self.props.horizontalHeader().setStretchLastSection(True)
        self.props.setEditTriggers(QTableWidget.NoEditTriggers)
        self.props.setMinimumHeight(200)
        col.addWidget(self.props)
        return box

    def _fill_props(self):
        rows = cs.properties(self.canvas.scene)
        self.props.setRowCount(len(rows))
        for r, (k, v) in enumerate(rows):
            self.props.setItem(r, 0, QTableWidgetItem(language.tr(k)))
            self.props.setItem(r, 1, QTableWidgetItem(str(v)))
        self.props.resizeColumnToContents(0)

    # ---------------------------------------------- out of the window
    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, language.tr("Export structure"),
            self.canvas.scene.name.split(" ")[0],
            "XYZ (*.xyz);;PDB (*.pdb);;CIF (*.cif);;MOL (*.mol);;SDF (*.sdf)")
        if not path:
            return
        try:
            out = chem_io.export(self.canvas.scene, path)
        except BuildError as exc:
            QMessageBox.warning(self, language.tr("Export"), str(exc))
            return
        self.status.setText(language.tr("Wrote {p} ({n} atoms).").format(
            p=out["path"], n=out["atoms"]))

    def build_into_document(self):
        try:
            out = build(self.window_, self.canvas.scene, self.film,
                        self.equation, self.style.currentData(),
                        self.cell_box.isChecked())
        except BuildError as exc:
            QMessageBox.warning(self, language.tr("Build"), str(exc))
            return None
        self.status.setText(language.tr("Built into the document.") +
                            ("  " + " ".join(out.get("notes", []))
                             if out.get("notes") else ""))
        return out


def build(window, scene, film=None, equation="", style="ball_and_stick",
          cell_box=True) -> dict:
    """Put *scene* (or the reaction *film*) into the window's document."""
    from . import molecule_build as mb
    if film is not None:
        from . import chem_reaction
        code, stats = chem_reaction.animated_program(film, equation)
        out = mb.apply(window, code, stats, fn=12)
        out["play"] = "View ▸ Customizer ▸ rx_t ▶ plays the reaction"
        return out
    if not scene.atoms:
        raise BuildError("The structure is empty.")
    code, stats = mb.molecule_program(scene.to_molecule(), style, fn=12,
                                      name=scene.name)
    if cell_box and scene.edges:
        r = mb._n(0.03 * mb.NM)
        sticks = [f"  hull() {{ translate({mb._vec(p)}) sphere(r = {r}, "
                  f"$fn = 6); translate({mb._vec(q)}) sphere(r = {r}, "
                  f"$fn = 6); }}" for p, q in scene.edges]
        code += ('color("#8a94a6") {  // Cell box\n' + "\n".join(sticks)
                 + "\n}\n")
    return mb.apply(window, code, stats, fn=12)


def open_builder(window, show=True):
    """Show the (one) Chemistry Builder."""
    panel = getattr(window, "_chem_builder", None)
    if panel is None:
        panel = window._chem_builder = ChemistryBuilder(window)
    if show:
        panel.show()
        panel.raise_()
    return panel
