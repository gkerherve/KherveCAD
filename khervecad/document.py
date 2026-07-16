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

from .model import NODE_TYPES, CadNode, DocumentModel

FORMAT_VERSION = 4          # 4: "component" (Object) node type


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
            "dimensions": model.dimensions,
            "tree": node_to_dict(model.root)}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)


def load_kcad(model: DocumentModel, path: str):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("format") != "kcad":
        raise ValueError("not a KherveCAD document")
    model.root = node_from_dict(data["tree"])
    # segment override — default on at 45 when the file predates it
    model.global_fn = int(data.get("global_fn", 45))
    model.global_fn_on = bool(data.get("global_fn_on", True))
    model.dimensions = [dict(d) for d in data.get("dimensions", [])]
    model.group_variables()               # gather loose top-level vars
    model.structure_changed.emit()
    model.dimensions_changed.emit()


def export_scad(model: DocumentModel, path: str):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(model.to_scad())
