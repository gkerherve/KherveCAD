"""The `pid` MCP tool (mcp_tools.py is past its size): build and read
the document's P&ID through the same `pid.Diagram` the window edits.

Actions: state (default: symbols, lines, notes, problems), symbols (the
symbol catalogue with ports), add (symbols list), set (one symbol by id
or tag), connect (lines list), set_line, remove, note, sheet (size,
fields, colour_lines), from_model, schedules, export (path: .pdf .svg
.png .dxf for the drawing, .xlsx .csv for the schedules), clear, render
(a PNG of the sheet the assistant can look at). Every change is one undo
step in the P&ID window and is saved in the document.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import pid as P
from . import pid_symbols as ps


class PidError(Exception):
    pass


def catalogue():
    return [{"kind": k, "label": s.label, "group": s.group,
             "tag_prefix": s.prefix, "ports": {
                 name: {"x": p[0], "y": p[1], "leaves": p[2]}
                 for name, p in s.ports.items()},
             "size_mm": [s.w, s.h], "data_fields": list(s.fields),
             "description": s.description}
            for k, s in ps.SYMBOLS.items()]


def _state(d):
    return {"sheet": d.sheet, "size_mm": list(d.size), "fields": d.fields,
            "symbols": [{k: s.get(k) for k in ("id", "kind", "tag",
                                                "label", "x", "y", "rot",
                                                "mirror", "data", "node")}
                        for s in d.symbols],
            "lines": [{k: ln.get(k) for k in (
                "id", "number", "kind", "service", "size", "material",
                "from", "to", "label", "insulated", "arrow")} |
                {"points": len(ln.get("points") or [])} for ln in d.lines],
            "notes": d.notes, "problems": d.check(),
            "usable_area_mm": [P.MARGIN + 5, P.MARGIN + 5,
                               d.size[0] - P.MARGIN - 5,
                               d.size[1] - P.MARGIN - P.TITLE_H - 5],
            "line_kinds": list(P.LINE_KINDS),
            "services": {k: v[0] for k, v in P.SERVICES.items() if k}}


def _end(spec):
    if isinstance(spec, str):
        # "P-101.out" or "s3:in"
        for sep in (":", "."):
            if sep in spec:
                sym, port = spec.rsplit(sep, 1)
                return {"symbol": sym, "port": port}
        raise PidError(f"a line end is 'TAG.port' or {{symbol, port}}, "
                       f"not {spec!r}")
    if isinstance(spec, dict):
        return dict(spec)
    raise PidError(f"bad line end {spec!r}")


def run(window, params):
    from .pid_window import diagram_of
    action = params.get("action") or "state"
    if action == "symbols":
        return {"symbols": catalogue(), "groups": list(ps.GROUPS)}
    d = diagram_of(window)
    try:
        result = _apply(window, d, action, params)
    except (P.PidError, KeyError, TypeError) as exc:
        raise PidError(str(exc))
    return result


def _apply(window, d, action, params):
    from .pid_window import store
    if action == "state":
        return _state(d)
    if action == "add":
        added = []
        for spec in params.get("symbols") or []:
            s = d.add_symbol(spec["kind"], spec.get("x", 50),
                             spec.get("y", 50), spec.get("tag"),
                             spec.get("label", ""), spec.get("rot", 0),
                             spec.get("mirror", False), spec.get("data"),
                             spec.get("node", ""))
            added.append({"id": s["id"], "tag": s["tag"], "ports": {
                k: v[0] for k, v in d.ports(s).items()}})
        store(window, d, "Add symbols")
        return {"added": added, "problems": d.check()}
    if action == "set":
        target = params.get("id") or params.get("tag")
        changes = {k: params[k] for k in ("x", "y", "rot", "mirror", "tag",
                                          "label", "node", "data", "kind")
                   if k in params and not (k == "tag" and
                                           params.get("id") is None)}
        s = d.set_symbol(target, **changes)
        store(window, d, "Edit symbol")
        return {"symbol": s}
    if action == "connect":
        made = []
        for spec in params.get("lines") or []:
            ln = d.connect(_end(spec["from"]), _end(spec["to"]),
                           spec.get("kind", "process"),
                           spec.get("service", ""), spec.get("size", ""),
                           spec.get("material", ""), spec.get("number"),
                           spec.get("label", ""), spec.get("arrow", True),
                           spec.get("insulated", False),
                           spec.get("points"))
            made.append({"id": ln["id"], "number": ln.get("number", ""),
                         "points": ln["points"]})
        store(window, d, "Connect")
        return {"lines": made, "problems": d.check()}
    if action == "set_line":
        target = params.get("id") or params.get("number")
        changes = {k: params[k] for k in ("service", "size", "material",
                                          "label", "kind", "arrow",
                                          "insulated", "points")
                   if k in params}
        if "new_number" in params:
            changes["number"] = params["new_number"]
        ln = d.set_line(target, **changes)
        if params.get("reroute"):
            ln["auto"] = True
            d.reroute()
        store(window, d, "Edit line")
        return {"line": ln}
    if action == "remove":
        d.remove(params.get("ids") or [])
        store(window, d, "Delete")
        return {"symbols": len(d.symbols), "lines": len(d.lines)}
    if action == "note":
        n = d.add_note(params.get("text", ""), params.get("x", 30),
                       params.get("y", 30), params.get("size", 3.0))
        store(window, d, "Add note")
        return {"note": n}
    if action == "sheet":
        if params.get("sheet"):
            if params["sheet"] not in P.SHEETS:
                raise PidError(f"sheet is one of {list(P.SHEETS)}")
            d.sheet = params["sheet"]
        d.fields.update({k: str(v) for k, v in
                         (params.get("fields") or {}).items()})
        if "colour_lines" in params:
            d.colour_lines = bool(params["colour_lines"])
        store(window, d, "Sheet")
        return {"sheet": d.sheet, "fields": d.fields}
    if action == "from_model":
        if params.get("replace", True):
            d = P.Diagram({"sheet": d.sheet, "fields": d.fields})
        d, found = P.from_model(window.model, d)
        store(window, d, "Start from model")
        return {"found": [{"part": n, "kind": k} for n, k in found],
                "symbols": len(d.symbols),
                "note": "Symbols are laid out in rows: move them "
                        "(set x, y) and connect their ports."}
    if action == "schedules":
        return d.schedules()
    if action == "export":
        from . import pid_render
        path = params.get("path")
        if not path:
            raise PidError("export needs a path")
        low = str(path).lower()
        if low.endswith((".xlsx", ".csv")):
            return {"written": pid_render.export_schedules(d, path)}
        return {"written": pid_render.export(d, path)}
    if action == "clear":
        d = P.Diagram({"sheet": d.sheet, "fields": d.fields})
        store(window, d, "Clear")
        return {"cleared": True}
    if action == "render":
        from . import pid_render
        from .mcp_tools import IMAGE_KEY
        import base64
        from PyQt5.QtCore import QBuffer, QByteArray, QIODevice
        image = pid_render.to_image(d, float(params.get("px_per_mm", 5.0)))
        data = QByteArray()
        buf = QBuffer(data)
        buf.open(QIODevice.WriteOnly)
        image.save(buf, "PNG")
        return {IMAGE_KEY: base64.b64encode(bytes(data)).decode("ascii"),
                "width": image.width(), "height": image.height(),
                "problems": d.check()}
    raise PidError(f"unknown action {action!r}")
