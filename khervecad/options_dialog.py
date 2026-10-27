"""Tools ▸ Options… — every preference in one window, the way
SolidWorks keeps them (2026-10-27, the user: units, the decimals shown
in dimensions, the language, the style — "all this should be in
there"). Two pages like SolidWorks' System Options / Document
Properties: what belongs to the program (language, theme, interface
style, OpenSCAD) and what belongs to the open document (unit, scale,
common segments, how dimensions read). The separate menu commands stay
for the assistants and the menus that list them; this window only
gathers them.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                             QDialogButtonBox, QFormLayout, QHBoxLayout,
                             QLabel, QLineEdit, QListWidget, QPushButton,
                             QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from . import language, units

_SETTINGS = ("Kherve", "KherveCAD")


def load():
    """Put the saved dimension display into units (at start-up)."""
    s = QSettings(*_SETTINGS)
    try:
        units.DIM_DECIMALS = max(0, min(6, int(
            s.value("options/dim_decimals", 2))))
    except (TypeError, ValueError):
        units.DIM_DECIMALS = 2
    units.TRAILING_ZEROS = str(s.value("options/trailing_zeros",
                                       "false")).lower() in ("true", "1")


def save_dimensions(decimals, trailing):
    units.DIM_DECIMALS = int(decimals)
    units.TRAILING_ZEROS = bool(trailing)
    s = QSettings(*_SETTINGS)
    s.setValue("options/dim_decimals", int(decimals))
    s.setValue("options/trailing_zeros", bool(trailing))


class OptionsDialog(QDialog):
    PAGES = ("System Options", "Document Properties")

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        tr = language.tr
        self.setWindowTitle(tr("Options"))
        self.pages = QListWidget()
        self.pages.addItems([tr(p) for p in self.PAGES])
        self.pages.setFixedWidth(170)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._system_page())
        self.stack.addWidget(self._document_page())
        self.pages.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.pages.setCurrentRow(0)
        body = QHBoxLayout()
        body.addWidget(self.pages)
        body.addWidget(self.stack, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok
                                   | QDialogButtonBox.Cancel
                                   | QDialogButtonBox.Apply)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self.apply)
        lay = QVBoxLayout(self)
        lay.addLayout(body)
        lay.addWidget(buttons)
        self.resize(620, 400)

    # ── pages ──────────────────────────────────────────────────────
    def _system_page(self):
        tr = language.tr
        from . import toolbar_style
        from .style import THEMES, current_theme
        page = QWidget()
        form = QFormLayout(page)
        self.lang = QComboBox()
        for code, label in language.LANGUAGES.items():
            self.lang.addItem(label, code)
        self.lang.setCurrentIndex(max(0, self.lang.findData(
            language.current_language())))
        form.addRow(tr("Language:"), self.lang)
        form.addRow("", QLabel(tr("(takes effect the next time "
                                  "KherveCAD starts)")))
        self.theme = QComboBox()
        for name in THEMES:
            self.theme.addItem(tr(name), name)
        self.theme.setCurrentIndex(max(0, self.theme.findData(
            current_theme())))
        form.addRow(tr("Theme:"), self.theme)
        self.style = QComboBox()
        for name in toolbar_style.STYLES:
            self.style.addItem(tr(toolbar_style.LABELS[name]), name)
        self.style.setCurrentIndex(max(0, self.style.findData(
            toolbar_style.current(self.win))))
        form.addRow(tr("Interface style:"), self.style)
        locate = QPushButton(tr("Locate OpenSCAD…"))
        locate.clicked.connect(self.win._locate_openscad)
        form.addRow(tr("OpenSCAD:"), locate)
        return page

    def _document_page(self):
        tr = language.tr
        model = self.win.model
        page = QWidget()
        form = QFormLayout(page)
        self.unit = QComboBox()
        for code, _label in units.choices():
            self.unit.addItem(f"{units.symbol(code)} — "
                              f"{tr(units.name(code))}", code)
        self.unit.setCurrentIndex(max(0, self.unit.findData(
            units.coerce(model.unit))))
        form.addRow(tr("Units:"), self.unit)
        self.scale = QLineEdit(units.ratio_text(model.real_scale))
        form.addRow(tr("Scale (1 : N):"), self.scale)
        b = self.win.builder
        self.fn = QSpinBox()
        self.fn.setRange(0, 512)
        self.fn.setSpecialValueText(tr("each object its own"))
        self.fn.setValue(b.fn_spin.value() if b.fn_check.isChecked()
                         else 0)
        form.addRow(tr("Common segments ($fn):"), self.fn)
        self.decimals = QSpinBox()
        self.decimals.setRange(0, 6)
        self.decimals.setValue(units.DIM_DECIMALS)
        form.addRow(tr("Dimension decimals:"), self.decimals)
        self.zeros = QCheckBox(tr("Keep trailing zeros (2.50, not 2.5)"))
        self.zeros.setChecked(units.TRAILING_ZEROS)
        form.addRow("", self.zeros)
        self.example = QLabel()
        form.addRow(tr("Example:"), self.example)
        self.decimals.valueChanged.connect(self._show_example)
        self.zeros.toggled.connect(self._show_example)
        self.unit.currentIndexChanged.connect(self._show_example)
        self._show_example()
        return page

    def _show_example(self, *_):
        old = units.DIM_DECIMALS, units.TRAILING_ZEROS
        units.DIM_DECIMALS = self.decimals.value()
        units.TRAILING_ZEROS = self.zeros.isChecked()
        try:
            self.example.setText(units.length(12.5, self.unit.currentData()))
        finally:
            units.DIM_DECIMALS, units.TRAILING_ZEROS = old

    # ── applying ───────────────────────────────────────────────────
    def apply(self):
        win = self.win
        code = self.lang.currentData()
        if code != language.current_language():
            win._set_language(code)
        from .style import apply_style, current_theme
        from . import toolbar_style
        if self.theme.currentData() != current_theme():
            apply_style(QApplication.instance(), self.theme.currentData())
            win.builder.refresh_theme()
            toolbar_style.restyle(win)
        if self.style.currentData() != toolbar_style.current(win):
            toolbar_style.apply(win, self.style.currentData())
        model = win.model
        if self.unit.currentData() != units.coerce(model.unit):
            model.set_unit(self.unit.currentData())
        if self.scale.text().strip() != units.ratio_text(model.real_scale):
            try:
                model.set_real_scale(self.scale.text())
            except ValueError:
                self.scale.setText(units.ratio_text(model.real_scale))
        b = win.builder
        value = self.fn.value()
        if value >= 3:
            b.fn_spin.setValue(value)
        b.fn_check.setChecked(value >= 3)
        if (self.decimals.value(), self.zeros.isChecked()) != \
                (units.DIM_DECIMALS, units.TRAILING_ZEROS):
            save_dimensions(self.decimals.value(), self.zeros.isChecked())
            win.view2d.viewport().update()
            win.view3d.update()

    def accept(self):
        self.apply()
        super().accept()


def open_dialog(win, page=0):
    dlg = OptionsDialog(win)
    dlg.pages.setCurrentRow(page)
    dlg.exec_()
    return dlg
