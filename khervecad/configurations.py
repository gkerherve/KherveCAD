"""Configurations (Qt-free), 2026-10-21 — SolidWorks' configurations
from the user's "do them all": named sets of the document's global
variable values ("M6", "M8", "Long", "Short"), switched in one step.

Stored on the document root as ``params["configurations"]`` =
``{name: {variable: value}}`` and ``params["configuration"]`` = the
active name, so they are saved in the .kcad and go through undo like any
param, with no new format version. Applying one writes the values into
the `assign` nodes (expressions included), which re-solves everything
that reads them — a configuration is only a remembered set of the
Variables sheet. A variable a configuration does not name keeps its
value.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

KEY = "configurations"
ACTIVE = "configuration"


def variables(model):
    """{name: assign node} of the document's global variables."""
    out = {}
    for node in model.global_assigns():
        var = str(node.params.get("variable", "")).strip()
        if var:
            out[var] = node
    return out


def current_values(model):
    return {k: n.params.get("value") for k, n in variables(model).items()}


def all_of(model):
    return dict(model.root.params.get(KEY) or {})


def active(model):
    return model.root.params.get(ACTIVE) or ""


def save(model, name, values=None):
    """Store *values* (default: every global variable as it stands) as
    configuration *name*, replacing one of that name; it becomes the
    active one."""
    name = str(name).strip()
    if not name:
        raise ValueError("A configuration needs a name.")
    known = variables(model)
    vals = current_values(model) if values is None else dict(values)
    unknown = [k for k in vals if k not in known]
    if unknown:
        raise ValueError("No variable %s in the document." %
                         ", ".join(sorted(unknown)))
    confs = all_of(model)
    confs[name] = vals
    model.root.params[KEY] = confs
    model.root.params[ACTIVE] = name
    model.node_changed.emit(model.root)
    return confs[name]


def apply(model, name):
    """Write configuration *name*'s values into the variables."""
    confs = all_of(model)
    if name not in confs:
        raise ValueError("No configuration %r (there are: %s)." % (
            name, ", ".join(confs) or "none"))
    known = variables(model)
    changed = []
    for var, value in confs[name].items():
        node = known.get(var)
        if node is not None and node.params.get("value") != value:
            node.params["value"] = value
            changed.append(node)
    model.root.params[ACTIVE] = name
    for node in changed:
        model.node_changed.emit(node)
    model.node_changed.emit(model.root)
    return [n.params["variable"] for n in changed]


def remove(model, name):
    confs = all_of(model)
    confs.pop(name, None)
    if confs:
        model.root.params[KEY] = confs
    else:
        model.root.params.pop(KEY, None)
    if active(model) == name:
        model.root.params.pop(ACTIVE, None)
    model.node_changed.emit(model.root)


def differs(model, name):
    """Variables whose value now differs from configuration *name*."""
    cur = current_values(model)
    return sorted(k for k, v in all_of(model).get(name, {}).items()
                  if cur.get(k) != v)


def state(model):
    return dict(active=active(model), configurations=all_of(model),
                variables=current_values(model),
                modified=differs(model, active(model)) if active(model)
                else [])


# ------------------------------------------------------------------ UI
def open_window(win):
    """Tools ▸ Configurations…: the list, Apply, Save current as…,
    Update, Delete."""
    from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QInputDialog,
                                 QLabel, QListWidget, QMessageBox,
                                 QPushButton, QVBoxLayout)
    from . import language
    dlg = getattr(win, "_configurations_window", None)
    if dlg is None:
        dlg = QDialog(win)
        dlg.setWindowTitle(language.tr("Configurations"))
        lay = QVBoxLayout(dlg)
        dlg.status = QLabel()
        dlg.status.setWordWrap(True)
        dlg.list = QListWidget()
        dlg.detail = QLabel()
        dlg.detail.setWordWrap(True)
        lay.addWidget(dlg.status)
        lay.addWidget(dlg.list)
        lay.addWidget(dlg.detail)
        row = QHBoxLayout()
        lay.addLayout(row)
        buttons = {}
        for key, text in (("apply", "Apply"), ("new", "Save current as…"),
                          ("update", "Update from current"),
                          ("delete", "Delete"), ("close", "Close")):
            b = QPushButton(language.tr(text))
            row.addWidget(b)
            buttons[key] = b

        def name():
            item = dlg.list.currentItem()
            return item.data(256) if item else None

        def fill():
            dlg.list.clear()
            act = active(win.model)
            for n in all_of(win.model):
                from PyQt5.QtWidgets import QListWidgetItem
                it = QListWidgetItem(("● " if n == act else "   ") + n)
                it.setData(256, n)
                dlg.list.addItem(it)
                if n == act:
                    dlg.list.setCurrentItem(it)
            if not variables(win.model):
                dlg.status.setText(language.tr(
                    "The document has no variables yet. Add some in the "
                    "Variables tab, then save their values here."))
            else:
                dlg.status.setText(language.tr(
                    "A configuration remembers the values of the "
                    "document's variables. Active: %s") % (act or "none"))
            show()

        def show():
            n = name()
            vals = all_of(win.model).get(n, {}) if n else {}
            dlg.detail.setText(", ".join(
                f"{k} = {v}" for k, v in vals.items()))

        def do(fn):
            try:
                fn()
            except ValueError as exc:
                QMessageBox.warning(dlg, language.tr("Configurations"),
                                    str(exc))
            fill()

        def new():
            text, ok = QInputDialog.getText(
                dlg, language.tr("New configuration"),
                language.tr("Name:"))
            if ok and text.strip():
                do(lambda: save(win.model, text.strip()))

        dlg.list.currentItemChanged.connect(lambda *_: show())
        buttons["apply"].clicked.connect(
            lambda: name() and do(lambda: apply(win.model, name())))
        buttons["new"].clicked.connect(new)
        buttons["update"].clicked.connect(
            lambda: name() and do(lambda: save(win.model, name())))
        buttons["delete"].clicked.connect(
            lambda: name() and do(lambda: remove(win.model, name())))
        buttons["close"].clicked.connect(dlg.close)
        dlg.fill = fill
        win._configurations_window = dlg
    dlg.fill()
    dlg.show()
    dlg.raise_()
    return dlg
