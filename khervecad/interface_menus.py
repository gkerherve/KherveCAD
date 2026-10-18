"""The menu bar of the Fusion and SolidWorks Interface Styles
(toolbar_style.py): the same commands, organised the way that program
organises them.

- **Fusion** has no classic menu bar; its commands live in the File
  menu and the Design workspace's panels. Here they become File, Edit,
  Create, Modify, Assemble, Inspect, Insert, Utilities, View and Help —
  each panel's commands in Fusion's order (Press Pull, Fillet, Chamfer,
  Shell under Modify; Measure, Interference, Zebra, Draft, Section
  Analysis under Inspect...).
- **SolidWorks** has File, Edit, View, Insert, Tools, Window and Help,
  with Insert ▸ Boss/Base, Cut, Features, Pattern/Mirror, Fastening
  Feature, Surface, Curve, and Tools ▸ Sketch Entities, Dimensions,
  Evaluate, Add-Ins, Options.

Nothing is created here: every item is an action of the classic menus
(found by its path, `index`), and a classic submenu named in a layout
comes along whole, filling itself as it always did (Open Recent, the
Library). The classic menus are kept, not deleted, so going back puts
them on the bar again. A test checks that every classic command is
somewhere in each layout (`missing`).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import re

from PyQt5.QtWidgets import QMenu

from . import language


def norm(text):
    """A menu text as a path segment: no mnemonic, shortcut or dots."""
    text = re.sub(r"&(?=[^&])", "", str(text)).replace("&&", "&")
    text = text.split("\t")[0].replace("…", "").replace("...", "")
    return re.sub(r"\s+", " ", text).strip().lower()


#: a layout: [(menu title, [item, ...]), ...]; an item is a classic
#: path "menu/item" (a submenu path brings the whole submenu), "-" for a
#: separator, or (submenu title, [items]) for a new submenu
FUSION = [
    ("&File", [
        "file/new", "file/new window", "file/open", "file/open recent",
        "-", "file/save", "file/save as",
        "-", ("&Export", [
            "file/export openscad", "file/export stl",
            "file/export for other cad (step/iges/rhino)", "-",
            "file/export png", "file/export turntable movie",
            "file/render photo (blender)", "-",
            "file/export animated character (glb)",
            "file/pose character"]),
        ("&3D Print", ["file/publish to printables", "file/export stl"]),
        ("&Share", ["file/publish to printables", "file/send to planetcraft"]),
        "-", "file/show in file explorer",
        "-", "file/exit"]),
    ("&Edit", [
        "edit/undo", "edit/redo", "-", "edit/cut", "edit/copy",
        "edit/paste", "edit/delete", "edit/duplicate", "-", "edit/group",
        "edit/ungroup", "edit/move up", "edit/move down"]),
    ("&Create", [
        "insert/new object", ("Create &Sketch", ["insert/2d shapes"]),
        "-", "tools/extrude/linear extrude", "tools/extrude/rotate extrude",
        "tools/extrude/sweep along path",
        "tools/extrude/loft through sections",
        "-", "insert/mechanical features/hole (counterbore, countersink, "
        "nut trap)", "insert/mechanical features/thread (screw thread)",
        "-", "insert/3d solids/cube", "insert/3d solids/cylinder",
        "insert/3d solids/sphere", "insert/3d solids", "-",
        ("&Pattern", ["insert/repeat & logic/pattern (linear / polar / "
                      "grid)", "insert/repeat & logic/scatter on surface",
                      "insert/repeat & logic/for loop"]),
        "tools/move & transform/mirror", "-",
        ("Create &Form", ["insert/subd box (smooth, edit its cage)",
                          "tools/convert to subd (smooth cage)",
                          "tools/edit vertices (edit mode)"]),
        ("S&urface", ["tools/surface from curves",
                      "insert/draw 3d curve (click points)"]),
        "insert/mechanical features", "insert/shapes & patterns",
        "insert/repeat & logic"]),
    ("&Modify", [
        "tools/finish/push / pull faces", "tools/finish/fillet edges",
        "tools/finish/bevel edges", "tools/deform & sculpt/shell (hollow)",
        "tools/move & transform/scale", "tools/combine",
        "tools/finish/bisect (knife)", "-", "tools/move & transform",
        "tools/finish/hull", "tools/finish/minkowski (round edges)", "-",
        "tools/deform & sculpt", "tools/character",
        "tools/edit vertices (edit mode)", "-",
        "view/customizer (sliders)", "edit/document units",
        "edit/document scale (1 : n)"]),
    ("&Assemble", [
        "insert/new object", "tools/snap objects",
        "view/gumball (move / turn handles)", "-", "view/exploded view",
        "view/animate ($t)"]),
    ("I&nspect", [
        "tools/measure & annotate/measure distance",
        "analyse/check interference", "-", "analyse/heat map",
        "view/cut through", "-", "analyse/mass properties",
        "analyse/check for 3d printing", "analyse/check sharp edges",
        "analyse/check fits & tolerances", "analyse/check welds", "-",
        "tools/measure & annotate/add dimension",
        "view/dimensions on selection", "view/clear dimensions",
        "view/compare to reference image (overlay)"]),
    ("&Insert", [
        "file/import openscad", "file/import mesh (stl/obj/off/3mf)",
        "file/import cad file (step/iges/rhino)",
        "file/import 2d drawing (svg/dxf)",
        "file/import height map (surface)",
        "file/import animated character (glb)", "-",
        "view/add reference image", "view/clear reference images", "-",
        "insert/part library", "library", "insert/code & files", "-",
        ("&Builders", [
            "tools/house builder", "tools/city builder",
            "tools/human builder", "tools/car builder",
            "tools/lego builder", "tools/crystal builder",
            "tools/compound builder", "tools/chemistry builder", "-",
            "tools/add a figure"])]),
    ("U&tilities", [
        ("&Drawing", ["file/blueprint (2d drawing)",
                      "file/bill of materials",
                      "file/p&id (process diagram)",
                      "file/make 2d drawing of this view"]),
        ("&Make", ["file/publish to printables", "file/export stl"]),
        ("&Add-Ins", ["ai", "git"]),
        "-", "edit/locate openscad", "edit/language"]),
    ("&View", [
        "view/grid", "view/snap", "view/vibe model", "-",
        "view/zoom in", "view/zoom out", "view/reset 2d zoom",
        "view/fit sketch", "view/zoom to selection", "view/fit 3d view",
        "-", "view/3d camera", "view/3d projection", "view/3d render style",
        "view/3d background", "-", "view/3d platform and shadow",
        "view/3d cavity shading", "view/3d edge lines",
        "view/3d scale bar", "view/3d ground grid",
        "view/3d smooth shading", "view/3d hardware rendering (opengl)",
        "-", "view/theme", "view/interface style"]),
    ("&Help", ["help"]),
]

SOLIDWORKS = [
    ("&File", [
        "file/new", "file/new window", "file/open", "file/open recent",
        "-", "file/save", "file/save as",
        ("&Export", [
            "file/export openscad", "file/export stl",
            "file/export for other cad (step/iges/rhino)",
            "file/export animated character (glb)",
            "file/pose character"]),
        "-", "file/blueprint (2d drawing)",
        "file/make 2d drawing of this view", "-",
        ("Print&3D", ["file/publish to printables", "file/export stl"]),
        ("Pu&blish", ["file/publish to printables",
                      "file/send to planetcraft"]),
        "-", "file/show in file explorer", "-", "file/exit"]),
    ("&Edit", [
        "edit/undo", "edit/redo", "-", "edit/cut", "edit/copy",
        "edit/paste", "edit/delete", "-", "edit/duplicate", "edit/group",
        "edit/ungroup", "edit/move up", "edit/move down"]),
    ("&View", [
        ("&Display", ["view/3d render style", "view/3d background", "-",
                      "view/3d cavity shading", "view/3d edge lines",
                      "view/3d smooth shading",
                      "view/3d platform and shadow",
                      "view/3d hardware rendering (opengl)", "-",
                      "view/exploded view", "view/cut through"]),
        ("&Modify", ["view/zoom in", "view/zoom out", "view/reset 2d zoom",
                     "view/fit sketch", "view/zoom to selection",
                     "view/fit 3d view", "-",
                     "view/gumball (move / turn handles)"]),
        ("&Lights and Cameras", ["view/3d camera", "view/3d projection"]),
        ("&Hide / Show", ["view/grid", "view/snap", "view/3d ground grid",
                          "view/3d scale bar", "-",
                          "view/dimensions on selection",
                          "view/clear dimensions", "-",
                          "view/add reference image",
                          "view/clear reference images",
                          "view/compare to reference image (overlay)"]),
        ("&User Interface", ["view/theme", "view/interface style",
                             "view/vibe model"]),
        ("Screen &Capture", ["file/export png",
                             "file/export turntable movie",
                             "file/render photo (blender)"])]),
    ("&Insert", [
        ("&Boss/Base", ["tools/extrude/linear extrude",
                        "tools/extrude/rotate extrude",
                        "tools/extrude/sweep along path",
                        "tools/extrude/loft through sections",
                        "tools/finish/push / pull faces"]),
        ("&Cut", ["tools/combine/difference", "tools/finish/bisect (knife)",
                  "tools/combine/intersection"]),
        ("&Features", ["tools/finish/fillet edges",
                       "tools/finish/bevel edges",
                       "tools/deform & sculpt/shell (hollow)",
                       "tools/move & transform/scale", "-",
                       "tools/combine", "tools/finish/hull",
                       "tools/finish/minkowski (round edges)", "-",
                       "tools/deform & sculpt", "tools/move & transform"]),
        ("&Pattern/Mirror", [
            "tools/move & transform/mirror",
            "insert/repeat & logic/pattern (linear / polar / grid)",
            "insert/repeat & logic/scatter on surface"]),
        ("Fas&tening Feature", ["insert/mechanical features"]),
        ("&Surface", ["tools/surface from curves",
                      "insert/subd box (smooth, edit its cage)",
                      "tools/convert to subd (smooth cage)"]),
        ("Cur&ve", ["insert/draw 3d curve (click points)",
                    "insert/shapes & patterns/3d curve"]),
        "-", "insert/new object", "insert/part library", "library", "-",
        ("S&ketch", ["insert/2d shapes"]), "insert/3d solids",
        "insert/shapes & patterns", "insert/repeat & logic",
        "insert/code & files", "tools/character", "-",
        ("&Import", ["file/import openscad",
                     "file/import mesh (stl/obj/off/3mf)",
                     "file/import cad file (step/iges/rhino)",
                     "file/import 2d drawing (svg/dxf)",
                     "file/import height map (surface)",
                     "file/import animated character (glb)"]),
        "view/add reference image"]),
    ("&Tools", [
        ("Sketch &Entities", ["insert/2d shapes"]),
        ("&Dimensions", ["tools/measure & annotate/add dimension",
                         "view/dimensions on selection",
                         "view/clear dimensions"]),
        "tools/edit vertices (edit mode)", "-",
        "tools/measure & annotate/measure distance",
        "analyse/mass properties",
        ("E&valuate", ["analyse/check for 3d printing",
                       "analyse/check interference",
                       "analyse/check sharp edges",
                       "analyse/check fits & tolerances",
                       "analyse/check welds", "analyse/heat map"]),
        "-", "tools/snap objects", "-",
        ("&Applications", [
            "tools/house builder", "tools/city builder",
            "tools/human builder", "tools/car builder",
            "tools/lego builder", "tools/crystal builder",
            "tools/compound builder", "tools/chemistry builder", "-",
            "tools/add a figure"]),
        ("Engineering &Documents", ["file/bill of materials",
                                    "file/p&id (process diagram)",
                                    "file/blueprint (2d drawing)"]),
        "view/customizer (sliders)", "view/animate ($t)", "-",
        ("Add-&Ins", ["ai", "git"]),
        ("&Options", ["edit/document units", "edit/document scale (1 : n)",
                      "edit/locate openscad", "edit/language"])]),
    ("&Window", [
        "file/new window", "-", "view/customizer (sliders)",
        "ai/chatbox (requires api key)", "view/vibe model"]),
    ("&Help", ["help"]),
]

LAYOUTS = {"Fusion": FUSION, "SolidWorks": SOLIDWORKS}


def classic_menus(win):
    """The classic top-level menu actions, remembered the first time."""
    got = getattr(win, "_classic_menu_actions", None)
    if got is None:
        got = [a for a in win.menuBar().actions() if a.menu() is not None]
        win._classic_menu_actions = got
    return got


def index(win):
    """path -> QAction for every item and submenu of the classic menus
    (a submenu's path gives its menu action). Library submenus are not
    walked: the Library comes along whole."""
    paths = {}

    def walk(menu, prefix):
        for act in menu.actions():
            if act.isSeparator():
                continue
            path = prefix + "/" + norm(act.text())
            paths.setdefault(path, act)
            if act.menu() is not None and prefix != "library":
                walk(act.menu(), path)

    for top in classic_menus(win):
        name = norm(top.text())
        paths[name] = top
        walk(top.menu(), name)
    return paths


def unresolved(win, layout):
    """Paths in *layout* that name nothing (a renamed classic item)."""
    paths = index(win)
    bad = []

    def walk(items):
        for item in items:
            if isinstance(item, tuple):
                walk(item[1])
            elif item != "-" and item not in paths:
                bad.append(item)
    for _title, items in layout:
        walk(items)
    return bad


def _add(menu, item, paths):
    if item == "-":
        menu.addSeparator()
    elif isinstance(item, tuple):
        title, items = item
        sub = menu.addMenu(language.tr(title))
        sub.setToolTipsVisible(True)
        for it in items:
            _add(sub, it, paths)
    else:
        act = paths.get(item)
        if act is None:
            return
        if act.menu() is not None and "/" not in item:
            # a whole classic top menu inside a new one (Help, AI, Git,
            # the Library) — its items, or itself as a submenu
            menu.addMenu(act.menu())
        else:
            menu.addAction(act)


def build(win, style):
    """Put *style*'s menu bar up (the classic one for the default)."""
    bar = win.menuBar()
    classic = classic_menus(win)
    for menu in getattr(win, "_style_menus", []):
        menu.deleteLater()
    win._style_menus = []
    _clear(bar)
    layout = LAYOUTS.get(style)
    if layout is None:
        for act in classic:
            bar.addAction(act)
        return
    paths = index(win)
    for title, items in layout:
        if items == ["help"]:
            help_menu = paths["help"].menu()
            bar.addMenu(help_menu)
            continue
        menu = QMenu(language.tr(title), bar)
        menu.setToolTipsVisible(True)
        for item in items:
            _add(menu, item, paths)
        bar.addMenu(menu)
        win._style_menus.append(menu)
    hover = getattr(win, "_menu_hover", None)
    if hover is not None:
        for menu in win._style_menus:
            hover.hook(menu)


def _clear(bar):
    """Take every menu off the bar without deleting any (the classic
    menus must survive a style switch)."""
    for act in bar.actions():
        bar.removeAction(act)


def leaves(menu, seen=None):
    """Every command reachable from *menu*, through its submenus."""
    seen = set() if seen is None else seen
    out = set()
    if id(menu) in seen:
        return out
    seen.add(id(menu))
    for act in menu.actions():
        if act.isSeparator():
            continue
        if act.menu() is not None:
            out.add(act)
            out |= leaves(act.menu(), seen)
        else:
            out.add(act)
    return out


def missing(win):
    """Classic commands the current menu bar cannot reach."""
    shown = set()
    for act in win.menuBar().actions():
        if act.menu() is not None:
            shown |= leaves(act.menu())
            shown.add(act)
    names = {norm(a.text()) for a in shown}
    lost = []
    for top in classic_menus(win):
        if top in shown:
            continue
        for act in leaves(top.menu()):
            if act.menu() is None and act not in shown and act.isVisible() \
                    and act.text() and norm(act.text()) not in names:
                # (a classic menu's copy of a command shown elsewhere —
                # Tools' Blueprint is File's — counts as shown)
                lost.append(norm(top.text()) + "/" + norm(act.text()))
    return lost
