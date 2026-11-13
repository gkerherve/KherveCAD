# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""SolidWorks' Shell window (2026-11-13, the user: "the shell does not
seem to be doing shell", with SolidWorks' open ring): a Shell made
CLOSED looks exactly like the solid from outside, so nothing seemed to
happen. Now, as in SolidWorks, the window asks for the wall thickness
and the FACES TO REMOVE, picked in the 3D view (a second click on a face
takes it back). Each face is stored as a `remove` row [x, y, z, nx, ny,
nz] in the part's frame and found again on every rebuild by the name of
the feature that made it (shell.removed_faces), so the top of an extrude
stays open when the extrude grows.
"""

from . import fillet_pick, language


def _panel(window):
    return getattr(window, "_shell_panel", None)


def start(window, node) -> bool:
    """Open the Shell window for *node* and arm the face pick."""
    world, local = fillet_pick.meshes(window, node)
    if world is None:
        window.statusBar().showMessage(
            language.tr("Shell: put a solid inside it first."), 6000)
        return False
    from .tool_panel import ToolPanel
    tr = language.tr
    model, view = window.model, window.view3d
    old = _panel(window)
    if old is not None:
        old.close()
    state = {"node": node, "world": world, "local": local, "done": False}

    def finish(keep):
        if state["done"]:
            return
        state["done"] = True
        if view._pick_cb is not None:
            view._pick_cb = None
            view._end_pick_mode()
        panel.close()
        window._shell_panel = None
        if not keep and node.parent is not None:
            model.ungroup(node)
        else:
            window.builder.active_tree().select_nodes([node])

    panel = ToolPanel(view, tr("Shell"), on_ok=lambda: finish(True),
                      on_cancel=lambda: finish(False))
    panel.hint(tr("Click the faces to remove (they are left open); click "
                  "one again to keep it. No face = a closed hollow part."))
    panel.number("thickness", tr("Thickness:"),
                 float(node.params.get("thickness", 2.0)),
                 lambda v: model.set_param(node, "thickness", float(v)),
                 minimum=0.01, step=0.5)
    panel.selection("faces", tr("Faces to remove"))
    panel.finish()
    window._shell_panel = panel

    def refresh():
        n = len(node.params.get("remove") or [])
        panel.boxes["faces"].set_text(
            tr("{n} face(s)").format(n=n) if n else
            tr("Click faces in the 3D view"))

    def on_pick(desc, _key):
        if desc is None:                 # Esc / right-click: done
            finish(True)
            return
        row = fillet_pick.face_from_pick(desc, world, local)
        if row is None:
            window.statusBar().showMessage(
                tr("Shell: click a face, not an edge."), 3000)
        else:
            rows = [list(r) for r in (node.params.get("remove") or [])]
            same = [r for r in rows if _same_face(r, row, local)]
            if same:
                rows = [r for r in rows if r not in same]
            else:
                rows.append(row)
            model.set_param(node, "remove", rows)
            refresh()
        arm()

    def arm():
        if state["done"]:
            return
        view.start_pick(on_pick, groups=[(node, world)],
                        banner=tr("Shell: click the faces to remove · "
                                  "Esc or OK when done"),
                        labeler=lambda d, _k: tr("Face — click to remove"),
                        done=False)

    refresh()
    panel.open()
    arm()
    return True


def _same_face(a, b, local):
    """Two rows naming the same face: the face the second's point lies
    on is the first's (same region of the uncut part)."""
    from . import shell
    pa = shell.removed_faces(local, [a])
    pb = shell.removed_faces(local, [b])
    return bool(pa & pb)
