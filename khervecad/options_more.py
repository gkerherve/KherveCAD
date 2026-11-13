"""The rest of Tools ▸ Options (2026-11-13, the user: "what else is
missing ... SolidWorks, Blender, Fusion?" then "all of them"). Every
preference here is a QSettings key under ``options/`` with a default in
`PREFS`; `get` reads it anywhere. The pages are built into the Options
window by `add_pages`, and `start(win)` puts what must act at start-up
in place (undo limit, keyboard shortcuts, backups, the view's look).

What each one drives:
- Mouse & navigation: zoom direction, zoom toward the cursor, orbit
  speed and which mouse buttons orbit / pan (`view3d` reads `mode_for`).
- Display: selection colour, edge thickness, field of view, anti-aliasing
  samples (glrender's framebuffer).
- Colours: a named scheme for the selection and the sketch inks
  (free / fully defined / over defined).
- Default template: the unit and mass material a NEW document starts with.
- Backup: a copy of the open document every N minutes, N copies kept.
- Keyboard: any menu command rebound (`shortcuts/<menu path>`).
- Performance: the triangle count past which orbiting draws a draft.
- Grid & units: dual dimensions (mm and inches together).
- Drawings: the drafting standard (ISO / ANSI / DIN): text height and
  arrowheads on the Blueprint.
- Import / export: Y-up STL export.
- Undo: how many steps are kept (from the next launch).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import time

from PyQt5.QtCore import QSettings

_SETTINGS = ("Kherve", "KherveCAD")

#: which buttons turn and move the view, like the programs people know.
#: Left always orbits (the 3D view selects nothing with it). Values:
#: (button, modifier) -> "orbit" | "pan"
MOUSE_SCHEMES = {
    "KherveCAD": {("middle", ""): "pan", ("right", ""): "pan"},
    "SolidWorks": {("middle", ""): "orbit", ("middle", "ctrl"): "pan",
                   ("right", ""): "pan"},
    "Fusion": {("middle", ""): "pan", ("middle", "shift"): "orbit",
               ("right", ""): "pan"},
    "Blender": {("middle", ""): "orbit", ("middle", "shift"): "pan",
                ("right", ""): "pan"},
    "Inventor": {("middle", ""): "pan", ("middle", "shift"): "orbit",
                 ("right", ""): "pan"},
}

#: colour schemes: selection tint + sketch inks (free, defined, over)
SCHEMES = {
    "Classic": ("#ff2d2d", "#1d4ed8", "#111111", "#d32f2f"),
    "Blue selection": ("#3d8bff", "#1d4ed8", "#111111", "#d32f2f"),
    "Green selection": ("#2fbf5a", "#1d4ed8", "#111111", "#d32f2f"),
    "Orange selection": ("#ff9a1f", "#1565c0", "#1b1b1b", "#c62828"),
    "High contrast": ("#ffd400", "#0047ff", "#000000", "#ff0000"),
}

#: standard -> (annotation text height mm, arrow length, arrow width)
STANDARDS = {"ISO": (3.5, 3.0, 1.0), "ANSI": (3.0, 3.2, 1.07),
             "DIN": (3.5, 2.5, 0.85)}

PREFS = {
    "reverse_zoom": False,
    "zoom_to_cursor": True,
    "orbit_speed": 100,              # %
    "mouse_scheme": "KherveCAD",
    "scheme": "Classic",
    "edge_width": 1.2,               # px
    "fov": 0,                        # degrees, 0 = the usual 45°
    "aa_samples": 4,
    "new_unit": "mm",
    "new_material": "",
    "backup": True,
    "backup_minutes": 10,
    "backup_copies": 5,
    "draft_above": 9000,
    "dual_dimensions": False,
    "standard": "ISO",
    "stl_y_up": False,
    "undo_limit": 0,                 # 0 = no limit
}


def get(key):
    """A preference with its type, the default when unset or broken."""
    default = PREFS[key]
    value = QSettings(*_SETTINGS).value("options/" + key, default)
    try:
        if isinstance(default, bool):
            return str(value).lower() in ("true", "1")
        if isinstance(default, int):
            return int(float(value))
        if isinstance(default, float):
            return float(value)
    except (TypeError, ValueError):
        return default
    return str(value)


def put(key, value):
    QSettings(*_SETTINGS).setValue("options/" + key, value)


# ── what the views ask ─────────────────────────────────────────────
def mode_for(button, modifiers):
    """'orbit' / 'pan' for a non-left button by the mouse scheme."""
    from PyQt5.QtCore import Qt
    name = {Qt.MiddleButton: "middle", Qt.RightButton: "right"}.get(button)
    if name is None:
        return "orbit"
    mod = ("ctrl" if modifiers & Qt.ControlModifier else
           "shift" if modifiers & Qt.ShiftModifier else "")
    table = MOUSE_SCHEMES.get(get("mouse_scheme"), MOUSE_SCHEMES["KherveCAD"])
    return table.get((name, mod)) or table.get((name, ""), "pan")


def focal_factor():
    """The view's focal length over its short side (1.2 = the usual)."""
    fov = get("fov")
    if fov <= 0:
        return 1.2
    fov = max(10, min(120, fov))
    return 0.5 / math.tan(math.radians(fov) / 2)


def apply_view(view):
    """Selection colour, draft size, and a new framebuffer for the
    sample count (glrender makes it again at the next paint)."""
    scheme = SCHEMES.get(get("scheme"), SCHEMES["Classic"])
    view.HIGHLIGHT_COLOR = scheme[0]
    from . import units
    units.DUAL = get("dual_dimensions")
    try:
        from . import blueprint_items as bi
        bi.TEXT, bi.ARROW_L, bi.ARROW_W = STANDARDS.get(
            get("standard"), STANDARDS["ISO"])
    except Exception:
        pass
    view.DRAFT_ABOVE = max(500, get("draft_above"))
    gl = getattr(view, "_gl", None) or getattr(view, "gl", None)
    if gl is not None and hasattr(gl, "_fbo_size"):
        gl._fbo_size = None
    try:
        from . import sketch_state
        sketch_state.INK.update(free=scheme[1], defined=scheme[2],
                                over=scheme[3])
    except Exception:
        pass
    view.update()


# ── start-up ───────────────────────────────────────────────────────
def start(win):
    """Put the preferences that act on their own in place."""
    limit = get("undo_limit")
    stack = win.model.undo_stack
    if limit > 0 and stack.count() == 0:
        stack.setUndoLimit(limit)
    apply_shortcuts(win)
    apply_view(win.view3d)
    restart_backups(win)


def apply_shortcuts(win):
    from PyQt5.QtGui import QKeySequence
    from . import interface_menus
    s = QSettings(*_SETTINGS)
    s.beginGroup("shortcuts")
    keys = {k: s.value(k) for k in s.childKeys()}
    s.endGroup()
    if not keys:
        return
    try:
        paths = interface_menus.index(win)
    except Exception:
        return
    for path, act in paths.items():
        stored = keys.get(_key(path))
        if stored is not None:
            act.setShortcut(QKeySequence(str(stored)))


def _key(path):
    """A menu path as one QSettings key (no slashes)."""
    return path.replace("/", "|")


def save_shortcut(path, text):
    s = QSettings(*_SETTINGS)
    s.setValue("shortcuts/" + _key(path), text)


# ── backups ────────────────────────────────────────────────────────
def backup_folder():
    from PyQt5.QtCore import QStandardPaths
    base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) \
        or os.path.expanduser("~")
    return os.path.join(base, "Backups")


def restart_backups(win):
    from PyQt5.QtCore import QTimer
    timer = getattr(win, "_kc_backup_timer", None)
    if timer is None:
        timer = QTimer(win)
        timer.timeout.connect(lambda: backup_now(win))
        win._kc_backup_timer = timer
    timer.stop()
    if get("backup"):
        timer.start(max(1, get("backup_minutes")) * 60_000)


def backup_now(win):
    """Write a copy of the open document if it changed; keep the newest
    `backup_copies` per document. Never raises (a timer slot)."""
    try:
        if not getattr(win, "_dirty", False):
            return None
        from . import document
        stem = os.path.splitext(os.path.basename(
            getattr(win, "_path", None) or "Untitled.kcad"))[0]
        folder = backup_folder()
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "%s %s.kcad" % (
            stem, time.strftime("%Y-%m-%d %H-%M-%S")))
        document.save_kcad(win.model, path)
        mine = sorted(f for f in os.listdir(folder)
                      if f.startswith(stem + " 2") and f.endswith(".kcad"))
        for old in mine[:-max(1, get("backup_copies"))]:
            os.remove(os.path.join(folder, old))
        return path
    except Exception:
        return None


# ── new documents and exports ─────────────────────────────────────
def new_document(win):
    """The default template's unit and material on a new document."""
    model = win.model
    unit = get("new_unit")
    if unit and unit != "mm":
        try:
            model.set_unit(unit)
        except Exception:
            pass
    material = get("new_material")
    if material:
        try:
            from . import massbar
            massbar.set_material(win, material)
        except Exception:
            pass
    if hasattr(model, "undo_stack"):
        model.undo_stack.clear()


def y_up_stl(path):
    """Turn a written STL so +Y is up (x, y, z) -> (x, z, -y)."""
    from .engine import parse_stl, write_stl
    tris = parse_stl(path)
    turned = [tuple((p[0], p[2], -p[1]) for p in tri) for tri in tris]
    write_stl(turned, path)


# ── the Options pages ─────────────────────────────────────────────
PAGES = [("System Options", ["Mouse", "Colors", "Keyboard", "Backup",
                             "Import Export"]),
         ("Document Properties", ["Template", "Drafting Standard"])]


def add_pages(dialog):
    """Pages built into the Options window; `apply_pages` saves them."""
    from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox,
                                 QSpinBox)
    tr = dialog_tr()
    dialog._prefs = []

    def check(form, key, label):
        box = QCheckBox(tr(label))
        box.setChecked(get(key))
        form.addRow("", box)
        dialog._prefs.append((box, key))
        return box

    def spin(form, key, label, lo, hi, suffix="", real=False):
        box = QDoubleSpinBox() if real else QSpinBox()
        box.setRange(lo, hi)
        if real:
            box.setSingleStep(0.1)
        box.setValue(get(key))
        if suffix:
            box.setSuffix(suffix)
        form.addRow(tr(label), box)
        dialog._prefs.append((box, key))
        return box

    def combo(form, key, label, items):
        box = QComboBox()
        for text, data in items:
            box.addItem(tr(text), data)
        i = box.findData(get(key))
        box.setCurrentIndex(max(0, i))
        form.addRow(tr(label), box)
        dialog._prefs.append((box, key))
        return box

    pages = {}
    page, form = dialog._form(
        "Which mouse buttons turn and move the 3D view, the way the "
        "programs you know do it. The left button always turns.")
    combo(form, "mouse_scheme", "Mouse buttons like:",
          [(n, n) for n in MOUSE_SCHEMES])
    spin(form, "orbit_speed", "Orbit speed:", 20, 400, " %")
    check(form, "reverse_zoom", "Reverse the wheel's zoom direction")
    check(form, "zoom_to_cursor", "Zoom toward the mouse pointer")
    pages["Mouse"] = page

    page, form = dialog._form(
        "The selection tint and the sketch line colours (blue = can "
        "still move, black = fully defined, red = over defined).")
    combo(form, "scheme", "Colour scheme:", [(n, n) for n in SCHEMES])
    spin(form, "edge_width", "Edge line thickness:", 0.5, 4.0, " px",
         real=True)
    spin(form, "fov", "Field of view (0 = usual):", 0, 120, " °")
    combo(form, "aa_samples", "Anti-aliasing:",
          [("Off", 0), ("2x", 2), ("4x", 4), ("8x", 8)])
    spin(form, "draft_above", "Draft while turning past:", 500, 2_000_000,
         " triangles")
    pages["Colors"] = page

    pages["Keyboard"] = _keyboard_page(dialog)

    page, form = dialog._form(
        "A copy of the open document is kept in the backup folder while "
        "it has unsaved changes.")
    check(form, "backup", "Keep backup copies")
    spin(form, "backup_minutes", "Every:", 1, 240, " min")
    spin(form, "backup_copies", "Copies kept per document:", 1, 100)
    spin(form, "undo_limit", "Undo steps kept (0 = all, next launch):",
         0, 10000)
    from PyQt5.QtWidgets import QLabel
    form.addRow(tr("Backup folder:"), QLabel(backup_folder()))
    pages["Backup"] = page

    page, form = dialog._form()
    check(form, "stl_y_up", "Export STL with Y up (game engines, "
                            "some renderers)")
    check(form, "dual_dimensions", "Show lengths in mm and inches "
                                   "together")
    pages["Import Export"] = page

    from . import units
    page, form = dialog._form(
        "What a new document starts with (File ▸ New).")
    combo(form, "new_unit", "Unit:",
          [(units.name(c), c) for c in units.choices()])
    try:
        from . import analysis
        mats = [("None", "")] + [(m, m) for m in analysis.MATERIALS]
    except Exception:
        mats = [("None", "")]
    combo(form, "new_material", "Material:", mats)
    pages["Template"] = page

    page, form = dialog._form(
        "The drafting standard Blueprint sheets follow: annotation text "
        "height and arrowhead size.")
    combo(form, "standard", "Standard:", [(s, s) for s in STANDARDS])
    pages["Drafting Standard"] = page
    return pages


def dialog_tr():
    from . import language
    return language.tr


def _keyboard_page(dialog):
    from PyQt5.QtGui import QKeySequence
    from PyQt5.QtWidgets import (QHeaderView, QKeySequenceEdit, QLineEdit,
                                 QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                                 QWidget)
    tr = dialog_tr()
    page = QWidget()
    lay = QVBoxLayout(page)
    search = QLineEdit()
    search.setPlaceholderText(tr("Search commands…"))
    tree = QTreeWidget()
    tree.setHeaderLabels([tr("Command"), tr("Shortcut")])
    tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
    dialog._keys = []                       # (path, action, editor)
    for path, act in sorted(dialog._paths.items()):
        if act.menu() is not None or not act.text():
            continue
        item = QTreeWidgetItem(tree, [path.replace("/", " ▸ "), ""])
        edit = QKeySequenceEdit(act.shortcut())
        tree.setItemWidget(item, 1, edit)
        dialog._keys.append((path, act, edit, item))

    def filt(text):
        text = text.lower()
        for _p, _a, _e, item in dialog._keys:
            item.setHidden(bool(text) and text not in item.text(0).lower())
    search.textChanged.connect(filt)
    lay.addWidget(search)
    lay.addWidget(tree)
    dialog._key_seq = QKeySequence
    return page


def apply_pages(dialog):
    from PyQt5.QtWidgets import QCheckBox, QComboBox
    for box, key in getattr(dialog, "_prefs", ()):
        if isinstance(box, QCheckBox):
            put(key, box.isChecked())
        elif isinstance(box, QComboBox):
            put(key, box.currentData())
        else:
            put(key, box.value())
    for path, act, edit, _item in getattr(dialog, "_keys", ()):
        seq = edit.keySequence()
        if seq != act.shortcut():
            act.setShortcut(seq)
            save_shortcut(path, seq.toString())
    win = dialog.win
    apply_view(win.view3d)
    restart_backups(win)
    win.view2d.viewport().update()


def widgets(dialog):
    return [b for b, _k in getattr(dialog, "_prefs", ())]
