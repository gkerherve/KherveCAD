"""The SHEET METAL ribbon tab (2026-10-27, the user: SolidCraft "has a
whole tab on the ribbon about it — introduce the same"): Base Flange,
Convert to Sheet Metal, Edge Flange, Fold, Hem, Path Flange, Perforate
and Flat Pattern (CREATE); Unfold, Refold and Sheet Metal Rules
(MODIFY); DXF and bend table (EXPORT). The edits are sheet_metal_ops;
this is the clicks and the forms.

An edge tool (Flange, Hem, Path Flange) first asks for a click on an
edge of the body in the 3D view — the nearest flangeable edge is taken
— then opens its form with that edge chosen (the drop-down lists every
edge if the click missed).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from pathlib import Path

from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog,
                             QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                             QFormLayout, QHBoxLayout, QLineEdit,
                             QListWidget, QPushButton,
                             QVBoxLayout)

from . import language, sheet_metal_ops as ops

#: key -> (label, glyph, panel, tip)
COMMANDS = {
    "sm_base": ("Base Flange/Tab", "mdi.square-outline", "create",
                "A flat sheet from the selected sketch shape (rectangle, "
                "polygon, circle), else 100 × 60 mm — the start of every "
                "sheet metal part."),
    "sm_arch": ("Arch Plate", "mdi.arch", "create",
                "A new base flange shaped like an arch: a half circle "
                "over straight sides — the back plate of a bracket."),
    "sm_convert": ("Convert to Sheet Metal", "mdi.cube-unfolded", "create",
                   "Turns the selected plate — a thin cube or an extruded "
                   "sketch shape — into a sheet metal body you can flange "
                   "and unfold."),
    "sm_flange": ("Edge Flange", "mdi.page-layout-header", "create",
                  "Click an edge of the sheet: a wall is bent off it "
                  "(height to the outside, angle, bend radius from the "
                  "rule)."),
    "sm_fold": ("Fold", "mdi.book-open-variant", "create",
                "Bends the sheet along a line across it (Sketched Bend); "
                "the outline stays the flat blank."),
    "sm_jog": ("Jog", "mdi.stairs", "create",
               "Two opposite bends from a sketched line: click two points "
               "for the line, the side that stays fixed, then the offset, "
               "angle and positions in its window."),
    "sm_hole": ("Hole", "mdi.circle-outline", "create",
                "Click on the sheet: a hole is cut there (diameter in its "
                "window); it follows its panel through a jog."),
    "sm_slot": ("Slot", "mdi.minus-circle-outline", "create",
                "Click the two ends of a slot's centre line, set the "
                "width: a slot is cut in the sheet."),
    "sm_hem": ("Hem", "mdi.wrap", "create",
               "Click an edge: it is folded right back over itself, the "
               "rule's hem gap inside."),
    "sm_path": ("Path Flange", "mdi.vector-polyline", "create",
                "Click an edge: a chain of flanges — one bend per corner "
                "(length, angle; length, angle…)."),
    "sm_contour": ("Contour Flange", "mdi.chart-line-variant", "create",
                   "A new body from an open profile in the XZ plane — a "
                   "channel, a Z or a hat section — with one bend at "
                   "every corner."),
    "sm_mirror": ("Mirror", "mdi.flip-horizontal", "create",
                  "Mirrors chosen features — an ear and its hole, tabs, "
                  "holes — about a plane across the sheet."),
    "sm_lpattern": ("Linear Pattern", "mdi.view-grid-plus", "create",
                    "Repeats chosen features (a gusset, a hole, a tab) "
                    "at a fixed step."),
    "sm_cpattern": ("Circular Pattern", "mdi.rotate-right", "create",
                    "Repeats chosen features (a tab and its jog) round a "
                    "centre."),
    "sm_gusset": ("Sheet Metal Gusset", "mdi.triangle-outline", "create",
                  "Click a bend: a stamped rib is added across its "
                  "inside corner — depths, width and draft in the form."),
    "sm_tabjog": ("Jog Tab", "mdi.stairs", "create",
               "Click two points across a tab: two bends step the part "
               "beyond that line out of the sheet's plane by the offset."),
    "sm_tab": ("Tab", "mdi.tab-plus", "create",
               "Merges a round-ended tab into the sheet — with a hole, "
               "and it may stand in an opening: give the centre of its "
               "round end, its width, length and direction."),
    "sm_corner": ("Break Corner", "mdi.vector-radius", "create",
                  "Click a corner of the sheet: it is rounded (or cut "
                  "off) by the size you give — in the folded part and "
                  "the flat pattern."),
    "sm_phole": ("Panel Hole", "mdi.circle-double", "create",
                "Click the sheet where the hole goes, give its diameter "
                "and position: a round hole through the sheet — in the "
                "folded part and the flat pattern."),
    "sm_perforate": ("Perforate", "mdi.dots-grid", "create",
                     "A staggered or square field of holes over the flat "
                     "sheet, clear of the edges and the bends — in the "
                     "flat pattern and the DXF."),
    "sm_flat": ("Create Flat Pattern", "mdi.layers-outline", "create",
                "A flat copy of the body beside it: the blank to cut, its "
                "bend lines in the bend table."),
    "sm_unfold": ("Unfold", "mdi.arrow-expand-horizontal", "modify",
                  "Shows the selected body flat (its flat pattern)."),
    "sm_refold": ("Refold", "mdi.arrow-collapse-horizontal", "modify",
                  "Folds an unfolded body back up."),
    "sm_rules": ("Sheet Metal Rules", "mdi.ruler-square", "modify",
                 "Named sets of thickness, bend radius, K-factor and hem "
                 "gap (document variables) — apply one to a body and it "
                 "follows the rule."),
    "sm_dxf": ("Export Flat Pattern as DXF", "mdi.file-export-outline",
               "export", "The flat pattern for the laser: CUT outlines and "
               "holes, BEND_UP / BEND_DOWN lines, ETCH notes, in mm."),
    "sm_bend_table": ("Export Bend Table", "mdi.table", "export",
                      "Every bend as CSV: direction, angle, radius, length, "
                      "allowance and the flat centre line."),
}
PANELS = {"create": "Create", "modify": "Modify", "export": "Export"}


def actions(win, panel=None):
    acts = getattr(win, "_sheet_actions", None)
    if acts is None:
        from PyQt5.QtWidgets import QAction
        from . import icons, toolbars, tooltips
        for key, (label, _g, _p, tip) in COMMANDS.items():
            tooltips.TIPS.setdefault(key, (label, tip, [], ""))
        acts = []
        for key, (label, glyph, _p, _tip) in COMMANDS.items():
            act = QAction(icons.icon(glyph, icons.family_color("extrude")),
                          language.tr(label), win)
            act.setData(key)
            toolbars.remember_glyph(act, glyph, "extrude")
            tooltips.apply(act, key)
            act.triggered.connect(lambda _=False, k=key: run(win, k))
            acts.append(act)
        win._sheet_actions = acts
    if panel is None:
        return acts
    return [a for a in acts if COMMANDS[a.data()][2] == panel]


def build_menu(win, menu):
    """Insert ▸ Sheet Metal: every command of the tab."""
    sub = menu.addMenu(language.tr("Sheet &Metal"))
    sub.setToolTipsVisible(True)
    last = None
    for act in actions(win):
        panel = COMMANDS[act.data()][2]
        if last is not None and panel != last:
            sub.addSeparator()
        sub.addAction(act)
        last = panel
    return sub


# ============================================================ helpers
def _say(win, text, ms=8000):
    win.statusBar().showMessage(text, ms)
    view = getattr(win, "view3d", None)
    if view is not None and hasattr(view, "flash"):
        try:
            view.flash(text)
        except Exception:
            pass


def _selected(win):
    try:
        return list(win.builder.active_tree().selected_nodes())
    except Exception:
        return []


def _body(win, quiet=False):
    """The body the command works on: the selection's, else the only
    one in view."""
    for node in _selected(win):
        body = ops.find_body(node)
        if body is not None:
            return body
    root = win._render_scope()[0]
    bodies = [n for n in root.walk() if n.type == ops.KIND]
    if len(bodies) == 1:
        return bodies[0]
    if not quiet:
        _say(win, language.tr(
            "Select a sheet metal body first (Base Flange makes one)."))
    return None


def _spin(value, lo, hi, decimals=2, suffix=" mm"):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setValue(value)
    s.setSuffix(suffix)
    s.setKeyboardTracking(False)
    return s


def _form(win, title):
    dlg = QDialog(win)
    dlg.setWindowTitle(language.tr(title))
    lay = QVBoxLayout(dlg)
    form = QFormLayout()
    lay.addLayout(form)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok |
                               QDialogButtonBox.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    lay.addWidget(buttons)
    return dlg, form


#: tests answer the forms: key -> dict of values (None = cancel)
ANSWERS = {}


def _ask(key, dlg, read):
    if key in ANSWERS:
        got = ANSWERS[key]
        return None if got is None else dict(read(), **got)
    if dlg.exec_() != QDialog.Accepted:
        return None
    return read()


def _edge_combo(win, body, chosen=None):
    combo = QComboBox()
    items = ops.edge_list(win.model, body)
    for item in items:
        combo.addItem(item["label"], (item["panel"], item["edge"]))
    if chosen is not None:
        for i, item in enumerate(items):
            if (item["panel"], item["edge"]) == chosen:
                combo.setCurrentIndex(i)
    return combo


def _pick_edge(win, body, then):
    """A click on an edge of the body in the 3D view, then *then*(edge)
    with (panel, edge) or None (missed / Esc)."""
    from . import bake, mesh
    view = win.view3d
    root = win._render_scope()[0]
    iso = root if root is not win.model.root else None
    env = bake._codegen_env(body)
    with win._isolated_frame(iso):
        tris = mesh.selected_world_tris(root, {body.id},
                                        fn=win.model.effective_fn())
        matrix = mesh.ancestor_matrix(body, env, stop=iso)
    if not tris or not hasattr(view, "start_pick"):
        then(None)
        return

    def picked(desc, _node=None):
        if desc is None:
            then(None)
            return
        item = ops.nearest_edge(win.model, body, desc.get("pos"), matrix)
        then((item["panel"], item["edge"]) if item else None)
    view.start_pick(picked, groups=[(body, tris)], banner=language.tr(
        "Click the edge to bend · Esc chooses from a list"),
        labeler=lambda desc, node: getattr(node, "name", ""))


# ============================================================ commands
def run(win, key):
    try:
        return HANDLERS[key](win)
    except ValueError as exc:
        _say(win, str(exc))
        return None


def base_flange(win):
    model = win.model
    shapes = [n for n in _selected(win) if ops.outline_of(n)]
    parent = win.builder.isolated_component()
    if shapes:
        from . import anchors
        shape = shapes[0]
        outline = ops.outline_of(shape, anchors.doc_env(model))
        holder = shape.parent
        body = ops.insert_base(model, outline, parent=holder)
        model.move_node(body, holder, holder.children.index(shape))
        model.set_param(shape, "visible", False) \
            if "visible" in shape.params else None
        shape.visible = False
        model.structure_changed.emit()
    else:
        body = ops.insert_base(model, parent=parent)
        if parent is None:
            win._geometry_created_in_main(body)
    win.builder.active_tree().select_nodes([body])
    _say(win, language.tr(
        "Base flange: now Edge Flange (click an edge), Fold or Hem — "
        "Unfold shows the blank."))
    return body


def arch_plate(win):
    dlg, form = _form(win, "Arch Plate")
    f = {"width": _spin(80.0, 1.0, 1e5), "below": _spin(60.0, 0.0, 1e5),
         "thickness": _spin(1.5, 0.05, 100.0, 2),
         "radius": _spin(1.5, 0.0, 1e3, 2),
         "k_factor": _spin(0.5, 0.0, 1.0, 2, "")}
    for name, label in (("width", "Width (the arch's diameter)"),
                        ("below", "Straight height below the arch centre"),
                        ("thickness", "Thickness"),
                        ("radius", "Bend radius"), ("k_factor", "K-factor")):
        form.addRow(language.tr(label), f[name])
    got = _ask("sm_arch_form", dlg, lambda: {k: w.value()
                                             for k, w in f.items()})
    if not got:
        return None
    parent = win.builder.isolated_component()
    body = ops.insert_base(win.model, ops.arch_outline(got["width"],
                                                       got["below"]),
                           parent=parent, name="Base-Flange1",
                           thickness=got["thickness"],
                           radius=got["radius"])
    win.model.set_param(body, "k_factor", got["k_factor"])
    if parent is None:
        win._geometry_created_in_main(body)
    win.builder.active_tree().select_nodes([body])
    _say(win, language.tr("Arch plate: now Edge Flange, Panel Hole, Tab…"))
    return body


def convert(win):
    nodes = _selected(win)
    if not nodes:
        raise ValueError(language.tr(
            "Select the plate to convert (a thin cube or an extruded "
            "sketch shape)."))
    body = ops.convert(win.model, nodes[0])
    win.builder.active_tree().select_nodes([body])
    _say(win, language.tr("Converted to sheet metal — {t} mm thick.")
         .format(t=body.params.get("thickness")))
    return body


def _flange_form(win, body, edge, title, kind):
    dlg, form = _form(win, title)
    combo = _edge_combo(win, body, edge)
    form.addRow(language.tr("Edge"), combo)
    fields = {}
    if kind == "flange":
        fields["height"] = _spin(20.0, 0.1, 1e5)
        fields["angle"] = _spin(90.0, -179.0, 179.0, 1, " °")
        fields["radius"] = _spin(0.0, 0.0, 1e4)
        fields["inset_a"] = _spin(0.0, 0.0, 1e5)
        fields["inset_b"] = _spin(0.0, 0.0, 1e5)
        labels = ("Height (to the outside)", "Angle", "Bend radius "
                  "(0 = the body's)", "Inset at the start",
                  "Inset at the end")
    elif kind == "hem":
        fields["length"] = _spin(8.0, 0.1, 1e5)
        labels = ("Length (to the fold)",)
    else:
        fields["path"] = QLineEdit("20, 90; 10, 90")
        labels = ("Segments: length, angle; …",)
    for (name, w), label in zip(fields.items(), labels):
        form.addRow(language.tr(label), w)
    ear = None
    if kind == "flange":
        ear = QCheckBox(language.tr("Edit profile: a round-ended ear"))
        form.addRow("", ear)
        for name, label, val in (("ear_center", "Ear centre along the "
                                  "edge", 20.0),
                                 ("ear_width", "Ear width", 15.0),
                                 ("ear_hole", "Ear hole diameter (0 = "
                                  "none)", 0.0)):
            fields[name] = _spin(val, 0.0, 1e5)
            form.addRow(language.tr(label), fields[name])
    flip = None
    if kind == "hem":
        flip = QCheckBox(language.tr("Fold under (down) instead of over"))
        form.addRow("", flip)

    def read():
        out = {"edge": combo.currentData()}
        for name, w in fields.items():
            out[name] = w.text() if isinstance(w, QLineEdit) else w.value()
        if flip is not None:
            out["flip"] = flip.isChecked()
        if ear is not None:
            out["ear"] = ear.isChecked()
        return out
    return dlg, read


def _edge_tool(win, kind, title):
    body = _body(win)
    if body is None:
        return None

    def go(edge):
        dlg, read = _flange_form(win, body, edge, title, kind)
        got = _ask("sm_" + kind, dlg, read)
        if not got or got.get("edge") is None:
            return
        panel, edge_ = got["edge"]
        try:
            if kind == "flange" and got.get("ear"):
                ops.add_ear(win.model, body, panel, edge_,
                            got["ear_center"], got["ear_width"],
                            got["height"], got["angle"], got["radius"],
                            got["ear_hole"])
            elif kind == "flange":
                ops.add_flange(win.model, body, panel, edge_, got["height"],
                               got["angle"], got["radius"], got["inset_a"],
                               got["inset_b"])
            elif kind == "hem":
                ops.add_hem(win.model, body, panel, edge_, got["length"],
                            got.get("flip", False))
            else:
                ops.path_flange(win.model, body, panel, edge_,
                                parse_path(got["path"]))
        except ValueError as exc:
            _say(win, str(exc))
            return
        report(win, body)
    if ("sm_" + kind) in ANSWERS:
        go(ANSWERS.get("sm_" + kind + "_edge"))
    else:
        _pick_edge(win, body, go)
    return body


def parse_path(text):
    """'20, 90; 10, -90' -> [(20, 90), (10, -90)]."""
    out = []
    for part in str(text).replace("\n", ";").split(";"):
        bits = [b for b in part.replace(" ", ",").split(",") if b.strip()]
        if not bits:
            continue
        length = float(bits[0])
        angle = float(bits[1]) if len(bits) > 1 else 90.0
        out.append((length, angle))
    if not out:
        raise ValueError(language.tr("Path Flange: give length, angle "
                                     "pairs"))
    return out


def report(win, body):
    d = ops.describe(win.model, body)
    if d["errors"]:
        _say(win, language.tr("Sheet metal: {error}").format(
            error=d["errors"][0]), 10000)
    else:
        _say(win, language.tr(
            "{name}: {bends} bends, flat blank {w:.1f} × {h:.1f} mm — "
            "Ctrl+Z to undo.").format(name=body.name, bends=d["bends"],
                                       w=d["flat_size"][0],
                                       h=d["flat_size"][1]))


def flange(win):
    return _edge_tool(win, "flange", "Edge Flange")


def hem(win):
    return _edge_tool(win, "hem", "Hem")


def path(win):
    return _edge_tool(win, "path", "Path Flange")


def fold(win):
    body = _body(win)
    if body is None:
        return None
    pts = [p for p in body.params.get("outline") or []]
    xs = [float(p[0]) for p in pts if not isinstance(p[0], str)] or [0, 100]
    ys = [float(p[1]) for p in pts if not isinstance(p[1], str)] or [0, 60]
    mx = (min(xs) + max(xs)) / 2
    dlg, form = _form(win, "Fold")
    f = {"x1": _spin(mx, -1e5, 1e5), "y1": _spin(min(ys) - 1, -1e5, 1e5),
         "x2": _spin(mx, -1e5, 1e5), "y2": _spin(max(ys) + 1, -1e5, 1e5),
         "angle": _spin(90.0, -179.0, 179.0, 1, " °"),
         "radius": _spin(0.0, 0.0, 1e4)}
    for name, label in (("x1", "Line from X"), ("y1", "Line from Y"),
                        ("x2", "Line to X"), ("y2", "Line to Y"),
                        ("angle", "Angle"),
                        ("radius", "Bend radius (0 = the body's)")):
        form.addRow(language.tr(label), f[name])
    got = _ask("sm_fold", dlg, lambda: {k: w.value() for k, w in f.items()})
    if not got:
        return None
    ops.add_fold(win.model, body, (got["x1"], got["y1"]),
                 (got["x2"], got["y2"]), got["angle"], got["radius"])
    report(win, body)
    return body


def contour(win):
    dlg, form = _form(win, "Contour Flange")
    text = QLineEdit("0, 30; 0, 0; 50, 0; 50, 30")
    width = _spin(60.0, 0.1, 1e5)
    form.addRow(language.tr("Profile points X, Z; …"), text)
    form.addRow(language.tr("Width"), width)
    got = _ask("sm_contour", dlg, lambda: {"points": text.text(),
                                            "width": width.value()})
    if not got:
        return None
    pts = []
    for part in str(got["points"]).split(";"):
        bits = [b for b in part.replace(" ", ",").split(",") if b.strip()]
        if len(bits) >= 2:
            pts.append((float(bits[0]), float(bits[1])))
    parent = win.builder.isolated_component()
    body = ops.insert_contour(win.model, pts, got["width"], parent=parent)
    if parent is None:
        win._geometry_created_in_main(body)
    report(win, body)
    return body


def _pick_point(win, body, then, banner="Click where the hole goes · "
                "Esc types its position"):
    """A click on a face of the body in the 3D view, then *then*(panel,
    u, v) in that panel's own frame (None = missed / Esc)."""
    from . import bake, mesh
    view = win.view3d
    root = win._render_scope()[0]
    iso = root if root is not win.model.root else None
    env = bake._codegen_env(body)
    with win._isolated_frame(iso):
        tris = mesh.selected_world_tris(root, {body.id},
                                        fn=win.model.effective_fn())
        matrix = mesh.ancestor_matrix(body, env, stop=iso)
    if not tris or not hasattr(view, "start_pick"):
        then(None)
        return

    def picked(desc, _node=None):
        if desc is None or not (desc.get("point") or desc.get("pos")):
            then(None)
            return
        try:
            then(ops.locate(win.model, body,
                            desc.get("point") or desc["pos"], matrix))
        except ValueError:
            then(None)
    view.start_pick(picked, groups=[(body, tris)], banner=language.tr(banner),
        labeler=lambda desc, node: getattr(node, "name", ""))


def panel_hole(win):
    body = _body(win)
    if body is None:
        return None

    def go(spot):
        panel, u, v = spot if spot else (0, 0.0, 0.0)
        dlg, form = _form(win, "Simple Hole")
        f = {"panel": _spin(panel, 0, 999, 0, ""),
             "u": _spin(u, -1e5, 1e5), "v": _spin(v, -1e5, 1e5),
             "diameter": _spin(6.5, 0.1, 1e4)}
        for name, label in (("panel", "Panel (0 = the base)"),
                            ("u", "Position U"), ("v", "Position V"),
                            ("diameter", "Hole diameter")):
            form.addRow(language.tr(label), f[name])
        got = _ask("sm_phole_form", dlg, lambda: {k: w.value()
                                            for k, w in f.items()})
        if not got:
            return
        try:
            ops.add_panel_hole(win.model, body, int(got["panel"]), got["u"],
                         got["v"], got["diameter"])
        except ValueError as exc:
            _say(win, str(exc))
            return
        report(win, body)
    if "sm_phole_spot" in ANSWERS:
        go(ANSWERS["sm_phole_spot"])
    else:
        _pick_point(win, body, go)
    return body


def _feature_list(win, body, form):
    """A multi-selection list of the body's copyable features."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QListWidgetItem
    from . import sheet_metal_patterns as pat
    lst = QListWidget()
    lst.setSelectionMode(QListWidget.MultiSelection)
    for feat in pat.features(win.model, body):
        item = QListWidgetItem(feat["label"])
        item.setData(Qt.UserRole, (feat["kind"], feat["index"]))
        lst.addItem(item)
    form.addRow(language.tr("Features"), lst)

    def chosen():
        return [i.data(Qt.UserRole) for i in lst.selectedItems()]
    return lst, chosen


def _pattern_tool(win, key, title, fields, apply):
    """Mirror / Linear / Circular Pattern: pick the features, the numbers,
    OK. *fields* = [(name, label, default, lo, hi, decimals)]."""
    body = _body(win)
    if body is None:
        return None
    dlg, form = _form(win, title)
    _lst, chosen = _feature_list(win, body, form)
    f = {}
    for name, label, default, lo, hi, dec in fields:
        f[name] = _spin(default, lo, hi, dec, "" if dec == 0 else " mm")
        form.addRow(language.tr(label), f[name])
    extra = {}
    if key == "sm_mirror":
        plane = QComboBox()
        plane.addItems([language.tr("Across X (the Right plane)"),
                        language.tr("Across Y (the Front plane)")])
        form.addRow(language.tr("Mirror plane"), plane)
        extra["plane"] = plane
    got = _ask(key + "_form", dlg, lambda: dict(
        {k: w.value() for k, w in f.items()}, features=chosen(),
        **{k: ("x", "y")[w.currentIndex()] for k, w in extra.items()}))
    if not got:
        return None
    if not got.get("features"):
        _say(win, language.tr("{t}: choose the features to repeat.")
             .format(t=title))
        return None
    try:
        apply(body, got)
    except ValueError as exc:
        _say(win, str(exc))
        return None
    report(win, body)
    return body


def mirror(win):
    from . import sheet_metal_patterns as pat
    return _pattern_tool(
        win, "sm_mirror", "Mirror", [("at", "Plane position", 0.0, -1e5,
                                      1e5, 2)],
        lambda body, g: pat.mirror(win.model, body,
                                   [tuple(i) for i in g["features"]],
                                   g.get("plane", "x"), g["at"]))


def linear_pattern(win):
    from . import sheet_metal_patterns as pat

    def go(body, g):
        for kind, index in g["features"]:
            pat.linear(win.model, body, kind, index, int(g["count"]),
                       g["dx"], g["dy"])
    return _pattern_tool(
        win, "sm_lpattern", "Linear Pattern",
        [("count", "Instances", 3, 2, 999, 0),
         ("dx", "Step U (a gusset: along its bend)", 30.0, -1e5, 1e5, 2),
         ("dy", "Step V", 0.0, -1e5, 1e5, 2)], go)


def circular_pattern(win):
    from . import sheet_metal_patterns as pat

    def go(body, g):
        for kind, index in g["features"]:
            pat.circular(win.model, body, kind, index, int(g["count"]),
                         (g["cx"], g["cy"]), g["total"])
    return _pattern_tool(
        win, "sm_cpattern", "Circular Pattern",
        [("count", "Instances", 4, 2, 999, 0),
         ("cx", "Centre U", 0.0, -1e5, 1e5, 2),
         ("cy", "Centre V", 0.0, -1e5, 1e5, 2),
         ("total", "Angle (360 = a full turn)", 360.0, -360.0, 360.0,
          1)], go)


def gusset(win):
    body = _body(win)
    if body is None:
        return None

    def go(bend, along):
        dlg, form = _form(win, "Sheet Metal Gusset")
        f = {"bend": _spin(bend, 1, 999, 0, ""),
             "offset": _spin(along, 0, 1e5), "d1": _spin(10.0, 0.1, 1e4),
             "d2": _spin(10.0, 0.1, 1e4), "width": _spin(7.5, 0.1, 1e4),
             "draft": _spin(20.0, 0.0, 80.0, 1, " °")}
        for name, label in (("bend", "Bend number (bend table)"),
                            ("offset", "Offset along the bend"),
                            ("d1", "Depth on the first face (d1)"),
                            ("d2", "Depth on the second face (d2)"),
                            ("width", "Width"), ("draft", "Side draft")):
            form.addRow(language.tr(label), f[name])
        got = _ask("sm_gusset_form", dlg, lambda: {k: w.value()
                                                   for k, w in f.items()})
        if not got:
            return
        try:
            ops.add_gusset(win.model, body, int(got["bend"]),
                           got["offset"], got["d1"], got["d2"],
                           got["width"], got["draft"])
        except ValueError as exc:
            _say(win, str(exc))
            return
        report(win, body)

    if "sm_gusset_spot" in ANSWERS:
        go(*ANSWERS["sm_gusset_spot"])
        return body
    from . import bake, mesh
    view = win.view3d
    root = win._render_scope()[0]
    iso = root if root is not win.model.root else None
    env = bake._codegen_env(body)
    with win._isolated_frame(iso):
        tris = mesh.selected_world_tris(root, {body.id},
                                        fn=win.model.effective_fn())
        matrix = mesh.ancestor_matrix(body, env, stop=iso)
    if not tris or not hasattr(view, "start_pick"):
        go(1, 0.0)
        return body

    def picked(desc, _node=None):
        if desc is None or not (desc.get("point") or desc.get("pos")):
            return
        try:
            bend, along = ops.nearest_bend(
                win.model, body, desc.get("point") or desc["pos"], matrix)
        except ValueError as exc:
            _say(win, str(exc))
            return
        go(bend, along)
    view.start_pick(picked, groups=[(body, tris)], banner=language.tr(
        "Click the bend to stiffen · Esc cancels"),
        labeler=lambda desc, node: getattr(node, "name", ""))
    return body


def tab_jog(win):
    body = _body(win)
    if body is None:
        return None

    def go(first, second):
        (panel, u1, v1), (panel2, u2, v2) = first, second
        dlg, form = _form(win, "Jog")
        f = {"panel": _spin(panel, 0, 999, 0, ""),
             "x1": _spin(u1, -1e5, 1e5), "y1": _spin(v1, -1e5, 1e5),
             "x2": _spin(u2, -1e5, 1e5), "y2": _spin(v2, -1e5, 1e5),
             "offset": _spin(10.0, 0.1, 1e4),
             "angle": _spin(90.0, -179.0, 179.0, 1, " °"),
             "radius": _spin(0.0, 0.0, 1e4)}
        for name, label in (("panel", "Panel (0 = the base)"),
                            ("x1", "Line from U"), ("y1", "Line from V"),
                            ("x2", "Line to U"), ("y2", "Line to V"),
                            ("offset", "Jog offset"),
                            ("angle", "Jog angle (negative = down)"),
                            ("radius", "Bend radius (0 = the body's)")):
            form.addRow(language.tr(label), f[name])
        stretch = QCheckBox(language.tr(
            "Stretch the line across the tab it crosses"))
        stretch.setChecked(True)
        form.addRow("", stretch)
        got = _ask("sm_tabjog_form", dlg, lambda: dict(
            {k: w.value() for k, w in f.items()},
            extend=stretch.isChecked()))
        if not got:
            return
        try:
            ops.add_tab_jog(win.model, body, int(got["panel"]),
                        (got["x1"], got["y1"]), (got["x2"], got["y2"]),
                        got["offset"], got["angle"], got["radius"],
                        extend=got.get("extend", True))
        except ValueError as exc:
            _say(win, str(exc))
            return
        report(win, body)

    if "sm_tabjog_spots" in ANSWERS:
        go(*ANSWERS["sm_tabjog_spots"])
        return body

    def first(spot):
        if spot is None:
            return
        _pick_point(win, body, lambda second: go(spot, second)
                    if second else None,
                    banner="Click the line's end · Esc cancels")
    _pick_point(win, body, first, banner="Click the line's start, across "
                "the tab · Esc cancels")
    return body


def tab(win):
    body = _body(win)
    if body is None:
        return None
    dlg, form = _form(win, "Tab")
    f = {"panel": _spin(0, 0, 999, 0, ""), "u": _spin(0.0, -1e5, 1e5),
         "v": _spin(15.0, -1e5, 1e5), "width": _spin(10.0, 0.1, 1e4),
         "length": _spin(20.0, 0.1, 1e5),
         "angle": _spin(90.0, -360.0, 360.0, 1, " °"),
         "hole": _spin(5.5, 0.0, 1e4)}
    for name, label in (("panel", "Panel (0 = the base)"),
                        ("u", "Round end centre U"),
                        ("v", "Round end centre V"), ("width", "Width"),
                        ("length", "Length (from that centre)"),
                        ("angle", "Direction (0 = +U, 90 = +V)"),
                        ("hole", "Hole diameter (0 = none)")):
        form.addRow(language.tr(label), f[name])
    got = _ask("sm_tab_form", dlg, lambda: {k: w.value()
                                            for k, w in f.items()})
    if not got:
        return None
    try:
        ops.add_tab(win.model, body, int(got["panel"]), got["u"], got["v"],
                    got["width"], got["length"], got["angle"], got["hole"])
    except ValueError as exc:
        _say(win, str(exc))
        return None
    report(win, body)
    return body


def corner(win):
    body = _body(win)
    if body is None:
        return None

    def go(spot):
        panel, u, v = spot if spot else (0, 0.0, 0.0)
        dlg, form = _form(win, "Break Corner")
        f = {"panel": _spin(panel, 0, 999, 0, ""),
             "u": _spin(u, -1e5, 1e5), "v": _spin(v, -1e5, 1e5),
             "size": _spin(10.0, 0.1, 1e4)}
        for name, label in (("panel", "Panel (0 = the base)"),
                            ("u", "Near U"), ("v", "Near V"),
                            ("size", "Radius")):
            form.addRow(language.tr(label), f[name])
        chamfer = QCheckBox(language.tr("Chamfer instead of a round"))
        form.addRow("", chamfer)
        got = _ask("sm_corner_form", dlg, lambda: dict(
            {k: w.value() for k, w in f.items()},
            chamfer=chamfer.isChecked()))
        if not got:
            return
        try:
            ops.add_corner(win.model, body, int(got["panel"]), got["u"],
                           got["v"], got["size"], got.get("chamfer", False))
        except ValueError as exc:
            _say(win, str(exc))
            return
        report(win, body)
    if "sm_corner_spot" in ANSWERS:
        go(ANSWERS["sm_corner_spot"])
    else:
        _pick_point(win, body, go, banner="Click the corner to break · "
                    "Esc types its position")
    return body


def perforate(win):
    body = _body(win)
    if body is None:
        return None
    dlg, form = _form(win, "Perforate")
    f = {"diameter": _spin(5.0, 0.1, 1e4), "pitch": _spin(8.0, 0.2, 1e4),
         "margin": _spin(0.0, 0.0, 1e4)}
    for name, label in (("diameter", "Hole diameter"), ("pitch", "Pitch"),
                        ("margin", "Margin (0 = one diameter)")):
        form.addRow(language.tr(label), f[name])
    square = QComboBox()
    square.addItems([language.tr("Staggered (60°)"), language.tr("Square")])
    form.addRow(language.tr("Pattern"), square)
    got = _ask("sm_perforate", dlg, lambda: dict(
        {k: w.value() for k, w in f.items()},
        square=square.currentIndex() == 1))
    if not got:
        return None
    ops.perforate(win.model, body, got["diameter"], got["pitch"],
                  got["margin"], got["square"])
    pat = ops.pattern(win.model, body)
    _say(win, language.tr("Perforated: {n} holes in the flat pattern — "
                          "Unfold to see them.").format(n=len(pat["holes"])))
    return body


def flat_pattern(win):
    body = _body(win)
    if body is None:
        return None
    comp, pat = ops.flat_pattern_part(win.model, body)
    win.builder.active_tree().select_nodes([comp])
    _say(win, language.tr("Flat pattern: {w:.1f} × {h:.1f} mm blank, "
                          "{n} bends.").format(w=pat["width"],
                                               h=pat["height"],
                                               n=len(pat["bend_table"])))
    return comp


def unfold(win):
    body = _body(win)
    if body is not None:
        ops.set_flat(win.model, body, True)
        report(win, body)
    return body


def refold(win):
    body = _body(win)
    if body is not None:
        ops.set_flat(win.model, body, False)
        report(win, body)
    return body


def export_dxf(win, path=None):
    from . import sheet_body
    body = _body(win)
    if body is None:
        return None
    path = path or _save_path(win, body, "flat", "DXF (*.dxf)", ".dxf",
                              "Export Flat Pattern as DXF")
    if not path:
        return None
    sheet_body.flat_dxf(ops.pattern(win.model, body), path)
    _say(win, language.tr("Flat pattern written: {path}").format(path=path))
    return path


def export_bend_table(win, path=None):
    from . import sheet_body
    body = _body(win)
    if body is None:
        return None
    path = path or _save_path(win, body, "bends", "CSV (*.csv)", ".csv",
                              "Export Bend Table")
    if not path:
        return None
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(sheet_body.bend_table_csv(ops.pattern(win.model, body)))
    _say(win, language.tr("Bend table written: {path}").format(path=path))
    return path


def _save_path(win, body, what, filt, ext, title):
    start = f"{body.name}-{what}{ext}"
    if getattr(win, "_path", None):
        start = str(Path(win._path).with_name(start))
    path, _f = QFileDialog.getSaveFileName(win, language.tr(title), start,
                                           filt)
    if path and not path.lower().endswith(ext):
        path += ext
    return path


# ============================================================ rules
class RulesDialog(QDialog):
    """Sheet Metal Rules: the document's rules, edited, added, deleted
    and applied to the selected body."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle(language.tr("Sheet Metal Rules"))
        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        self.list = QListWidget()
        left.addWidget(self.list)
        row = QHBoxLayout()
        for text, slot in (("New…", self.new), ("Delete", self.delete)):
            b = QPushButton(language.tr(text))
            b.clicked.connect(slot)
            row.addWidget(b)
        left.addLayout(row)
        lay.addLayout(left)
        right = QVBoxLayout()
        form = QFormLayout()
        self.fields = {
            "thickness": _spin(2.0, 0.01, 100.0, 3),
            "bend_radius": _spin(2.0, 0.0, 1000.0, 3),
            "k_factor": _spin(0.44, 0.0, 1.0, 3, ""),
            "hem_gap": _spin(1.0, 0.0, 100.0, 3)}
        for key, label in (("thickness", "Thickness"),
                           ("bend_radius", "Bend radius"),
                           ("k_factor", "K-factor"),
                           ("hem_gap", "Hem gap")):
            form.addRow(language.tr(label), self.fields[key])
            self.fields[key].valueChanged.connect(self.save)
        right.addLayout(form)
        apply_b = QPushButton(language.tr("Apply to selected body"))
        apply_b.clicked.connect(self.apply)
        right.addWidget(apply_b)
        close = QPushButton(language.tr("Close"))
        close.clicked.connect(self.accept)
        right.addStretch(1)
        right.addWidget(close)
        lay.addLayout(right)
        self.list.currentTextChanged.connect(self.show_rule)
        self.refresh()

    def refresh(self, select=None):
        self.list.blockSignals(True)
        self.list.clear()
        names = sorted(ops.rules(self.win.model))
        self.list.addItems(names)
        self.list.blockSignals(False)
        if names:
            self.list.setCurrentRow(names.index(select)
                                    if select in names else 0)

    def show_rule(self, name):
        values = ops.rules(self.win.model).get(name, {})
        from . import mesh
        for key, w in self.fields.items():
            w.blockSignals(True)
            w.setValue(mesh.rv(values.get(key, ops.RULE_FIELDS[key][2])))
            w.blockSignals(False)

    def save(self, *_a):
        name = self.list.currentItem().text() if self.list.currentItem() \
            else None
        if name:
            ops.set_rule(self.win.model, name,
                         **{k: round(w.value(), 6)
                            for k, w in self.fields.items()})

    def new(self, name=None):
        from PyQt5.QtWidgets import QInputDialog
        if not name:
            name, ok = QInputDialog.getText(self, language.tr("New rule"),
                                            language.tr("Rule name:"),
                                            text="Steel 2 mm")
            if not ok or not name:
                return None
        slug = ops.set_rule(self.win.model, name)
        self.refresh(slug)
        return slug

    def delete(self):
        item = self.list.currentItem()
        if item is not None:
            ops.delete_rule(self.win.model, item.text())
            self.refresh()

    def apply(self):
        item = self.list.currentItem()
        body = _body(self.win)
        if item is None or body is None:
            return
        ops.apply_rule(self.win.model, body, item.text())
        report(self.win, body)


def rules(win):
    dlg = RulesDialog(win)
    if "sm_rules" in ANSWERS:
        return dlg
    dlg.exec_()
    return dlg


def jog(win):
    from . import sheet_jog_ui
    return sheet_jog_ui.jog(win)


def hole(win):
    from . import sheet_cut_ui
    return sheet_cut_ui.start(win, "hole")


def slot(win):
    from . import sheet_cut_ui
    return sheet_cut_ui.start(win, "slot")


HANDLERS = {"sm_hole": hole, "sm_slot": slot, "sm_base": base_flange, "sm_arch": arch_plate, "sm_convert": convert, "sm_jog": jog,
            "sm_flange": flange, "sm_fold": fold, "sm_hem": hem,
            "sm_path": path, "sm_contour": contour,
            "sm_phole": panel_hole, "sm_corner": corner, "sm_tab": tab,
            "sm_tabjog": tab_jog, "sm_gusset": gusset, "sm_mirror": mirror,
            "sm_lpattern": linear_pattern, "sm_cpattern": circular_pattern, "sm_perforate": perforate, "sm_flat": flat_pattern,
            "sm_unfold": unfold, "sm_refold": refold, "sm_rules": rules,
            "sm_dxf": export_dxf, "sm_bend_table": export_bend_table}
