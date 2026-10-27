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
            if kind == "flange":
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


HANDLERS = {"sm_base": base_flange, "sm_convert": convert,
            "sm_flange": flange, "sm_fold": fold, "sm_hem": hem,
            "sm_path": path, "sm_contour": contour,
            "sm_perforate": perforate, "sm_flat": flat_pattern,
            "sm_unfold": unfold, "sm_refold": refold, "sm_rules": rules,
            "sm_dxf": export_dxf, "sm_bend_table": export_bend_table}
