"""`.kcad` JSON (de)serialisation and `.scad` export.

The `.kcad` format stores the object tree verbatim; the OpenSCAD
program is never stored because it is always regenerated from the
tree. When a node type gains new persisted properties, bump
``FORMAT_VERSION`` and keep loading backward compatible.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import os

from .meshimport import relative_for_save, resolve_paths
from .model import NODE_TYPES, CadNode, DocumentModel, retire_masters
from .units import coerce

FORMAT_VERSION = 13         # 4: "component" (Object) node type
                            # 5: instances (reference->component) may
                            #    carry a "mate" record
                            # 6: organic/mesh node types; color nodes
                            #    carry a "material" (absent = Default)
                            # 7: stl_import carries rx/ry/rz/scale, and
                            #    its path is relative to the .kcad when
                            #    the mesh is inside the document folder
                            # 8: "drawing" — the Blueprint sheet (views,
                            #    annotations, title block); absent = none
                            # 9: "unit" — the display unit (units.py);
                            #    absent = "mm"
                            # 10: "house" — the House Builder design
                            #    (house.house_to_spec); absent = none
                            # 11: "city" — the City Builder design
                            # 12: "real_scale" — the N of 1 : N, what the
                            #    scale bar measures (absent = 1, life size)
                            #    (city.resolve); absent = none
                            # 13: "collections" — Blender-style sets of
                            #    parts, [{name, visible, locked}]; members
                            #    carry params["collection"]; absent = none


def node_to_dict(node: CadNode) -> dict:
    data = {"type": node.type, "name": node.name,
            "visible": node.visible, "params": node.params}
    if node.children:
        data["children"] = [node_to_dict(c) for c in node.children]
    return data


def node_from_dict(data: dict) -> CadNode:
    type = data.get("type", "union")
    if type != "root" and type not in NODE_TYPES:
        raise ValueError(f"unknown node type: {type}")
    node = CadNode(type, data.get("name", ""))
    node.visible = bool(data.get("visible", True))
    node.params.update(data.get("params", {}))
    for child in data.get("children", []):
        node.add(node_from_dict(child))
    return node


def save_kcad(model: DocumentModel, path: str):
    data = {"format": "kcad", "version": FORMAT_VERSION,
            "global_fn": int(model.global_fn),
            "global_fn_on": bool(model.global_fn_on),
            "unit": model.unit,
            "dimensions": model.dimensions,
            "references": model.reference_images,
            "tree": node_to_dict(model.root)}
    if model.real_scale != 1.0:
        # only a scale model says so: a life-size file stays as it was
        data["real_scale"] = model.real_scale
    if model.drawing:
        data["drawing"] = model.drawing
    if model.house:
        data["house"] = model.house
    if model.city:
        data["city"] = model.city
    if model.collections:
        data["collections"] = model.collections
    relative_for_save(data["tree"], path)   # the folder travels whole
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)


def load_kcad(model: DocumentModel, path: str):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("format") != "kcad":
        raise ValueError("not a KherveCAD document")
    model.root = node_from_dict(data["tree"])
    retire_masters(model.root)          # an old Masters store -> Objects
    resolve_paths(model.root, os.path.dirname(os.path.abspath(path)))
    # segment override — default on at 45 when the file predates it
    model.global_fn = int(data.get("global_fn", 45))
    model.global_fn_on = bool(data.get("global_fn_on", True))
    model.dimensions = [dict(d) for d in data.get("dimensions", [])]
    model.reference_images = [dict(r) for r in data.get("references", [])]
    model.drawing = data.get("drawing") or None
    model.house = data.get("house") or None
    model.city = data.get("city") or None
    model.collections = [dict(c) for c in data.get("collections") or []]
    old_unit, model.unit = model.unit, coerce(data.get("unit", "mm"))
    old_scale = model.real_scale
    try:
        model.real_scale = float(data.get("real_scale", 1.0) or 1.0)
    except (TypeError, ValueError):
        model.real_scale = 1.0
    if not model.real_scale > 0:
        model.real_scale = 1.0
    model.group_variables()               # gather loose top-level vars
    model.structure_changed.emit()
    model.dimensions_changed.emit()
    model.references_changed.emit()
    model.drawing_changed.emit()
    if model.unit != old_unit:
        model.unit_changed.emit(model.unit)
    if model.real_scale != old_scale:
        model.scale_changed.emit(model.real_scale)


def export_scad(model: DocumentModel, path: str):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(model.to_scad())
