"""Regenerate the User Guide's screenshots (khervecad/help/*.png).

    python packaging/make_help_screenshots.py [only-this-shot ...]

Drives the real main window offscreen — the same widgets the user
sees, set up by the same calls the tools make — and grabs each panel,
dialog and menu the guide shows, with numbered call-outs painted over
the overview shots. Re-run it after a UI change so the manual never
shows a window that no longer exists.

It never writes the user's settings: view options are set on the
widgets directly, not through the setters that persist them.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
import time
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "khervecad" / "help"

from PyQt5.QtCore import (QElapsedTimer, QEvent, QPoint,  # noqa: E402
                          QRect, Qt)
from PyQt5.QtGui import (QColor, QFont, QImage, QPainter,  # noqa: E402
                         QPen)
from PyQt5.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv[:1])
app.setStyle("Fusion")

from khervecad import examples, scadparse  # noqa: E402
from khervecad.style import apply_style, current_theme  # noqa: E402

apply_style(app, current_theme())

from khervecad.mainwindow import MainWindow  # noqa: E402

ACCENT = QColor("#e07b39")
WIDE = 1100                     # window shots are scaled down to this


# ------------------------------------------------------------ helpers
def settle(ms=400):
    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < ms:
        app.processEvents()
        # processEvents() never runs deleteLater(): a panel rebuilt
        # twice would show its old widgets under the new ones
        app.sendPostedEvents(None, QEvent.DeferredDelete)
        time.sleep(0.01)


def wait_exact(win, limit_s=40):
    """Let the OpenSCAD engine finish its renders (when it is
    installed), so holes show cut."""
    if not win.engine.available:
        settle(300)
        return
    deadline = time.monotonic() + limit_s
    settle(600)
    while time.monotonic() < deadline:
        settle(250)
        label = win.view3d.source
        if "parts exact" in label:
            done, total = label.split("parts exact")[0].split("—")[-1] \
                .strip().split("/")
            if done == total and not win._shot_busy:
                break
        elif not win._shot_busy:
            break
    settle(300)


def finish_3d(win):
    win.view3d.wait_for_bsp()
    settle(150)


def save(img, name, width=None):
    if isinstance(img, QImage) is False:
        img = img.toImage()
    if width and img.width() > width:
        img = img.scaledToWidth(width, Qt.SmoothTransformation)
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(str(OUT / f"{name}.png"), "PNG")
    print(f"  {name}.png  {img.width()}x{img.height()}")


def badge(painter, x, y, number, text=""):
    """A numbered orange disc, with an optional caption to its right."""
    r = 13
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor("white"), 2))
    painter.setBrush(ACCENT)
    painter.drawEllipse(QPoint(x, y), r, r)
    font = QFont(painter.font())
    font.setBold(True)
    font.setPixelSize(14)
    painter.setFont(font)
    painter.drawText(QRect(x - r, y - r, 2 * r, 2 * r), Qt.AlignCenter,
                     str(number))
    if text:
        font.setPixelSize(13)
        painter.setFont(font)
        width = painter.fontMetrics().horizontalAdvance(text) + 14
        box = QRect(x + r + 4, y - 11, width, 22)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(30, 33, 38, 215))
        painter.drawRoundedRect(box, 5, 5)
        painter.setPen(QColor("white"))
        painter.drawText(box, Qt.AlignCenter, text)


def top_left(widget, win, dx=18, dy=18):
    p = widget.mapTo(win, QPoint(0, 0))
    return p.x() + dx, p.y() + dy


def new_window():
    win = MainWindow()
    win.resize(1440, 900)
    view = win.view3d
    view.style, view.background = "Shaded", "Light"
    view.stage = False                   # whatever this machine saved
    view.brightness = view.contrast = 0.0
    view.projection = "Perspective"
    win._shot_busy = False
    win.engine.busy_changed.connect(
        lambda busy: setattr(win, "_shot_busy", bool(busy)))
    win.show()
    settle(300)
    return win


def load(win, label):
    build = next(b for name, _cat, b in examples.EXAMPLES if name == label)
    examples.load_example(win.model, build)
    win._dirty = False
    win.view3d.user_moved = False
    win._fitted = False
    settle(300)
    win.view3d.fit()
    win.view2d.fit_content()


def select(win, nodes, tree=None):
    (tree or win.builder.active_tree()).select_nodes(list(nodes))
    settle(150)


# -------------------------------------------------------------- shots
def shot_window(win):
    load(win, "Bolted flange joint")
    wait_exact(win)
    win.view3d.fit()
    finish_3d(win)
    img = win.grab().toImage()
    p = QPainter(img)
    b = win.builder
    tools = win._tools_bar
    badge(p, *top_left(b, win, 210, 150), 1, "Object tree & tabs")
    badge(p, *top_left(win.properties, win, 60, 40), 2, "Properties")
    badge(p, *top_left(win.view2d, win, 120, 40), 3, "2D sketch")
    badge(p, *top_left(win.view3d, win, 230, 60), 4, "3D preview")
    badge(p, *top_left(tools, win, 26, tools.height() - 40), 5,
          "Drawing tools & solids")
    badge(p, *top_left(win._options_bar, win, 470, 50), 6, "Main toolbar")
    p.end()
    save(img, "window", WIDE)


def shot_toolbars(win):
    bar = win._options_bar
    src = bar.grab().toImage()
    img = QImage(src.width(), src.height() + 34, QImage.Format_ARGB32)
    img.fill(QColor(win.palette().window().color()))
    p = QPainter(img)
    p.drawImage(0, 0, src)
    acts = [a for a in bar.actions()]

    def span(first, last):
        a = bar.widgetForAction(acts[first]).geometry()
        z = bar.widgetForAction(acts[last]).geometry()
        return a.left(), z.right()

    # locate the sections by their separators
    seps = [i for i, a in enumerate(acts) if a.isSeparator()]
    bounds = [0] + [s + 1 for s in seps]
    ends = [s - 1 for s in seps] + [len(acts) - 1]
    names = ["File", "Undo", "Operations (drop-down groups)", "Assembly",
             "Sketch: grid, snap, plane", "3D view", "AI"]
    p.setRenderHint(QPainter.Antialiasing)
    font = QFont(p.font())
    font.setPixelSize(12)
    font.setBold(True)
    p.setFont(font)
    y = src.height() + 6
    for name, lo, hi in zip(names, bounds, ends):
        left, right = span(lo, hi)
        p.setPen(QPen(ACCENT, 2))
        p.drawLine(left + 3, y, right - 3, y)
        p.drawLine(left + 3, y - 4, left + 3, y)
        p.drawLine(right - 3, y - 4, right - 3, y)
        p.setPen(QColor("#5a4a3a"))
        p.drawText(QRect(left - 40, y + 2, right - left + 80, 22),
                   Qt.AlignHCenter | Qt.AlignTop, name)
    p.end()
    save(img, "toolbar_main")
    save(win._tools_bar.grab(), "toolbar_tools")
    for key in ("extrude", "transform", "combine", "deform", "character",
                "logic"):
        menu = win._op_groups[key].menu()
        menu.ensurePolished()
        menu.adjustSize()
        save(menu.grab(), f"group_{key}")


def shot_tutorial(win):
    win.model.clear()
    win._dirty = False
    win._set_plane("Top (XY)")
    win.builder.setCurrentIndex(0)
    settle(200)
    # 1. draw a rectangle (it becomes a new Object, opened for editing)
    rect = win.scene._create("rect", dict(x=-30.0, y=-20.0, width=60.0,
                                          height=40.0))
    win.scene.node_created.emit(rect)
    select(win, [rect])
    win.view2d.fit_content()
    win.view3d.yaw, win.view3d.pitch = 35.0, 30.0
    win.view3d.fit()
    finish_3d(win)
    save(win.grab(), "tutorial_1_rectangle", WIDE)
    # 2. extrude it
    win._apply_operation("linear_extrude")
    ext = rect.parent
    win.model.set_param(ext, "height", 8.0)
    settle(200)
    win.view3d.yaw, win.view3d.pitch = 35.0, 30.0
    win.view3d.fit()
    finish_3d(win)
    save(win.grab(), "tutorial_2_extrude", WIDE)
    # 3. a cylinder through it
    win._add_primitive("cylinder")
    tree = win.builder.active_tree()
    cyl = tree.selected_nodes()[0]
    for key, value in (("radius_bottom", 8.0), ("radius_top", 8.0),
                       ("height", 20.0), ("z", -6.0)):
        win.model.set_param(cyl, key, value)
    select(win, [cyl])
    win.view3d.fit()
    finish_3d(win)
    save(win.grab(), "tutorial_3_cylinder", WIDE)
    save(win.properties.grab(), "properties")
    # 4. cut it out
    select(win, [ext, cyl])
    win._apply_operation("difference")
    select(win, [])
    wait_exact(win)
    win.view3d.fit()
    finish_3d(win)
    save(win.grab(), "tutorial_4_difference", WIDE)
    save(win.view3d.grab(), "view3d_plate")
    save(win.builder.grab(), "tab_object")
    win.builder.setCurrentIndex(4)                   # Code tab
    settle(300)
    save(win.builder.grab(), "tab_code")


def shot_tabs(win):
    load(win, "Bolt circle (Masters demo)")
    win.builder.setCurrentIndex(0)
    settle(200)
    save(win.builder.grab(), "tab_main")
    win.builder.setCurrentIndex(2)
    settle(200)
    save(win.builder.grab(), "tab_masters")
    load(win, "Parametric box")
    win.builder.setCurrentIndex(3)
    settle(200)
    save(win.builder.grab(), "tab_variables")
    win.builder.setCurrentIndex(0)
    comps = [n for n in win.model.root.walk() if n.type == "component"]
    if comps:
        win.builder.open_component(comps[0])
        settle(300)
        save(win.builder.grab(), "tab_object")
    win.builder.setCurrentIndex(0)


def shot_named_rows(win):
    code = (
        'body = [50, 80, 40];\n'
        'color("pink") cube(body, center=true);  // Body\n'
        'color("pink") translate([0, 50, 12]) '
        'cube([36, 30, 30], center=true);  // Head\n'
        'color("hotpink") translate([0, 66, 8]) '
        'cube([16, 4, 10], center=true);  // Snout\n'
        'for (px = [-1, 1]) for (py = [-1, 1])  // Legs\n'
        '    color("pink") translate([px * 17, py * 28, -40]) '
        'cylinder(h=25, r=7);  // Leg\n'
        'color("pink") translate([0, -42, 10]) '
        'sphere(4);  // Tail\n')
    root, _warn = scadparse.parse_scad(code)
    win.model.root = root
    win.model.group_variables()
    win.model.structure_changed.emit()
    win._dirty = False
    win.builder.setCurrentIndex(0)
    win.view3d.yaw, win.view3d.pitch = 30.0, 20.0
    win.view3d.user_moved = False
    win.view3d.fit()
    settle(300)
    win.builder.tree.expandAll()
    settle(150)
    save(win.builder.grab(), "named_rows")
    finish_3d(win)
    save(win.view3d.grab(), "named_rows_3d")


def shot_sketch(win):
    win.model.clear()
    win._dirty = False
    win.builder.setCurrentIndex(0)
    win._set_plane("Top (XY)")
    rect = win.scene._create("rect", dict(x=0.0, y=0.0, width=60.0,
                                          height=35.0))
    win.scene.node_created.emit(rect)
    circ = win.scene._create("circle", dict(x=45.0, y=17.5,
                                            radius=9.0))
    win.scene.node_created.emit(circ)
    select(win, [rect])
    win.view2d.fit_content()
    settle(300)
    save(win.view2d.grab(), "sketch")


def shot_styles(win):
    load(win, "Meshing gear pair")
    wait_exact(win)
    view = win.view3d
    view.resize(520, 360)
    from khervecad.view3d import RENDER_STYLES
    tiles = []
    for style in ("Shaded", "Brushed metal", "Wireframe", "X-ray"):
        if style not in RENDER_STYLES:
            continue
        view.style = style
        view.fit()
        finish_3d(win)
        tiles.append((style, view.grab().toImage()))
    view.style = "Shaded"
    w, h = tiles[0][1].width(), tiles[0][1].height()
    img = QImage(2 * w + 6, 2 * h + 6, QImage.Format_ARGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    for k, (style, tile) in enumerate(tiles):
        x, y = (k % 2) * (w + 6), (k // 2) * (h + 6)
        p.drawImage(x, y, tile)
        badge(p, x + w - 170, y + h - 60, k + 1, style)
    p.end()
    save(img, "render_styles", WIDE)
    win.resize(1440, 900)
    settle(200)


def shot_character(win):
    for label, name in (("Tulip", "character_tulip"),
                        ("Oak", "character_oak")):
        match = [b for n, _c, b in examples.EXAMPLES if label in n]
        if not match:
            continue
        examples.load_example(win.model, match[0])
        win._dirty = False
        win.view3d.user_moved = False
        win.view3d.yaw, win.view3d.pitch = 35.0, 18.0
        win.view3d.fit()
        finish_3d(win)
        save(win.view3d.grab(), name)


def shot_dialogs(win):
    from khervecad.library import PartLibraryDialog
    dlg = PartLibraryDialog(win.model, win)
    dlg.show()
    settle(300)
    save(dlg.grab(), "dialog_library")
    dlg.close()

    # (no Connect-to-Claude shot: its config snippet shows the local
    # paths of whoever runs this script)

    from khervecad.updater import Release, UpdateDialog, UpdateInfo
    info = UpdateInfo(
        current=(0, 1, 191), sha="08face1", family="windows",
        release=Release(tag="v0.1.200", version=(0, 1, 200),
                        name="KherveCAD v0.1.200"),
        notes="## A tidier toolbar\n\nThe operations are grouped into "
              "drop-down families, and every icon explains itself.",
        changes="### New\n- grouped toolbar with drop-down families and "
                "how-to tips\n- name tree rows from code comments - "
                "Cube [Body]\n\n### Fixed\n- 3D view draws in exact order "
                "without a manual Redraw\n")
    dlg = UpdateDialog(info, "Download and install", win)
    dlg.show()
    settle(300)
    save(dlg.grab(), "dialog_update")
    dlg.close()

    win._chat_dock.show()
    settle(400)
    save(win.chat.grab(), "chat_panel")
    win._chat_dock.hide()

    for title in ("Examples", "Library"):
        menu = next((a.menu() for a in win.menuBar().actions()
                     if a.text().replace("&", "") == title), None)
        if menu is not None:
            menu.ensurePolished()
            menu.adjustSize()
            save(menu.grab(), f"menu_{title.lower()}")


def shot_attach(win):
    """Two Objects and the Attach dialog between them."""
    from khervecad.mates import AttachDialog
    win.model.clear()
    win._dirty = False
    base = win.model.new_component(visible=True)
    win.model.add_node("cube", parent=base)
    top = win.model.new_component(visible=True)
    win.model.add_node("cylinder", parent=top)
    settle(300)
    dlg = AttachDialog(win.model, top, win)
    dlg.show()
    settle(300)
    save(dlg.grab(), "dialog_attach")
    dlg.reject()


def shot_vibe(win):
    """Vibe Model: the 3D view alone, the toggle lit on the toolbar."""
    match = [b for n, _c, b in examples.EXAMPLES if n == "Tulip"]
    if not match:
        return
    examples.load_example(win.model, match[0])
    win._dirty = False
    win.set_vibe_model(True)
    settle(300)
    win.view3d.user_moved = False
    win.view3d.yaw, win.view3d.pitch = 35.0, 18.0
    win.view3d.fit()
    finish_3d(win)
    save(win.grab(), "vibe_model", WIDE)
    win.set_vibe_model(False)
    settle(200)


def shot_stage(win):
    """The platform & shadow stage, set on the widget so the user's
    persisted setting is untouched."""
    load(win, "Desk setup")
    view = win.view3d
    view.stage = True
    view.user_moved = False
    view.yaw, view.pitch = 35.0, 25.0
    view.fit()
    finish_3d(win)
    save(view.grab(), "stage", 900)
    view.stage = False


def shot_sweep(win):
    load(win, "Pipe run & handrail (sweep)")
    wait_exact(win)
    view = win.view3d
    view.user_moved = False
    view.yaw, view.pitch = 30.0, 22.0
    view.fit()
    finish_3d(win)
    save(view.grab(), "sweep", 900)


def shot_fillet(win):
    load(win, "Filleted block (fillet edges)")
    wait_exact(win)
    view = win.view3d
    view.stage = False
    view.user_moved = False
    view.yaw, view.pitch = -50.0, 28.0
    view.fit()
    finish_3d(win)
    save(view.grab(), "fillet", 900)


def shot_pattern(win):
    load(win, "Bolt circle & stair (pattern)")
    wait_exact(win)
    view = win.view3d
    view.stage = False
    view.user_moved = False
    view.yaw, view.pitch = 140.0, 26.0
    view.fit()
    view.distance *= 1.2          # the near stair overhangs a tight fit
    finish_3d(win)
    save(view.grab(), "pattern", 900)


def shot_shell(win):
    load(win, "Hollow cup (shell)")
    wait_exact(win)
    view = win.view3d
    view.stage = False
    view.user_moved = False
    view.yaw, view.pitch = -35.0, 40.0        # look into the cup
    view.fit()
    finish_3d(win)
    save(view.grab(), "shell", 900)


def shot_print_check(win):
    """The print check on a T: the top's underside is an overhang."""
    from khervecad.analysis_dialog import open_analysis
    win.model.clear()
    win._dirty = False
    win.builder.setCurrentIndex(0)
    stem = win.model.add_node("cube", dict(width=6.0, depth=6.0,
                                           height=30.0, x=12.0, y=12.0))
    win.model.add_node("cube", dict(width=30.0, depth=30.0, height=5.0,
                                    z=30.0))
    settle(300)
    dlg = open_analysis(win, "print", nodes=list(win.model.root.children))
    settle(300)
    dlg.show_box.setChecked(True)
    settle(300)
    save(dlg.grab(), "print_check")
    dlg.close()
    settle(100)


SHOTS = [shot_window, shot_toolbars, shot_tutorial, shot_tabs,
         shot_named_rows, shot_sketch, shot_styles, shot_character,
         shot_attach, shot_dialogs, shot_vibe, shot_stage, shot_sweep,
         shot_fillet, shot_pattern, shot_shell, shot_print_check]


def main(only=()):
    win = new_window()
    print(f"OpenSCAD engine: "
          f"{'found' if win.engine.available else 'not found'}")
    failed = []
    for shot in SHOTS:
        if only and shot.__name__.replace("shot_", "") not in only:
            continue
        print(shot.__name__)
        try:
            shot(win)
        except Exception:                       # keep the other shots
            traceback.print_exc()
            failed.append(shot.__name__)
    win._dirty = False
    win.close()
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
