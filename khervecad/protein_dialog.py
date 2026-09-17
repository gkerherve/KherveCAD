"""The Compound Builder's **Protein** tab (Library ▸ Molecules ▸ Compound
Builder…).

Where the protein comes from:

- **Preset** — the ready peptides of `protein_build.PRESETS` (helices, a
  hairpin, collagen, melittin…);
- **Sequence** — one-letter codes (FASTA pasted as it is) and a
  secondary structure: a word (helix, strand, polyproline, coil) or a
  letter per residue, ``CEEEETTEEEEC``;
- **PDB ID** / **AlphaFold** — downloaded from RCSB or the AlphaFold
  database when Fetch is pressed (on a worker thread, so the window
  stays alive), then kept;
- **File** — a .pdb / .cif on disk.

The panel shows chains, residues, helix and strand counts, mass and the
triangle count before anything is built; **Save PDB…** writes the
structure (a built peptide included) for PyMOL, ChimeraX or a docking
tool.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import threading

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout,
                             QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                             QPlainTextEdit, QPushButton, QStackedWidget,
                             QWidget)

from . import protein as P
from . import protein_build as PB

SOURCES = (("Preset", "preset"), ("Sequence", "sequence"),
           ("PDB ID (RCSB)", "pdb"), ("AlphaFold (UniProt)", "alphafold"),
           ("File", "file"))
STYLE_LABELS = {"cartoon": "Cartoon", "cartoon_sticks":
                "Cartoon + side chains", "trace": "Backbone trace",
                "ball_and_stick": "Ball and stick", "sticks": "Sticks",
                "space_filling": "Space filling"}
COLOUR_LABELS = {"structure": "Secondary structure", "chain": "Chain",
                 "rainbow": "Rainbow (N → C)", "residue": "Residue type",
                 "hydropathy": "Hydropathy", "element": "Element"}


class ProteinTab(QWidget):
    """Builds `protein_build` programs; *changed* is called on edits."""

    def __init__(self, changed, parent=None):
        super().__init__(parent)
        self._changed = changed
        self._fetched = {}                     # (kind, id) -> Protein
        self._job = None
        form = QFormLayout(self)
        self.source = QComboBox()
        for label, key in SOURCES:
            self.source.addItem(label, key)
        form.addRow("From:", self.source)
        self.stack = QStackedWidget()
        form.addRow(self.stack)
        # preset
        self.preset = QComboBox()
        for key, (name, seq, _ss, note) in PB.PRESETS.items():
            self.preset.addItem(name, key)
            self.preset.setItemData(self.preset.count() - 1,
                                    f"{note} — {len(seq)} residues",
                                    Qt.ToolTipRole)
        self.stack.addWidget(self._row(self.preset))
        # sequence
        page = QWidget()
        seq_form = QFormLayout(page)
        seq_form.setContentsMargins(0, 0, 0, 0)
        self.sequence = QPlainTextEdit()
        self.sequence.setPlaceholderText("One-letter codes, e.g. "
                                         "GIGAVLKVLTTGLPALISWIKRKRQQ "
                                         "(FASTA is fine)")
        self.sequence.setMaximumHeight(70)
        seq_form.addRow("Sequence:", self.sequence)
        self.secondary = QLineEdit("helix")
        self.secondary.setToolTip(
            "helix, strand, polyproline or coil for the whole chain — or "
            "a letter per residue: H helix, G 3-10, E strand, T turn (two "
            "between strands make a hairpin), P polyproline, L left-"
            "handed, C coil. Short strings are padded with coil.")
        seq_form.addRow("Structure:", self.secondary)
        self.name = QLineEdit()
        self.name.setPlaceholderText("optional name")
        seq_form.addRow("Name:", self.name)
        self.stack.addWidget(page)
        # PDB / AlphaFold
        self.pdb_id = QLineEdit("1CRN")
        self.pdb_id.setToolTip("Four characters: 1CRN crambin, 1UBQ "
                               "ubiquitin, 4HHB haemoglobin, 1GFL GFP")
        self.fetch_pdb = QPushButton("Fetch")
        self.stack.addWidget(self._row(self.pdb_id, self.fetch_pdb))
        self.uniprot = QLineEdit("P69905")
        self.uniprot.setToolTip("A UniProt accession: P69905 haemoglobin "
                                "alpha, P0DTC2 SARS-CoV-2 spike, P04637 "
                                "p53")
        self.fetch_af = QPushButton("Fetch")
        self.stack.addWidget(self._row(self.uniprot, self.fetch_af))
        # file
        self.path = QLineEdit()
        self.path.setPlaceholderText(".pdb or .cif file")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        self.stack.addWidget(self._row(self.path, browse))
        # drawing
        self.style = QComboBox()
        for key in PB.STYLES:
            self.style.addItem(STYLE_LABELS[key], key)
        form.addRow("Style:", self.style)
        self.colour = QComboBox()
        self.colour.addItem("Automatic", "")
        for key in PB.COLOURS:
            self.colour.addItem(COLOUR_LABELS[key], key)
        form.addRow("Colour:", self.colour)
        self.chains = QLineEdit()
        self.chains.setPlaceholderText("all chains (or e.g. A, B)")
        form.addRow("Chains:", self.chains)
        extras = QHBoxLayout()
        self.ligands = QCheckBox("Ligands")
        self.ligands.setChecked(True)
        self.water = QCheckBox("Water")
        extras.addWidget(self.ligands)
        extras.addWidget(self.water)
        extras.addStretch(1)
        self.save_pdb = QPushButton("Save PDB…")
        self.save_pdb.clicked.connect(self._save_pdb)
        extras.addWidget(self.save_pdb)
        form.addRow(extras)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow(self.info)
        self._poll = QTimer(self)
        self._poll.setInterval(150)
        self._poll.timeout.connect(self._check_job)
        self.source.currentIndexChanged.connect(self._source_changed)
        self.fetch_pdb.clicked.connect(lambda: self._fetch("pdb"))
        self.fetch_af.clicked.connect(lambda: self._fetch("alphafold"))
        for w in (self.preset, self.style, self.colour):
            w.currentIndexChanged.connect(lambda _i: changed())
        for w in (self.secondary, self.name, self.chains, self.path,
                  self.pdb_id, self.uniprot):
            w.textChanged.connect(lambda _t: changed())
        self.sequence.textChanged.connect(changed)
        for w in (self.ligands, self.water):
            w.toggled.connect(lambda _on: changed())

    @staticmethod
    def _row(*widgets):
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        for w in widgets:
            row.addWidget(w, 1 if isinstance(w, (QLineEdit, QComboBox))
                          else 0)
        return page

    def _source_changed(self, index):
        self.stack.setCurrentIndex(index)
        self._changed()

    def _browse(self):
        path, _f = QFileDialog.getOpenFileName(
            self, "Protein structure", "",
            "Structures (*.pdb *.ent *.cif *.mmcif *.pdb.gz *.cif.gz);;"
            "All files (*)")
        if path:
            self.path.setText(path)

    # ------------------------------------------------------ fetching
    def _key(self, kind):
        text = (self.pdb_id if kind == "pdb" else self.uniprot).text()
        return kind, text.strip().upper()

    def _fetch(self, kind):
        if self._job is not None:
            return
        key = self._key(kind)
        box = {}

        def work():
            try:
                box["protein"] = P.fetch(key[1] if kind == "pdb" else "",
                                         key[1] if kind != "pdb" else "")
            except Exception as exc:                  # noqa: BLE001
                box["error"] = str(exc)

        self._job = (key, box, threading.Thread(target=work, daemon=True))
        self._job[2].start()
        for b in (self.fetch_pdb, self.fetch_af):
            b.setEnabled(False)
        self.info.setText(f"Downloading {key[1]}…")
        self._poll.start()

    def _check_job(self):
        key, box, thread = self._job
        if thread.is_alive():
            return
        self._poll.stop()
        self._job = None
        for b in (self.fetch_pdb, self.fetch_af):
            b.setEnabled(True)
        if "protein" in box:
            self._fetched[key] = box["protein"]
        else:
            self.info.setText("<span style='color:#c0392b'>"
                              f"{box.get('error', 'Download failed')}</span>")
            return
        self._changed()

    # --------------------------------------------------------- state
    def protein(self) -> P.Protein:
        kind = self.source.currentData()
        try:
            if kind == "preset":
                return PB.preset(self.preset.currentData())
            if kind == "sequence":
                text = self.sequence.toPlainText().strip()
                if not text:
                    raise PB.BuildError("Type a sequence.")
                return P.build_peptide(text, self.secondary.text(),
                                       name=self.name.text().strip())
            if kind in ("pdb", "alphafold"):
                key = self._key(kind)
                if key not in self._fetched:
                    raise PB.BuildError(f"Press Fetch to download "
                                        f"{key[1] or 'the structure'}.")
                return self._fetched[key]
            path = self.path.text().strip()
            if not path:
                raise PB.BuildError("Choose a .pdb or .cif file.")
            cached = self._fetched.get(("file", path))
            if cached is None:
                cached = self._fetched[("file", path)] = \
                    P.read_structure(path)
            return cached
        except P.ProteinError as exc:
            raise PB.BuildError(str(exc))

    def program(self):
        p = self.protein()
        return PB.protein_program(
            p, self.style.currentData(), self.colour.currentData(),
            self.chains.text(), self.ligands.isChecked(),
            self.water.isChecked())

    def describe(self, stats) -> str:
        chains = ", ".join(f"{c} ({len(s)})" for c, s in
                           stats["chains"].items())
        extra = []
        if stats.get("ligands"):
            extra.append("ligands " + " ".join(stats["ligands"][:8]))
        if stats.get("clashes"):
            extra.append(f"<span style='color:#c0392b'>{stats['clashes']} "
                         "atom clashes — no fold, only local "
                         "structure</span>")
        return (f"<b>{stats['name']}</b> — {stats['residues']} residues, "
                f"{stats['atoms']:,} atoms, {stats['mass_kda']} kDa<br>"
                f"chains {chains}; {stats['helix_residues']} in helices, "
                f"{stats['strand_residues']} in strands"
                + ("<br>" + "; ".join(extra) if extra else "")
                + f"<br>≈ {stats['triangles']:,} triangles")

    def _save_pdb(self):
        try:
            p = self.protein()
        except PB.BuildError as exc:
            QMessageBox.warning(self, "Save PDB", str(exc))
            return
        path, _f = QFileDialog.getSaveFileName(
            self, "Save PDB", f"{p.name}.pdb", "PDB (*.pdb)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(P.to_pdb(p))
        except OSError as exc:
            QMessageBox.warning(self, "Save PDB", str(exc))
