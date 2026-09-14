"""The quick drawing behind the `export_drawing` MCP tool: the model's
triangles and a `drawing.layout` of them. The interactive drawing is
the Blueprint window (blueprint.py, File ▸ Blueprint…).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from pathlib import Path

from . import drawing, mesh

STANDARD = ("Front", "Top", "Right", "Isometric")


def model_tris(window):
    """The mesh the drawing is of: the selection, else the whole
    document (the Object being edited, in the Object tab)."""
    nodes = window.builder.active_tree().selected_nodes()
    fn = window.model.effective_fn()
    if nodes:
        with window._isolated_frame(window.builder.isolated_component()):
            return mesh.selected_world_tris(
                window._render_scope()[0], {n.id for n in nodes}, fn=fn), \
                nodes[0].name
    root = window._render_scope()[0]
    iso = root if root is not window.model.root else None
    with window._isolated_frame(iso):
        tris = mesh.tessellate(root, fn=fn)
    name = root.name if iso is not None else (
        Path(window._path).stem if window._path else "Part")
    return tris, name


def make_layout(window, *, sheet="A4", views=STANDARD, dimensions=True,
                section_axis=None, title=None, scale=None,
                hidden_lines=True):
    tris, name = model_tris(window)
    if not tris:
        raise ValueError("nothing to draw — the model has no solid")
    return drawing.layout(tris, sheet=sheet, views=views,
                          dimensions=dimensions, section_axis=section_axis,
                          title=title or name, scale=scale,
                          hidden_lines=hidden_lines,
                          unit=getattr(window.model, "unit", "mm"))
