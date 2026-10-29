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
                             QLabel, QLineEdit, QPushButton,
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


#: SolidWorks' Options tree: (heading, [page names]) — the page builders
#: are OptionsDialog._page_<name in lower case, spaces as _>
TREE = [
    ("System Options", ["General", "Display", "Sketch", "View",
                        "Performance", "FeatureManager", "File Locations"]),
    ("Document Properties", ["Units", "Image Quality", "Material"]),
]


def _flat():
    return [(head, name) for head, names in TREE for name in names]


class OptionsDialog(QDialog):
    """SolidWorks' Options: a tree of pages on the left (System Options
    for the program, Document Properties for the open document) and the
    page on the right. A switch here is the SAME action the menus use
    (found by its menu path, `interface_menus.index`), so the two can
    never disagree."""

    PAGES = tuple(name for _h, name in _flat())
    #: the first Document Properties page (open_dialog(win, 1) opens it)
    DOCUMENT = next(i for i, (h, _n) in enumerate(_flat())
                    if h == "Document Properties")

    def __init__(self, win):
        super().__init__(win)
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem
        from . import interface_menus
        self.win = win
        tr = language.tr
        self.setWindowTitle(tr("Options"))
        try:
            self._paths = interface_menus.index(win)
        except Exception:                         # never stop the window
            self._paths = {}
        self._checks = []                 # (QCheckBox, action)
        self._choices = []                # (QComboBox, {data: action})
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setFixedWidth(200)
        self.stack = QStackedWidget()
        self._items = []
        for head, names in TREE:
            top = QTreeWidgetItem(self.tree, [tr(head)])
            top.setFlags(top.flags() & ~Qt.ItemIsSelectable)
            f = top.font(0)
            f.setBold(True)
            top.setFont(0, f)
            for name in names:
                item = QTreeWidgetItem(top, [tr(name)])
                item.setData(0, Qt.UserRole, len(self._items))
                self._items.append(item)
                builder = getattr(self, "_page_" + name.lower().replace(
                    " ", "_"))
                self.stack.addWidget(builder())
            top.setExpanded(True)
        self.tree.currentItemChanged.connect(self._picked)
        # pages.setCurrentRow(i) kept (older callers, tests)
        self.pages = self
        body = QHBoxLayout()
        body.addWidget(self.tree)
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
        self.resize(760, 480)
        self.setCurrentRow(0)
        # Apply to try a setting, Cancel to take it back (the user)
        self._initial = self._state()
        self._applied = False

    def setCurrentRow(self, row):
        row = max(0, min(int(row), len(self._items) - 1))
        self.tree.setCurrentItem(self._items[row])
        self.stack.setCurrentIndex(row)

    def currentRow(self):
        return self.stack.currentIndex()

    def _picked(self, item, _old=None):
        from PyQt5.QtCore import Qt
        row = item.data(0, Qt.UserRole) if item is not None else None
        if row is not None:
            self.stack.setCurrentIndex(int(row))

    # ── helpers ────────────────────────────────────────────────────
    def _form(self, intro=None):
        page = QWidget()
        form = QFormLayout(page)
        if intro:
            note = QLabel(language.tr(intro))
            note.setWordWrap(True)
            form.addRow(note)
        return page, form

    def _check(self, form, path, label):
        """A box bound to the checkable menu action at *path*."""
        act = self._paths.get(path)
        box = QCheckBox(language.tr(label))
        if act is None:
            box.setEnabled(False)
        else:
            box.setChecked(act.isChecked())
            self._checks.append((box, act))
        form.addRow("", box)
        return box

    def _choice(self, form, prefix, label):
        """A drop-down of the exclusive menu actions under *prefix*."""
        combo = QComboBox()
        acts = {}
        for path, act in sorted(self._paths.items()):
            if path.startswith(prefix + "/") and act.isCheckable() and \
                    "/" not in path[len(prefix) + 1:]:
                text = act.text().replace("&", "")
                combo.addItem(language.tr(text), path)
                acts[path] = act
                if act.isChecked():
                    combo.setCurrentIndex(combo.count() - 1)
        combo.setEnabled(bool(acts))
        self._choices.append((combo, acts))
        form.addRow(language.tr(label), combo)
        return combo

    # ── System Options ─────────────────────────────────────────────
    def _page_general(self):
        tr = language.tr
        page, form = self._form()
        self.lang = QComboBox()
        for code, label in language.LANGUAGES.items():
            self.lang.addItem(label, code)
        self.lang.setCurrentIndex(max(0, self.lang.findData(
            language.current_language())))
        form.addRow(tr("Language:"), self.lang)
        form.addRow("", QLabel(tr("(takes effect the next time "
                                  "KherveCAD starts)")))
        self._check(form, "help/check for updates automatically",
                    "Check for updates automatically")
        self._check(form, "help/show help while hovering menus",
                    "Show help while hovering menus")
        from . import user_library_dialog
        self.autosave = QCheckBox(tr("Save new Objects to My Library "
                                     "automatically"))
        self.autosave.setChecked(user_library_dialog.autosave_enabled())
        form.addRow("", self.autosave)
        return page

    def _page_display(self):
        tr = language.tr
        from . import toolbar_style
        from .style import THEMES, current_theme
        page, form = self._form()
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
        self._choice(form, "view/3d render style", "Display style:")
        self._choice(form, "view/3d background", "Background:")
        for path, label in (
                ("view/3d smooth shading", "Smooth shading"),
                ("view/3d edge lines", "Edge lines"),
                ("view/3d cavity shading", "Cavity shading"),
                ("view/3d platform and shadow", "Platform and shadow"),
                ("view/3d ground grid", "Ground grid"),
                ("view/3d scale bar", "Scale bar"),
                ("view/3d axes (x y z)", "Axes (X Y Z)")):
            self._check(form, path, label)
        return page

    def _page_sketch(self):
        tr = language.tr
        from . import sketch_constraints as sc
        page, form = self._form()
        self._check(form, "view/grid", "Display grid")
        self._check(form, "view/snap", "Snap to grid")
        self.grid = QLineEdit("%g" % self.win.scene.grid_size)
        form.addRow(tr("Grid spacing (mm):"), self.grid)
        self._check(form, "view/show smart dimensions",
                    "Show Smart Dimensions")
        self._check(form, "view/show dimensions",
                    "Show automatic sizes on every shape")
        self.scale_first = QCheckBox(tr("Scale the sketch on its first "
                                        "dimension"))
        self.scale_first.setChecked(sc.scale_first_enabled())
        form.addRow("", self.scale_first)
        return page

    def _page_view(self):
        page, form = self._form()
        self._choice(form, "view/3d projection", "Projection:")
        self._check(form, "view/gumball (move / turn handles)",
                    "Move / turn handles (Gumball)")
        return page

    def _page_performance(self):
        page, form = self._form(
            "Hardware rendering draws the 3D view with OpenGL; without "
            "it a software painter is used. OpenSCAD renders the exact "
            "parts in the background.")
        self._check(form, "view/3d hardware rendering (opengl)",
                    "Hardware rendering (OpenGL)")
        return page

    def _page_featuremanager(self):
        from . import tree_history
        page, form = self._form()
        self.history = QCheckBox(language.tr(
            "Show the tree as a feature history (SolidWorks' "
            "FeatureManager)"))
        self.history.setChecked(tree_history.enabled())
        form.addRow("", self.history)
        return page

    def _page_file_locations(self):
        tr = language.tr
        from . import user_library
        page, form = self._form()
        locate = QPushButton(tr("Locate OpenSCAD…"))
        locate.clicked.connect(self.win._locate_openscad)
        found = getattr(self.win.engine, "binary", None) or tr("not found")
        form.addRow(tr("OpenSCAD:"), QLabel(str(found)))
        form.addRow("", locate)
        try:
            lib = str(user_library.folder())
        except Exception:
            lib = ""
        form.addRow(tr("My Library:"), QLabel(lib))
        form.addRow(tr("Exact part cache:"),
                    QLabel(str(getattr(self.win.engine, "cache_dir", "")
                               or "")))
        return page

    # ── Document Properties ────────────────────────────────────────
    def _page_units(self):
        tr = language.tr
        model = self.win.model
        page, form = self._form()
        self.unit = QComboBox()
        for code, _label in units.choices():
            self.unit.addItem(f"{units.symbol(code)} — "
                              f"{tr(units.name(code))}", code)
        self.unit.setCurrentIndex(max(0, self.unit.findData(
            units.coerce(model.unit))))
        form.addRow(tr("Units:"), self.unit)
        self.scale = QLineEdit(units.ratio_text(model.real_scale))
        form.addRow(tr("Scale (1 : N):"), self.scale)
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

    def _page_image_quality(self):
        tr = language.tr
        b = self.win.builder
        page, form = self._form(
            "How round round things are: the segments every circle, "
            "sphere and cylinder gets (OpenSCAD's $fn).")
        self.fn = QSpinBox()
        self.fn.setRange(0, 512)
        self.fn.setSpecialValueText(tr("each object its own"))
        self.fn.setValue(b.fn_spin.value() if b.fn_check.isChecked()
                         else 0)
        form.addRow(tr("Common segments ($fn):"), self.fn)
        return page

    def _page_material(self):
        tr = language.tr
        from . import analysis, massbar
        page, form = self._form(
            "The material the status bar's mass, the Blueprint title "
            "block and the bill of materials weigh the parts in.")
        self.material = QComboBox()
        for name in analysis.MATERIALS:
            self.material.addItem(tr(name), name)
        self.material.setCurrentIndex(max(0, self.material.findData(
            massbar.material_of(self.win.model))))
        form.addRow(tr("Material:"), self.material)
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
        self._applied = True
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
        for box, act in self._checks:
            if box.isChecked() != act.isChecked():
                act.trigger()                # the menu's own command
        for combo, acts in self._choices:
            act = acts.get(combo.currentData())
            if act is not None and not act.isChecked():
                act.trigger()
        s = QSettings(*_SETTINGS)
        from . import user_library_dialog, sketch_constraints as sc
        s.setValue(user_library_dialog.AUTOSAVE_KEY,
                   self.autosave.isChecked())
        s.setValue(sc.SCALE_FIRST, self.scale_first.isChecked())
        try:
            grid = float(self.grid.text().replace(",", "."))
            if grid > 0 and abs(grid - win.scene.grid_size) > 1e-12:
                win._set_grid_step(grid)
        except ValueError:
            self.grid.setText("%g" % win.scene.grid_size)
        from . import tree_history
        if self.history.isChecked() != tree_history.enabled():
            win.builder.set_history(self.history.isChecked())
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
        from . import massbar
        if self.material.currentData() != massbar.material_of(model):
            massbar.set_material(win, self.material.currentData())

    def _widgets(self):
        boxes = [self.lang, self.theme, self.style, self.autosave,
                 self.scale_first, self.grid, self.history, self.unit,
                 self.scale, self.fn, self.decimals, self.zeros,
                 self.material]
        boxes += [b for b, _a in self._checks]
        boxes += [c for c, _a in self._choices]
        return boxes

    def _state(self):
        out = []
        for w in self._widgets():
            if isinstance(w, QComboBox):
                out.append(w.currentIndex())
            elif isinstance(w, QCheckBox):
                out.append(w.isChecked())
            elif isinstance(w, QSpinBox):
                out.append(w.value())
            else:
                out.append(w.text())
        return out

    def _restore(self, state):
        for w, v in zip(self._widgets(), state):
            if isinstance(w, QComboBox):
                w.setCurrentIndex(v)
            elif isinstance(w, QCheckBox):
                w.setChecked(v)
            elif isinstance(w, QSpinBox):
                w.setValue(v)
            else:
                w.setText(v)

    def accept(self):
        self.apply()
        super().accept()

    def reject(self):
        """Cancel after Apply: everything goes back as it was."""
        if self._applied:
            self._restore(self._initial)
            self.apply()
            self._applied = False
        super().reject()


def action(win):
    """The window's one Options action (gear), shared by the Edit menu
    and the top bar — SolidWorks keeps its Options gear up there."""
    act = getattr(win, "_options_act", None)
    if act is None:
        from PyQt5.QtWidgets import QAction
        from . import icons
        act = QAction(icons.icon("mdi.cog-outline"),
                      language.tr("&Options..."), win)
        act.setShortcut("Ctrl+,")
        act.setMenuRole(QAction.NoRole)
        act.setToolTip(language.tr(
            "Options — units, dimension decimals, language, theme and "
            "interface style in one window (Ctrl+,)"))
        act.triggered.connect(lambda: open_dialog(win))
        win._options_act = act
    return act


def add_mac_settings(win, menu):
    """Also File ▸ Options, and on macOS the app menu's Settings… (Cmd+,)
    — where a Mac user looks first; a PreferencesRole action leaves the
    menu it is added to, so it is a second action."""
    menu.addAction(action(win))
    import sys
    if sys.platform == "darwin":
        from PyQt5.QtWidgets import QAction
        mac = QAction(language.tr("Settings..."), win)
        mac.setMenuRole(QAction.PreferencesRole)
        mac.triggered.connect(lambda: open_dialog(win))
        menu.addAction(mac)
        win._options_mac = mac


def open_dialog(win, page=0):
    """*page*: a page name, or 0 (System Options) / 1 (Document
    Properties) as before."""
    dlg = OptionsDialog(win)
    if isinstance(page, str):
        row = OptionsDialog.PAGES.index(page) if page in \
            OptionsDialog.PAGES else 0
    else:
        row = OptionsDialog.DOCUMENT if page == 1 else int(page)
    dlg.setCurrentRow(row)
    dlg.exec_()
    return dlg
