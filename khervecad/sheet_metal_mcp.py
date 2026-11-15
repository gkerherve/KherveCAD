"""MCP `sheet_metal`: the SHEET METAL tab for an assistant — the same
sheet_metal_ops calls the ribbon makes.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import sheet_body, sheet_jog, sheet_metal_ops as ops


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
    if action == "flange" and params.get("ear"):
        index = ops.add_ear(model, body, panel, edge,
                            float(params.get("center", 0.0)),
                            float(params.get("width", 15.0)),
                            params.get("height", 20.0),
                            params.get("angle", 90.0),
                            params.get("bend_radius", 0.0),
                            float(params.get("hole_diameter", 0.0)))
        out = ops.describe(model, body)
        out["made_panels"] = [index]
        return out
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
    elif action == "panel_hole":
        if params.get("u") is not None and params.get("v") is not None:
            u, v = float(params["u"]), float(params["v"])
        elif params.get("along") is not None:
            u, v = ops.edge_position(model, body, panel, edge,
                                     float(params["along"]),
                                     float(params.get("across", 0.0)))
        else:
            raise ValueError("panel_hole: give u and v (the panel's own frame) "
                             "or edge + along + across")
        ops.add_panel_hole(model, body, panel, u, v,
                     params.get("diameter", 5.0))
    elif action == "tab":
        if params.get("u") is None or params.get("v") is None:
            raise ValueError("tab: u and v (the centre of its round end, "
                             "in the panel's own frame)")
        ops.add_tab(model, body, panel, float(params["u"]),
                    float(params["v"]), float(params.get("width", 10.0)),
                    float(params.get("length", 20.0)),
                    float(params.get("angle", 90.0)),
                    float(params.get("hole_diameter", 0.0)))
    elif action == "jog":
        line = params.get("line")
        if not line or len(line) != 2:
            raise ValueError("jog: line = [[x1, y1], [x2, y2]] across the "
                             "base, in its own frame")
        ops.add_jog(model, body, line[0], line[1],
                    params.get("offset", 20.0), params.get("angle", 60.0),
                    params.get("bend_radius", 0),
                    sheet_jog.DIM_MODES.index(params.get("dimension",
                                                         "outside")),
                    int(params.get("position", 3)),
                    -1 if params.get("fixed_side", "right") == "right"
                    else 1,
                    -1 if params.get("direction", "up") == "down" else 1)
    elif action == "hole":
        ops.add_hole(model, body, params.get("x", 0.0), params.get("y", 0.0),
                     params.get("diameter", 5.0))
    elif action == "slot":
        line = params.get("line")
        if not line or len(line) != 2:
            raise ValueError("slot: line = [[x1, y1], [x2, y2]] (the "
                             "centre line), width")
        ops.add_slot(model, body, line[0], line[1], params.get("width", 5.0))
    elif action == "tab_jog":
        line = params.get("line")
        if not line or len(line) != 2:
            raise ValueError("tab_jog: line = [[x1, y1], [x2, y2]] across "
                             "the tab, in the panel's own frame")
        ops.add_tab_jog(model, body, panel, line[0], line[1],
                        float(params.get("offset", 10.0)),
                        float(params.get("angle", 90.0)),
                        float(params.get("bend_radius", 0.0)),
                        params.get("fixed"), bool(params.get("extend")))
    elif action in ("mirror", "linear_pattern", "circular_pattern"):
        from . import sheet_metal_patterns as pat
        items = [(i["kind"], int(i["index"])) for i in
                 params.get("features") or []]
        if not items:
            raise ValueError(f"{action}: features = [{{kind, index}}, ...] "
                             "(kind pholes|tabs|tabjogs|gussets|corners|ears, "
                             "index from 0 — state lists them)")
        if action == "mirror":
            pat.mirror(model, body, items, params.get("plane", "x"),
                       float(params.get("at", 0.0)))
        else:
            for kind, index in items:
                if action == "linear_pattern":
                    pat.linear(model, body, kind, index,
                               int(params.get("count", 2)),
                               float(params.get("dx", 0.0)),
                               float(params.get("dy", 0.0)))
                else:
                    pat.circular(model, body, kind, index,
                                 int(params.get("count", 4)),
                                 params.get("pivot") or (0.0, 0.0),
                                 float(params.get("total", 360.0)))
    elif action == "gusset":
        if params.get("bend") is None or params.get("offset") is None:
            raise ValueError("gusset: bend (its number in the bend table, "
                             "from 1) and offset (mm along it from its "
                             "start)")
        ops.add_gusset(model, body, int(params["bend"]),
                       float(params["offset"]), float(params.get("d1", 10)),
                       float(params.get("d2", 10)),
                       float(params.get("width", 7.5)),
                       float(params.get("draft", 20.0)))
    elif action == "corner":
        if params.get("u") is not None and params.get("v") is not None:
            u, v = float(params["u"]), float(params["v"])
        elif params.get("along") is not None:
            u, v = ops.edge_position(model, body, panel, edge,
                                     float(params["along"]), 0.0)
        else:
            raise ValueError("corner: give u and v (near the corner, in "
                             "the panel's frame) or edge + along 0 "
                             "(the edge's start) / its length (the end)")
        ops.add_corner(model, body, panel, u, v, params.get("size", 5.0),
                       bool(params.get("chamfer")))
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
