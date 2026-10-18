"""The DRAWING SET: one Blueprint sheet per Object, besides the assembly.

Engineering drawings come one per part: the assembly sheet (the whole
model, its parts list and balloons — `DocumentModel.drawing`, as
before) and a PART sheet for every Object (`DocumentModel.part_drawings`
{Object name: sheet state}, saved in the .kcad). A part sheet draws the
Object alone in its own frame (`anchors.local_tris`), its title block
carries the part's BOM line (part number, material, mass) and "sheet n
of N", and its parts list is that Object's OWN bill of materials — its
labelled components, balloons on them.

The Blueprint window gets a Drawing picker (Assembly, then every part),
"Make all part drawings" and "Export drawing set" (one multi-page PDF,
or a folder of PDF / DXF / SVG / PNG files, one per sheet). Qt-side
helpers only; the window calls in through small hooks so blueprint.py
stays its size.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import copy
import re
from pathlib import Path

from PyQt5.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import (QApplication, QComboBox, QFileDialog,
                             QLabel, QMessageBox)

ASSEMBLY = "Assembly"


# ── which sheets there are ─────────────────────────────────────────

def parts(model):
    """[(name, Object)] that get a part drawing: every part and
    sub-assembly of the BOM, in BOM order, each definition once."""
    from . import bom
    defs = {c.name: c for c in model.all_components()}
    b = bom.build(model, "parts")
    out, seen = [], set()
    for ln in b.flat():
        if ln.kind not in ("part", "assembly"):
            continue
        comp = next((n for n in ln.nodes if n is not None and
                     n.type == "component"), None) or defs.get(ln.name)
        if comp is None or comp.name in seen:
            continue
        # the lone Object wrapping a whole design IS the assembly sheet
        if ln.level == 0 and len(b.lines) == 1 and ln.children and any(
                c.kind in ("part", "assembly") for c in ln.children):
            continue
        seen.add(comp.name)
        out.append((comp.name, comp))
    return out


def component(model, name):
    for c in model.all_components():
        if c.name == name:
            return c
    return None


def store_of(model):
    store = getattr(model, "part_drawings", None)
    if store is None:
        store = model.part_drawings = {}
    return store


def stored(win):
    if win.current is None:
        return win.model.drawing
    return store_of(win.model).get(win.current)


def store(win, state):
    if win.current is None:
        win.model.drawing = state
    else:
        store_of(win.model)[win.current] = state


# ── a part's sheet ─────────────────────────────────────────────────

def part_tris(model, name):
    from .anchors import doc_env, local_tris
    comp = component(model, name)
    if comp is None:
        return []
    try:
        env = doc_env(model)
    except Exception:                              # noqa: BLE001
        env = {}
    return local_tris(comp, env, model.effective_fn())


def part_line(model, name):
    """The BOM line of the Object *name* in the whole design (its part
    number, material and mass), or None."""
    from . import bom
    for ln in bom.build(model, "parts").flat():
        if ln.name == name and ln.kind in ("part", "assembly"):
            return ln
    return None


def part_lines(model, name, most=40):
    """The Object's OWN parts list: its sub-parts, or its labelled
    components."""
    from . import bom
    comp = component(model, name)
    if comp is None:
        return []
    # from the WHOLE design's BOM, so a component's part number continues
    # its part's (ASHP-01-09-03) on every sheet and in every export
    for ln in bom.build(model, "components").flat():
        if ln.kind in ("part", "assembly") and comp in ln.nodes:
            lines = list(ln.children)
            for c in lines:
                c.children = []
            return lines[:most]
    b = bom.build(model, "components", scope=comp)
    return b.lines[:most]


def fresh_part(win):
    """A new sheet for the part on show: views, dimensions, its title
    block filled from its BOM line, its own parts list and balloons."""
    from .blueprint_scene import DEFAULT_SHEET, default_fields
    name = win.current
    fields = default_fields(name)
    line = part_line(win.model, name)
    if line is not None:
        fields["number"] = line.get("part_no") or fields["number"]
        if line.get("material"):
            fields["material"] = line.get("material")
        mass = line.get("mass_each")
        if mass:
            fields["mass"] = (f"{mass:.3g} kg" if mass >= 1 else
                              f"{mass * 1000:.3g} g")
    names = [n for n, _c in parts(win.model)]
    if name in names:
        fields["sheet_no"] = f"{names.index(name) + 2} / {len(names) + 1}"
    win.scene.load_state({"sheet": DEFAULT_SHEET, "fields": fields})
    if win.scene.geometry.tris:
        win.scene.new_layout()
        win.scene.auto_dimension()
        if len(part_lines(win.model, name)) >= 2:
            lay_out_with_list(win)


def lay_out_with_list(win):
    """Views arranged round the parts list, not under it: place the list
    once to learn its size, arrange the views above or beside it at the
    biggest scale that fits, dimension them again, then place the list
    with its balloons."""
    win.add_bom(balloons=False)
    listed = [n for n in win.scene.notes() if n.KIND == "bom"]
    if listed:
        win.scene.keep_clear = listed[0].sceneBoundingRect()
        try:
            win.scene.arrange()
        finally:
            win.scene.keep_clear = None
        win.scene.auto_dimension()
    win.add_bom(balloons=True)


def bom_rows(model, lines, numbered=True):
    from . import bom
    rows = []
    for i, ln in enumerate(lines, 1):
        ln.values["sheet_item"] = str(i)
        desc = ln.get("description") or ""
        name = desc if desc.startswith(ln.name) else (
            f"{ln.name} — {desc}" if desc else ln.name)
        mass = ln.get("mass_each")
        rows.append([str(i), ln.get("part_no"), name,
                     ln.get("material") or "",
                     str(bom.line_row(ln)["qty"]) +
                     ("" if ln.unit == "pc" else f" {ln.unit}"),
                     f"{mass:.3g}" if mass else ""])
    return rows


# ── the window's picker and the set's export ───────────────────────

def install_ui(win, bar):
    """The Drawing picker and the set actions on a bar of their OWN,
    on its own row: at the end of the main bar they fell behind its
    overflow chevron, and nobody found the second sheet."""
    from PyQt5.QtCore import Qt as _Qt
    if hasattr(win, "addToolBarBreak"):
        win.addToolBarBreak(_Qt.TopToolBarArea)
        bar = win.addToolBar("Drawing")
        bar.setObjectName("drawing_set_bar")
        bar.setMovable(False)
    else:
        bar.addSeparator()
    bar.addWidget(QLabel(" Drawing "))
    win.drawing_combo = QComboBox()
    win.drawing_combo.setMinimumWidth(220)
    from .blueprint import _tip
    win.drawing_combo.setToolTip(_tip(
        "Drawing", "Which drawing of the set to show: the assembly, or "
        "one Object's own part drawing."))
    win.drawing_combo.activated.connect(lambda _i: _picked(win))
    from PyQt5.QtWidgets import QToolButton
    for text, step, tip in (("◀", -1, "Previous drawing"),
                            ("▶", 1, "Next drawing")):
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.clicked.connect(lambda _c=False, k=step: step_drawing(win, k))
        bar.addWidget(b)
        if step < 0:
            bar.addWidget(win.drawing_combo)
    win.drawing_page = QLabel("")
    bar.addWidget(win.drawing_page)
    from . import icons
    from PyQt5.QtWidgets import QAction
    make = QAction(icons.icon("mdi.file-document-multiple-outline"),
                   "Make all part drawings", win)
    make.setToolTip(_tip(
        "Make all part drawings",
        "Creates a drawing for every Object that has none yet."))
    make.triggered.connect(lambda: make_all(win))
    bar.addAction(make)
    exp = QAction(icons.icon("mdi.book-open-page-variant-outline"),
                  "Export drawing set…", win)
    exp.setToolTip(_tip(
        "Export drawing set",
        "Writes every drawing of the set in one go."))
    exp.triggered.connect(lambda: export_dialog(win))
    bar.addAction(exp)
    drop = QAction(icons.icon("mdi.file-remove-outline"),
                   "Delete this drawing", win)
    drop.setToolTip(_tip(
        "Delete this drawing",
        "Removes the part drawing on screen from the set (the model is "
        "untouched; the assembly sheet cannot be deleted)."))
    drop.triggered.connect(lambda: delete_current(win))
    bar.addAction(drop)
    refill(win)


def refill(win):
    combo = getattr(win, "drawing_combo", None)
    if combo is None:
        return
    combo.blockSignals(True)
    combo.clear()
    combo.addItem(ASSEMBLY + " (whole design)", None)
    made = store_of(win.model)
    listed = set()
    for name, _c in parts(win.model):
        combo.addItem(("● " if name in made else "○ ") + name, name)
        listed.add(name)
    # a sheet made for an Object the parts list does not name (the lone
    # Object wrapping the whole design) is still a sheet of the set
    known = {c.name for c in win.model.all_components()}
    for name in made:
        if name not in listed and name in known:
            combo.addItem("● " + name, name)
    combo.setCurrentIndex(max(0, combo.findData(win.current)))
    combo.blockSignals(False)
    page = getattr(win, "drawing_page", None)
    if page is not None:
        page.setText(f"  {combo.currentIndex() + 1} of {combo.count()}")


def delete_current(win):
    """Drop the part drawing on screen and go back to the assembly."""
    name = win.current
    if name is None:
        return False
    store_of(win.model).pop(name, None)
    win.current = None
    win.load()
    refill(win)
    return True


def step_drawing(win, step):
    """◀ / ▶: the previous or next drawing in the picker."""
    combo = win.drawing_combo
    i = combo.currentIndex() + step
    if 0 <= i < combo.count():
        combo.setCurrentIndex(i)
        _picked(win)


def _picked(win):
    show(win, win.drawing_combo.currentData())


def show(win, name):
    """Switch the window to drawing *name* (None = the assembly)."""
    if name == win.current:
        return
    win.flush_pending()
    win.current = name
    win.load()
    refill(win)
    win.setWindowTitle(f"Blueprint — {win.scene.title_text()}")


def make_all(win, names=None):
    """A sheet for every part (or *names*) that has none; returns the
    names made. The window comes back to the drawing it was on."""
    keep = win.current
    made = []
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        for name, _c in parts(win.model):
            if names is not None and name not in names:
                continue
            if name in store_of(win.model):
                continue
            win.current = name
            win.load()
            made.append(name)
    finally:
        win.current = keep
        win.load()
        QApplication.restoreOverrideCursor()
    refill(win)
    win.status(f"{len(made)} part drawing(s) made — pick one in Drawing.")
    return made


def sheets(win):
    """[(name or None, state)] of the whole set, assembly first, made
    where missing."""
    make_all(win)
    out = [(None, copy.deepcopy(win.model.drawing))]
    made = store_of(win.model)
    for name, _c in parts(win.model):
        if name in made:
            out.append((name, copy.deepcopy(made[name])))
    return out


def _scene_for(win, name, state, number, total):
    from .blueprint_scene import BlueprintScene, Geometry
    scene = BlueprintScene()
    scene.unit = win.model.unit
    tris = list(win.main.view3d.model_mesh or ()) if name is None else \
        part_tris(win.model, name)
    scene.geometry = Geometry(tris)
    state = copy.deepcopy(state or {})
    state.setdefault("fields", {})["sheet_no"] = f"{number} / {total}"
    scene.load_state(state)
    return scene


def export_set(win, path):
    """Write the whole set: *path* ending .pdf is one multi-page PDF;
    anything else is a folder, one file per sheet in each of PDF, DXF,
    SVG and PNG. Returns the files written."""
    from PyQt5.QtGui import QPageSize, QPdfWriter
    from . import blueprint_export
    win.flush_pending()
    all_sheets = sheets(win)
    total = len(all_sheets)
    path = Path(path)
    written = []
    if path.suffix.lower() == ".pdf":
        writer = None
        painter = None
        for i, (name, state) in enumerate(all_sheets, 1):
            scene = _scene_for(win, name, state, i, total)
            rect = scene.sheet_rect()
            size = QPageSize(QSizeF(rect.width(), rect.height()),
                             QPageSize.Millimeter)
            if writer is None:
                writer = QPdfWriter(str(path))
                writer.setPageSize(size)
                writer.setPageMargins(QMarginsF(0, 0, 0, 0))
                writer.setResolution(600)
                writer.setCreator("KherveCAD")
                writer.setTitle("Drawing set")
                painter = QPainter(writer)
            else:
                writer.setPageSize(size)
                writer.newPage()
            blueprint_export.paint_sheet(scene, painter, QRectF(
                0, 0, writer.width(), writer.height()))
        if painter is not None:
            painter.end()
        written.append(str(path))
        return written
    path.mkdir(parents=True, exist_ok=True)
    for i, (name, state) in enumerate(all_sheets, 1):
        scene = _scene_for(win, name, state, i, total)
        stem = f"{i:02d} " + _safe(name or ASSEMBLY)
        for ext in (".pdf", ".dxf", ".svg", ".png"):
            out = path / (stem + ext)
            blueprint_export.export(scene, out)
            written.append(str(out))
    return written


def _safe(name):
    return re.sub(r"[\\/:*?\"<>|]+", "-", str(name)).strip() or "sheet"


def export_dialog(win):
    start = str(Path.home() / "Documents" / "Drawing set.pdf")
    path, chosen = QFileDialog.getSaveFileName(
        win, "Export drawing set", start,
        "One PDF, every sheet a page (*.pdf);;"
        "A folder: PDF, DXF, SVG and PNG per sheet (*)")
    if not path:
        return
    if "folder" in chosen.lower() and path.lower().endswith(".pdf"):
        path = path[:-4]
    try:
        files = export_set(win, path)
    except OSError as exc:
        QMessageBox.warning(win, "Drawing set", str(exc))
        return
    win.status(f"Drawing set written: {len(files)} file(s) — {path}")


# ── MCP ────────────────────────────────────────────────────────────

def run_tool(main, params):
    """The `drawing_set` MCP tool's body."""
    from .blueprint import open_blueprint
    action = params.get("action") or "list"
    names = [n for n, _c in parts(main.model)]
    made = store_of(main.model)
    if action == "list":
        return {"sheets": [{"name": ASSEMBLY, "made":
                            bool(main.model.drawing)}] +
                [{"name": n, "made": n in made} for n in names],
                "total": len(names) + 1}
    win = open_blueprint(main)
    if action == "make":
        want = params.get("names")
        bad = [n for n in (want or []) if n not in names]
        if bad:
            raise ValueError(f"no part drawing for {bad}; parts: {names}")
        got = make_all(win, want)
        return {"made": got, "total": len(names) + 1}
    if action == "show":
        name = params.get("name") or None
        if name == ASSEMBLY:
            name = None
        if name is not None and name not in names:
            raise ValueError(f"no part {name!r}; parts: {names}")
        show(win, name)
        return {"showing": name or ASSEMBLY,
                "title": win.scene.title_text()}
    if action == "export":
        path = params.get("path")
        if not path:
            raise ValueError("export needs a path (.pdf, or a folder)")
        return {"written": export_set(win, path)}
    if action == "render":
        import base64
        from PyQt5.QtCore import QBuffer, QByteArray, QIODevice
        from . import blueprint_export
        from .mcp_server import IMAGE_KEY
        name = params.get("name") or None
        if name == ASSEMBLY:
            name = None
        show(win, name)
        image = blueprint_export.to_image(win.scene, 4.0)
        data = QByteArray()
        buf = QBuffer(data)
        buf.open(QIODevice.WriteOnly)
        image.save(buf, "PNG")
        return {IMAGE_KEY: base64.b64encode(bytes(data)).decode("ascii"),
                "showing": name or ASSEMBLY}
    raise ValueError(f"unknown action {action!r}")
