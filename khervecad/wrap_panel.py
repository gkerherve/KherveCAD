# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""The Wrap window (2026-11-14): as SolidWorks' Wrap — Emboss / Deboss,
the depth, and what is written: a TEXT ready at once (most wraps are a
word on a mug or a scale on a knob), its size, and where round the part
it starts. Every change shows at once; Cancel takes the Wrap away.
"""

from . import language


def _text_node(node):
    return next((c for c in node.children if c.type == "text"), None)


def start(window, node) -> bool:
    from .tool_panel import ToolPanel
    from . import mesh
    tr = language.tr
    model, view = window.model, window.view3d
    body = next((c for c in node.children if c.type != "text"), None)
    if body is None:
        return False
    text = _text_node(node)
    if text is None and not [c for c in node.children if c is not body]:
        tris = mesh.tessellate(body)
        zs = [p[2] for t in tris for p in t] or [0.0]
        text = model.add_node("text", dict(
            text="KCAD", size=8.0, halign="center", valign="center",
            x=0.0, y=round((min(zs) + max(zs)) / 2, 3)),
            parent=node, name="Wrap sketch")
        model.set_param(node, "angle", -90.0)   # across the front (−Y)
    old = getattr(window, "_wrap_panel", None)
    if old is not None:
        old.hide()
    done = {"v": False}

    def finish(keep):
        if done["v"]:
            return
        done["v"] = True
        panel.hide()
        panel.deleteLater()
        window._wrap_panel = None
        if not keep and node.parent is not None:
            if text is not None and text.parent is node:
                model.remove_node(text)
            model.ungroup(node)
        else:
            window.builder.active_tree().select_nodes([node])

    panel = ToolPanel(view, tr("Wrap"), on_ok=lambda: finish(True),
                      on_cancel=lambda: finish(False))
    panel.hint(tr("Text (or 2D shapes drawn inside the Wrap) wrapped "
                  "round the part: raised or cut in."))
    panel.choice("kind", tr("Type:"),
                 [("emboss", tr("Emboss (raised)")),
                  ("deboss", tr("Deboss (cut in)"))],
                 node.params.get("kind", "emboss"),
                 lambda v: model.set_param(node, "kind", v))
    panel.number("depth", tr("Depth:"), float(node.params.get("depth", 1.0)),
                 lambda v: model.set_param(node, "depth", float(v)),
                 minimum=0.01, step=0.5)
    if text is not None:
        from PyQt5.QtWidgets import QLineEdit
        edit = QLineEdit(str(text.params.get("text", "")), panel)
        edit.textChanged.connect(
            lambda t: model.set_param(text, "text", t))
        panel._grid_row(tr("Text:"), edit, "text")
        panel.number("size", tr("Size:"), float(text.params.get("size", 8)),
                     lambda v: model.set_param(text, "size", float(v)),
                     minimum=0.5, step=1.0)
    panel.number("angle", tr("Start angle:"),
                 float(node.params.get("angle", 0.0)),
                 lambda v: model.set_param(node, "angle", float(v)),
                 suffix=" °", minimum=-360.0, maximum=360.0, step=5.0)
    panel.finish()
    window._wrap_panel = panel
    panel.open()
    return True
