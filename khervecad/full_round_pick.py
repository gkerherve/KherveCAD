# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""The Full Round Fillet window (2026-11-14): SolidWorks' three boxes —
Side face set 1, Centre face set, Side face set 2 — filled by clicks in
the 3D view, in that order (a click goes to the first empty box; Reset
starts again). Nothing clicked = the top face with its own sides; the
centre alone finds its sides too. Each face is a `pick` row [x, y, z].
"""

from . import fillet_pick, language

BOXES = ("side1", "centre", "side2")


def _panel(window):
    return getattr(window, "_full_round_panel", None)


def start(window, node) -> bool:
    world, local = fillet_pick.meshes(window, node)
    if world is None:
        window.statusBar().showMessage(
            language.tr("Full round fillet: put a solid inside it first."),
            6000)
        return False
    from .tool_panel import ToolPanel
    tr = language.tr
    model, view = window.model, window.view3d
    old = _panel(window)
    if old is not None:
        old.hide()
    state = {"done": False, "rows": [None, None, None]}

    def finish(keep):
        if state["done"]:
            return
        state["done"] = True
        if view._pick_cb is not None:
            view._pick_cb = None
            view._end_pick_mode()
        panel.hide()
        panel.deleteLater()
        window._full_round_panel = None
        if not keep and node.parent is not None:
            model.ungroup(node)
        else:
            window.builder.active_tree().select_nodes([node])

    panel = ToolPanel(view, tr("Full Round Fillet"),
                      on_ok=lambda: finish(True),
                      on_cancel=lambda: finish(False))
    panel.hint(tr("Click a side face, then the centre face, then the "
                  "other side face. Nothing clicked = the top face."))
    panel.selection("side1", tr("Side face set 1"))
    panel.selection("centre", tr("Centre face set"))
    panel.selection("side2", tr("Side face set 2"))
    panel.finish()
    window._full_round_panel = panel

    def write():
        rows = state["rows"]
        if all(rows):
            pick = rows
        elif rows[1] and not rows[0] and not rows[2]:
            pick = [rows[1]]
        elif any(rows):
            return                         # wait for the other clicks
        else:
            pick = []
        model.set_param(node, "pick", [list(r) for r in pick])

    def refresh():
        for key, row in zip(BOXES, state["rows"]):
            panel.boxes[key].set_text(tr("Face") if row else
                                      tr("— click a face"))
        empty = [k for k, r in zip(BOXES, state["rows"]) if not r]
        if empty:
            panel.boxes[empty[0]].set_active(True) if hasattr(
                panel.boxes[empty[0]], "set_active") else None

    def on_pick(desc, _key):
        if desc is None:
            finish(True)
            return
        row = fillet_pick.face_from_pick(desc, world, local)
        if row is None:
            window.statusBar().showMessage(
                tr("Full round fillet: click a face, not an edge."), 3000)
        else:
            rows = state["rows"]
            i = next((k for k in range(3) if rows[k] is None), None)
            if i is None:                  # a fourth click starts again
                rows[:] = [None, None, None]
                i = 0
            rows[i] = [round(float(v), 4) for v in row[:3]]
            write()
            refresh()
        arm()

    def arm():
        if state["done"]:
            return
        n = sum(1 for r in state["rows"] if r)
        what = (tr("side face 1"), tr("the centre face"),
                tr("side face 2"))[n % 3]
        view.start_pick(on_pick, groups=[(node, world)],
                        banner=tr("Full round: click {what} · Esc or OK "
                                  "when done").format(what=what),
                        labeler=lambda d, _k: tr("Face"), done=False)

    refresh()
    panel.open()
    arm()
    return True
