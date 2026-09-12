"""The Analyse windows: Mass properties, Check for 3D printing, Check
interference (analysis.py does the arithmetic).

Non-modal, so a report stays open while the part is fixed; the print
check can show the offending faces on the model through the 3D view's
selection highlight, and puts the ordinary highlight back when closed.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog,
                             QDialogButtonBox, QDoubleSpinBox,
                             QFormLayout, QHBoxLayout, QLabel,
                             QPushButton, QTextBrowser, QVBoxLayout)

from . import analysis, mesh

_SETTINGS = ("Kherve", "KherveCAD")

_STATUS_COLOR = {"pass": "#2e8b57", "warn": "#d08a00", "fail": "#c0392b"}


def part_tris(window, nodes):
    """World triangles of *nodes* as the views show them (exact per-part
    meshes where rendered), and whether any is only approximated."""
    root = window._render_scope()[0]
    iso = root if root is not window.model.root else None
    fn = window.model.effective_fn()
    ids = {n.id for n in nodes}
    with window._isolated_frame(iso):
        tris = mesh.selected_world_tris(root, ids, fn=fn)
    approx = any(mesh.uses_booleans(n) for n in nodes)
    return tris, approx


def assembly_parts(window):
    """[(name, node)] of the visible top-level parts to check against
    each other — the assembly."""
    root = window.model.root
    parts = []
    for n in root.children:
        if n.visible and n.type not in ("variables", "masters", "assign"):
            parts.append((n.name, n))
    return parts


def _fmt(v, digits=2):
    return f"{v:,.{digits}f}"


def mass_html(props, material, price, currency) -> str:
    grams = analysis.mass(props["volume"], material)
    hours = analysis.print_time(props["volume"])
    rows = [
        ("Volume", f"{_fmt(props['volume'] / 1000, 3)} cm³ "
                   f"({_fmt(props['volume'], 0)} mm³)"),
        ("Surface area", f"{_fmt(props['area'] / 100, 2)} cm²"),
        ("Size", " × ".join(_fmt(s, 2) for s in props["size"]) + " mm"),
        ("Centre of mass", ", ".join(_fmt(c, 2) for c in props["centroid"])
                           + " mm"),
        ("Bounding box", f"{[round(v, 2) for v in props['min']]} to "
                         f"{[round(v, 2) for v in props['max']]}"),
        (f"Mass ({material}, solid)", f"{_fmt(grams, 1)} g"),
        ("Material cost", f"{currency}{_fmt(analysis.cost(grams, price), 2)}"
                          f" at {currency}{price:g}/kg"),
        ("Print time (rough)", f"about {hours:.1f} h at "
                               f"{analysis.PRINT_MM3_PER_S:g} mm³/s"),
    ]
    body = "".join(f"<tr><td><b>{k}</b></td><td>{v}</td></tr>"
                   for k, v in rows)
    return f"<table cellpadding='4'>{body}</table>"


def print_html(report) -> str:
    rows = []
    for c in report["checks"]:
        color = _STATUS_COLOR[c["status"]]
        rows.append(f"<tr><td><b>{c['name']}</b></td>"
                    f"<td style='color:{color}'><b>{c['status'].upper()}"
                    f"</b></td><td>{c['message']}</td></tr>")
    worst = report["summary"]
    head = (f"<p style='color:{_STATUS_COLOR.get(worst, '#000')}'><b>"
            f"{'Ready to print' if worst == 'pass' else 'Look at the ' + ('warnings' if worst == 'warn' else 'failures')}"
            f"</b></p>")
    return head + f"<table cellpadding='4'>{''.join(rows)}</table>"


def interference_html(pairs) -> str:
    if not pairs:
        return "<p>Select at least two parts (or have two in Main).</p>"
    words = {"intersect": ("#c0392b", "INTERSECT"),
             "contains": ("#d08a00", "CONTAINS"),
             "inside": ("#d08a00", "INSIDE"),
             "clear": ("#2e8b57", "clear")}
    rows = []
    for p in pairs:
        color, word = words[p["status"]]
        detail = ""
        if p["status"] == "intersect":
            detail = f"crossing near {p['points'][0]}" if p.get("points") \
                else ""
        elif p["status"] == "contains":
            detail = f"{p['b']} lies inside {p['a']}"
        elif p["status"] == "inside":
            detail = f"{p['a']} lies inside {p['b']}"
        rows.append(f"<tr><td>{p['a']}</td><td>{p['b']}</td>"
                    f"<td style='color:{color}'><b>{word}</b></td>"
                    f"<td>{detail}</td></tr>")
    bad = sum(1 for p in pairs if p["status"] != "clear")
    head = ("<p><b>No parts overlap.</b></p>" if not bad else
            f"<p style='color:#c0392b'><b>{bad} pair(s) overlap.</b></p>")
    return head + f"<table cellpadding='4'>{''.join(rows)}</table>"


class AnalysisDialog(QDialog):
    """kind: "mass" | "print" | "interference"."""

    def __init__(self, window, kind, nodes, parent=None):
        super().__init__(parent or window)
        self.window_ = window
        self.kind = kind
        self.nodes = list(nodes)
        self.setModal(False)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.resize(560, 420)
        self._highlighted = False
        titles = {"mass": "Mass properties",
                  "print": "Check for 3D printing",
                  "interference": "Check interference"}
        self.setWindowTitle(titles[kind])
        layout = QVBoxLayout(self)
        settings = QSettings(*_SETTINGS)
        self.browser = QTextBrowser()
        if kind == "mass":
            form = QFormLayout()
            self.material = QComboBox()
            self.material.addItems(list(analysis.MATERIALS))
            self.material.setCurrentText(str(settings.value(
                "analysis/material", analysis.DEFAULT_MATERIAL)))
            self.price = QDoubleSpinBox()
            self.price.setRange(0.0, 100000.0)
            self.price.setDecimals(2)
            self.price.setValue(float(settings.value(
                "analysis/price_per_kg", analysis.DEFAULT_PRICE)))
            self.currency = str(settings.value("analysis/currency",
                                               analysis.DEFAULT_CURRENCY))
            form.addRow("Material", self.material)
            form.addRow(f"Price per kg ({self.currency})", self.price)
            layout.addLayout(form)
            self.material.currentTextChanged.connect(self.refresh)
            self.price.valueChanged.connect(self.refresh)
        elif kind == "print":
            form = QFormLayout()
            self.overhang = QDoubleSpinBox()
            self.overhang.setRange(10.0, 89.0)
            self.overhang.setSuffix("°")
            self.overhang.setValue(float(settings.value(
                "analysis/overhang", analysis.DEFAULT_OVERHANG)))
            self.min_wall = QDoubleSpinBox()
            self.min_wall.setRange(0.1, 50.0)
            self.min_wall.setDecimals(2)
            self.min_wall.setSuffix(" mm")
            self.min_wall.setValue(float(settings.value(
                "analysis/min_wall", analysis.DEFAULT_MIN_WALL)))
            form.addRow("Overhang limit", self.overhang)
            form.addRow("Minimum wall", self.min_wall)
            layout.addLayout(form)
            row = QHBoxLayout()
            self.show_box = QCheckBox("Show overhangs and thin walls on "
                                      "the model")
            self.show_box.toggled.connect(self._toggle_highlight)
            row.addWidget(self.show_box)
            again = QPushButton("Check again")
            again.clicked.connect(self.refresh)
            row.addWidget(again)
            layout.addLayout(row)
        layout.addWidget(self.browser, 1)
        self.note = QLabel("")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
        self.report = None
        self.refresh()

    # ------------------------------------------------------------ data
    def refresh(self):
        settings = QSettings(*_SETTINGS)
        if self.kind == "interference":
            parts = []
            for name, node in self.nodes:
                tris, _approx = part_tris(self.window_, [node])
                parts.append((name, tris))
            self.report = analysis.interference(parts)
            self.browser.setHtml(interference_html(self.report))
            return
        tris, approx = part_tris(self.window_, self.nodes)
        self.note.setText(
            "The mesh comes from the built-in preview, which only "
            "approximates booleans (holes uncut) — figures are "
            "approximate until the exact render lands." if approx else "")
        if self.kind == "mass":
            material = self.material.currentText()
            price = self.price.value()
            settings.setValue("analysis/material", material)
            settings.setValue("analysis/price_per_kg", price)
            self.report = analysis.mass_properties(tris)
            self.browser.setHtml(mass_html(self.report, material, price,
                                           self.currency))
        else:
            settings.setValue("analysis/overhang", self.overhang.value())
            settings.setValue("analysis/min_wall", self.min_wall.value())
            self.report = analysis.print_check(
                tris, overhang_deg=self.overhang.value(),
                min_wall=self.min_wall.value())
            self.browser.setHtml(print_html(self.report))
            if self._highlighted:
                self._toggle_highlight(True)

    def _toggle_highlight(self, on):
        view = self.window_.view3d
        if on and self.report:
            tris = self.report["overhang_tris"] + self.report["thin_tris"]
            view.set_highlight_mesh(tris)
            self._highlighted = True
        elif self._highlighted:
            view.set_highlight_mesh(self.window_._highlight_tris())
            self._highlighted = False

    def closeEvent(self, event):
        self._toggle_highlight(False)
        super().closeEvent(event)


def open_analysis(window, kind, nodes=None):
    """Open one of the windows for the selection (or, for the
    interference check with fewer than two selected, every part in
    Main)."""
    if nodes is None:
        tree = window.builder.active_tree()
        nodes = tree.selected_nodes()
    if kind == "interference":
        chosen = [(n.name, n) for n in nodes]
        if len(chosen) < 2:
            chosen = assembly_parts(window)
        dialog = AnalysisDialog(window, kind, chosen)
    else:
        if not nodes:
            nodes = [n for n in window.model.root.children
                     if n.visible and n.type not in ("variables",
                                                     "masters", "assign")]
        if not nodes:
            window.statusBar().showMessage(
                "Nothing to analyse — select a part, or build one.", 4000)
            return None
        dialog = AnalysisDialog(window, kind, nodes)
    dialog.show()
    return dialog
