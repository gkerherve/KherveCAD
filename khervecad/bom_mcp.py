"""The `bill_of_materials` MCP tool (mcp_tools.py is past its size).

action "get" (default) returns the BOM rows, totals and mass by
material; "set" types fields onto a line (by its item number or node
ids) — part_no, description, material, finish, supplier, cost, mass,
unit, notes, exclude; "export" writes .csv / .xlsx / .html / .json;
"place" puts the parts list and balloons on the Blueprint.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import bom


class BomError(Exception):
    pass


def _find(b, params, model):
    item = str(params.get("item") or "").strip()
    if item:
        for ln in b.flat():
            if ln.values.get("item") == item:
                return ln
        raise BomError(f"no BOM line {item!r}")
    ids = params.get("ids") or []
    if ids:
        want = {int(i) for i in ids}
        for ln in b.flat():
            if want & {n.id for n in ln.nodes if n is not None}:
                return ln
        raise BomError(f"no BOM line holds nodes {sorted(want)}")
    raise BomError("give the line's item number ('1.3.2') or node ids")


def run(window, params):
    model = window.model
    action = params.get("action") or "get"
    detail = params.get("detail") or "components"
    if detail not in ("components", "parts", "assemblies"):
        raise BomError("detail is components, parts or assemblies")
    b = bom.build(model, detail)
    if action == "get":
        rows = b.rows(params.get("max_level"))
        keep = params.get("columns")
        if keep:
            rows = [{k: v for k, v in r.items()
                     if k in keep or k in ("item", "level")} for r in rows]
        return {"title": b.title, "rows": rows, "totals": b.totals(),
                "by_material_kg": b.summary_by_material(),
                "editable": list(bom.EDITABLE),
                "materials": sorted(bom.DENSITY),
                "warnings": b.warnings[:20],
                "note": "Masses are SOLID estimates from the preview mesh "
                        "and the material's density; set 'mass' on a line "
                        "for a hollow part."}
    if action == "set":
        fields = params.get("fields") or {}
        if not fields:
            raise BomError("give fields to set")
        bad = [k for k in fields if k not in bom.EDITABLE]
        if bad:
            raise BomError(f"not BOM fields: {bad}; editable: "
                           f"{list(bom.EDITABLE)}")
        line = _find(b, params, model)
        from .bom_window import set_line_fields
        set_line_fields(model, line, fields)
        b = bom.build(model, detail)
        for ln in b.flat():
            if ln.values.get("item") == line.values.get("item"):
                return {"set": fields, "line": bom.line_row(ln),
                        "totals": b.totals()}
        return {"set": fields, "totals": b.totals()}
    if action == "export":
        path = params.get("path")
        if not path:
            raise BomError("export needs a path (.csv .xlsx .html .json)")
        try:
            written = bom.export(b, path)
        except (OSError, ValueError) as exc:
            raise BomError(str(exc))
        return {"written": written, "lines": len(b.flat()),
                "totals": b.totals()}
    if action == "place":
        board = window.open_blueprint()
        board.add_bom(detail="parts", balloons=params.get("balloons",
                                                          True))
        n = sum(1 for x in board.scene.notes() if x.KIND == "balloon"
                and x.data.get("auto"))
        return {"placed": True, "balloons": n,
                "mass": board.scene.fields.get("mass", "")}
    raise BomError(f"unknown action {action!r}")
