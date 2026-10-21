"""Equal sizes between parts (Qt-free + a small dialog), 2026-10-21 —
SolidWorks' Equal relation / linked dimensions across features, from the
user ("like you would choose two surfaces to be the same").

Two size parameters (a cylinder's radius and a hole's, two plates'
thickness, a cube's width and another's depth) are made equal the
parametric way: ONE document variable drives both. `link` creates the
variable (named from what it measures, value = the first one's current
size) or reuses it when the first already reads a bare variable, and
writes its name into both params. That is plain OpenSCAD — `hole_d =
8; ... cylinder(d = hole_d) ... cylinder(d = hole_d)` — so it survives
export and import, shows in the Variables sheet and Customizer, and
editing the variable resizes both. `unlink` freezes a param back to its
number.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import re

from . import expr

#: params that place or turn a part, never a size
PLACEMENT = {"x", "y", "z", "rx", "ry", "rz", "x1", "y1", "x2", "y2",
             "px", "py", "pz", "start_angle", "segments", "alpha"}
_IDENT = re.compile(r"^[A-Za-z_]\w*$")


def size_params(node):
    """[(key, label)] of a node's numeric SIZE parameters."""
    from .model import NODE_TYPES
    spec = NODE_TYPES.get(node.type, {})
    out = []
    for entry in spec.get("schema", []):
        key, label, kind = entry[0], entry[1], entry[2]
        if kind in ("float", "int") and key not in PLACEMENT:
            out.append((key, label))
    return out


def _value(model, node, key):
    from .anchors import doc_env
    return expr.resolve(node.params.get(key, 0), doc_env(model), 0.0)


def _slug(text):
    s = re.sub(r"[^A-Za-z0-9]+", "_", str(text)).strip("_").lower()
    if not s or s[0].isdigit():
        s = "v_" + s
    return s


def _free_name(model, base):
    taken = {str(n.params.get("variable", "")) for n in model.root.walk()
             if n.type == "assign"}
    name, k = base, 2
    while name in taken:
        name, k = f"{base}_{k}", k + 1
    return name


def link(model, a, key_a, b, key_b, name=None):
    """Make b.key_b always equal a.key_a. Returns the variable name."""
    for node, key in ((a, key_a), (b, key_b)):
        if key not in dict(size_params(node)):
            raise ValueError("%s has no size %r (it has: %s)." % (
                node.name, key, ", ".join(k for k, _ in size_params(node))
                or "none"))
    current = a.params.get(key_a)
    if name is None and isinstance(current, str) and \
            _IDENT.match(current.strip()):
        name = current.strip()             # already driven: share it
    else:
        value = _value(model, a, key_a)
        if name is None:
            from .model import name_tag
            base = name_tag(a.name) or a.type
            name = _free_name(model, _slug(f"{base}_{key_a}"))
        name = str(name).strip()
        if not _IDENT.match(name):
            raise ValueError("%r is not a variable name." % name)
        existing = [n for n in model.global_assigns()
                    if n.params.get("variable") == name]
        if not existing:
            from .model import CadNode
            var = CadNode("assign", name, dict(variable=name,
                                                value=round(value, 6)))
            model.root.add(var, _first_index(model))
    a.params[key_a] = name
    b.params[key_b] = name
    model.structure_changed.emit()
    return name


def _first_index(model):
    """Variables go before the geometry, after the other variables."""
    kids = model.root.children
    i = 0
    while i < len(kids) and kids[i].type in ("assign", "variables",
                                             "scad_use"):
        i += 1
    return i


def unlink(model, node, key):
    """Freeze *node*.key back to the number it stands for."""
    node.params[key] = round(_value(model, node, key), 6)
    model.node_changed.emit(node)
    return node.params[key]


def links(model):
    """{variable: [(node, key)]} for every size two or more nodes share
    through a bare variable."""
    out = {}
    for n in model.root.walk():
        for key, _l in size_params(n):
            v = n.params.get(key)
            if isinstance(v, str) and _IDENT.match(v.strip()):
                out.setdefault(v.strip(), []).append((n, key))
    return {k: v for k, v in out.items() if len(v) > 1}


# ------------------------------------------------------------------ UI
def open_dialog(win, a, b):
    """Right-click ▸ Make Sizes Equal… on two selected nodes."""
    from PyQt5.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                                 QFormLayout, QLineEdit, QMessageBox)
    from . import language
    dlg = QDialog(win)
    dlg.setWindowTitle(language.tr("Make sizes equal"))
    form = QFormLayout(dlg)
    combos = []
    for node in (a, b):
        c = QComboBox()
        for key, label in size_params(node):
            c.addItem("%s  (%s)" % (language.tr(label),
                                     node.params.get(key)), key)
        form.addRow(node.name, c)
        combos.append(c)
    name = QLineEdit()
    name.setPlaceholderText(language.tr("automatic"))
    form.addRow(language.tr("Variable name"), name)
    box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    box.accepted.connect(dlg.accept)
    box.rejected.connect(dlg.reject)
    form.addRow(box)
    if not combos[0].count() or not combos[1].count():
        QMessageBox.information(win, language.tr("Make sizes equal"),
                                language.tr("Both need a size parameter."))
        return None
    if dlg.exec_() != QDialog.Accepted:
        return None
    try:
        var = link(win.model, a, combos[0].currentData(), b,
                   combos[1].currentData(), name.text().strip() or None)
    except ValueError as exc:
        QMessageBox.warning(win, language.tr("Make sizes equal"), str(exc))
        return None
    win.statusBar().showMessage(language.tr(
        "Equal: both now read the variable %s — change it in the "
        "Variables tab.") % var, 8000)
    return var
