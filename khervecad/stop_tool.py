"""Stop whatever is running and go back to selecting (2026-10-21, the
user started a fillet pick and could not get out of it: "the first
button on all should be to stop ... like the mouse").

`stop(window)` ends every active mode, whichever started it: the 3D
view's pick (fillet / snap / push-pull…), an edit tool on the 3D view
(Edit Mode, Gumball, sculpt, paint, 3D curve), the 2D view's drawing /
constraint / modify tools and their half-made shapes — and picks the
Select arrow. The ribbon shows it as the FIRST button of every tab
(`action`), and Esc anywhere in the main window does the same once the
view under the cursor has had its own chance (a view still handles Esc
first: Edit Mode cancels a drag before leaving).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import language


def stop(window):
    """End every active tool / mode. Returns True if anything stopped."""
    stopped = False
    view = window.view3d
    from . import plane_pick
    if plane_pick.active(window):
        plane_pick.stop(window)
        stopped = True
    if getattr(view, "_pick_cb", None) is not None:
        view.cancel_pick()
        stopped = True
    session = getattr(window, "_edit_session", None)
    if session is not None:
        try:
            session.exit()
        except Exception:                      # pragma: no cover
            pass
        stopped = True
    act = getattr(window, "_gumball_act", None)
    if act is not None and act.isChecked():
        act.setChecked(False)
        stopped = True
    tool = getattr(view, "edit_tool", None)
    if tool is not None:
        for name in ("exit", "close", "_end", "stop", "cancel"):
            fn = getattr(tool, name, None)
            if callable(fn):
                try:
                    fn()
                except Exception:              # pragma: no cover
                    pass
                break
        view.edit_tool = None
        view.update()
        stopped = True
    if getattr(window, "_face_sketch", None) is not None and \
            not getattr(window, "_sketching", False):
        # the classic layout's face sketch ends here (no Exit Sketch)
        from . import face_sketch
        face_sketch.close(window)
        window.view2d.scene().rebuild()
        stopped = True
    scene = window.view2d.scene()
    from .view2d import SELECT
    if getattr(scene, "tool", SELECT) != SELECT:
        stopped = True
    try:
        scene.cancel_tool()
    except Exception:                          # pragma: no cover
        pass
    window._set_tool(SELECT)
    for a in window._tool_group.actions():
        if a.data() == SELECT:
            a.setChecked(True)
    window.statusBar().showMessage(language.tr(
        "Stopped — back to selecting.") if stopped else language.tr(
        "Selecting: click objects in the tree or the views."), 3000)
    return stopped


def action(window):
    """The Select / Stop action (one per window)."""
    act = getattr(window, "_stop_act", None)
    if act is not None:
        return act
    from PyQt5.QtWidgets import QAction
    from . import icons, toolbars, tooltips
    tooltips.TIPS.setdefault("stop_select", (
        "Select (stop)",
        "Stops whatever tool is running — a fillet pick, a sketch or "
        "constraint tool, Edit Mode, the Gumball — and goes back to "
        "selecting with the mouse.",
        ["Click it, or press Esc."], None))
    act = QAction(icons.icon("mdi.cursor-default-outline"),
                  language.tr("Select"), window)
    act.setData("stop_select")
    toolbars.remember_glyph(act, "mdi.cursor-default-outline", None)
    tooltips.apply(act, "stop_select")
    act.triggered.connect(lambda _=False: stop(window))
    window._stop_act = act
    return act


def install_escape(window):
    """Esc in the main window stops tools, wherever the focus is. A
    view whose own tool is busy gets the key itself (Edit Mode cancels a
    drag, a polygon takes a point back) — this shortcut only fires when
    no widget used it."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QShortcut
    from PyQt5.QtGui import QKeySequence
    sc = QShortcut(QKeySequence(Qt.Key_Escape), window)
    sc.setContext(Qt.WindowShortcut)
    sc.activated.connect(lambda: stop(window))
    window._stop_escape = sc
    return sc
