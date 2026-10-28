"""Type a size by clicking its dimension in the 2D view (2026-10-21, the
user: "click on the 5 millimetres and change it").

Show Dimensions labels every shape (view2d `_draw_auto_dims`); each
label it draws is remembered with what it measures (`_dim_hits`: chip
rect + (node, kind, index)). A click on one opens a box over it with the
value; Enter applies:

- rectangle width / height and circle diameter — the shape's own params;
- a line's length — its second end moves along the line;
- a polygon side — a driving Length constraint on that side (SolidWorks'
  smart dimension), the solver moving the drawing as little as it can.

`apply` is Qt-free.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math


def _num(v, default=0.0):
    from .expr import resolve
    try:
        return float(resolve(v, {}, default))
    except (TypeError, ValueError):
        return default


def current(node, kind, index):
    """The value a dimension label shows."""
    if kind == "constraint":                  # a sketch's own dimension
        from . import sketch_constraints as sc
        return _num(sc.rows(node)[index].get("value"))
    p = node.params
    if kind == "width":
        return _num(p.get("width"))
    if kind == "height":
        return _num(p.get("height"))
    if kind == "diameter":
        return 2 * _num(p.get("radius"))
    if kind == "length":
        return math.hypot(_num(p.get("x2")) - _num(p.get("x1")),
                          _num(p.get("y2")) - _num(p.get("y1")))
    if kind == "edge":
        pts = p.get("points") or []
        a, b = pts[index], pts[(index + 1) % len(pts)]
        return math.hypot(_num(b[0]) - _num(a[0]), _num(b[1]) - _num(a[1]))
    raise KeyError(kind)


def apply(model, node, kind, index, value):
    """Set the size; raises ValueError for a value it cannot take."""
    value = float(value)
    if kind == "constraint":
        from . import sketch_constraints as sc
        row = sc.rows(node)[index]
        if row["kind"] != "angle" and value <= 0:
            raise ValueError("A size must be more than zero.")
        sc.set_value(model, node, index, value)
        return
    if value <= 0:
        raise ValueError("A size must be more than zero.")
    if kind in ("width", "height"):
        model.set_param(node, kind, value)
    elif kind == "diameter":
        model.set_param(node, "radius", value / 2.0)
    elif kind == "length":
        x1, y1 = _num(node.params.get("x1")), _num(node.params.get("y1"))
        x2, y2 = _num(node.params.get("x2")), _num(node.params.get("y2"))
        d = math.hypot(x2 - x1, y2 - y1) or 1.0
        node.params["x2"] = round(x1 + (x2 - x1) / d * value, 6)
        model.set_param(node, "y2", round(y1 + (y2 - y1) / d * value, 6))
    elif kind == "edge":
        from . import sketch_constraints as sc
        parent = node.parent
        ref = sc.ref_of(parent, node, "e%d" % index)
        for i, row in enumerate(sc.rows(parent)):
            if row["kind"] == "length" and row["refs"] == [ref]:
                sc.set_value(model, parent, i, value)
                break
        else:
            sc.add(model, parent, "length", [ref], value)
    else:
        raise KeyError(kind)


# =================================================================== Qt

def hit(view, pos):
    for rect, ctx in getattr(view, "_dim_hits", []) or []:
        if rect.contains(pos.x(), pos.y()) and ctx and ctx[0] is not None:
            return rect, ctx
    return None


def press(view, pos):
    """A click on a dimension label: type its value. True when taken."""
    from .view2d import SELECT
    scene = view.scene()
    # with Select, and with Smart Dimension too (SolidWorks: a dimension
    # is dragged or retyped while the tool is still on)
    if getattr(scene, "tool", SELECT) not in (SELECT, "con_dimension"):
        return False
    got = hit(view, pos)
    if got is None:
        return False
    rect, (node, kind, index) = got
    if kind == "constraint":
        view._dim_selected = (node, index)      # Delete removes it
        # a sketch dimension: a drag moves it out of the way, a click
        # without moving types its value (release). Lengths slide their
        # dimension line; Ø, R and angles move their value
        from . import sketch_constraints as sc
        try:
            was = list(sc.rows(node)[index].get("label_offset") or (0, 0))
        except IndexError:
            was = [0, 0]
        view._dim_drag = {"rect": rect, "ctx": (node, kind, index),
                          "start": pos, "moved": False, "was": was,
                          "linear": _linear(node, index)}
        return True
    open_editor(view, rect, node, kind, index)
    return True


DRAG_PX = 4


def _linear(cont, index):
    from . import sketch_constraints as sc
    from .sketch_constrain_ui import LINEAR
    try:
        return sc.rows(cont)[index]["kind"] in LINEAR
    except (IndexError, KeyError):
        return False


def scale(view):
    """Pixels per model unit in the sketch view."""
    return abs(view.transform().m11()) or 1.0


def move(view, pos):
    """Drag a sketch dimension: its line follows the mouse, square to
    what it measures (`row["offset"]`, model units). True when taken."""
    drag = getattr(view, "_dim_drag", None)
    if drag is None:
        return False
    if not drag["moved"] and math.hypot(
            pos.x() - drag["start"].x(),
            pos.y() - drag["start"].y()) < DRAG_PX:
        return True
    drag["moved"] = True
    from . import sketch_constraints as sc
    from .sketch_constrain_ui import _shape_items, linear_ends
    cont, _kind, index = drag["ctx"]
    row = sc.rows(cont)[index]
    if not drag["linear"]:
        k = scale(view)
        row["label_offset"] = [
            round(drag["was"][0] + (pos.x() - drag["start"].x()) / k, 3),
            round(drag["was"][1] + (pos.y() - drag["start"].y()) / k, 3)]
        view.viewport().update()
        return True
    items = {it.node.id: it for it in _shape_items(view.scene())}
    try:
        pa, pb = linear_ends(view, items, cont, row)
    except (KeyError, ValueError, IndexError, TypeError):
        return True
    vx, vy = pb.x() - pa.x(), pb.y() - pa.y()
    plen = math.hypot(vx, vy) or 1.0
    nx, ny = -vy / plen, vx / plen
    off = (pos.x() - pa.x()) * nx + (pos.y() - pa.y()) * ny - 12
    row["offset"] = round(off / scale(view), 3)
    view.viewport().update()
    return True


def release(view, pos):
    """End a drag (one undo step), or a click: type the value."""
    drag = getattr(view, "_dim_drag", None)
    if drag is None:
        return False
    view._dim_drag = None
    node, kind, index = drag["ctx"]
    if drag["moved"]:
        from . import sketch_constraints as sc
        rs = sc.rows(node)
        node.params[sc.KEY] = rs
        view.scene().model.node_changed.emit(node)
    else:
        open_editor(view, drag["rect"], node, kind, index)
    return True


def open_editor(view, rect, node, kind, index):
    from PyQt5.QtWidgets import QLineEdit
    old = getattr(view, "_dim_editor", None)
    if old is not None:
        old.deleteLater()
    box = QLineEdit("%g" % round(current(node, kind, index), 4),
                    view.viewport())
    box.setFixedWidth(max(64, int(rect.width()) + 16))
    box.move(int(rect.x()) - 6, int(rect.y()) - 2)
    box.selectAll()
    view._dim_editor = box
    model = scene_model = view.scene().model
    del scene_model

    def done():
        from PyQt5 import sip
        if sip.isdeleted(view) or sip.isdeleted(box) or \
                getattr(view, "_dim_editor", None) is not box:
            return              # the view went (closed while typing)
        view._dim_editor = None
        text = box.text().strip().replace(",", ".")
        box.deleteLater()
        try:
            apply(model, node, kind, index, float(text))
        except (ValueError, KeyError, IndexError) as exc:
            win = view.window()
            if hasattr(win, "statusBar"):
                win.statusBar().showMessage(str(exc), 5000)
        view.viewport().update()
    box.returnPressed.connect(done)
    box.editingFinished.connect(done)
    box.show()
    box.setFocus()
    return box


# ------------------------------------------------- removing dimensions
# (2026-10-28, the user: "how do you remove dimensions? all, or some?")
def selected(view):
    """(sketch, row index) of the dimension last clicked, still there."""
    got = getattr(view, "_dim_selected", None)
    if not got:
        return None
    from . import sketch_constraints as sc
    node, index = got
    try:
        row = sc.rows(node)[index]
    except (IndexError, TypeError):
        return None
    return (node, index) if "value" in row else None


def delete(view, node, index):
    from . import sketch_constraints as sc
    try:
        sc.remove(view.scene().model, node, index)
    except Exception as exc:                  # pragma: no cover
        view.scene().status.emit(str(exc))
        return
    view._dim_selected = None
    view.viewport().update()
    view.scene().status.emit("Dimension deleted (Ctrl+Z brings it back).")


def delete_all(view, node):
    """Every dimension of the sketch *node*; its relations stay."""
    from . import sketch_constraints as sc
    rows = sc.rows(node)
    keep = [r for r in rows if "value" not in r]
    gone = len(rows) - len(keep)
    if not gone:
        return 0
    model = view.scene().model
    if keep:
        model.set_param(node, sc.KEY, keep)
    else:
        node.params.pop(sc.KEY, None)
        model.node_changed.emit(node)
    view._dim_selected = None
    view.viewport().update()
    view.scene().status.emit(
        "%d dimension(s) of %s deleted (Ctrl+Z brings them back)."
        % (gone, node.name))
    return gone


def delete_key(view):
    """Delete / Backspace with a dimension selected. True when taken."""
    got = selected(view)
    if got is None:
        return False
    delete(view, *got)
    return True


def context_menu(view, pos, global_pos):
    """Right-click on a dimension's value: delete it, or all of the
    sketch's. True when a dimension was under the click."""
    got = hit(view, pos)
    if got is None or got[1][1] != "constraint":
        return False
    from PyQt5.QtWidgets import QMenu
    from . import language
    node, _kind, index = got[1]
    view._dim_selected = (node, index)
    view.viewport().update()
    menu = QMenu(view)
    one = menu.addAction(language.tr("Delete dimension"))
    every = menu.addAction(language.tr(
        "Delete all dimensions of this sketch"))
    hook = getattr(view, "menu_hook", None)
    chosen = hook(menu) if hook is not None else menu.exec_(global_pos)
    if chosen is one:
        delete(view, node, index)
    elif chosen is every:
        delete_all(view, node)
    return True
