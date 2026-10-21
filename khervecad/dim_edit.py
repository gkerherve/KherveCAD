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
    if getattr(scene, "tool", SELECT) != SELECT:
        return False
    got = hit(view, pos)
    if got is None:
        return False
    rect, (node, kind, index) = got
    open_editor(view, rect, node, kind, index)
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
        if getattr(view, "_dim_editor", None) is not box:
            return
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
