"""Mass in the status bar (2026-10-27) — SolidWorks shows the part's mass
properties as you work; here a status-bar button reads

    Mass 52.4 g · 42.3 cm³ · PLA

for the selection (else everything in view), updated half a second
after the model or the selection changes. A click opens the material
list (analysis.MATERIALS); the choice is the document's, kept on the
root as ``params["mass_material"]`` (so it saves and undoes with the
document) and used by this readout. `readout` is the arithmetic.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import language

KEY = "mass_material"
MAX_TRIS = 400000                 # past this the readout waits for Analyse
DELAY_MS = 500


def material_of(model):
    from . import analysis
    m = model.root.params.get(KEY) or analysis.DEFAULT_MATERIAL
    return m if m in analysis.MATERIALS else analysis.DEFAULT_MATERIAL


def readout(tris, unit="mm", material="PLA"):
    """(text, grams, cm³) for a closed world mesh in document units."""
    from . import analysis, units
    if not tris:
        return "", 0.0, 0.0
    if len(tris) > MAX_TRIS:
        return language.tr("Mass: large model — Analyse ▸ Mass "
                           "Properties"), 0.0, 0.0
    vol = abs(analysis.mass_properties(tris)["volume"])
    mm3 = vol * units.to_mm(unit) ** 3
    grams = analysis.mass(mm3, material)
    cm3 = mm3 / 1000.0
    if grams >= 1000:
        mass = f"{grams / 1000:.3g} kg"
    elif grams >= 0.01:
        mass = f"{grams:.3g} g"
    else:
        mass = f"{grams * 1000:.3g} mg"
    return (f"{language.tr('Mass')} {mass} · {cm3:.3g} cm³ · "
            f"{language.tr(material)}", grams, cm3)


# =================================================================== Qt

def install(window):
    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import QToolButton
    btn = QToolButton(window)
    btn.setObjectName("mass_readout")
    btn.setAutoRaise(True)
    btn.setToolTip(language.tr(
        "Mass of the selection (or everything in view), solid, in the "
        "document's material — click to choose the material."))
    btn.clicked.connect(lambda: choose(window))
    window.statusBar().addPermanentWidget(btn)
    timer = QTimer(window)
    timer.setSingleShot(True)
    timer.setInterval(DELAY_MS)
    timer.timeout.connect(lambda: update(window))
    window._mass_btn, window._mass_timer = btn, timer
    window.model.structure_changed.connect(timer.start)
    window.model.node_changed.connect(lambda _n: timer.start())
    for tree in (window.builder.tree, window.builder.object_tab.tree):
        tree.selection_changed.connect(lambda *_a: timer.start())
    timer.start()
    return btn


def is_solid(node):
    """Does *node* make a SOLID (not a flat sketch, nor construction)?
    A flat shape's triangles would count as volume."""
    from .model import NODE_TYPES
    for n in node.walk():
        spec = NODE_TYPES.get(n.type, {})
        if spec.get("category") == "3d" or n.type in (
                "linear_extrude", "rotate_extrude", "reference"):
            return True
    return False


def _tris(window):
    from . import mesh
    try:
        sel = window.builder.active_tree().selected_nodes()
    except Exception:
        sel = []
    root = window._render_scope()[0]
    nodes = [n for n in sel if is_solid(n)] if sel else [
        c for c in root.children if c.visible and is_solid(c)]
    if not nodes:
        return [], bool(sel)
    try:
        return mesh.selected_world_tris(
            root, {n.id for n in nodes},
            fn=window.model.effective_fn()), bool(sel)
    except Exception:
        return [], bool(sel)


def update(window):
    btn = getattr(window, "_mass_btn", None)
    if btn is None:
        return ""
    try:
        tris, selected = _tris(window)
        text, _g, _v = readout([t for t in tris if len(t) == 3],
                               getattr(window.model, "unit", "mm"),
                               material_of(window.model))
    except Exception:                    # a readout never stops the app
        text = ""
    if text and selected:
        text = language.tr("Selected") + ": " + text
    btn.setText(text)
    btn.setVisible(bool(text))
    return text


def set_material(window, material):
    model = window.model
    model.root.params[KEY] = material
    model.node_changed.emit(model.root)
    update(window)


def choose(window):
    from PyQt5.QtGui import QCursor
    from PyQt5.QtWidgets import QMenu
    from . import analysis
    menu = QMenu(window)
    now = material_of(window.model)
    for name, density in analysis.MATERIALS.items():
        act = menu.addAction(f"{language.tr(name)}  ({density:g} g/cm³)")
        act.setCheckable(True)
        act.setChecked(name == now)
        act.triggered.connect(lambda _=False, n=name:
                              set_material(window, n))
    menu.exec_(QCursor.pos())
