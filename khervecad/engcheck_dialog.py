"""Analyse ▸ Check Sharp Edges… and Analyse ▸ Check Fits & Tolerances…
(engcheck_mcp.py gathers the meshes, edgecheck.py / fitcheck.py do the
arithmetic). Non-modal, like the other Analyse windows; the sharp-edge
window tints the edges on the model and offers to fillet them or to
note "break sharp edges" on the Blueprint.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import html

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox,
                             QDoubleSpinBox, QFormLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTextBrowser,
                             QVBoxLayout)

from . import edgecheck, engcheck_mcp, fitcheck, language
from .analysis_dialog import _STATUS_COLOR

_WORD = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}


def _status(s):
    return (f"<b style='color:{_STATUS_COLOR.get(s, '#000')}'>"
            f"{language.tr(_WORD.get(s, s))}</b>")


def sharp_html(report) -> str:
    rows = "".join(
        f"<tr><td>{i + 1}</td><td>{c['length']:g}</td>"
        f"<td>{c['face_angle']:g}°</td>"
        f"<td>{'convex' if c['convex'] else 'concave'}</td>"
        f"<td>{', '.join(f'{v:g}' for v in c['centre'])}</td></tr>"
        for i, c in enumerate(report["chains"][:edgecheck.MAX_LISTED]))
    head = f"<p>{_status(report['status'])} {html.escape(report['message'])}</p>"
    if not rows:
        return head
    return head + ("<table cellpadding='3'><tr><th>#</th><th>Length</th>"
                   "<th>Faces meet</th><th></th><th>Centre</th></tr>"
                   + rows + "</table>")


def fit_html(report) -> str:
    if not report["pairs"]:
        return "<p>" + language.tr(
            "No parts are mated, touching or within reach of each "
            "other.") + "</p>"
    rows = "".join(
        f"<tr><td>{html.escape(p['a'])}</td><td>{html.escape(p['b'])}</td>"
        f"<td>{_status(p['status'])}</td>"
        f"<td>{html.escape(p['message'])}</td></tr>"
        for p in report["pairs"])
    return (f"<p>{_status(report['summary'])}</p>"
            f"<table cellpadding='3'>{rows}</table>")


def stack_html(report) -> str:
    rows = "".join(
        f"<tr><td>{x['index']}</td><td>{'+' if x['sign'] > 0 else '−'}</td>"
        f"<td>{x['nominal']:g}</td><td>+{x['plus']:g} / −{x['minus']:g}"
        f"</td></tr>" for x in report["lines"])
    return (f"<p>{_status(report['status'])} "
            f"{html.escape(report['message'])}</p>"
            + (f"<table cellpadding='3'><tr><th>Note</th><th></th>"
               f"<th>Nominal</th><th>Tolerance</th></tr>{rows}</table>"
               if rows else ""))


class _Base(QDialog):
    def __init__(self, window, nodes, title):
        super().__init__(window)
        self.window_ = window
        self.nodes = list(nodes)
        self.setModal(False)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(title)
        self.resize(600, 460)
        self.layout_ = QVBoxLayout(self)
        self.form = QFormLayout()
        self.layout_.addLayout(self.form)
        self.row = QHBoxLayout()
        self.layout_.addLayout(self.row)
        self.browser = QTextBrowser()
        self.layout_.addWidget(self.browser, 1)
        self.note = QLabel("")
        self.note.setWordWrap(True)
        self.layout_.addWidget(self.note)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        self.layout_.addWidget(buttons)

    def _spin(self, lo, hi, value, suffix, decimals=2):
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setDecimals(decimals)
        s.setSuffix(suffix)
        s.setValue(value)
        return s

    def _button(self, text, slot):
        b = QPushButton(language.tr(text))
        b.clicked.connect(slot)
        self.row.addWidget(b)
        return b


class SharpEdgeDialog(_Base):
    def __init__(self, window, nodes):
        super().__init__(window, nodes, language.tr("Check sharp edges"))
        self._highlighted = False
        self.angle = self._spin(10.0, 179.0,
                                edgecheck.DEFAULT_FACE_ANGLE, "°", 1)
        self.radius = self._spin(0.05, 50.0, 0.5, " mm")
        self.concave = QCheckBox(language.tr("Inside corners too"))
        self.form.addRow(language.tr("Sharp when faces meet under"),
                         self.angle)
        self.form.addRow(language.tr("Fillet radius"), self.radius)
        self.form.addRow("", self.concave)
        self.show_box = QCheckBox(language.tr("Show them on the model"))
        self.show_box.setChecked(True)
        self.show_box.toggled.connect(self._toggle_highlight)
        self.row.addWidget(self.show_box)
        self._button("Check again", self.refresh)
        self.fillet_btn = self._button("Fillet these", self.fillet)
        self._button("Add 'break sharp edges' note to the Blueprint",
                     self.add_note)
        self.angle.valueChanged.connect(self.refresh)
        self.concave.toggled.connect(self.refresh)
        self.report = None
        self.refresh()

    def refresh(self):
        self.report = engcheck_mcp.sharp_report(
            self.window_, self.nodes, self.angle.value(),
            self.concave.isChecked())
        self.browser.setHtml(sharp_html(self.report))
        self.fillet_btn.setEnabled(any(p["fillet_seeds"] for p in
                                       self.report["per_node"]))
        self.note.setText(language.tr(
            "Holes and booleans come from the built-in preview; edges "
            "where a union's shapes meet are not seen.")
            if self.report["approximate"] else "")
        if self.show_box.isChecked():
            self._toggle_highlight(True)

    def _toggle_highlight(self, on):
        view = self.window_.view3d
        if on and self.report:
            view.set_highlight_mesh(self.report["tris"])
            self._highlighted = True
        elif self._highlighted:
            view.set_highlight_mesh(self.window_._highlight_tris())
            self._highlighted = False

    def fillet(self):
        made = engcheck_mcp.fillet_sharp(self.window_, self.nodes,
                                         self.radius.value(),
                                         self.angle.value())
        self.note.setText(language.tr(
            "{count} fillet(s) added — the rounding shows in the exact "
            "OpenSCAD render; Ctrl+Z takes it back.").format(
                count=len(made)))
        self.nodes = [m for m in made] or self.nodes

    def add_note(self):
        engcheck_mcp.note_on_blueprint(self.window_)
        self.note.setText(language.tr("Note added to the Blueprint."))

    def closeEvent(self, event):
        self._toggle_highlight(False)
        super().closeEvent(event)


class FitDialog(_Base):
    def __init__(self, window, nodes):
        super().__init__(window, nodes,
                         language.tr("Check fits & tolerances"))
        self.clearance = self._spin(0.0, 50.0, fitcheck.DEFAULT_CLEARANCE,
                                    " mm", 3)
        self.near = self._spin(0.0, 1000.0, fitcheck.DEFAULT_NEAR, " mm")
        self.chain = QLineEdit()
        self.chain.setPlaceholderText(language.tr(
            "Blueprint note numbers, e.g. 3, 5, -7 (blank = every "
            "toleranced dimension)"))
        self.limits = QLineEdit()
        self.limits.setPlaceholderText(language.tr("min, max (optional)"))
        self.form.addRow(language.tr("Wanted clearance"), self.clearance)
        self.form.addRow(language.tr("Neighbours within"), self.near)
        self.form.addRow(language.tr("Stack-up chain"), self.chain)
        self.form.addRow(language.tr("Stack-up limits"), self.limits)
        self._button("Check again", self.refresh)
        self.refresh()

    def _chain(self):
        text = self.chain.text().replace(";", ",").strip()
        if not text:
            return None
        out = []
        for part in text.split(","):
            n = int(part.strip())
            out.append({"index": abs(n), "sign": -1 if n < 0 else 1}
                       if part.strip().startswith("-") else n)
        return out

    def refresh(self):
        parts = engcheck_mcp.fit_report(self.window_, self.nodes,
                                        self.clearance.value(),
                                        self.near.value())
        text = "<h3>" + language.tr("Clearances") + "</h3>" + \
            fit_html(parts)
        text += "<h3>" + language.tr("Tolerance stack-up") + "</h3>"
        try:
            notes = engcheck_mcp.sheet_notes(self.window_.model)
            limits = [float(v) for v in self.limits.text().split(",")] \
                if self.limits.text().strip() else None
            text += stack_html(fitcheck.stackup(notes, self._chain(),
                                                limits))
        except (engcheck_mcp.CheckError, ValueError) as exc:
            text += f"<p>{html.escape(str(exc))}</p>"
        self.browser.setHtml(text)


def open_check(window, kind, nodes=None):
    """kind "sharp" | "fit": for the selection, else the scope's parts."""
    if nodes is None:
        nodes = window.builder.active_tree().selected_nodes()
    if kind == "fit" and len(nodes) < 2:
        nodes = engcheck_mcp.scope_parts(window)
    if not nodes:
        nodes = engcheck_mcp.scope_parts(window)
    if not nodes:
        window.statusBar().showMessage(language.tr(
            "Nothing to analyse — select a part, or build one."), 4000)
        return None
    dialog = (SharpEdgeDialog if kind == "sharp" else FitDialog)(
        window, nodes)
    dialog.show()
    return dialog
