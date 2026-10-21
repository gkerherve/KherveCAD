"""The sketch's CONSTRAIN panel (2026-10-21): click tools in the 2D view
that add `sketch_constraints` rows, the glyphs that show them on the
sketch, the Constraints window and the MCP `sketch_constraint` body.

A constraint tool is one of the scene's tools ("con_<kind>"): each click
picks the nearest point (ends, corners, centres, vertices) or, failing
that, the nearest curve (a line, an edge, a circle) of a shape; once it
has what the kind needs, the constraint is added (a dimension asks its
value, the measured one offered). Every pick must sit in the same
container — constraints belong to the container holding the shapes.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import sketch_constraints as sc

PREFIX = "con_"
#: (kind, mdi glyph) in the panel's order: Fusion's CONSTRAINTS first,
#: then the driven dimensions
TOOLS = [
    ("coincident", "mdi.vector-point"),
    ("horizontal", "mdi.arrow-left-right"),
    ("vertical", "mdi.arrow-up-down"),
    ("equal", "mdi.equal"),
    ("parallel", "mdi.format-align-justify"),
    ("perpendicular", "mdi.vector-line"),
    ("tangent", "mdi.circle-half-full"),
    ("concentric", "mdi.circle-double"),
    ("collinear", "mdi.dots-horizontal"),
    ("midpoint", "mdi.format-horizontal-align-center"),
    ("symmetric", "mdi.mirror"),
    ("fix", "mdi.lock-outline"),
    ("point_on", "mdi.vector-circle-variant"),
    ("distance", "mdi.ruler"),
    ("hdistance", "mdi.arrow-expand-horizontal"),
    ("vdistance", "mdi.arrow-expand-vertical"),
    ("length", "mdi.ruler-square"),
    ("point_line", "mdi.format-line-spacing"),
    ("radius", "mdi.radius-outline"),
    ("diameter", "mdi.diameter-outline"),
    ("angle", "mdi.angle-acute"),
]
#: glyph letters drawn on the sketch per kind
MARK = {"coincident": "●", "horizontal": "H", "vertical": "V",
        "parallel": "∥", "perpendicular": "⊥", "tangent": "T",
        "equal": "=", "concentric": "◎", "collinear": "—",
        "midpoint": "M", "symmetric": "⇹", "fix": "🔒", "point_on": "∘"}
PICK_PX = 10.0
#: what each constraint does (the tooltips' "what")
WHAT = {
    "coincident": "Makes two points one: line ends meet, a corner lands "
                  "on a centre.",
    "horizontal": "Makes a line level — or two points level with each "
                  "other.",
    "vertical": "Makes a line upright — or two points one above the "
                "other.",
    "parallel": "Keeps two lines (or edges) parallel.",
    "perpendicular": "Keeps two lines at a right angle.",
    "tangent": "Makes a line or circle just touch a circle.",
    "equal": "Makes two things the SAME SIZE: two lines (or rectangle / "
             "polygon edges) the same length, two circles the same "
             "radius. Change one and the other follows.",
    "concentric": "Puts two circles on one centre.",
    "collinear": "Puts two lines on one straight line.",
    "midpoint": "Puts a point at the middle of a line.",
    "symmetric": "Mirrors two points about a line.",
    "fix": "Locks a point where it is now.",
    "point_on": "Keeps a point on a line or circle.",
    "distance": "Drives the distance between two points.",
    "hdistance": "Drives the horizontal distance between two points.",
    "vdistance": "Drives the vertical distance between two points.",
    "length": "Drives a line's length.",
    "point_line": "Drives the distance from a point to a line.",
    "radius": "Drives a circle's radius.",
    "diameter": "Drives a circle's diameter.",
    "angle": "Drives the angle between two lines.",
}
TIPS = {
    "con_auto": ("Auto constrain",
                 "Adds the constraints the sketch already looks like it "
                 "has: nearly level / upright lines, line ends that meet.",
                 ["Select a shape of the sketch (or nothing for the "
                  "whole scope).", "Click Auto constrain."],
                 "The status bar says how many degrees of freedom are "
                 "left."),
    "con_list": ("Constraints",
                 "Lists the sketch's constraints and dimensions, says "
                 "whether it is fully constrained, and edits or deletes "
                 "them.",
                 ["Select a shape of the sketch.", "Click Constraints…"],
                 None),
}
for _kind, _what in WHAT.items():
    TIPS[PREFIX + _kind] = (
        sc.KINDS[_kind][0], _what,
        ["Pick the tool, then click: " + ", then ".join(
            "a " + w for w in sc.KINDS[_kind][1]) + ".",
         "Points (ends, corners, centres) win over curves under the "
         "cursor; right-click or Esc starts again."]
        + (["Type the value — a number or an expression of the "
            "variables (w / 2)."] if sc.KINDS[_kind][2] else []),
        "Drag a shape afterwards and the rest follows the constraints.")


def tool_of(kind):
    return PREFIX + kind


def handles(tool):
    return isinstance(tool, str) and tool.startswith(PREFIX) \
        and tool[len(PREFIX):] in sc.KINDS


def prompt(kind, n):
    picks = sc.KINDS[kind][1]
    if kind in sc.TWO_POINT:
        return "%s: click a line, or two points." % sc.KINDS[kind][0]
    return "%s: click %s %d of %d." % (sc.KINDS[kind][0],
                                       "a " + picks[min(n, len(picks) - 1)],
                                       n + 1, len(picks))


# -------------------------------------------------------------- picking
def _shape_items(scene):
    from .view2d import ShapeItem
    return [it for it in scene.items()
            if isinstance(it, ShapeItem)
            and getattr(it, "node", None) is not None
            and it.node.type in sc.SHAPES and it.node.parent is not None]


def _entities(node):
    """(name, kind) of every entity of a shape."""
    t = node.type
    if t == "line":
        return [("p1", "point"), ("p2", "point"), ("l", "line")]
    if t == "rect":
        return [("v%d" % i, "point") for i in range(4)] + [("c", "point")] \
            + [("e%d" % i, "line") for i in range(4)]
    if t == "circle":
        return [("c", "point"), ("o", "circle")]
    n = len(node.params.get("points") or [])
    return [("v%d" % i, "point") for i in range(n)] + \
        [("e%d" % i, "line") for i in range(n)]


def _seg_dist(p, a, b):
    ab = (b[0] - a[0], b[1] - a[1])
    L = ab[0] ** 2 + ab[1] ** 2 or 1e-12
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1])
                     / L))
    return math.hypot(p[0] - a[0] - t * ab[0], p[1] - a[1] - t * ab[1])


def pick(scene, scene_pos, want=None):
    """The (node, entity name, kind) nearest *scene_pos* — points before
    curves — of the kinds *want* allows, or None."""
    from .polygon_draw import px_to_scene
    from .view2d_edit import in_frame_coords
    tol = px_to_scene(scene, PICK_PX)
    allowed = {"curve": ("line", "circle")}.get(want, (want,)) \
        if want else ("point", "line", "circle")
    best = None
    for item in _shape_items(scene):
        q = in_frame_coords(item, scene_pos)
        p = (q.x(), q.y())
        node = item.node
        for name, kind in _entities(node):
            if kind not in allowed:
                continue
            try:
                if kind == "point":
                    pt = sc._point(node, name, {})
                    d = math.hypot(p[0] - pt[0], p[1] - pt[1])
                    rank = 0
                elif kind == "line":
                    a, b = sc._line(node, name, {})
                    d, rank = _seg_dist(p, a, b), 1
                else:
                    c, r = sc._circle(node, name, {})
                    d = abs(math.hypot(p[0] - c[0], p[1] - c[1]) - r)
                    rank = 1
            except (KeyError, ValueError, IndexError):
                continue
            if d <= tol and (best is None or (rank, d) < best[0]):
                best = ((rank, d), (node, name, kind))
    return best[1] if best else None


def _state(scene):
    if not hasattr(scene, "_con_picks"):
        scene._con_picks = []
    return scene._con_picks


def drop(scene):
    scene._con_picks = []
    scene.update()


def _ask_value(scene, kind, measured):
    hook = getattr(scene, "ask_value", None)
    if hook is not None:
        return hook(kind, measured)
    from PyQt5.QtWidgets import QInputDialog
    from . import language
    views = scene.views()
    unit = "°" if kind == "angle" else "mm"
    text, ok = QInputDialog.getText(
        views[0] if views else None, language.tr(sc.KINDS[kind][0]),
        language.tr("Value (%s) — a number or an expression:") % unit,
        text="%g" % round(measured, 4))
    return text.strip() if ok and text.strip() else None


def _value(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return text                 # an expression of the variables


def press(scene, event):
    from PyQt5.QtCore import Qt
    event.accept()
    if event.button() == Qt.RightButton:
        drop(scene)
        return
    if event.button() != Qt.LeftButton:
        return
    kind = scene.tool[len(PREFIX):]
    picks = _state(scene)
    wants = sc.KINDS[kind][1]
    if kind in sc.TWO_POINT:
        want = None if not picks else "point"
    else:
        want = wants[len(picks)]
    hit = pick(scene, event.scenePos(), want)
    if hit is None or (kind in sc.TWO_POINT and not picks
                       and hit[2] == "circle"):
        scene.status.emit(prompt(kind, len(picks)))
        return
    node, name, k = hit
    if picks and node.parent is not picks[0][0].parent:
        scene.status.emit("Constraints join shapes of one group: pick a "
                          "shape beside the first.")
        return
    picks.append(hit)
    done = len(picks) == len(wants) or \
        (kind in sc.TWO_POINT and k == "line" and len(picks) == 1)
    if not done:
        scene.status.emit(prompt(kind, len(picks)))
        scene.update()
        return
    finish(scene, kind)


def finish(scene, kind):
    picks = list(_state(scene))
    drop(scene)
    container = picks[0][0].parent
    refs = [sc.ref_of(container, node, name) for node, name, _ in picks]
    value = None
    if sc.KINDS[kind][2]:
        text = _ask_value(scene, kind, sc.measure(container, kind, refs))
        if text is None:
            return None
        value = _value(text)
    try:
        report = sc.add(scene.model, container, kind, refs, value)
    except ValueError as exc:
        scene.status.emit(str(exc))
        return None
    scene.status.emit("%s added — %s" % (sc.KINDS[kind][0],
                                         sc.status_text(report)))
    return report


def key(scene, event):
    from PyQt5.QtCore import Qt
    if event.key() == Qt.Key_Escape and _state(scene):
        drop(scene)
        return True
    return False


# --------------------------------------------------------------- glyphs
def paint(view, painter):
    """The constraints of every container on the sketch: a letter at
    each constrained entity, a dimension's value beside it; picks in
    progress ringed."""
    from PyQt5.QtCore import QPointF, Qt
    from PyQt5.QtGui import QColor, QFont, QPen
    scene = view.scene()
    model = getattr(scene, "model", None)
    if model is None:
        return
    items = {it.node.id: it for it in _shape_items(scene)}

    def at(node, name):
        item = items.get(node.id)
        if item is None:
            return None
        k = sc.kind_of(node, name)
        if k == "point":
            p = sc._point(node, name, {})
        elif k == "line":
            a, b = sc._line(node, name, {})
            p = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        else:
            c, r = sc._circle(node, name, {})
            p = (c[0] + r * 0.707, c[1] + r * 0.707)
        frame = item.parentItem()
        q = QPointF(*p)
        if frame is not None:
            q = frame.mapToScene(q)
        return view.mapFromScene(q)

    painter.save()
    painter.resetTransform()
    font = QFont(painter.font())
    font.setPointSize(8)
    font.setBold(True)
    painter.setFont(font)
    ink = QColor("#c75b12")
    painter.setPen(QPen(ink, 1.2))
    for cont in sc.containers(model):
        for row in sc.rows(cont):
            spots = []
            try:
                for ref in row["refs"]:
                    node, name = sc.entity(cont, ref)
                    spot = at(node, name)
                    if spot is not None:
                        spots.append(spot)
            except (KeyError, ValueError, IndexError):
                continue
            if not spots:
                continue
            if "value" in row:
                x = sum(s.x() for s in spots) / len(spots)
                y = sum(s.y() for s in spots) / len(spots)
                unit = "°" if row["kind"] == "angle" else ""
                prefix = {"radius": "R", "diameter": "Ø"}.get(row["kind"],
                                                             "")
                painter.drawText(QPointF(x + 6, y - 6), "%s%s%s" % (
                    prefix, row["value"], unit))
            else:
                for s in spots:
                    painter.drawText(QPointF(s.x() + 5, s.y() - 5),
                                     MARK.get(row["kind"], "?"))
    painter.setPen(QPen(QColor("#2176c7"), 2))
    painter.setBrush(Qt.NoBrush)
    for node, name, _ in getattr(scene, "_con_picks", []):
        spot = at(node, name)
        if spot is not None:
            painter.drawEllipse(spot, 6, 6)
    painter.restore()


# ---------------------------------------------------- window and panel
def container_for(win):
    """Where the panel's commands act: the parent of a selected shape,
    a selected container, else the scope's root."""
    sel = [win.model.find(i) for i in getattr(win, "_selected_ids", ())]
    sel = [n for n in sel if n is not None]
    for n in sel:
        if n.type in sc.SHAPES and n.parent is not None:
            return n.parent
        if n.params.get(sc.KEY):
            return n
    iso = win.builder.isolated_component()
    return iso if iso is not None else win.model.root


def auto(win):
    cont = container_for(win)
    n = sc.auto_constrain(win.model, cont)
    report = sc.solve(cont, write=False)
    win.statusBar().showMessage(
        "Auto constrain: %d constraint%s added — %s" % (
            n, "" if n == 1 else "s", sc.status_text(report)), 8000)
    return n


def open_window(win):
    from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QLabel,
                                 QListWidget, QPushButton, QVBoxLayout,
                                 QInputDialog, QMessageBox)
    from . import language
    dlg = getattr(win, "_constraints_window", None)
    if dlg is None:
        dlg = QDialog(win)
        dlg.setWindowTitle(language.tr("Sketch constraints"))
        lay = QVBoxLayout(dlg)
        dlg.status = QLabel()
        dlg.status.setWordWrap(True)
        dlg.list = QListWidget()
        lay.addWidget(dlg.status)
        lay.addWidget(dlg.list)
        row = QHBoxLayout()
        lay.addLayout(row)
        buttons = {}
        for key, text in (("value", "Edit value…"), ("delete", "Delete"),
                          ("auto", "Auto constrain"),
                          ("close", "Close")):
            b = QPushButton(language.tr(text))
            row.addWidget(b)
            buttons[key] = b

        def fill():
            cont = container_for(win)
            dlg.container = cont
            dlg.list.clear()
            for r in sc.rows(cont):
                dlg.list.addItem(sc.describe(cont, r))
            dlg.status.setText(language.tr(
                "%s — %d constraint(s). %s") % (
                cont.name, len(sc.rows(cont)),
                sc.status_text(sc.solve(cont, write=False))))

        def delete():
            i = dlg.list.currentRow()
            if i >= 0:
                sc.remove(win.model, dlg.container, i)
                fill()

        def edit():
            i = dlg.list.currentRow()
            rs = sc.rows(dlg.container)
            if i < 0 or "value" not in rs[i]:
                return
            text, ok = QInputDialog.getText(
                dlg, language.tr("Value"), language.tr("New value:"),
                text=str(rs[i]["value"]))
            if ok and text.strip():
                try:
                    sc.set_value(win.model, dlg.container, i,
                                 _value(text.strip()))
                except ValueError as exc:
                    QMessageBox.warning(dlg, language.tr("Constraints"),
                                        str(exc))
                fill()

        buttons["value"].clicked.connect(edit)
        buttons["delete"].clicked.connect(delete)
        buttons["auto"].clicked.connect(lambda: (auto(win), fill()))
        buttons["close"].clicked.connect(dlg.close)
        dlg.fill = fill
        win._constraints_window = dlg
    dlg.fill()
    dlg.show()
    dlg.raise_()
    return dlg


def panel_actions(win):
    """The CONSTRAIN panel: Auto constrain, the Constraints window, then
    one checkable tool per kind (in the window's tool group)."""
    acts = getattr(win, "_constrain_actions", None)
    if acts is not None:
        return acts
    from PyQt5.QtWidgets import QAction
    from . import icons, language, toolbars, tooltips
    tooltips.TIPS.update(TIPS)
    acts = []
    for key, glyph, text, slot in (
            ("con_auto", "mdi.auto-fix", "Auto constrain",
             lambda: auto(win)),
            ("con_list", "mdi.format-list-checks", "Constraints…",
             lambda: open_window(win))):
        act = QAction(icons.icon(glyph, icons.family_color("draw")),
                      language.tr(text), win)
        act.setData(key)
        toolbars.remember_glyph(act, glyph, "draw")
        tooltips.apply(act, key)
        act.triggered.connect(lambda _=False, f=slot: f())
        acts.append(act)
    for kind, glyph in TOOLS:
        tool = tool_of(kind)
        act = QAction(icons.icon(glyph, icons.family_color("draw")),
                      language.tr(sc.KINDS[kind][0]), win)
        act.setData(tool)
        act.setCheckable(True)
        toolbars.remember_glyph(act, glyph, "draw")
        tooltips.apply(act, tool)
        act.triggered.connect(lambda _=False, t=tool: win._set_tool(t))
        win._tool_group.addAction(act)
        acts.append(act)
    # the constraints first (what the panel shows), Auto / list after
    acts = acts[2:] + acts[:2]
    win._constrain_actions = acts
    return acts


# ------------------------------------------------------------------ MCP
def run_mcp(win, params):
    """MCP `sketch_constraint`: list / add / remove / set_value / auto /
    solve on a container (node_id; default the scope's root)."""
    model = win.model
    nid = params.get("node_id")
    cont = model.find(int(nid)) if nid is not None else None
    if nid is not None and cont is None:
        raise ValueError("No node %s." % nid)
    if cont is None:
        iso = win.builder.isolated_component()
        cont = iso if iso is not None else model.root
    action = params.get("action", "list")
    out = {"node_id": cont.id}
    if action == "add":
        report = sc.add(model, cont, params["kind"], params["refs"],
                        params.get("value"))
        out["status"] = sc.status_text(report)
    elif action == "remove":
        sc.remove(model, cont, int(params["index"]))
    elif action == "set_value":
        sc.set_value(model, cont, int(params["index"]), params["value"])
    elif action == "auto":
        out["added"] = sc.auto_constrain(model, cont)
    elif action != "list" and action != "solve":
        raise ValueError("Unknown action %r." % action)
    report = sc.solve(cont, write=False)
    out.update(
        status=sc.status_text(report), dof=report.get("dof"),
        ok=report.get("ok"),
        constraints=[dict(index=i, text=sc.describe(cont, r), **r)
                     for i, r in enumerate(sc.rows(cont))],
        shapes=[dict(index=i, id=n.id, type=n.type, name=n.name,
                     entities=[e for e, _ in _entities(n)])
                for i, n in enumerate(cont.children)
                if n.type in sc.SHAPES])
    return out
