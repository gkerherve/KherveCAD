"""The ribbon the Fusion and SolidWorks Interface Styles put under the
quick-access row (toolbar_style.py): the horizontal bar's tools on tabs.

Both styles share the tabs and their panels (`TABS`, `PANELS`) and lay a
panel out the way the program they imitate does:

- **Fusion** — tabs on top (SOLID, FORM...), a workspace button at the
  left; each panel is a row of icons with its name underneath in
  capitals and a ▾ that lists the whole panel.
- **SolidWorks** — the CommandManager: the panel's first tool a large
  button with its name under it, the rest small buttons with their
  names beside them in columns of three, a line between panels, the tabs
  underneath. When the window is too narrow for the names the small
  buttons drop them (SolidWorks does the same).

Nothing here owns an action: the buttons show the window's own actions
(`toolbars.make_bar_actions`), so a ribbon can be thrown away and built
again at any time.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import re

from PyQt5.QtCore import QSettings, QSize, Qt, QTimer
from PyQt5.QtWidgets import (QAction, QFrame, QGridLayout, QHBoxLayout,
                             QMenu, QSizePolicy, QStackedWidget, QTabBar,
                             QToolButton, QVBoxLayout, QWidget)

from . import icons, language, toolbars, tooltips

_SETTINGS = ("Kherve", "KherveCAD")
TAB_KEY = "ribbon/tab"

#: (key, Fusion title, SolidWorks title, panel keys)
TABS = [
    # the vertical bar's tools live on the ribbon too (2026-10-19, the
    # user: Fusion has no tool column — sketching is a tab of its own)
    # grouped like Fusion's SKETCH tab (CREATE / MODIFY / INSERT)
    ("sketch", "SKETCH", "Sketch", ["sketch", "sketch_shapes",
                                    "sketch_modify", "sketch_constrain",
                                    "sketch_insert"]),
    # (2026-10-20, the user asked for a check that every menu command is
    # on the ribbon, grouped where Fusion would put it: the mechanical
    # features, a SURFACE tab, SubD in FORM, figures in CHARACTER, the
    # assembly tools, imports, Shell in MODIFY)
    ("features", "SOLID", "Features",
     ["create", "extrude", "cuts", "mechanical", "transform",
      "combine", "finish", "logic", "assemble", "solid_insert",
      "document"]),
    ("surface", "SURFACE", "Surfaces", ["curves", "surfaces"]),
    ("form", "FORM", "Sculpt", ["form_create", "deform", "edit"]),
    ("character", "CHARACTER", "Character", ["figures", "character"]),
    ("inspect", "INSPECT", "Evaluate",
     ["analyse", "checks", "dimension"]),
    # everything that turns the model into something handed on —
    # drawings, files, pictures (2026-10-20, the user: "something called
    # publish ... the blueprint, the P&ID, publish to Printables, the
    # export to videos"; the drawings had wandered INSPECT -> UTILITIES)
    ("publish", "PUBLISH", "Publish",
     ["documents", "pub_share", "pub_media"]),
    ("utilities", "UTILITIES", "Utilities",
     ["util_addins", "util_utility"]),
    # every builder window (2026-10-19, the user: "where are all the
    # builders?") — the Tools menu's Builders section
    ("build", "BUILD", "Builders", ["builders"]),
]

#: panels that are not operation families: key -> title
EXTRA_PANELS = {"cuts": "Cut", "pub_share": "Share", "pub_media": "Pictures & video",
                "util_make": "Make", "util_addins": "Add-ins",
                "util_utility": "Utility", "assemble_more": "Assemble", "mechanical": "Features", "_mechanical_menu": "Features", "_move_tools": "Move", "curves": "Curves",
                "surfaces": "From curves", "form_create": "Create form",
                "figures": "Figures", "solid_insert": "Insert",
                "sketch_shapes": "Shapes", "shapes3d": "Shapes",
                "document": "Document", "checks": "Evaluate", "dimension": "Dimension",
                "builders": "Builders", "sketch": "Create", "create": "Create",
                "sketch_modify": "Modify", "sketch_insert": "Insert",
                "sketch_constrain": "Constraints",
                "assemble": "Assemble", "edit": "Edit mesh",
                "analyse": "Analyse", "documents": "Drawings"}
#: SolidWorks panels whose tools are all large buttons
ALL_LARGE = {"builders", "edit", "analyse", "documents"}

#: icon sizes (px)
FUSION_ICON = QSize(26, 26)
SW_LARGE = QSize(30, 30)
SW_SMALL = QSize(18, 18)
#: icons a Fusion panel shows before the rest wait in its ▾ menu, by
#: how many panels share the tab (a tab of one panel has room for more)
FUSION_SHOWN = {1: 12, 2: 7}
#: the Inspect menu's other commands on the INSPECT tab (2026-10-19,
#: the user: the menu had far more than the tab): classic menu path,
#: glyph for an item that has no icon of its own
MENU_PANELS = {
    "checks": [("analyse/heat map", "mdi.thermometer"),
               ("analyse/check sharp edges", "mdi.angle-acute"),
               ("analyse/check fits & tolerances", "mdi.arrow-collapse-horizontal"),
               ("analyse/check welds", "mdi.fire"),
               ("view/compare to reference image (overlay)",
                "mdi.image-filter-center-focus")],
    # Insert ▸ Shapes & patterns on the ribbon too (the user, same day)
    "sketch_shapes": [
        ("insert/shapes & patterns/regular polygon / star", None),
        ("insert/shapes & patterns/rounded polygon (radius per corner)",
         "mdi.vector-polygon"),
        ("insert/shapes & patterns/bézier shape (closed)", None),
        ("insert/shapes & patterns/svg path shape", None),
        ("insert/shapes & patterns/honeycomb panel (2d)", None)],
    "shapes3d": [("insert/shapes & patterns/3d curve", None),
                 ("insert/shapes & patterns/regular polyhedron", None)],
    "mechanical": [
        ("insert/mechanical features/hole (counterbore, countersink, "
         "nut trap)", None),
        ("insert/mechanical features/thread (screw thread)", None),
        ("insert/mechanical features/gear (involute)", None),
        ("insert/mechanical features/knurled cylinder", None),
        ("insert/mechanical features/textured cylinder / panel", None),
        ("insert/code & files/sheet metal part", None)],
    "curves": [("insert/draw 3d curve (click points)", None),
               ("insert/shapes & patterns/3d curve", None)],
    # six kinds of one node: each its own picture ("!" = always)
    "surfaces": [("tools/surface from curves/" + t, g) for t, g in (
        ("loft — a skin through the curves, in order", "!mdi.vector-curve"),
        ("sweep — first curve is the rail, the rest are profiles",
         "!mdi.vector-polyline"),
        ("sweep along two rails — first two curves are rails",
         "!mdi.vector-line"),
        ("patch — fill inside the first (closed) curve",
         "!mdi.texture-box"),
        ("revolve — turn the curve about the z axis",
         "!mdi.rotate-3d-variant"),
        ("extrude — push the curve straight up", "!mdi.arrow-expand-up"))],
    "form_create": [("insert/subd box (smooth, edit its cage)", None),
                    ("tools/convert to subd (smooth cage)", None)],
    "figures": [("tools/add a figure/human figure", None),
                ("tools/add a figure/skin (body round a skeleton)", None)],
    "solid_insert": [
        ("insert/part library", None),
        ("file/import openscad", "mdi.code-braces-box"),
        ("file/import mesh (stl/obj/off/3mf)", "mdi.cube-scan"),
        ("file/import cad file (step/iges/rhino)", None),
        ("file/import height map (surface)", None),
        ("file/import image stack (tiff)", None),
        ("file/import animated character (glb)", None),
        ("view/add reference image", None),
        ("view/clear reference images", "mdi.image-remove"),
        ("insert/code & files", None)],
    "assemble_more": [
        ("insert/new object", None),
        ("view/exploded view", None),
        ("view/animate ($t)", None)],
    # Snap and the Gumball beside Translate: they move parts too (the user)
    "_move_tools": [("view/gumball (move / turn handles)", None)],
    "pub_share": [("file/publish to printables", None),
                  ("file/export stl", None),
                  ("file/export for other cad (step/iges/rhino)", None),
                  ("file/export openscad", None),
                  ("file/export animated character (glb)", None),
                  ("file/send to planetcraft", None)],
    "pub_media": [("file/export png", None),
                  ("file/export turntable movie", None),
                  ("file/render photo (blender)", None)],
    "util_addins": [("ai/connect to claude (simple)", None),
                    ("ai/chatbox (requires api key)", None),
                    ("ai/mesh from photo", None),
                    ("git/commit", None), ("git/push", None),
                    ("git/pull", None),
                    ("git/connect to github / gitlab", None)],
    "util_utility": [("edit/locate openscad", None),
                     ("edit/language", None)],
    "document": [("edit/common segments ($fn)", "kc:common_segments"),
                 ("edit/document units", "mdi.ruler-square"),
                 ("edit/document scale (1 : n)", "mdi.scale-balance"),
                 ("view/customizer (sliders)", None),
                 ("edit/configurations", "kc:configurations")],
    "dimension": [("tools/measure & annotate/add dimension", None),
                  ("view/show dimensions", "mdi.ruler"),
                  ("view/clear dimensions", "mdi.eraser")],
}
#: panels whose tools all show, names under the icons (few, big tools)
FUSION_NAMED = {"builders"}
#: panels whose every tool shows as an icon (the INSPECT tab has room)
FUSION_ALL = {"analyse", "checks", "dimension",
              "sketch_shapes", "shapes3d"}
FUSION_SHOWN_MANY = 4
#: icons shown by panels with a count of their own
PANEL_SHOWN = {"sketch": 12, "sketch_modify": 10, "sketch_constrain": 15}
#: the sketch MODIFY panel: operations from the families, in this order
SKETCH_MODIFY = ["translate", "rotate", "scale", "mirror", "pattern"]

#: tips for the analysis actions made here (the menu items they copy
#: have none of their own)
_TIPS = {
    "mass_properties": (
        "Mass properties",
        "Volume, surface area, centre of mass and mass of the selection "
        "(else of the whole document) in the material you pick.",
        ["Select a part (or nothing for everything).",
         "Click Mass properties and pick a material."], None),
    "print_check": (
        "Check for 3D printing",
        "Is the part watertight, how much overhangs past the angle, "
        "where are the walls thinner than the nozzle can print?",
        ["Select the part.", "Click, then show the faults on the model."],
        None),
    "interference": (
        "Check interference",
        "Do these parts overlap, touch or sit inside each other? With "
        "fewer than two selected, every part in Main is checked.",
        ["Select two or more parts (or none).", "Click."], None),
}
for _key, _tip in _TIPS.items():
    tooltips.TIPS.setdefault(_key, _tip)


def analysis_actions(win):
    """Mass properties, the print check and interference as actions —
    made once per window, like the Analyse menu's items they copy."""
    acts = getattr(win, "_ribbon_actions", None)
    if acts is not None:
        return acts
    from .analysis_dialog import open_analysis
    acts = []
    for glyph, text, key, kind in (
            ("mdi.scale-balance", "Mass properties", "mass_properties",
             "mass"),
            ("mdi.printer-3d-nozzle-outline", "Print check", "print_check",
             "print"),
            ("mdi.vector-intersection", "Interference", "interference",
             "interference")):
        act = QAction(icons.icon(glyph, icons.family_color("measure")),
                      language.tr(text), win)
        act.setData(key)
        toolbars.remember_glyph(act, glyph, "measure")
        tooltips.apply(act, key)
        act.triggered.connect(lambda _=False, k=kind: open_analysis(win, k))
        acts.append(act)
    win._ribbon_actions = acts
    return acts


def sketch_extra(win):
    """Offset (the sketch's own MODIFY tool, in no family) and Import
    2D drawing — made once per window."""
    acts = getattr(win, "_sketch_actions", None)
    if acts is not None:
        return acts
    from .model import NODE_TYPES
    spec = NODE_TYPES["offset"]
    acts = {}
    for key, glyph, text, slot, family in (
            ("offset", spec["icon"], spec["label"],
             lambda: win._apply_operation("offset"), "transform"),
            ("import_2d", "mdi.svg", "Import 2D drawing",
             win.import_drawing, "draw")):
        act = QAction(icons.icon(glyph, icons.family_color(family)),
                      language.tr(text), win)
        act.setData(key)
        toolbars.remember_glyph(act, glyph, family)
        tooltips.apply(act, key)
        act.triggered.connect(lambda _=False, f=slot: f())
        acts[key] = act
    win._sketch_actions = acts
    return acts


def style_of(win):
    return getattr(win, "_interface_style", "")


def self_style(win):
    style = getattr(win, "_interface_style", "Fusion")
    return style if style in ("Fusion", "SolidWorks") else "Fusion"


#: a painted icon for a menu command that has no key of its own, or
#: shares one (the six surfaces from curves are one node): path -> key
PAINT = {
    "file/export for other cad (step/iges/rhino)": "export_cad",
    "file/export openscad": "export_scad",
    "file/export animated character (glb)": "export_glb",
    "file/send to planetcraft": "planetcraft",
    "file/export png": "export_png",
    "file/export turntable movie": "export_movie",
    "file/render photo (blender)": "render_photo",
    "file/make 2d drawing of this view": "make2d",
    "file/publish to printables": "printables",
    "file/export stl": "export_stl",
    "ai/connect to claude (simple)": "claude_connect",
    "ai/chatbox (requires api key)": "chatbox",
    "ai/mesh from photo": "photo3d",
    "git/commit": "git_commit",
    "git/push": "git_push",
    "git/pull": "git_pull",
    "git/connect to github / gitlab": "git_remote",
    "edit/locate openscad": "locate_openscad",
    "edit/language": "language",
    "insert/new object": "new_object",
    "view/gumball (move / turn handles)": "gumball",
    "view/exploded view": "explode",
    "view/animate ($t)": "animate",
    "insert/part library": "part_library",
    "file/import openscad": "import_scad",
    "file/import mesh (stl/obj/off/3mf)": "import_mesh",
    "file/import cad file (step/iges/rhino)": "import_cad",
    "file/import height map (surface)": "import_heightmap",
    "file/import image stack (tiff)": "import_stack",
    "file/import animated character (glb)": "import_glb",
    "view/add reference image": "ref_add",
    "view/clear reference images": "ref_clear",
    "insert/code & files": "code_files",
    "edit/document units": "doc_units",
    "edit/configurations": "configurations",
    "edit/document scale (1 : n)": "doc_scale",
    "view/customizer (sliders)": "customizer",
    "analyse/heat map": "heatmap",
    "analyse/check sharp edges": "sharp_edges",
    "analyse/check fits & tolerances": "fits",
    "analyse/check welds": "welds",
    "view/compare to reference image (overlay)": "ref_compare",
    "view/show dimensions": "dims_selection",
    "view/clear dimensions": "dims_clear",
    "insert/subd box (smooth, edit its cage)": "subd_box",
    "tools/convert to subd (smooth cage)": "subd_convert",
}
for _t, _k in (("loft — a skin through the curves, in order", "srf_loft"),
               ("sweep — first curve is the rail, the rest are profiles",
                "srf_sweep"),
               ("sweep along two rails — first two curves are rails",
                "srf_sweep2"),
               ("patch — fill inside the first (closed) curve", "srf_patch"),
               ("revolve — turn the curve about the z axis", "srf_revolve"),
               ("extrude — push the curve straight up", "srf_extrude")):
    PAINT["tools/surface from curves/" + _t] = _k


def _painted(win, acts):
    """Every action with a drawing in this style (icons_cad*) wears it —
    the user: all icons remade in Fusion's / SolidWorks' look, never a
    recoloured glyph. The classic icon is kept for the way back."""
    from . import icons_cad
    style = self_style(win)
    classic = win.__dict__.setdefault("_classic_icons", {})
    for act in acts:
        key = act.property("kc_paint") or act.data()
        if not isinstance(key, str):
            continue
        # toolbar_style.restyle_icons already painted a bar action; and
        # an icon set twice makes every button on the action take its
        # whole text again (a shared Shell lost its short name)
        # (only skip what is painted in THIS style already: an action made
        # while the ribbon is built — the Cut panel's — came after
        # restyle_icons and kept its red glyph, 2026-10-25)
        if act.property("kc_painted") == style:
            continue
        art = icons_cad.icon(key, style)
        if art is None:
            continue
        classic.setdefault(act, act.icon())
        if not act.property("kc_glyph"):
            act.setProperty("kc_glyph", "painted")
        act.setProperty("kc_paint", key)
        act.setProperty("kc_painted", style)
        act.setIcon(art)
    return acts


def _helped(acts):
    """Every ribbon button shows its detail help card on hover (the
    user: the new icons had only their name) — the tool's own tip, else
    the menu item's help card, else its status line."""
    from . import menu_help
    for act in acts:
        if "<" in (act.toolTip() or ""):
            continue                       # a rich card already
        key = act.property("kc_paint") or act.data()
        if isinstance(key, str) and key in tooltips.TIPS:
            tooltips.apply(act, key)
            continue
        card = menu_help.resolve(act)
        if card:
            act.setToolTip(card)
        elif act.statusTip():
            act.setToolTip("<b>%s</b><br>%s" % (
                short_name(act.text()), act.statusTip()))
    return acts


def panel_actions(win, key):
    """(title, actions) of panel *key*, in the style's painted icons,
    each with its help card."""
    title, acts = _panel_actions(win, key)
    return title, _helped(_painted(win, acts))


def _panel_actions(win, key):
    """(title, actions) of panel *key*."""
    parts = win._bar_parts
    families = dict(parts["families"])
    if key == "finish":                # Fusion's MODIFY holds Shell too
        acts = list(families.get("finish", []))
        shell = [a for _k, fam in parts["families"] for a in fam
                 if a.data() == "shell"]
        return language.tr(tooltips.GROUPS.get("finish", ("Finish", ""))[0]
                           ), acts + [a for a in shell if a not in acts]
    if key in families:
        title = tooltips.GROUPS.get(key, (key, ""))[0]
        if key == "extrude":
            from . import drag_feature
            return language.tr(title), list(families[key]) + [
                drag_feature.action(win)]
        if key == "transform":
            # Translate's neighbours: the Gumball and Snap move parts too
            return language.tr(title), list(families[key]) + \
                _panel_actions(win, "_move_tools")[1] + [parts["snap"]]
        return language.tr(title), families[key]
    title = language.tr(EXTRA_PANELS[key])
    if key == "assemble":
        return title, panel_actions(win, "assemble_more")[1]
    from .view2d import MEASURE
    if key == "sketch":
        from . import sketch_mode
        from .view2d import SELECT
        # ONE Sketch Mode button does create / edit / on a face (the
        # user); Select is the tab's first button already
        first = [sketch_mode.create_action(win)] \
            if style_of(win) in ("Fusion", "SolidWorks") else []
        if style_of(win) == "SolidWorks":
            # Smart Dimension, a large button RIGHT of Sketch (the user)
            first = first + [a for a in win._tool_group.actions()
                             if a.data() == "con_dimension"][:1]
        tools = [a for a in win._tool_group.actions()
                 if a.data() not in (MEASURE, SELECT)
                 and not str(a.data()).startswith(("con_", "sk_"))]
        # Create Region first, before Line (the user)
        tools.sort(key=lambda a: a.data() != "make_region")
        return title, first + tools
    if key == "cuts":
        # SolidWorks' Extruded / Revolved / Swept / Lofted / Boundary Cut
        from . import cut_feature, hole_wizard
        acts = _painted(win, list(cut_feature.actions(win)) +
                        [hole_wizard.action(win)])
        acts = acts[:-1]
        # the Hole Wizard sits with the cuts, after Extruded Cut, as on
        # SolidWorks' ribbon (the user)
        return title, acts[:1] + [hole_wizard.action(win)] + acts[1:]
    if key == "mechanical":
        # the mechanical parts (gears, threads, knurls…); the Hole Wizard
        # is in the Cut panel now
        return title, _panel_actions(win, "_mechanical_menu")[1]
    if key == "_mechanical_menu":
        key = "mechanical"
    if key in MENU_PANELS:
        from .interface_menus import index
        paths = index(win)
        acts = []
        for path, glyph in MENU_PANELS[key]:
            act = paths.get(path)
            if act is None:
                continue
            if path in PAINT and act.property("kc_paint") != PAINT[path]:
                act.setProperty("kc_paint", PAINT[path])
                act.setProperty("kc_painted", None)   # paint it afresh
            if glyph and glyph.startswith("!"):
                act.setIcon(icons.icon(glyph[1:], icons.family_color(
                    "extrude")))
            elif glyph and glyph.startswith("kc:"):
                from . import icons_cad
                act.setData(glyph[3:])
                painted = icons_cad.icon(glyph[3:], self_style(win))
                if painted is not None:
                    act.setIcon(painted)
                toolbars.remember_glyph(act, "mdi.circle-slice-8",
                                        "measure")
            elif act.icon().isNull() and glyph:
                family = "draw" if key.startswith("sketch") else "measure"
                act.setIcon(icons.icon(glyph, icons.family_color(family)))
                toolbars.remember_glyph(act, glyph, family)
            acts.append(act)
        return title, acts
    if key == "sketch_modify":
        ops = {a.data(): a for _k, fam in parts["families"] for a in fam}
        from . import sketch_modify, sketch_tools2
        return title, [sketch_tools2.construction_action(win)] + \
            list(sketch_modify.panel_actions(win)) + [
            sketch_extra(win)["offset"]] + [
            ops[k] for k in SKETCH_MODIFY if k in ops]
    if key == "sketch_constrain":
        from . import sketch_constrain_ui
        acts = list(sketch_constrain_ui.panel_actions(win))
        if style_of(win) == "SolidWorks":
            # Smart Dimension sits beside Sketch, not here (the user)
            acts = [a for a in acts
                    if a.data() != sketch_constrain_ui.DIMENSION]
        return title, acts
    if key == "sketch_insert":
        return title, [sketch_extra(win)["import_2d"]]
    if key == "builders":
        return title, list(getattr(win, "_builder_actions", []))
    if key == "create":
        drawing = set(win._tool_group.actions())
        return title, [a for a in win._tools_bar.actions()
                       if not a.isSeparator() and a not in drawing
                       and a.text() and a.data() is not None
                       and a.data() != "house_builder"] \
            + panel_actions(win, "shapes3d")[1]   # 3D curve, polyhedron
    if key == "edit":
        return title, [win._edit_mesh_act]
    if key == "documents":
        from .interface_menus import index
        make2d = index(win).get("file/make 2d drawing of this view")
        extra = []
        if make2d is not None:
            make2d.setProperty("kc_paint", "make2d")
            extra.append(make2d)
        return title, list(parts["docs"]) + extra
    # analyse: the measure tool of the vertical bar, the three checks
    # and a section (Cut Through)
    measure = [a for a in win._tool_group.actions() if a.data() == MEASURE]
    return title, measure + analysis_actions(win) + [win._cut_tool_act]


def short_name(text):
    """A button's name without its explanation in brackets: "Resize
    (absolute size)" is "Resize" (the tooltip keeps the whole)."""
    text = text.split("\t")[0]           # a menu item's shortcut
    # a menu item's mnemonic ("New &Object", "Export S&TL"); "&&" is a
    # real "&" ("P&&ID")
    text = text.replace("&&", "\0").replace("&", "").replace("\0", "&")
    text = text.split(" — ")[0]          # "Loft — a skin through ..."
    text = re.sub(r"(\.\.\.|…)\s*$", "", text)   # and its dots
    return re.sub(r"\s*\(.*\)\s*$", "", text) or text


def _plain(text):
    """*text* shown as written on a button: "P&ID" keeps its "&"."""
    return text.replace("&", "&&")


def _button(action, size, style, parent):
    b = QToolButton(parent)
    b.setDefaultAction(action)
    b.setIconSize(size)
    b.setToolButtonStyle(style)
    b.setAutoRaise(True)
    if action.menu() is not None:      # a submenu (Heat Map): opens on click
        b.setPopupMode(QToolButton.InstantPopup)
        b.setStyleSheet("QToolButton::menu-indicator { image: none; }")
    if style != Qt.ToolButtonIconOnly:
        text = short_name(action.text())
        if style == Qt.ToolButtonTextUnderIcon:
            text = two_lines(text)
        b.setText(_plain(text))
    return b


def two_lines(text, width=10):
    """A long name under an icon on two lines, broken at the space
    nearest its middle ("Extruded Boss/Base" -> "Extruded\nBoss/Base"),
    so a large button stays narrow."""
    if len(text) <= width or " " not in text:
        return text
    spaces = [i for i, c in enumerate(text) if c == " "]
    cut = min(spaces, key=lambda i: abs(i - len(text) / 2))
    return text[:cut] + "\n" + text[cut + 1:]


def _separator(parent):
    line = QFrame(parent)
    line.setObjectName("panelSep")
    line.setFrameShape(QFrame.VLine)
    line.setFrameShadow(QFrame.Plain)
    return line


class Ribbon(QWidget):
    """Tabs of panels over (Fusion) or above (SolidWorks) their tabs."""

    def __init__(self, win, style: str, parent=None):
        super().__init__(parent)
        self.setObjectName("ribbon")
        self.win = win
        self.style_name = style
        self.fusion = style == "Fusion"
        #: SolidWorks small buttons per page, whose names drop when space
        #: is short; each page's width with every name shown, measured
        #: once it is styled and shown (measured just after dropping the
        #: names, the hint is stale)
        self.small = {}
        self._compact = {}
        self._full = {}
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.tabs = QTabBar(self)
        self.tabs.setObjectName("ribbonTabs")
        self.tabs.setDrawBase(False)
        self.tabs.setExpanding(False)
        self.tabs.setFocusPolicy(Qt.NoFocus)
        if not self.fusion:
            self.tabs.setShape(QTabBar.RoundedSouth)
        self.stack = QStackedWidget(self)
        for key, fusion_title, sw_title, panels in TABS:
            self.tabs.addTab(language.tr(fusion_title if self.fusion
                                         else sw_title))
            self.stack.addWidget(self._page(panels))

        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(6 if self.fusion else 4, 0, 4, 0)
        tab_row.setSpacing(8)
        if self.fusion:
            # file and undo on the tabs' own line, like KherveTeX: no
            # separate quick-access row above the ribbon
            self.quick = self._quick_buttons(win)
            for b in self.quick:
                tab_row.addWidget(b)
            tab_row.addWidget(self._workspace_button())
        tab_row.addWidget(self.tabs)
        # the command search, after the last tab (ribbon_search.py)
        from .ribbon_search import SearchBox
        self.search = SearchBox(self)
        tab_row.addWidget(self.search)
        tab_row.addStretch(1)
        if self.fusion and getattr(win, "_vibe_act", None) is not None:
            tab_row.addWidget(_button(win._vibe_act, QSize(18, 18),
                                      Qt.ToolButtonIconOnly, self))
        if self.fusion:
            outer.addLayout(tab_row)
            outer.addWidget(self.stack)
        else:
            outer.addWidget(self.stack)
            outer.addLayout(tab_row)

        saved = QSettings(*_SETTINGS).value(TAB_KEY, 0)
        try:
            index = min(max(int(saved), 0), len(TABS) - 1)
        except (TypeError, ValueError):
            index = 0
        self.tabs.setCurrentIndex(index)
        self.stack.setCurrentIndex(index)
        self.tabs.currentChanged.connect(self._tab_changed)

    def _quick_buttons(self, win):
        parts = getattr(win, "_bar_parts", {})
        out = []
        for group in ("file", "undo"):
            for act in parts.get(group, []):
                out.append(_button(act, QSize(18, 18),
                                   Qt.ToolButtonIconOnly, self))
            if out and group == "file":
                out.append(_separator(self))
        return out

    # ------------------------------------------------------------ tabs
    def _tab_changed(self, index):
        self.stack.setCurrentIndex(index)
        QSettings(*_SETTINGS).setValue(TAB_KEY, index)
        # leaving the SKETCH tab finishes the sketch (there is no Finish
        # Sketch button any more)
        from . import sketch_mode
        if 0 <= index < len(TABS) and TABS[index][0] != "sketch" and \
                sketch_mode.sketching(self.win):
            sketch_mode.finish(self.win)
        self._fit()
        # the page only becomes visible after this returns: measure again
        # then, or a too-wide page kept its names and squeezed them
        QTimer.singleShot(0, self._fit)

    def show_tab(self, key):
        """Bring the tab *key* ("features", "form"...) to the front."""
        for i, tab in enumerate(TABS):
            if tab[0] == key:
                self.tabs.setCurrentIndex(i)

    def _workspace_button(self):
        """Fusion's workspace switcher: here it lists the tabs."""
        b = QToolButton(self)
        b.setObjectName("workspace")
        b.setText(language.tr("DESIGN") + "  ▾")
        b.setPopupMode(QToolButton.InstantPopup)
        b.setToolButtonStyle(Qt.ToolButtonTextOnly)
        b.setToolTip(language.tr("Pick a tab of tools"))
        menu = QMenu(b)
        for i, tab in enumerate(TABS):
            menu.addAction(language.tr(tab[1]).title(),
                           lambda i=i: self.tabs.setCurrentIndex(i))
        b.setMenu(menu)
        return b

    # ----------------------------------------------------------- pages
    def _page(self, panels):
        page = QWidget(self)
        page.setObjectName("ribbonPage")
        row = QHBoxLayout(page)
        row.setContentsMargins(6, 3, 6, 2)
        row.setSpacing(4)
        # the first button of every tab: Select — stops any tool (the
        # user could not get out of a fillet pick)
        # (SolidWorks: not on the tabs — the quick-access bar has it, as
        # in SolidWorks, and Esc stops a tool; the user, 2026-10-25)
        from . import stop_tool
        if self.fusion:
            stop = _helped(_painted(self.win, [stop_tool.action(self.win)]))
            row.addWidget(self._fusion_panel(page, language.tr("Select"),
                                             stop, 1))
            row.addWidget(_separator(page))
        for i, key in enumerate(panels):
            if i:
                row.addWidget(_separator(page))
            title, actions = panel_actions(self.win, key)
            if self.fusion:
                shown = PANEL_SHOWN.get(
                    key, FUSION_SHOWN.get(len(panels), FUSION_SHOWN_MANY))
                if key in FUSION_ALL:
                    shown = len(actions)
                row.addWidget(self._fusion_panel(page, title,
                                                 actions, shown,
                                                 key in FUSION_NAMED))
            else:
                row.addWidget(self._sw_panel(page, key, actions))
        row.addStretch(1)
        return page

    def _fusion_panel(self, page, title, actions, shown, named=False):
        panel = QWidget(page)
        col = QVBoxLayout(panel)
        col.setContentsMargins(2, 0, 2, 0)
        col.setSpacing(0)
        icons_row = QHBoxLayout()
        icons_row.setSpacing(1)
        for act in (actions if named else actions[:shown]):
            b = _button(act, FUSION_ICON, Qt.ToolButtonTextUnderIcon
                        if named else Qt.ToolButtonIconOnly, panel)
            if named:      # "House Builder..." reads "House"
                b.setText(_plain(re.sub(r"\s*Builder\.*$", "",
                                        act.text().replace("&", ""))))
            icons_row.addWidget(b)
        icons_row.addStretch(1)
        col.addLayout(icons_row)
        label = QToolButton(panel)
        label.setObjectName("panelLabel")
        label.setText(_plain(title.upper()) + " ▾")
        label.setPopupMode(QToolButton.InstantPopup)
        label.setToolButtonStyle(Qt.ToolButtonTextOnly)
        label.setToolTip(language.tr("Every tool of {panel}").format(
            panel=title))
        menu = QMenu(title, label)
        menu.setToolTipsVisible(True)
        for act in actions:
            menu.addAction(act)
        label.setMenu(menu)
        col.addWidget(label, 0, Qt.AlignHCenter)
        return panel

    def _sw_panel(self, page, key, actions):
        panel = QWidget(page)
        row = QHBoxLayout(panel)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(1)
        large = actions if key in ALL_LARGE else actions[:1]
        if key == "sketch" and len(actions) > 1 and \
                actions[1].data() == "con_dimension":
            large = actions[:2]          # Sketch and Smart Dimension
        for act in large:
            b = _button(act, SW_LARGE, Qt.ToolButtonTextUnderIcon, panel)
            b.setObjectName("large")
            row.addWidget(b)
        rest = actions[len(large):]
        if rest:
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(1)
            grid.setVerticalSpacing(0)
            for i, act in enumerate(rest):
                b = _button(act, SW_SMALL, Qt.ToolButtonTextBesideIcon,
                            panel)
                b.setObjectName("small")
                grid.addWidget(b, i % 3, i // 3, Qt.AlignLeft)
                self.small.setdefault(self.stack.count(), []).append(b)
            row.addLayout(grid)
        return panel

    # ---------------------------------------------------------- sizing
    def sizeHint(self):
        # narrow on purpose: an expanding widget in a QToolBar takes the
        # bar's width, where a wide hint would push it into the overflow
        h = super().sizeHint().height()
        return QSize(240, h)

    def minimumSizeHint(self):
        return QSize(120, super().sizeHint().height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._fit)

    def _fit(self):
        """SolidWorks: the small buttons drop their names when the page
        does not fit, and take them back when it does."""
        index = self.stack.currentIndex()
        page = self.stack.currentWidget()
        if self.fusion or index not in self.small or page is None \
                or not page.isVisible():
            return
        if index not in self._full:             # never compacted yet
            self._full[index] = page.sizeHint().width()
        self._set_compact(index, self._full[index] > self.width())

    def _set_compact(self, index, on):
        if on == self._compact.get(index, False):
            return
        self._compact[index] = on
        style = (Qt.ToolButtonIconOnly if on
                 else Qt.ToolButtonTextBesideIcon)
        for b in self.small[index]:
            b.setToolButtonStyle(style)
