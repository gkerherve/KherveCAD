"""The `blueprint` MCP tool (mcp_tools.py is past its size): read and
edit the Blueprint sheet open in the window — its views, every
dimension and note, the title block — the same way the mouse does.

Every change goes through `BlueprintWindow.commit`, so it is one undo
step in the Blueprint window and is saved in the document, and the
sheet on screen changes as the assistant works.

Notes are addressed by their INDEX in `state`'s list (re-read it after a
remove: later indices shift). Anchored notes (dimensions, leaders,
centre marks...) belong to a view and store points in that view's
MODEL plane (u, v): Front = (x, z), Top = (x, y), Right = (y, z), Left
= (-y, z), Back = (-x, z), Bottom = (x, -y). A linear dimension may say
`side` (above / below / left / right) and `gap` (sheet mm past the
view's edge) instead of the raw `offset`.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import base64

from . import blueprint_items as bi
from . import drawing

#: model plane of each projected view, for the assistant
PLANES = {"Front": ("x", "z"), "Top": ("x", "y"), "Right": ("y", "z"),
          "Left": ("-y", "z"), "Back": ("-x", "z"), "Bottom": ("x", "-y")}
#: features listed per view (a thread has thousands of edge ends)
MAX_POINTS = 80
MAX_CIRCLES = 60
LINEAR = ("horizontal", "vertical", "aligned")


class BlueprintError(Exception):
    pass


def _r(v, n=3):
    return round(float(v), n)


def _view_info(view):
    d = view.data
    rect = view.mapRectToScene(view.content_rect())
    kind = d.get("kind", "projected")
    info = {"id": d["id"], "kind": kind, "name": d.get("name"),
            "label": view.label_text(), "scale": _r(view.scale_, 6),
            "sheet_rect_mm": [_r(rect.left(), 2), _r(rect.top(), 2),
                              _r(rect.right(), 2), _r(rect.bottom(), 2)]}
    if kind == "projected" and d.get("name") in PLANES:
        info["plane"] = {"u": PLANES[d["name"]][0],
                         "v": PLANES[d["name"]][1]}
    if kind in ("section", "detail"):
        info.update({k: d[k] for k in ("axis", "letter", "parent",
                                        "centre", "radius", "factor")
                     if k in d})
    if kind != "shaded":
        u0, v0, u1, v1 = view.bounds
        info["model_bounds"] = [_r(u0), _r(v0), _r(u1), _r(v1)]
        groups = {}
        for c in view.circles:
            key = (_r(c["r"], 2), bool(c["closed"]))
            groups.setdefault(key, []).append([_r(v) for v in c["centre"]])
        info["circles"] = [{"r": r, "closed": closed, "count": len(cs),
                            "centres": cs[:20]}
                           for (r, closed), cs in sorted(
                               groups.items(), key=lambda kv: -kv[0][0])
                           ][:MAX_CIRCLES]
        pts = set()
        for seg in view.lines.get("visible", ()):
            for p in seg:
                pts.add((_r(p[0], 2), _r(p[1], 2)))
        pts = sorted(pts)
        info["edge_points"] = [list(p) for p in pts[:MAX_POINTS]]
        if len(pts) > MAX_POINTS:
            info["edge_points_note"] = (f"{len(pts)} edge ends, first "
                                        f"{MAX_POINTS} listed")
    return info


def _note_info(index, note):
    out = {"index": index}
    out.update(note.to_dict())
    if note.KIND == "dim":
        out["shows"] = note.label()
        out["measured"] = _r(note.value(), 4)
    return out


def state(win):
    scene = win.scene
    return {"drawing": win.current or "Assembly",
            "sheet": scene.sheet,
            "sheet_size_mm": list(drawing.SHEETS[scene.sheet]),
            "usable_rect_mm": [_r(v, 1) for v in (
                scene.usable_rect().left(), scene.usable_rect().top(),
                scene.usable_rect().right(), scene.usable_rect().bottom())],
            "scale": scene.scale, "scale_label": drawing.scale_label(
                scene.scale) if scene.scale else "",
            "style": scene.look.style, "hidden_lines": scene.hidden_lines,
            "merge_parts": scene.merge_parts,
            "parts_joined": scene.geometry.joined,
            "fields": dict(scene.fields),
            "views": [_view_info(v) for v in scene.views.values()],
            "notes": [_note_info(i, n) for i, n in
                      enumerate(scene.notes())],
            "note_types": sorted(bi.NOTE_CLASSES),
            "sheet_coordinates": "sheet mm, x right, y DOWN from the top "
                                 "left; text and free notes use them"}


def _view_of(scene, ref):
    if ref is None or ref == "":
        return None
    if ref in scene.views:
        return scene.views[ref]
    for v in scene.views.values():
        if str(v.data.get("name", "")).lower() == str(ref).lower() or \
                v.label_text().lower() == str(ref).lower():
            return v
    raise BlueprintError(f"no view {ref!r}; views: " + ", ".join(
        f"{k} ({v.label_text()})" for k, v in scene.views.items()))


def _linear_offset(view, data, side, gap):
    """The `offset` that puts a linear dimension's line `gap` sheet mm
    outside the view on `side` (view-local y grows DOWN, the content
    spans y -h..0)."""
    w, h = view.size()
    a, b = view.to_local(data["a"]), view.to_local(data["b"])
    if data["kind"] == "horizontal" or (data["kind"] == "aligned" and
                                        side in ("above", "below")):
        mid = (a[1] + b[1]) / 2.0
        line = gap if side == "below" else -h - gap
        if side not in ("above", "below"):
            raise BlueprintError("a horizontal dimension's side is "
                                 "above or below")
        return line - mid
    if side not in ("left", "right"):
        raise BlueprintError("a vertical dimension's side is left or "
                             "right")
    mid = (a[0] + b[0]) / 2.0
    line = w + gap if side == "right" else -gap
    return line - mid


def _prepare(scene, spec):
    data = dict(spec)
    data.setdefault("type", "dim")
    if data["type"] not in bi.NOTE_CLASSES:
        raise BlueprintError(f"note type {data['type']!r} is one of "
                             f"{sorted(bi.NOTE_CLASSES)}")
    cls = bi.NOTE_CLASSES[data["type"]]
    view = _view_of(scene, data.pop("view", None))
    if getattr(cls, "ANCHORED", False) and view is None:
        raise BlueprintError(f"a {data['type']} note needs a view")
    side, gap = data.pop("side", None), data.pop("gap", None)
    if data["type"] == "dim":
        data.setdefault("kind", "horizontal")
        k = data["kind"]
        if k in LINEAR:
            if "a" not in data or "b" not in data:
                raise BlueprintError("a linear dimension needs a and b "
                                     "(model points in the view's plane)")
            if side is not None:
                data["offset"] = _linear_offset(
                    view, data, side, float(10.0 if gap is None else gap))
        elif k in ("diameter", "radius"):
            if "centre" not in data or "r" not in data:
                raise BlueprintError("a diameter / radius needs centre "
                                     "and r")
        elif k == "angle":
            if not all(key in data for key in ("vertex", "p1", "p2")):
                raise BlueprintError("an angle needs vertex, p1 and p2")
        else:
            raise BlueprintError(f"dimension kind is one of {LINEAR} + "
                                 "diameter, radius, angle")
    return data, view


def _commit(win, label):
    win.scene.update_marks()
    win.scene.update()
    win.commit(label)


def run(main, params):
    from .blueprint import open_blueprint
    from . import drawing_set
    action = params.get("action") or "state"
    win = open_blueprint(main)
    win.flush_pending()
    if "drawing" in params:
        name = params.get("drawing") or None
        if name == drawing_set.ASSEMBLY:
            name = None
        drawing_set.show(win, name)
    scene = win.scene
    try:
        return _apply(win, scene, action, params)
    except (KeyError, TypeError, IndexError) as exc:
        raise BlueprintError(f"{type(exc).__name__}: {exc}")


def _notes_at(scene, indices):
    notes = scene.notes()
    bad = [i for i in indices if not 0 <= int(i) < len(notes)]
    if bad:
        raise BlueprintError(f"no note {bad}; there are {len(notes)} "
                             f"(indices 0..{len(notes) - 1})")
    return [notes[int(i)] for i in indices]


def _apply(win, scene, action, params):
    if action == "state":
        return state(win)
    if action == "add":
        made = []
        for spec in params.get("notes") or []:
            data, view = _prepare(scene, spec)
            item = scene.add_note(data, view)
            if item is None:
                raise BlueprintError(f"could not add {spec}")
            made.append(item)
        _commit(win, f"Add {len(made)} annotation(s)")
        notes = scene.notes()
        return {"added": [_note_info(notes.index(n), n) for n in made],
                "notes": len(notes)}
    if action == "set":
        changes = params.get("changes") or {}
        if not changes:
            raise BlueprintError("set needs changes {field: value}")
        indices = params.get("indices")
        if indices is None:
            indices = [params.get("index")]
        items = _notes_at(scene, indices)
        st = scene.state()
        notes = scene.notes()
        for item in items:
            i = notes.index(item)
            data = dict(st["notes"][i])
            side, gap = changes.get("side"), changes.get("gap")
            data.update({k: v for k, v in changes.items()
                         if k not in ("side", "gap")})
            data.pop("auto", None)      # edited: auto-dimension keeps it
            if side is not None and data.get("kind") in LINEAR:
                view = scene.views.get(data.get("view"))
                data["offset"] = _linear_offset(
                    view, data, side, float(10.0 if gap is None else gap))
            st["notes"][i] = data
        scene.load_state(st)
        _commit(win, "Edit annotation")
        notes = scene.notes()
        return {"edited": [_note_info(int(i), notes[int(i)])
                           for i in indices]}
    if action == "remove":
        if params.get("auto"):
            items = [n for n in scene.notes() if n.data.get("auto")]
        else:
            items = _notes_at(scene, params.get("indices") or [])
        scene.remove(items)
        _commit(win, "Delete")
        return {"removed": len(items), "notes": len(scene.notes())}
    if action == "revision":
        from . import blueprint_more
        rev = blueprint_more.add_revision(scene, params.get("text", ""),
                                          params.get("by", ""))
        _commit(win, "Revision " + rev)
        return {"revision": rev}
    if action in ("baseline", "chain"):
        from . import blueprint_more
        view = _view_of(scene, params.get("view"))
        pts = params.get("points") or []
        if view is None or len(pts) < 2:
            raise BlueprintError(f"{action} needs a view and 2+ points")
        kind = params.get("kind") or "horizontal"
        notes = blueprint_more.baseline(pts[0], pts[1:], kind) \
            if action == "baseline" else blueprint_more.chain(pts, kind)
        for data in notes:
            scene.add_note(data, view)
        _commit(win, f"Add {action} dimensions")
        return {"added": len(notes), "notes": len(scene.notes())}
    if action == "auto_dimension":
        scene.auto_dimension()
        _commit(win, "Auto-dimension")
        return {"notes": len(scene.notes())}
    if action == "arrange":
        scene.arrange(params.get("scale"))
        win.sync_controls()
        _commit(win, "Auto-arrange")
        return {"scale": scene.scale,
                "views": [_view_info(v) for v in scene.views.values()]}
    if action == "new_sheet":
        fields = dict(scene.fields)
        win._fresh()
        scene.fields.update(fields)
        scene.refresh_title()
        win.sync_controls()
        _commit(win, "New sheet")
        return state(win)
    if action == "add_view":
        kind = params.get("kind") or "projected"
        if kind == "projected":
            name = params.get("name")
            if name not in drawing.VIEWS:
                raise BlueprintError(f"name is one of {list(drawing.VIEWS)}")
            item = win.add_projected(name)
        elif kind == "section":
            axis = params.get("axis") or "x"
            item = win.add_section(axis)
            if "offset" in params:
                item.data["offset"] = float(params["offset"])
                scene.fill_view(item)
                _commit(win, "Section offset")
        elif kind == "detail":
            parent = _view_of(scene, params.get("parent") or "Front")
            item = win.add_detail(parent, params["centre"],
                                  float(params.get("radius", 10.0)),
                                  float(params.get("factor", 2.0)))
        elif kind == "shaded":
            item = win.add_shaded()
        else:
            raise BlueprintError("kind is projected, section, detail or "
                                 "shaded")
        if "x" in params and "y" in params:
            item.setPos(float(params["x"]), float(params["y"]))
            _commit(win, "Move view")
        return {"view": _view_info(item)}
    if action == "set_view":
        view = _view_of(scene, params.get("view"))
        st = scene.state()
        for d in st["views"]:
            if d["id"] == view.data["id"]:
                for k in ("x", "y", "label", "show_label", "aligned",
                          "factor", "radius", "centre", "offset", "yaw",
                          "pitch", "width"):
                    if k in params:
                        d[k] = params[k]
        scene.load_state(st)
        _commit(win, "Edit view")
        return {"view": _view_info(scene.views[view.data["id"]])}
    if action == "remove_view":
        view = _view_of(scene, params.get("view"))
        scene.remove([view])
        _commit(win, "Delete view")
        return {"views": [v.label_text() for v in scene.views.values()]}
    if action == "sheet":
        if params.get("sheet"):
            if params["sheet"] not in drawing.SHEETS:
                raise BlueprintError(f"sheet is one of "
                                     f"{list(drawing.SHEETS)}")
            scene.set_sheet(params["sheet"])
        if "scale" in params:
            scale = params["scale"]
            if isinstance(scale, str):
                scale = drawing.parse_scale(scale)
                if scale is None:
                    raise BlueprintError("scale is a number (0.5) or text "
                                         "like '1:2'")
            scene.set_scale(float(scale))
        if params.get("style"):
            if params["style"] not in bi.STYLES:
                raise BlueprintError(f"style is one of {list(bi.STYLES)}")
            scene.look.style = params["style"]
        if "hidden_lines" in params:
            scene.hidden_lines = bool(params["hidden_lines"])
            scene.refill()
        if "merge_parts" in params:
            scene.merge_parts = bool(params["merge_parts"])
            scene.geometry = type(scene.geometry)(scene.geometry.raw,
                                                  scene.merge_parts)
            scene.refill()
        if params.get("fields"):
            scene.fields.update({k: str(v) for k, v in
                                 params["fields"].items()})
            scene.refresh_title()
        win.sync_controls()
        _commit(win, "Sheet")
        return {"sheet": scene.sheet, "scale": scene.scale,
                "style": scene.look.style,
                "hidden_lines": scene.hidden_lines,
                "merge_parts": scene.merge_parts,
                "parts_joined": scene.geometry.joined,
                "fields": dict(scene.fields)}
    if action == "update_from_model":
        win.update_from_model()
        return {"views": len(scene.views), "notes": len(scene.notes())}
    if action == "undo":
        win.undo_stack.undo()
        return {"notes": len(scene.notes())}
    if action == "redo":
        win.undo_stack.redo()
        return {"notes": len(scene.notes())}
    if action == "render":
        from PyQt5.QtCore import QBuffer, QByteArray, QIODevice
        from . import blueprint_export
        from .mcp_server import IMAGE_KEY
        image = blueprint_export.to_image(
            scene, float(params.get("px_per_mm", 4.0)))
        data = QByteArray()
        buf = QBuffer(data)
        buf.open(QIODevice.WriteOnly)
        image.save(buf, "PNG")
        return {IMAGE_KEY: base64.b64encode(bytes(data)).decode("ascii"),
                "drawing": win.current or "Assembly"}
    if action == "export":
        from . import blueprint_export
        path = params.get("path")
        if not path:
            raise BlueprintError("export needs a path (.pdf .svg .png .dxf)")
        blueprint_export.export(scene, path)
        return {"written": path}
    raise BlueprintError(f"unknown action {action!r}")
