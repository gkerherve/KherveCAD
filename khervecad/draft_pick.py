# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""The Draft window (2026-11-14, the user: "are you also looking at the
ease of using the tool you have just created"): as SolidWorks' Draft,
the angle, the neutral plane and the FACES TO DRAFT, clicked in the 3D
view (a second click takes a face back). No face clicked = every side
face. Each face is a `pick` row [x, y, z] in the part's frame, found
again by draft.py on every rebuild. Same flow as the Shell window.
"""

from . import fillet_pick, language


def _panel(window):
    return getattr(window, "_draft_panel", None)


def start(window, node) -> bool:
    """Open the Draft window for *node* and arm the face pick."""
    world, local = fillet_pick.meshes(window, node)
    if world is None:
        window.statusBar().showMessage(
            language.tr("Draft: put a solid inside it first."), 6000)
        return False
    from .tool_panel import ToolPanel
    tr = language.tr
    model, view = window.model, window.view3d
    old = _panel(window)
    if old is not None:
        old.hide()
    state = {"done": False}

    def finish(keep):
        if state["done"]:
            return
        state["done"] = True
        if view._pick_cb is not None:
            view._pick_cb = None
            view._end_pick_mode()
        panel.hide()
        panel.deleteLater()
        window._draft_panel = None
        if not keep and node.parent is not None:
            model.ungroup(node)
        else:
            window.builder.active_tree().select_nodes([node])

    panel = ToolPanel(view, tr("Draft"), on_ok=lambda: finish(True),
                      on_cancel=lambda: finish(False))
    panel.hint(tr("Click the side faces to draft; click one again to "
                  "leave it. No face = every side face."))
    panel.number("angle", tr("Draft angle:"),
                 float(node.params.get("angle", 3.0)),
                 lambda v: model.set_param(node, "angle", float(v)),
                 suffix=" °", minimum=-45.0, maximum=45.0, step=1.0)
    panel.choice("neutral", tr("Neutral plane:"),
                 [("bottom", tr("Bottom (narrower at the top)")),
                  ("top", tr("Top (narrower at the bottom)"))],
                 node.params.get("neutral", "bottom"),
                 lambda v: model.set_param(node, "neutral", v))
    panel.selection("faces", tr("Faces to draft"))
    panel.finish()
    window._draft_panel = panel

    def refresh():
        n = len(node.params.get("pick") or [])
        panel.boxes["faces"].set_text(
            tr("{n} face(s)").format(n=n) if n else
            tr("Every side face — or click faces"))

    def on_pick(desc, _key):
        if desc is None:                 # Esc / right-click: done
            finish(True)
            return
        row = fillet_pick.face_from_pick(desc, world, local)
        if row is None:
            window.statusBar().showMessage(
                tr("Draft: click a face, not an edge."), 3000)
        else:
            row = [round(float(v), 4) for v in row[:3]]
            rows = [list(r) for r in (node.params.get("pick") or [])]
            same = [r for r in rows if _same_face(r, row, local)]
            if same:
                rows = [r for r in rows if r not in same]
            else:
                rows.append(row)
            model.set_param(node, "pick", rows)
            refresh()
        arm()

    def arm():
        if state["done"]:
            return
        view.start_pick(on_pick, groups=[(node, world)],
                        banner=tr("Draft: click the faces to draft · "
                                  "Esc or OK when done"),
                        labeler=lambda d, _k: tr("Face — click to draft"),
                        done=False)

    refresh()
    panel.open()
    arm()
    return True


def _same_face(a, b, local):
    """Two points on the same flat face of the part."""
    from . import draft
    tris = [t[:3] for t in local]
    normals = [draft._normal(t) for t in tris]
    ia, ib = draft._nearest(tris, a), draft._nearest(tris, b)
    if ia is None or ib is None or normals[ia] is None:
        return False
    return ib in draft._coplanar_region(tris, normals, ia)
