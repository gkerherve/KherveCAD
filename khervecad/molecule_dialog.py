"""Library ▸ Compound Builder… — molecules, reactions and proteins.

A non-modal panel over `molecule_build`, three tabs:

- **Molecule** — a compound from the library (grouped by family) or any
  SMILES, drawn ball and stick, space filling or as sticks; the formula,
  molar mass and atom count update as you type.
- **Reaction** — an equation written the way chemists write it (``2 H2
  + O2 -> 2 H2O``; examples in the list), balanced on request; the
  panel shows the balanced equation, or what does not balance, before
  anything is built.
- **Protein** — `protein_dialog.ProteinTab`: a preset peptide, a
  sequence with its secondary structure, a PDB ID, an AlphaFold model
  or a structure file, drawn as a cartoon, trace or atoms.

Build adds one Object (the molecule, the whole reaction or the protein)
to Main as one undo step, in nanometres.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout,
                             QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                             QPushButton, QRadioButton, QTabWidget,
                             QVBoxLayout, QWidget)

from . import molecule as mol
from . import molecule_build as mb
from .protein_dialog import ProteinTab
from .molecule_library import CATEGORIES, COMPOUNDS, get

STYLE_CHOICES = (("Ball and stick", "ball_and_stick"),
                 ("Space filling", "space_filling"), ("Sticks", "sticks"),
                 ("Small balls (lattice)", "lattice"))
EXAMPLES = (
    ("Water from hydrogen and oxygen", "H2 + O2 -> H2O"),
    ("Methane burning", "CH4 + O2 -> CO2 + H2O"),
    ("Ethanol burning", "ethanol + O2 -> CO2 + H2O"),
    ("Haber process (reversible)", "N2 + H2 <=> NH3"),
    ("Respiration of glucose", "C6H12O6 + O2 -> CO2 + H2O"),
    ("Hydrogen peroxide decomposing", "H2O2 -> H2O + O2"),
    ("Ammonia neutralising HCl", "NH3 + HCl -> NH4+ + smiles:[Cl-]"),
    ("Ethylene hydrogenation", "C2H4 + H2 -> C2H6"),
    ("Esterification (ethyl acetate)",
     "acetic_acid + ethanol <=> ethyl_acetate + H2O"),
)


def _styles():
    box = QComboBox()
    for label, value in STYLE_CHOICES:
        box.addItem(label, value)
    return box


class CompoundBuilder(QDialog):
    """The non-modal Compound Builder panel."""

    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setWindowTitle("Compound Builder")
        self.setModal(False)
        # the tabs connect their widgets to it as they are built
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._refresh)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.tabs.addTab(self._molecule_tab(), "Molecule")
        self.tabs.addTab(self._reaction_tab(), "Reaction")
        self.protein_tab = ProteinTab(self._timer.start)
        self.tabs.addTab(self.protein_tab, "Protein")
        buttons = QHBoxLayout()
        self.go = QPushButton("Build")
        self.go.setDefault(True)
        self.go.clicked.connect(self.build_now)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        buttons.addStretch(1)
        buttons.addWidget(self.go)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self.tabs.currentChanged.connect(self._timer.start)
        self._refresh()

    # ------------------------------------------------------------ tabs
    def _molecule_tab(self):
        page = QWidget()
        form = QFormLayout(page)
        self.from_library = QRadioButton("From the library")
        self.from_smiles = QRadioButton("From SMILES")
        self.from_library.setChecked(True)
        pick = QHBoxLayout()
        pick.addWidget(self.from_library)
        pick.addWidget(self.from_smiles)
        form.addRow(pick)
        self.compound = QComboBox()
        for cat in CATEGORIES:
            members = [(k, v) for k, v in COMPOUNDS.items() if v[2] == cat]
            if not members:
                continue
            self.compound.addItem(f"— {cat} —")
            item = self.compound.model().item(self.compound.count() - 1)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            for key, (name, _s, _c, _f) in members:
                self.compound.addItem(f"   {name}", key)
        self.compound.setCurrentIndex(self.compound.findData("caffeine"))
        form.addRow("Compound:", self.compound)
        self.smiles = QLineEdit()
        self.smiles.setPlaceholderText("e.g. CCO (ethanol), c1ccccc1O "
                                       "(phenol)")
        form.addRow("SMILES:", self.smiles)
        self.name = QLineEdit()
        self.name.setPlaceholderText("optional name")
        form.addRow("Name:", self.name)
        self.mol_style = _styles()
        form.addRow("Style:", self.mol_style)
        self.mol_info = QLabel()
        self.mol_info.setWordWrap(True)
        self.mol_info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow(self.mol_info)
        for w in (self.from_library, self.from_smiles):
            w.toggled.connect(lambda _on: self._timer.start())
        self.compound.currentIndexChanged.connect(self._timer.start)
        self.smiles.textChanged.connect(self._timer.start)
        self.mol_style.currentIndexChanged.connect(self._timer.start)
        return page

    def _reaction_tab(self):
        page = QWidget()
        form = QFormLayout(page)
        self.example = QComboBox()
        self.example.addItem("Examples…", "")
        for label, eq in EXAMPLES:
            self.example.addItem(label, eq)
        self.example.currentIndexChanged.connect(self._use_example)
        form.addRow(self.example)
        self.equation = QLineEdit("CH4 + O2 -> CO2 + H2O")
        self.equation.setToolTip(
            "Species: library names or keys (ethanol), formulas (H2O, "
            "NH4+, SO4^2-) or smiles:... ; arrows -> <=> → ⇌ ; "
            "coefficients optional")
        form.addRow("Equation:", self.equation)
        self.balance = QCheckBox("Balance it (find the coefficients)")
        self.balance.setChecked(True)
        form.addRow(self.balance)
        self.labels = QCheckBox("Formula under each molecule")
        self.labels.setChecked(False)
        form.addRow(self.labels)
        self.rx_style = _styles()
        form.addRow("Style:", self.rx_style)
        self.rx_info = QLabel()
        self.rx_info.setWordWrap(True)
        self.rx_info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow(self.rx_info)
        self.equation.textChanged.connect(self._timer.start)
        for w in (self.balance, self.labels):
            w.toggled.connect(lambda _on: self._timer.start())
        self.rx_style.currentIndexChanged.connect(self._timer.start)
        return page

    def _use_example(self, _index):
        eq = self.example.currentData()
        if eq:
            self.equation.setText(eq)

    # ----------------------------------------------------------- state
    def molecule(self):
        if self.from_smiles.isChecked():
            text = self.smiles.text().strip()
            if not text:
                raise mb.BuildError("Type a SMILES string.")
            try:
                return mol.from_smiles(text, name=self.name.text().strip()
                                       or text)
            except mol.SmilesError as exc:
                raise mb.BuildError(str(exc))
        return get(self.compound.currentData() or "water")

    def program(self):
        """(code, stats, segments) of what Build would make."""
        if self.tabs.currentIndex() == 0:
            m = self.molecule()
            code, stats = mb.molecule_program(
                m, self.mol_style.currentData(),
                name=self.name.text().strip() if self.from_smiles.isChecked()
                else "")
        elif self.tabs.currentIndex() == 2:
            code, stats = self.protein_tab.program()
        else:
            code, stats = mb.reaction_program(
                self.equation.text(), self.balance.isChecked(),
                self.rx_style.currentData(), labels=self.labels.isChecked())
        return code, stats

    def _refresh(self):
        self.smiles.setEnabled(self.from_smiles.isChecked())
        self.name.setEnabled(self.from_smiles.isChecked())
        self.compound.setEnabled(self.from_library.isChecked())
        info = (self.mol_info, self.rx_info,
                self.protein_tab.info)[self.tabs.currentIndex()]
        try:
            _code, stats = self.program()
        except (mb.BuildError, ValueError) as exc:
            info.setText(f"<span style='color:#c0392b'>{exc}</span>")
            self.go.setEnabled(False)
            return
        self.go.setEnabled(True)
        if self.tabs.currentIndex() == 0:
            info.setText(f"<b>{stats['formula']}</b> — {stats['molar_mass']}"
                         f" g/mol, {stats['atoms']} atoms, {stats['bonds']} "
                         f"bonds<br>SMILES {stats['smiles']}<br>≈ "
                         f"{stats['triangles']:,} triangles")
        elif self.tabs.currentIndex() == 2:
            info.setText(self.protein_tab.describe(stats))
        else:
            verdict = ("balanced" if stats["balanced"] else
                       "<span style='color:#c0392b'>does not balance: " +
                       ", ".join(f"{k} {a:g} → {b:g}" for k, (a, b) in
                                 stats["atom_balance"].items() if a != b)
                       + "</span>")
            info.setText(f"<b>{stats['equation']}</b><br>{verdict}<br>≈ "
                         f"{stats['triangles']:,} triangles")

    # ----------------------------------------------------------- build
    def build_now(self):
        try:
            code, stats = self.program()
            out = mb.apply(self.window_, code, stats,
                           stats.get("segments", 16))
        except (mb.BuildError, ValueError) as exc:
            QMessageBox.warning(self, "Compound Builder", str(exc))
            return
        names = ", ".join(o["name"] for o in out.get("objects", []))
        self.window_.statusBar().showMessage(
            f"Built {names}. " + " ".join(out.get("notes", [])), 10000)


def open_builder(window):
    """Show the (one) Compound Builder panel."""
    panel = getattr(window, "_compound_builder", None)
    if panel is None:
        panel = window._compound_builder = CompoundBuilder(window)
    panel.show()
    panel.raise_()
    return panel
