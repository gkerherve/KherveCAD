# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Typing a dimension on the 3D view, and LINKING it by clicking another
(2026-11-10, the user, after SolidWorks' "= D1@Boss-Extrude1"): while a
value is being typed, a click on any other dimension — a sketch's Smart
Dimension or a feature's depth / angle (feature_dims) — puts that
dimension's VARIABLE into the box, so "w" or "w / 2" can be finished and
kept with Enter. A dimension that is still a plain number first becomes a
document variable (named after its feature or sketch and what it
measures, its value unchanged) that it is driven by, so both follow one
number — plain parametric OpenSCAD, as Make Sizes Equal does.

`open_editor(window, rect, text, commit, target)` is the one in-place box
both kinds use: Enter commits, Esc drops, and a focus loss commits only
when it was not a link click (the press that links takes the focus from
the box first)."""

import re

from . import sketch_constraints as sc

_IDENT = re.compile(r"^[A-Za-z_]\w*$")
#: a sketch dimension's kind in a variable's name
WORD = {"distance": "distance", "hdistance": "width", "vdistance": "height",
        "length": "length", "point_line": "distance", "radius": "radius",
        "diameter": "diameter", "angle": "angle", "arc_length": "arc"}


# --------------------------------------------------------------- editor
def open_editor(window, rect, text, commit, target):
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtWidgets import QLineEdit
    view = window.view3d
    old = getattr(view, "_dim3d_editor", None)
    if old is not None:
        view._dim3d_editor = None
        old.deleteLater()
    box = QLineEdit(text, view)
    box.setFixedWidth(max(90, int(rect.width()) + 30))
    box.move(int(rect.x()) - 8, int(rect.y()) - 3)
    box.setToolTip("Type a value, a calculation or a variable — or click "
                   "another dimension to link to it. Enter keeps it.")
    box.selectAll()
    box.show()
    box.setFocus()
    view._dim3d_editor = box
    view._dim3d_target = target
    state = {"linking": False}
    box._link_state = state

    def done():
        if getattr(view, "_dim3d_editor", None) is not box:
            return
        view._dim3d_editor = None
        view._dim3d_target = None
        typed = box.text().strip().replace(",", ".")
        box.deleteLater()
        view.update()
        if not typed:
            return
        try:
            commit(typed)
        except (ValueError, KeyError, IndexError) as exc:
            window.statusBar().showMessage(str(exc), 5000)
            view.flash("Dimension refused: %s" % exc, 8000)
        view.update()

    def drop():
        if getattr(view, "_dim3d_editor", None) is box:
            view._dim3d_editor = None
            view._dim3d_target = None
            box.deleteLater()
            view.update()

    def focus_left():
        # the focus went to the view for a click ON another dimension: a
        # link (press() fills the box) — anything else keeps the value
        from PyQt5.QtGui import QCursor
        from PyQt5.QtWidgets import QApplication
        if QApplication.mouseButtons() & Qt.LeftButton and \
                _target_at(window, view.mapFromGlobal(QCursor.pos())) \
                not in (None,):
            state["linking"] = True
            QTimer.singleShot(0, lambda: state.update(linking=False))
            return
        done()

    box.returnPressed.connect(done)
    box.editingFinished.connect(focus_left)
    box._done, box._drop = done, drop

    from PyQt5.QtCore import QObject

    class _Keys(QObject):
        def eventFilter(self, obj, event):
            from PyQt5.QtCore import QEvent
            if event.type() == QEvent.KeyPress and \
                    event.key() == Qt.Key_Escape:
                drop()
                return True
            return False
    box._keys = _Keys(box)
    box.installEventFilter(box._keys)
    view.update()                  # every feature's dimensions to click
    return box


# ------------------------------------------------------------- variables
def _free_name(model, base):
    from .equalize import _free_name as free
    return free(model, base)


def _slug(text):
    from .equalize import _slug as slug
    return slug(text)


def _new_variable(model, name, value):
    from .model import CadNode
    from .equalize import _first_index
    var = CadNode("assign", name, dict(variable=name, value=round(value, 6)))
    model.root.add(var, _first_index(model))
    return name


def variable_of(window, target):
    """The variable a dimension *target* stands for — made, and the
    dimension driven by it, when it was a plain number."""
    model = window.model
    from .anchors import doc_env
    from . import expr
    from .model import name_tag
    env = doc_env(model)
    kind = target[0]
    if kind == "feature":
        _k, node, key = target
        raw = node.params.get(key)
        if isinstance(raw, str) and _IDENT.match(raw.strip()):
            return raw.strip()
        value = float(expr.resolve(raw, env, 0.0))
        word = {"height": "depth", "height2": "depth2",
                "angle": "angle"}.get(key, key)
        name = _free_name(model, _slug("%s_%s" % (
            name_tag(node.name) or node.name, word)))
        _new_variable(model, name, value)
        model.set_param(node, key, name)
        return name
    _k, cont, index = target
    row = sc.rows(cont)[index]
    raw = row.get("value")
    if isinstance(raw, str) and _IDENT.match(raw.strip()):
        return raw.strip()
    value = float(sc.value_of(row, env))
    name = _free_name(model, _slug("%s_%s" % (
        name_tag(cont.name) or cont.name, WORD.get(row["kind"],
                                                    row["kind"]))))
    _new_variable(model, name, value)
    sc.set_value(model, cont, index, name)
    return name


# ----------------------------------------------------------- the click
def _target_at(window, pos):
    from . import feature_dims
    got = feature_dims.hit(window, pos)
    if got is not None:
        return ("feature", got[1], got[2])
    for hit in getattr(window, "_dims3d_hits", []):
        rect, cont, index = hit[:3]
        if rect.adjusted(-3, -3, 3, 3).contains(pos.x(), pos.y()):
            return ("sketch", cont, index)
    return None


def _same(a, b):
    return a is not None and b is not None and a[0] == b[0] and \
        a[1] is b[1] and a[2] == b[2]


def press(window, pos):
    """While a dimension is typed: a click on ANOTHER one links to it."""
    view = window.view3d
    box = getattr(view, "_dim3d_editor", None)
    if box is None:
        return False
    target = _target_at(window, pos)
    if target is None or _same(target, getattr(view, "_dim3d_target",
                                               None)):
        return False
    box._link_state["linking"] = True
    try:
        name = variable_of(window, target)
    except Exception as exc:              # never lose the box
        window.statusBar().showMessage("Could not link: %s" % exc, 6000)
        box.setFocus()
        return True
    if getattr(view, "_dim3d_editor", None) is not box:
        return True
    box.setText(name)
    box.setFocus()
    box.end(False)
    window.statusBar().showMessage(
        "Linked to %s — Enter keeps it (you may write %s / 2, %s + 5…)."
        % (name, name, name), 8000)
    window._dim_link_swallow = True
    return True


def release(window, pos):
    if getattr(window, "_dim_link_swallow", False):
        window._dim_link_swallow = False
        return True
    return False


def link(window, target, source):
    """Make *target* follow *source* (both ("feature", node, key) or
    ("sketch", container, index)): the MCP and test path."""
    name = variable_of(window, source)
    if target[0] == "feature":
        window.model.set_param(target[1], target[2], name)
    else:
        sc.set_value(window.model, target[1], target[2], name)
    return name
