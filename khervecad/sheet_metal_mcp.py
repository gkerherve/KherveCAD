"""MCP `sheet_metal`: the SHEET METAL tab for an assistant — the same
sheet_metal_ops calls the ribbon makes.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import sheet_body, sheet_metal_ops as ops


def _node(win, params, key="node_id"):
    nid = params.get(key)
    if nid is None:
        return None
    node = win.model.find(int(nid)) if hasattr(win.model, "find") else None
    if node is None:
        node = next((n for n in win.model.root.walk() if n.id == int(nid)),
                    None)
    if node is None:
        raise ValueError(f"no node {nid}")
    return node


def _body(win, params):
    node = _node(win, params)
    body = ops.find_body(node) if node is not None else None
    if body is None:
        bodies = [n for n in win.model.root.walk() if n.type == ops.KIND]
        if node is None and len(bodies) == 1:
            return bodies[0]
        raise ValueError("node_id: give the sheet metal body (list_tree "
                         "shows its id; action create makes one)")
    return body


def run(win, params):
    action = params.get("action", "state")
    model = win.model
    if action == "rules":
        return {"rules": ops.rules(model)}
    if action == "set_rule":
        slug = ops.set_rule(model, params["rule"], **{
            k: params[k] for k in ops.RULE_FIELDS if k in params})
        out = {"rule": slug, "rules": ops.rules(model)}
        if params.get("node_id") is not None:
            ops.apply_rule(model, _body(win, params), slug)
        return out
    if action == "delete_rule":
        ops.delete_rule(model, params["rule"])
        return {"rules": ops.rules(model)}
    if action == "create":
        parent = None
        if params.get("parent_id") is not None:
            parent = _node(win, params, "parent_id")
        if params.get("contour"):
            body = ops.insert_contour(model, params["contour"],
                                      params.get("width", 60.0),
                                      parent=parent,
                                      name=params.get("name", "Sheet metal"))
        else:
            body = ops.insert_base(model, params.get("outline"),
                                   parent=parent,
                                   name=params.get("name", "Sheet metal"),
                                   thickness=params.get("thickness"),
                                   radius=params.get("bend_radius"))
        if params.get("k_factor") is not None:
            model.set_param(body, "k_factor", params["k_factor"])
        if params.get("rule"):
            ops.apply_rule(model, body, params["rule"])
        return ops.describe(model, body)
    if action == "convert":
        node = _node(win, params)
        if node is None:
            raise ValueError("convert: node_id of the plate")
        return ops.describe(model, ops.convert(model, node))
    body = _body(win, params)
    if action == "state":
        return ops.describe(model, body)
    panel = int(params.get("panel", 0))
    edge = params.get("edge", 0)
    if action == "flange":
        then = [(h, a) for h, a in params.get("then") or []]
        made = ops.add_flange(model, body, panel, edge,
                              params.get("height", 20.0),
                              params.get("angle", 90.0),
                              params.get("bend_radius", 0.0),
                              params.get("inset_start", 0.0),
                              params.get("inset_end", 0.0), then)
        out = ops.describe(model, body)
        out["made_panels"] = made
        return out
    if action == "hem":
        ops.add_hem(model, body, panel, edge, params.get("length", 8.0),
                    bool(params.get("flip")))
    elif action == "path_flange":
        ops.path_flange(model, body, panel, edge,
                        [(h, a) for h, a in params.get("segments") or []])
    elif action == "fold":
        line = params.get("line")
        if not line or len(line) != 2:
            raise ValueError("fold: line = [[x1, y1], [x2, y2]] across the "
                             "base, in its own frame")
        ops.add_fold(model, body, line[0], line[1],
                     params.get("angle", 90.0), params.get("bend_radius", 0))
    elif action == "perforate":
        ops.perforate(model, body, params.get("diameter", 5.0),
                      params.get("pitch", 8.0), params.get("margin", 0.0),
                      params.get("pattern") == "square")
    elif action in ("unfold", "refold"):
        ops.set_flat(model, body, action == "unfold")
    elif action == "remove":
        ops.remove(model, body, params.get("what", "flanges"),
                   int(params.get("index", -1)))
    elif action == "apply_rule":
        ops.apply_rule(model, body, params["rule"])
    elif action == "flat_pattern":
        comp, pat = ops.flat_pattern_part(model, body)
        return {"object_id": comp.id, "width": round(pat["width"], 3),
                "height": round(pat["height"], 3),
                "bends": len(pat["bend_table"])}
    elif action == "export_dxf":
        path = params.get("path")
        if not path:
            raise ValueError("export_dxf: path")
        sheet_body.flat_dxf(ops.pattern(model, body), path,
                            params.get("bend_notes", True))
        return {"path": path}
    elif action == "export_bend_table":
        csv = sheet_body.bend_table_csv(ops.pattern(model, body))
        if params.get("path"):
            with open(params["path"], "w", encoding="utf-8") as fh:
                fh.write(csv)
            return {"path": params["path"]}
        return {"csv": csv}
    else:
        raise ValueError(f"unknown action {action!r}")
    return ops.describe(model, body)
