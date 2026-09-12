"""Runs an MCP tool against the live KherveCAD window.

`mcp_schema.py` is the contract; this is the implementation.  Every
method here touches the real `DocumentModel` and the real viewers, so
it MUST run on the GUI thread — `mcp_bridge.McpBridge` is what
guarantees that, and it also wraps each mutating call in one undo macro
so the user gets their model back with a single Ctrl+Z.

Nodes are addressed by ``CadNode.id``, which the app already keeps, so
there is no parallel identity scheme here.  Ids do not survive undo or
an open: both rebuild the tree from a snapshot, and the tool
descriptions say so.

Nothing here re-implements an editing operation.  Everything goes
through `DocumentModel` (which owns the change signals, the undo
snapshots and the mate bookkeeping), `scadparse` for code, `library`
for parts and `mates` for assemblies — so an MCP edit and a mouse edit
are the same edit.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import base64
import math
from pathlib import Path

from PyQt5.QtCore import QBuffer, QByteArray, Qt

from . import anchors, document, mates, mesh
from .mcp_schema import (CATEGORIES, DEFAULT_CATEGORY,
                         DEFAULT_LICENSE, DEFAULT_ORIGIN,
                         DEFAULT_VIEWS, FORMATS, ORIENTATIONS,
                         ORIGINS, PROJECTIONS, STILL_VIEWS,
                         WRAP_TYPES)
from .mcp_server import IMAGE_KEY
from .model import CONTAINER_TYPES, NODE_TYPES, validate

#: Cap on a rendered preview, so one look at the model stays cheap.
_DEFAULT_RENDER_WIDTH = 900

#: How long render_view waits for OpenSCAD by default, and at most.
_DEFAULT_WAIT_S = 30.0
_MAX_WAIT_S = 300.0

#: render_view parameters that call for the offscreen camera, which
#: leaves the user's own view where it is.
_CAMERA_KEYS = ("azimuth", "elevation", "distance", "zoom", "target",
                "target_node", "projection", "region", "orientations")

#: The largest side an offscreen render paints — a region crop renders
#: the whole picture bigger, then cuts the detail out of it.
_MAX_RENDER_SIDE = 4096


class ToolError(Exception):
    """A tool failed for a reason the client should read and act on."""


class McpToolExecutor:
    """Executes one named tool against a `MainWindow`."""

    def __init__(self, window):
        self._w = window

    # ── Plumbing ────────────────────────────────────────────────

    @property
    def _model(self):
        return self._w.model

    def execute(self, name: str, tool_input: dict) -> dict:
        """Run *name*; never raises — a failure comes back as {"error"}."""
        handler = getattr(self, f"_t_{name}", None)
        if handler is None:
            return {"error": f"Unknown tool: {name}"}
        try:
            return handler(tool_input or {})
        except ToolError as exc:
            return {"error": str(exc)}
        except Exception as exc:              # pragma: no cover - defensive
            return {"error": f"{type(exc).__name__}: {exc}"}

    # ── Node lookup ─────────────────────────────────────────────

    def _node(self, node_id):
        try:
            node = self._model.find(int(node_id))
        except (TypeError, ValueError):
            raise ToolError(f"{node_id!r} is not a node id.")
        if node is None:
            raise ToolError(
                f"No node with id {node_id} in the document. Ids are "
                "rebuilt by undo and by opening a file — call list_tree "
                "again.")
        return node

    def _nodes(self, ids):
        if not isinstance(ids, (list, tuple)) or not ids:
            raise ToolError("Pass a non-empty list of node ids.")
        return [self._node(i) for i in ids]

    def _scope(self):
        """The container new geometry belongs in: the Object the user
        has open in the Object tab, else the assembly root."""
        comp = self._w.builder.isolated_component()
        return comp if comp is not None else self._model.root

    def _env(self):
        return anchors.doc_env(self._model)

    def _fn(self):
        return self._model.effective_fn()

    def _errors(self):
        try:
            return validate(self._model.root)
        except Exception:
            return {}

    @staticmethod
    def _check_params(type_name: str, params) -> dict:
        """Reject a misspelt parameter rather than silently storing it.

        A stray key would sit in the node forever, do nothing, and give
        the client no hint that its edit was ignored.
        """
        if params is None:
            return {}
        if not isinstance(params, dict):
            raise ToolError("'params' must be an object.")
        known = set(NODE_TYPES[type_name]["params"])
        if type_name in ("component", "reference"):
            known |= {"mate", "anchors"}
        unknown = [k for k in params if k not in known]
        if unknown:
            raise ToolError(
                f"{type_name} has no parameter "
                f"{', '.join(repr(k) for k in unknown)}. It takes: "
                f"{', '.join(sorted(known))}.")
        return dict(params)

    def _bbox(self):
        try:
            tris = mesh.tessellate(self._model.root, fn=self._fn())
        except Exception:
            return None
        box = anchors.bbox(tris)
        if box is None:
            return None
        lo, hi = box
        return {"min": [round(v, 3) for v in lo],
                "max": [round(v, 3) for v in hi],
                "size": [round(hi[i] - lo[i], 3) for i in range(3)]}

    # ── Inspection ──────────────────────────────────────────────

    def _t_get_document_info(self, _params) -> dict:
        model, win = self._model, self._w
        errors = self._errors()
        comp = win.builder.isolated_component()
        objects = [{"id": c.id, "name": c.name, "visible": c.visible,
                    "instances": len(model.instances_of(c))}
                   for c in model.components()]
        masters = model.masters_group()
        return {
            "path": win._path,
            "unsaved_changes": bool(win._dirty),
            "units": "millimetres",
            "node_count": sum(1 for _ in model.root.walk()) - 1,
            "top_level": [n.name for n in model.root.children],
            "objects": objects,
            "masters": [m.name for m in masters.children] if masters
                       else [],
            "editing_object": ({"id": comp.id, "name": comp.name}
                               if comp is not None else None),
            "global_segments": int(model.global_fn),
            "global_segments_on": bool(model.global_fn_on),
            "openscad": {
                "available": bool(win.engine.available),
                "path": win.engine.binary or None,
                "note": ("Exact geometry: booleans really cut."
                         if win.engine.available else
                         "Not found — the preview approximates a "
                         "difference() by showing its first operand, so "
                         "holes look uncut. Edit > Locate OpenSCAD."),
            },
            "bounds_mm": self._bbox(),
            "reference_images": self._references(),
            "errors": [{"id": nid, "message": msg}
                       for nid, msg in errors.items()],
        }

    def _t_list_node_types(self, params) -> dict:
        want = params.get("category")
        out = []
        for name, spec in NODE_TYPES.items():
            if want and spec["category"] != want:
                continue
            out.append({
                "type": name,
                "label": spec["label"],
                "category": spec["category"],
                "container": name in CONTAINER_TYPES,
                "params": [
                    {"name": key, "label": label, "kind": kind,
                     "min": lo, "max": hi,
                     "default": spec["params"].get(key)}
                    for key, label, kind, lo, hi in spec["schema"]],
            })
        return {"count": len(out), "types": out,
                "note": ("A numeric parameter also accepts an "
                         "expression string, e.g. \"wall * 2\".")}

    def _describe(self, node, depth: int, params: bool, errors: dict):
        info = {"id": node.id, "type": node.type, "name": node.name,
                "children": len(node.children)}
        if not node.visible:
            info["visible"] = False
        if params and node.params:
            info["params"] = {k: v for k, v in node.params.items()
                              if k not in ("anchors",)}
        if node.id in errors:
            info["error"] = errors[node.id]
        if isinstance(node.params.get("mate"), dict):
            info["mate"] = dict(node.params["mate"])
        if node.children and depth != 0:
            info["nodes"] = [
                self._describe(c, depth - 1, params, errors)
                for c in node.children]
        return info

    def _t_list_tree(self, params) -> dict:
        root = (self._node(params["node_id"]) if params.get("node_id")
                else self._model.root)
        depth = params.get("depth")
        depth = 4 if depth is None else int(depth)
        show = params.get("params", True)
        errors = self._errors()
        return {
            "root": {"id": root.id, "type": root.type, "name": root.name},
            "editing_object": getattr(
                self._w.builder.isolated_component(), "name", None),
            "nodes": [self._describe(c, depth - 1, show, errors)
                      for c in root.children],
        }

    def _t_get_node(self, params) -> dict:
        node = self._node(params.get("node_id"))
        errors = self._errors()
        spec = NODE_TYPES.get(node.type, {})
        path, walker = [], node
        while walker is not None:
            path.append(walker.name)
            walker = walker.parent
        info = self._describe(node, 1, True, errors)
        info["path"] = " / ".join(reversed(path))
        info["parent_id"] = node.parent.id if node.parent else None
        info["label"] = spec.get("label", node.type)
        info["schema"] = [
            {"name": key, "label": label, "kind": kind,
             "min": lo, "max": hi}
            for key, label, kind, lo, hi in spec.get("schema", [])]
        return info

    def _t_get_code(self, params) -> dict:
        from . import bake
        model = self._model
        # a baked mesh (a blend) is thousands of rows of numbers nobody
        # reads: summarise them unless asked, so the program fits in a
        # client's context. Import ignores those rows, so the summarised
        # program still round-trips through apply_code.
        bake.ELIDE = not params.get("full")
        try:
            if params.get("node_id"):
                node = self._node(params["node_id"])
                code = model.subtree_scad(node)
                scope = node.name
            else:
                code = model.to_scad()
                scope = "whole document"
        finally:
            bake.ELIDE = False
        return {"scope": scope, "lines": len(code.splitlines()),
                "code": code}

    def _t_render_view(self, params) -> dict:
        win = self._w
        which = str(params.get("view", "3d")).lower()
        try:
            timeout = float(params.get("timeout", _DEFAULT_WAIT_S))
        except (TypeError, ValueError):
            raise ToolError("'timeout' must be a number of seconds.")
        timeout = min(max(timeout, 0.0), _MAX_WAIT_S)
        if which == "3d" and params.get("wait_for_exact", True):
            complete = self._wait_for_render(timeout)
        else:
            complete = self._render_settled()
        offscreen = which == "3d" and any(
            params.get(k) is not None for k in _CAMERA_KEYS)
        limit = max(int(params.get("max_width")
                        or _DEFAULT_RENDER_WIDTH), 16)
        if offscreen:
            image, extra = self._offscreen(params, limit)
        else:
            if params.get("orientation"):
                name = params["orientation"]
                if name not in ORIENTATIONS:
                    raise ToolError(
                        f"Unknown orientation {name!r}. Choose one of: "
                        f"{', '.join(ORIENTATIONS)}.")
                win.view3d.set_view(name)
            elif params.get("fit"):
                win.view3d.fit()
            widget = win.view2d if which == "2d" else win.view3d
            image = widget.grab()
            if image.isNull() or image.width() < 2:
                raise ToolError(
                    "The view has no size to render — the window may "
                    "be minimised.")
            if image.width() > limit:
                image = image.scaledToWidth(limit,
                                            Qt.SmoothTransformation)
            extra = ({"camera": win.view3d.camera_state()}
                     if which == "3d" else {})
        result = {IMAGE_KEY: self._png(image), "view": which,
                  "showing": (win.view3d.source if which == "3d" else
                              "sketch / assembly view"),
                  "width": image.width(), "height": image.height(),
                  "render_complete": complete}
        result.update(extra)
        if not complete:
            result["note"] = (
                "OpenSCAD was still rendering when the timeout ran out, "
                "so this is (partly) the built-in preview, where "
                "booleans are approximated. Call again, or raise "
                "timeout, for the exact render.")
        return result

    # ── render_view helpers ─────────────────────────────────────

    @staticmethod
    def _png(image) -> str:
        """A QImage/QPixmap as base64 PNG."""
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QBuffer.WriteOnly)
        image.save(buffer, "PNG")
        buffer.close()
        return base64.b64encode(bytes(data)).decode("ascii")

    def _render_settled(self) -> bool:
        engine = self._w.engine
        return not engine.available or engine.is_idle()

    def _wait_for_render(self, timeout_s: float) -> bool:
        """Pump the event loop until OpenSCAD is idle with nothing
        queued, so the picture shows the exact render and not the
        built-in approximation of it. True when it settled in time.

        Re-entry is safe: the bridge refuses a second tool call while
        this one runs — the guard an STL export already relies on."""
        import time

        from PyQt5.QtCore import QCoreApplication, QEventLoop, QThread
        engine = self._w.engine
        if not engine.available:
            return True           # the built-in preview IS the final word
        deadline = time.monotonic() + timeout_s
        calm = 0
        while True:
            QCoreApplication.processEvents(QEventLoop.AllEvents, 50)
            # idle on two passes in a row: a finished part that queues
            # the next render has had its chance to do so
            calm = calm + 1 if engine.is_idle() else 0
            if calm >= 2:
                return True
            if time.monotonic() >= deadline:
                return False
            QThread.msleep(15)

    def _world_tris(self, node) -> list:
        """World-space triangles of *node* as the 3D view draws it (in
        the Object tab, in that Object's own frame) — the built-in
        tessellation, so booleans are approximated."""
        win = self._w
        root = win._render_scope()[0]
        iso = root if root is not self._model.root else None
        with win._isolated_frame(iso):
            return mesh.selected_world_tris(root, {node.id},
                                            env=self._env(), fn=self._fn())

    def _world_points(self, node) -> list:
        return [v for tri in self._world_tris(node) for v in tri]

    @staticmethod
    def _number(params, key, positive=False):
        value = params.get(key)
        if value is None:
            return None
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ToolError(f"'{key}' must be a number.")
        if positive and value <= 0:
            raise ToolError(f"'{key}' must be greater than 0.")
        return value

    def _aim(self, params):
        """(yaw, pitch) for the offscreen camera: a preset, then any
        explicit azimuth/elevation on top."""
        view = self._w.view3d
        yaw, pitch = view.yaw, view.pitch
        name = params.get("orientation")
        if name:
            if name not in ORIENTATIONS:
                raise ToolError(
                    f"Unknown orientation {name!r}. Choose one of: "
                    f"{', '.join(ORIENTATIONS)}.")
            yaw, pitch = view.VIEWS[name]
        az = self._number(params, "azimuth")
        el = self._number(params, "elevation")
        return (yaw if az is None else az, pitch if el is None else el)

    def _offscreen(self, params, limit):
        """render_view from a camera of its own (View3D.snapshot)."""
        from PyQt5.QtCore import QRect
        view = self._w.view3d
        projection = params.get("projection")
        if projection is not None and projection not in PROJECTIONS:
            raise ToolError(f"Unknown projection {projection!r}. Choose "
                            f"one of: {', '.join(PROJECTIONS)}.")
        frame = None
        if params.get("target_node") is not None:
            node = self._node(params["target_node"])
            frame = self._world_points(node)
            if not frame:
                raise ToolError(
                    f"{node.name} has no geometry in the 3D view to "
                    "frame — it is hidden, empty, or 2D-only.")
        elif params.get("fit"):
            frame = True
        target = params.get("target")
        if target is not None:
            try:
                target = [float(v) for v in target]
            except (TypeError, ValueError):
                target = None
            if target is None or len(target) != 3:
                raise ToolError("'target' must be [x, y, z] in mm.")
        common = dict(distance=self._number(params, "distance", True),
                      target=target, projection=projection,
                      zoom=self._number(params, "zoom", True) or 1.0)
        if params.get("orientations"):
            return self._contact_sheet(params["orientations"], limit,
                                       frame, common)
        yaw, pitch = self._aim(params)
        vw, vh = view.width(), view.height()
        aspect = vh / vw if vw > 1 and vh > 1 else 0.75
        w, h = limit, max(int(round(limit * aspect)), 16)
        region = params.get("region")
        if region is None:
            image, cam = view.snapshot(w, h, yaw=yaw, pitch=pitch,
                                       frame=frame, **common)
            return image, {"camera": cam}
        try:
            x0, y0, x1, y1 = (float(v) for v in region)
        except (TypeError, ValueError):
            raise ToolError("'region' must be [x0, y0, x1, y1].")
        if not (0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0):
            raise ToolError("'region' is [x0, y0, x1, y1] as fractions "
                            "of the picture: 0 <= x0 < x1 <= 1 and "
                            "0 <= y0 < y1 <= 1.")
        # Same aspect as the whole picture, only bigger, so the framing
        # is the one the caller would see without a region.
        k = min(1.0 / (x1 - x0), 1.0 / (y1 - y0),
                _MAX_RENDER_SIDE / max(w, h))
        bw, bh = int(round(w * k)), int(round(h * k))
        image, cam = view.snapshot(bw, bh, yaw=yaw, pitch=pitch,
                                   frame=frame, **common)
        crop = image.copy(QRect(int(x0 * bw), int(y0 * bh),
                                max(int((x1 - x0) * bw), 1),
                                max(int((y1 - y0) * bh), 1)))
        if crop.width() > limit:
            crop = crop.scaledToWidth(limit, Qt.SmoothTransformation)
        return crop, {"camera": cam, "region": [x0, y0, x1, y1]}

    def _contact_sheet(self, names, limit, frame, common):
        """Several presets tiled into one labelled picture, each view
        framed on its own."""
        from PyQt5.QtCore import QRectF
        from PyQt5.QtGui import QColor, QImage, QPainter
        if not isinstance(names, (list, tuple)):
            raise ToolError("'orientations' must be a list of presets.")
        bad = [n for n in names if n not in ORIENTATIONS]
        if bad:
            raise ToolError(f"Unknown orientation {bad[0]!r}. Choose "
                            f"from: {', '.join(ORIENTATIONS)}.")
        names = list(dict.fromkeys(names))
        view = self._w.view3d
        cols = 1 if len(names) == 1 else 2 if len(names) <= 4 else 3
        rows = (len(names) + cols - 1) // cols
        tw = max(limit // cols, 64)
        th = max(int(tw * 0.75), 48)
        sheet = QImage(tw * cols, th * rows, QImage.Format_ARGB32)
        sheet.fill(QColor("#1e2226"))
        painter = QPainter(sheet)
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        tiles = []
        for i, name in enumerate(names):
            yaw, pitch = view.VIEWS[name]
            image, cam = view.snapshot(
                tw, th, yaw=yaw, pitch=pitch,
                frame=True if frame is None else frame, **common)
            x, y = (i % cols) * tw, (i // cols) * th
            painter.drawImage(x, y, image)
            painter.setPen(QColor("#1e2226"))
            painter.drawRect(x, y, tw - 1, th - 1)
            box = QRectF(x + 6, y + 6,
                         painter.fontMetrics().width(name) + 12, 20)
            painter.fillRect(box, QColor(0, 0, 0, 150))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(box, Qt.AlignCenter, name)
            tiles.append({"orientation": name, "camera": cam})
        painter.end()
        return sheet, {"tiles": tiles}

    def _t_list_parts(self, params) -> dict:
        from . import library
        part_id = params.get("part_id")
        if part_id:
            spec = library.PARTS.get(part_id)
            if spec is None:
                raise ToolError(f"No library part {part_id!r}.")
            sizes = spec.get("sizes") or {}
            return {
                "part_id": part_id, "label": spec["label"],
                "category": spec["category"],
                "sizes": {name: dict(dims) for name, dims in
                          sizes.items()},
                "dimensions": [{"name": k, "label": lbl}
                               for k, lbl in spec.get("fields", [])],
                "colors": list(spec.get("colors") or []),
            }
        want = params.get("category")
        groups = {}
        for pid, spec in library.PARTS.items():
            if want and spec["category"] != want:
                continue
            groups.setdefault(spec["category"], []).append(
                {"part_id": pid, "label": spec["label"],
                 "sizes": list(spec.get("sizes") or {})})
        return {"categories": [{"category": c, "parts": p}
                               for c, p in groups.items()]}

    def _t_list_examples(self, _params) -> dict:
        from . import examples
        return {"examples": [{"name": name, "category": category}
                             for name, category, _b in examples.EXAMPLES]}

    def _t_list_anchors(self, params) -> dict:
        model = self._model
        scope = (self._node(params["scope_id"]) if params.get("scope_id")
                 else None)
        available = mates.parts(model, scope)
        out = {"parts": [{"id": p.id, "name": p.name, "type": p.type}
                         for p in available]}
        if params.get("node_id"):
            node = self._node(params["node_id"])
            definition = mates.definition_of(model, node) or node
            found = anchors.anchors_of(definition, env=self._env(),
                                       fn=self._fn())
            out["node"] = {"id": node.id, "name": node.name}
            out["anchors"] = [{"name": a["name"], "kind": a["kind"],
                               "pos": [round(v, 3) for v in a["pos"]]}
                              for a in found]
            out["can_attach_to"] = [p.name for p
                                    in mates._mate_siblings(node)]
        return out

    # ── Measuring ───────────────────────────────────────────────

    def _node_box(self, node):
        pts = self._world_points(node)
        if not pts:
            raise ToolError(
                f"{node.name} has no geometry in the 3D view — it is "
                "hidden, empty, or 2D-only.")
        return ([min(p[i] for p in pts) for i in range(3)],
                [max(p[i] for p in pts) for i in range(3)])

    @staticmethod
    def _box_dict(lo, hi) -> dict:
        return {"min": [round(v, 3) for v in lo],
                "max": [round(v, 3) for v in hi],
                "size": [round(hi[i] - lo[i], 3) for i in range(3)],
                "center": [round((lo[i] + hi[i]) / 2, 3)
                           for i in range(3)]}

    def _t_get_node_bounds(self, params) -> dict:
        nodes = self._nodes(params.get("node_ids"))
        out, los, his = [], [], []
        for node in nodes:
            lo, hi = self._node_box(node)
            los.append(lo)
            his.append(hi)
            out.append({"id": node.id, "name": node.name,
                        **self._box_dict(lo, hi),
                        "approximate": mesh.uses_booleans(node)})
        result = {"nodes": out}
        if len(out) > 1:
            result["combined"] = self._box_dict(
                [min(lo[i] for lo in los) for i in range(3)],
                [max(hi[i] for hi in his) for i in range(3)])
        if any(e["approximate"] for e in out):
            result["note"] = (
                "Bounds come from the built-in tessellator, which "
                "approximates booleans (a difference shows its first "
                "operand). A cut never grows a part, so a difference's "
                "box is right; an intersection or minkowski can be off.")
        return result

    def _where(self, spec, label):
        """One end of a measurement: ``{"point": [x, y, z]}`` or
        ``{"node": id, "at": "center" | "min" | "max" | <anchor>}``.
        Returns (world point, (node, lo, hi) or None, description)."""
        if not isinstance(spec, dict):
            raise ToolError(
                f"'{label}' must be {{\"point\": [x, y, z]}} or "
                f"{{\"node\": id, \"at\": ...}}.")
        if spec.get("point") is not None:
            try:
                point = [float(v) for v in spec["point"]]
            except (TypeError, ValueError):
                point = []
            if len(point) != 3:
                raise ToolError(f"'{label}.point' must be [x, y, z].")
            return point, None, "point"
        if spec.get("node") is None:
            raise ToolError(f"'{label}' needs a 'point' or a 'node'.")
        node = self._node(spec["node"])
        lo, hi = self._node_box(node)
        box = (node, lo, hi)
        at = str(spec.get("at") or "center").strip()
        if at.lower() in ("center", "centre"):
            return ([(lo[i] + hi[i]) / 2 for i in range(3)], box,
                    f"{node.name} · centre")
        if at.lower() == "min":
            return lo, box, f"{node.name} · min corner"
        if at.lower() == "max":
            return hi, box, f"{node.name} · max corner"
        if node.type not in ("component", "reference"):
            raise ToolError(
                f"Anchors belong to Objects and their instances; "
                f"{node.name} is a {node.type}. Use at: center, min or "
                "max, or measure its Object.")
        definition = mates.definition_of(self._model, node) or node
        found = anchors.anchors_of(definition, env=self._env(),
                                   fn=self._fn())
        match = [a for a in found if a["name"].lower() == at.lower()]
        if not match:
            raise ToolError(
                f"{node.name} has no anchor {at!r}. Use center, min, max "
                f"or one of: {', '.join(a['name'] for a in found[:40])}.")
        pos, _direction = anchors.anchor_world(node, match[0], self._env())
        return pos, box, f"{node.name} · {match[0]['name']}"

    def _t_measure(self, params) -> dict:
        pa, box_a, la = self._where(params.get("a"), "a")
        pb, box_b, lb = self._where(params.get("b"), "b")
        delta = [pb[i] - pa[i] for i in range(3)]
        out = {"a": {"at": la, "point": [round(v, 3) for v in pa]},
               "b": {"at": lb, "point": [round(v, 3) for v in pb]},
               "delta": [round(v, 3) for v in delta],
               "distance": round(math.sqrt(sum(d * d for d in delta)), 3)}
        if box_a and box_b and box_a[0] is not box_b[0]:
            _na, alo, ahi = box_a
            _nb, blo, bhi = box_b
            # per axis: > 0 is clearance between the boxes, < 0 how far
            # they run into each other
            gap = [max(blo[i] - ahi[i], alo[i] - bhi[i]) for i in range(3)]
            out["gap"] = [round(g, 3) for g in gap]
            out["overlap"] = all(g < 0 for g in gap)
            out["clearance"] = round(
                math.sqrt(sum(max(g, 0.0) ** 2 for g in gap)), 3)
        return out

    def _t_section(self, params) -> dict:
        from . import section
        axis = str(params.get("axis", "")).lower()
        if axis not in section.PLANES:
            raise ToolError("'axis' must be 'x', 'y' or 'z'.")
        offset = self._number(params, "offset")
        try:
            timeout = float(params.get("timeout", _DEFAULT_WAIT_S))
        except (TypeError, ValueError):
            raise ToolError("'timeout' must be a number of seconds.")
        timeout = min(max(timeout, 0.0), _MAX_WAIT_S)
        if params.get("node_id") is not None:
            node = self._node(params["node_id"])
            tris = self._world_tris(node)
            complete = True
            source = f"built-in tessellation of {node.name}"
            if mesh.uses_booleans(node):
                source += " (booleans approximated)"
        else:
            complete = (self._wait_for_render(timeout)
                        if params.get("wait_for_exact", True)
                        else self._render_settled())
            tris = list(self._w.view3d.mesh)
            source = self._w.view3d.source
        if not tris:
            raise ToolError("There is nothing in the 3D view to cut.")
        sec = section.section(tris, axis, offset)
        limit = max(int(params.get("max_width") or 700), 120)
        image = section.draw(sec, limit, int(limit * 0.72))
        u_name, v_name = sec["plane"]
        outlines = []
        for o in sec["outlines"]:
            entry = {"closed": o["closed"], "vertices": len(o["points"]),
                     "area_mm2": round(o["area"], 3),
                     "hole": o["closed"] and o["area"] < 0}
            if params.get("include_points"):
                entry["points"] = [[round(u, 3), round(v, 3)]
                                   for u, v in o["points"]]
            outlines.append(entry)
        result = {IMAGE_KEY: self._png(image), "axis": axis,
                  "offset": round(sec["offset"], 3),
                  "plane": {"u": u_name, "v": v_name},
                  "outlines": outlines,
                  "area_mm2": round(sec["area"], 3),
                  "source": source, "render_complete": complete}
        if sec["bounds"]:
            u0, v0, u1, v1 = sec["bounds"]
            result["bounds"] = {u_name: [round(u0, 3), round(u1, 3)],
                                v_name: [round(v0, 3), round(v1, 3)]}
        else:
            k = section.PLANES[axis][0]
            vals = [v[k] for tri in tris for v in tri]
            result["note"] = (
                f"The plane misses the model: it spans {axis} = "
                f"{min(vals):g} to {max(vals):g} mm.")
        if any(not o["closed"] for o in sec["outlines"]):
            result["note"] = (
                "An outline did not close (drawn dashed red): the mesh "
                "has a gap on this plane — it is not watertight there.")
        return result

    def _t_check_code(self, params) -> dict:
        from .scadparse import parse_scad
        code = params.get("code")
        if not isinstance(code, str) or not code.strip():
            raise ToolError("'code' must be an OpenSCAD program.")
        try:
            root, warnings = parse_scad(code)
        except Exception as exc:
            raise ToolError(f"Could not parse that program: {exc}")
        types = {}
        for node in root.walk():
            if node is not root:
                types[node.type] = types.get(node.type, 0) + 1
        try:
            problems = validate(root)
        except Exception:
            problems = {}
        names = {n.id: n for n in root.walk()}
        return {
            "would_apply": bool(root.children),
            "top_level": len(root.children),
            "nodes": sum(types.values()),
            "types": dict(sorted(types.items())),
            "warnings": list(warnings),
            "problems": [{"node": names[i].name if i in names else i,
                          "type": names[i].type if i in names else "",
                          "message": msg}
                         for i, msg in problems.items()],
        }

    # ── Building ────────────────────────────────────────────────

    def _t_add_node(self, params) -> dict:
        type_name = str(params.get("type", ""))
        if type_name not in NODE_TYPES:
            raise ToolError(
                f"Unknown node type {type_name!r} — call "
                "list_node_types for the vocabulary.")
        values = self._check_params(type_name, params.get("params"))
        parent = (self._node(params["parent_id"])
                  if params.get("parent_id") else self._scope())
        if not parent.is_container():
            raise ToolError(
                f"'{parent.name}' ({parent.type}) cannot hold children.")
        node = self._model.add_node(type_name, values, parent,
                                    params.get("name", ""))
        if params.get("index") is not None:
            self._model.move_node(node, parent, int(params["index"]))
        return {"created": node.id, "type": node.type, "name": node.name,
                "parent": parent.name}

    def _t_set_params(self, params) -> dict:
        changes = params.get("changes")
        if not isinstance(changes, list) or not changes:
            raise ToolError("'changes' must be a non-empty list.")
        model = self._model
        touched, released = [], []
        for change in changes:
            node = self._node(change.get("id"))
            values = self._check_params(node.type, change.get("params"))
            if change.get("name"):
                model.rename(node, str(change["name"]))
            if "visible" in change:
                model.set_visible(node, bool(change["visible"]))
            had_mate = isinstance(node.params.get("mate"), dict)
            for key, value in values.items():
                model.set_param(node, key, value)
            if had_mate and not isinstance(node.params.get("mate"), dict):
                released.append(node.name)
            touched.append(node.id)
        result = {"updated": touched}
        if released:
            result["mates_released"] = released
            result["note"] = (
                "Setting a placement by hand releases the mate — it "
                "would otherwise overwrite the value on the next "
                "re-solve.")
        return result

    def _t_set_pose(self, params) -> dict:
        from . import expr
        wanted = params.get("joints")
        if not isinstance(wanted, dict):
            raise ToolError("'joints' must be an object: "
                            "{\"<joint name or id>\": {\"rx\": deg}}.")
        model, env = self._model, self._env()
        joints = [n for n in model.root.walk() if n.type == "joint"]
        index = {}
        for joint in joints:
            index.setdefault(str(joint.id), joint)
            index.setdefault(joint.name.lower(), joint)

        def num(node, key, default):
            try:
                return float(expr.resolve(node.params.get(key, default),
                                          env, default))
            except Exception:
                return default
        # check everything first: a typo halfway must not leave half
        # a pose applied
        plan, clamped = [], []
        for key, angles in wanted.items():
            joint = index.get(str(key).lower())
            if joint is None:
                names = ", ".join(j.name for j in joints) or \
                    "none yet — wrap a part in a joint node first"
                raise ToolError(f"No joint called {key!r}. Joints: {names}.")
            if not isinstance(angles, dict) or not angles or \
                    set(angles) - {"rx", "ry", "rz"}:
                raise ToolError(f"The pose for {joint.name} must be an "
                                "object of rx / ry / rz angles in degrees.")
            lo = num(joint, "min_angle", -180.0)
            hi = num(joint, "max_angle", 180.0)
            for axis, value in angles.items():
                try:
                    angle = float(value)
                except (TypeError, ValueError):
                    raise ToolError(f"{joint.name}.{axis} must be a "
                                    "number of degrees.")
                kept = min(max(angle, lo), hi)
                if kept != angle:
                    clamped.append({"joint": joint.name, "axis": axis,
                                    "asked": angle, "set": kept})
                plan.append((joint, axis, kept))
        for joint, axis, angle in plan:
            model.set_param(joint, axis, angle)
        result = {
            "posed": list(dict.fromkeys(j.name for j, _a, _v in plan)),
            "joints": [{"id": j.id, "name": j.name,
                        "angles": [round(num(j, k, 0.0), 3)
                                   for k in ("rx", "ry", "rz")],
                        "pivot": [round(num(j, k, 0.0), 3)
                                  for k in ("px", "py", "pz")],
                        "limits": [num(j, "min_angle", -180.0),
                                   num(j, "max_angle", 180.0)]}
                       for j in joints]}
        if clamped:
            result["clamped"] = clamped
            result["note"] = ("Some angles were past a joint's limits "
                              "and were clamped to them.")
        return result

    def _t_wrap_nodes(self, params) -> dict:
        op = str(params.get("operation", ""))
        if op not in WRAP_TYPES:
            raise ToolError(
                f"Cannot wrap in {op!r}. Choose one of: "
                f"{', '.join(WRAP_TYPES)}.")
        nodes = self._nodes(params.get("ids"))
        parents = {id(n.parent) for n in nodes}
        if len(parents) > 1:
            raise ToolError(
                "Those nodes have different parents. wrap_nodes works "
                "on siblings — move them together first.")
        if any(n.parent is None for n in nodes):
            raise ToolError("The document root cannot be wrapped.")
        values = self._check_params(op, params.get("params"))
        wrapper = self._model.wrap_nodes(nodes, op)
        if wrapper is None:
            raise ToolError("Nothing to wrap.")
        for key, value in values.items():
            wrapper.params[key] = value
        if params.get("name"):
            wrapper.name = str(params["name"])
        self._model.node_changed.emit(wrapper)
        return {"wrapper": wrapper.id, "type": op, "name": wrapper.name,
                "wrapped": [n.id for n in nodes]}

    def _t_move_node(self, params) -> dict:
        node = self._node(params.get("node_id"))
        parent = self._node(params.get("parent_id"))
        if not parent.is_container():
            raise ToolError(
                f"'{parent.name}' ({parent.type}) cannot hold children.")
        if node.parent is None:
            raise ToolError("The document root cannot be moved.")
        if any(n is node for n in self._model._ancestors(parent)):
            raise ToolError(
                f"'{parent.name}' is inside '{node.name}' — that would "
                "make the tree its own child.")
        index = params.get("index")
        self._model.move_node(node, parent,
                              None if index is None else int(index))
        return {"moved": node.id, "parent": parent.name,
                "index": node.index()}

    def _t_duplicate_node(self, params) -> dict:
        node = self._node(params.get("node_id"))
        if node.parent is None:
            raise ToolError("The document root cannot be duplicated.")
        clone = self._model.duplicate(node)
        return {"created": clone.id, "name": clone.name}

    def _t_delete_nodes(self, params) -> dict:
        nodes = self._nodes(params.get("ids"))
        gone = []
        for node in nodes:
            if node.parent is None:
                continue
            gone.append({"id": node.id, "name": node.name})
            self._model.remove_node(node)
        if not gone:
            raise ToolError("Nothing to delete.")
        return {"deleted": gone}

    def _t_ungroup_node(self, params) -> dict:
        node = self._node(params.get("node_id"))
        if not node.is_container() or node.parent is None:
            raise ToolError(
                f"'{node.name}' is not a container that can be "
                "ungrouped.")
        freed = [c.id for c in node.children]
        self._model.ungroup(node)
        return {"ungrouped": node.name, "freed": freed}

    def _t_set_color(self, params) -> dict:
        nodes = self._nodes(params.get("ids"))
        color = str(params.get("color", ""))
        if not color:
            raise ToolError("Pass a colour, e.g. '#4a90d9'.")
        alpha = float(params.get("alpha", 1.0))
        material = params.get("material")
        if material is not None:
            from .model import MATERIALS
            if material not in MATERIALS:
                raise ToolError(f"Unknown material {material!r}. Choose "
                                f"one of: {', '.join(MATERIALS)}.")
        wrappers = self._model.set_color(nodes, color, alpha, material)
        result = {"colored": [w.id for w in wrappers], "color": color,
                  "alpha": alpha}
        if material is not None:
            result["material"] = material
        return result

    def _t_round_edges(self, params) -> dict:
        nodes = self._nodes(params.get("ids"))
        radius = float(params.get("radius", 1.0))
        wrapper = self._model.round_edges(nodes, radius)
        if wrapper is None:
            raise ToolError("Nothing to round.")
        return {"wrapper": wrapper.id, "radius": radius,
                "note": "minkowski() with a sphere — slow to render; "
                        "keep the radius small."}

    def _t_apply_code(self, params) -> dict:
        from .chat import ChatPanel
        from .scadparse import parse_scad
        code = params.get("code")
        if not isinstance(code, str) or not code.strip():
            raise ToolError("'code' must be an OpenSCAD program.")
        mode = str(params.get("mode", "append")).lower()
        if mode not in ("append", "replace"):
            raise ToolError("'mode' must be 'append' or 'replace'.")
        try:
            root, warnings = parse_scad(code)
        except Exception as exc:
            raise ToolError(f"Could not parse that program: {exc}")
        # The parser never raises on a bad statement: it skips it with a
        # warning and carries on, which is right for importing a file
        # someone else wrote. For a program a client just composed it is
        # the wrong answer — applying nothing while reporting success is
        # a failure it cannot see. So refuse an empty parse.
        if not root.children:
            detail = ("; ".join(warnings[:5]) if warnings
                      else "it declared no geometry")
            raise ToolError(
                f"That program produced no objects: {detail}. Nothing "
                "was applied.")
        model = self._model
        target = (self._node(params["into_id"]) if params.get("into_id")
                  else self._scope())
        added = len(root.children)
        if target is model.root:
            if mode == "replace":
                model.root = root
            else:
                for child in list(root.children):
                    root.remove(child)
                    model.root.add(child)
            model.group_variables()
            model.structure_changed.emit()
        else:
            if not target.is_container():
                raise ToolError(
                    f"'{target.name}' ({target.type}) cannot hold "
                    "children.")
            # A program that is one module plus its call re-imports as a
            # single Object — unwrap it, or the part would nest inside
            # itself. Same helper the built-in assistant uses.
            nodes = ChatPanel._object_contents(root)
            if not nodes:
                raise ToolError(
                    "That program produced nothing to put inside "
                    f"'{target.name}'.")
            for node in list(nodes):
                node.parent.remove(node)
            if mode == "replace":
                for child in list(target.children):
                    target.remove(child)
            added = len(nodes)
            for node in nodes:
                target.add(node)
            model.structure_changed.emit()
        result = {"applied_into": target.name, "mode": mode,
                  "added": added,
                  "nodes": len(list(model.root.walk())) - 1}
        if warnings:
            result["warnings"] = warnings[:12]
        return result

    # ── Parts and assemblies ────────────────────────────────────

    def _t_make_object(self, params) -> dict:
        nodes = self._nodes(params.get("ids"))
        model = self._model
        if len(nodes) > 1:
            parents = {id(n.parent) for n in nodes}
            if len(parents) > 1:
                raise ToolError(
                    "Those nodes have different parents — group them "
                    "under one parent first.")
            node = model.group_nodes(nodes)
        else:
            node = nodes[0]
        comp = model.make_component(node)
        if comp is None:
            raise ToolError(
                f"'{node.name}' cannot become an Object.")
        if params.get("name"):
            comp = model.enclose_as_part(comp, str(params["name"]))
        return {"object": comp.id, "name": comp.name,
                "visible": comp.visible}

    def _t_add_instance(self, params) -> dict:
        comp = self._node(params.get("node_id"))
        if comp.type != "component":
            raise ToolError(
                f"'{comp.name}' is not an Object. Use make_object "
                "first, or add_linked_copy for a master.")
        ref = self._model.add_instance(comp)
        for key, value in self._check_params(
                "reference", params.get("params")).items():
            self._model.set_param(ref, key, value)
        return {"instance": ref.id, "name": ref.name, "of": comp.name}

    def _t_make_master(self, params) -> dict:
        node = self._node(params.get("node_id"))
        ref = self._model.make_master(node)
        if ref is None:
            raise ToolError(f"'{node.name}' cannot become a master.")
        return {"master": node.id, "name": node.name,
                "linked_copy": ref.id}

    def _t_add_linked_copy(self, params) -> dict:
        master = self._node(params.get("node_id"))
        ref = self._model.instance_master(master)
        for key, value in self._check_params(
                "reference", params.get("params")).items():
            self._model.set_param(ref, key, value)
        return {"copy": ref.id, "name": ref.name, "of": master.name}

    def _t_attach_parts(self, params) -> dict:
        model = self._model
        node = self._node(params.get("node_id"))
        if params.get("detach"):
            mates.detach(model, node)
            return {"detached": node.name}
        parent_name = str(params.get("parent", ""))
        siblings = {p.name: p for p in mates._mate_siblings(node)}
        if parent_name not in siblings:
            raise ToolError(
                f"'{node.name}' cannot attach to {parent_name!r}: a "
                f"mate parent must be a sibling. It can attach to: "
                f"{', '.join(siblings) or '(nothing at this level)'}.")
        child_anchor = str(params.get("anchor", ""))
        parent_anchor = str(params.get("parent_anchor", ""))
        for part, name in ((node, child_anchor),
                           (siblings[parent_name], parent_anchor)):
            definition = mates.definition_of(model, part) or part
            if mates.find_anchor(definition, name, env=self._env(),
                                 fn=self._fn()) is None:
                raise ToolError(
                    f"'{part.name}' has no anchor {name!r} — call "
                    "list_anchors for its names.")
        mates.attach(model, node, parent_name, child_anchor,
                     parent_anchor, float(params.get("offset", 0.0)),
                     float(params.get("spin", 0.0)))
        return {"attached": node.name, "to": parent_name,
                "placement": {k: node.params.get(k)
                              for k in model.PLACEMENT_KEYS}}

    def _t_insert_part(self, params) -> dict:
        from . import library
        part_id = str(params.get("part_id", ""))
        spec = library.PARTS.get(part_id)
        if spec is None:
            raise ToolError(
                f"No library part {part_id!r} — call list_parts.")
        sizes = spec.get("sizes") or {}
        size = params.get("size")
        if size and size not in sizes:
            match = [k for k in sizes if k.split(" ")[0] == size]
            if not match:
                raise ToolError(
                    f"{part_id} has no size {size!r}. It offers: "
                    f"{', '.join(sizes)}.")
            size = match[0]
        dims, size_key = {}, ""
        if sizes:
            keys = list(sizes)
            size_key = size or (keys[1] if len(keys) > 1 else keys[0])
            dims = dict(sizes[size_key])
            dims["_size"] = size_key
        dims.setdefault("port_length",
                        60.0 if sizes is library.CF_SIZES else 30.0)
        overrides = params.get("dims") or {}
        if not isinstance(overrides, dict):
            raise ToolError("'dims' must be an object of mm values.")
        dims.update(overrides)
        colors = spec.get("colors") or []
        if params.get("color"):
            want = str(params["color"]).strip().lower()
            match = [c for c in colors if c.lower() == want]
            if not match:
                raise ToolError(
                    f"{part_id} does not come in {params['color']!r}"
                    + (f". It offers: {', '.join(colors)}." if colors
                       else " — it has no colour choice."))
            dims["_color"] = match[0]
        node = library.build_part(part_id, dims)
        label = size_key.split(" ")[0] if size_key else ""
        if label and not node.name.startswith(label):
            node.name = f"{label} {node.name}"
        self._model.root.add(node)
        self._model.structure_changed.emit()
        # A library part is a finished part: one opaque row in the Main
        # assembly, its construction editable in the Object tab.
        comp = self._model.enclose_as_part(node, params.get("name", ""))
        return {"inserted": comp.id, "name": comp.name,
                "part_id": part_id, "size": size_key or None}

    def _t_select_nodes(self, params) -> dict:
        nodes = self._nodes(params["ids"]) if params.get("ids") else []
        tree = self._w.builder.active_tree()
        tree.select_nodes(nodes)
        return {"selected": [n.id for n in nodes]}

    # ── Document ────────────────────────────────────────────────

    def _t_set_render_options(self, params) -> dict:
        model, win = self._model, self._w
        if "segments" in params or "segments_on" in params:
            on = bool(params.get("segments_on", model.global_fn_on))
            value = params.get("segments")
            model.set_global_fn(on, None if value is None
                                else max(3, min(512, int(value))))
        if params.get("orientation"):
            name = params["orientation"]
            if name not in ORIENTATIONS:
                raise ToolError(f"Unknown orientation {name!r}.")
            win.view3d.set_view(name)
        elif params.get("fit"):
            win.view3d.fit()
        if params.get("projection"):
            name = params["projection"]
            if name not in PROJECTIONS:
                raise ToolError(f"Unknown projection {name!r}. Choose "
                                f"one of: {', '.join(PROJECTIONS)}.")
            win.set_projection(name)
        if params.get("stage") is not None:
            win.view3d.set_stage(bool(params["stage"]))
        if params.get("cavity") is not None:
            win.view3d.set_cavity(bool(params["cavity"]))
        if params.get("edges") is not None:
            win.view3d.set_edges(bool(params["edges"]))
        if params.get("opengl") is not None:
            win.view3d.set_hardware(bool(params["opengl"]))
        return {"global_segments": int(model.global_fn),
                "global_segments_on": bool(model.global_fn_on),
                "projection": win.view3d.projection,
                "stage": bool(win.view3d.stage),
                "opengl": bool(win.view3d.hardware),
                "cavity": bool(win.view3d.cavity),
                "edges": bool(win.view3d.edges)}

    def _guard_unsaved(self, params, tool: str):
        if self._w._dirty and not params.get("discard_unsaved_changes"):
            raise ToolError(
                "The user has unsaved changes. Offer to save_document "
                f"first; pass discard_unsaved_changes: true to {tool} "
                "only if they say to throw the work away.")

    def _fresh(self, path=None, dirty=False):
        """Settle the window after the document was replaced."""
        win = self._w
        win._path = path
        win._dirty = dirty
        win._fitted = False
        win.view3d.user_moved = False
        win.view3d.fit()
        win._update_title()

    def _references(self) -> list:
        return [{"index": i, "path": r.get("path"),
                 "plane": r.get("plane"),
                 "at": [r.get("x"), r.get("y")],
                 "size": [r.get("width"), r.get("height")],
                 "offset": r.get("offset", 0.0),
                 "opacity": r.get("opacity")}
                for i, r in enumerate(self._model.reference_images)]

    def _t_set_reference_image(self, params) -> dict:
        from . import refimage
        model = self._model
        if params.get("clear"):
            model.clear_reference_images()
        elif params.get("remove") is not None:
            index = int(params["remove"])
            if not 0 <= index < len(model.reference_images):
                raise ToolError(f"No reference image {index}; there are "
                                f"{len(model.reference_images)}.")
            model.remove_reference_image(index)
        else:
            path = str(params.get("path") or "")
            if not path:
                raise ToolError("Pass 'path' (an image file), or clear / "
                                "remove.")
            ratio = refimage.aspect(path)
            if ratio is None:
                raise ToolError(f"Could not read an image at {path!r}.")
            plane = {"Top": "Top (XY)", "Front": "Front (XZ)",
                     "Side": "Side (YZ)"}.get(params.get("plane") or "Top")
            if plane is None:
                raise ToolError("'plane' must be Top, Front or Side.")
            width = self._number(params, "width", True) or 100.0
            height = width * ratio
            x, y = self._number(params, "x"), self._number(params, "y")
            opacity = self._number(params, "opacity")
            model.add_reference_image(dict(
                path=path, plane=plane,
                x=-width / 2 if x is None else x,
                y=-height / 2 if y is None else y,
                width=width, height=height,
                offset=self._number(params, "offset") or 0.0,
                opacity=0.5 if opacity is None
                else min(max(opacity, 0.0), 1.0),
                visible=True))
        return {"reference_images": self._references()}

    def _t_load_example(self, params) -> dict:
        from . import examples
        name = str(params.get("name", ""))
        match = [b for n, _c, b in examples.EXAMPLES if n == name]
        if not match:
            raise ToolError(
                f"No example called {name!r} — call list_examples.")
        self._guard_unsaved(params, "load_example")
        examples.load_example(self._model, match[0])
        self._fresh(dirty=True)
        return {"loaded": name,
                "nodes": len(list(self._model.root.walk())) - 1}

    def _t_new_document(self, params) -> dict:
        self._guard_unsaved(params, "new_document")
        self._model.clear()
        self._fresh()
        return self._t_get_document_info({})

    def _t_open_document(self, params) -> dict:
        from . import scadparse
        from .engine import MESH_EXTS
        path = Path(str(params.get("path", ""))).expanduser()
        if not path.is_file():
            raise ToolError(f"No such file: {path}")
        self._guard_unsaved(params, "open_document")
        suffix = path.suffix.lower()
        extra = {}
        if suffix == ".kcad":
            document.load_kcad(self._model, str(path))
            self._fresh(path=str(path))
        elif suffix == ".scad":
            warnings = scadparse.import_scad(self._model, str(path))
            self._model.enclose_import_as_part(path.stem)
            # An import has no .kcad of its own yet, so it is unsaved
            # work from here on — the same as the File menu's import.
            self._fresh(dirty=True)
            if warnings:
                extra["warnings"] = warnings[:12]
            if not mesh.tessellate(self._model.root, fn=self._fn()):
                extra["note"] = (
                    "The program imported empty — it is probably built "
                    "on custom modules or functions outside the "
                    "importable subset. Add it as a scad_raw node "
                    "instead so the OpenSCAD engine still renders it.")
        elif suffix in MESH_EXTS:
            self._w._import_mesh_path(str(path))
            self._fresh(dirty=True)
        else:
            raise ToolError(
                f"{suffix or 'That file'} is not something KherveCAD "
                "opens — use .kcad, .scad or a mesh "
                f"({', '.join(MESH_EXTS)}).")
        self._w._add_recent(str(path))
        info = self._t_get_document_info({})
        info["opened"] = str(path)
        info.update(extra)
        return info

    def _t_save_document(self, params) -> dict:
        path = params.get("path") or self._w._path
        if not path:
            raise ToolError(
                "This document has never been saved, so there is "
                "nowhere to save it. Pass an absolute path ending in "
                ".kcad.")
        path = str(Path(str(path)).expanduser())
        if not path.lower().endswith(".kcad"):
            raise ToolError("Save as .kcad. For a program or a mesh use "
                            "export_document.")
        document.save_kcad(self._model, path)
        self._w._path = path
        self._w._dirty = False
        self._w._add_recent(path)
        self._w._update_title()
        return {"saved": path}

    def _t_export_document(self, params) -> dict:
        from .engine import write_stl
        path = str(Path(str(params.get("path", ""))).expanduser())
        suffix = Path(path).suffix.lower()
        if suffix == ".scad":
            document.export_scad(self._model, path)
            return {"exported": path, "format": "scad"}
        if suffix == ".png":
            from . import pngexport
            # the picture should show holes cut, as render_view does
            complete = self._wait_for_render(_DEFAULT_WAIT_S)
            try:
                result = pngexport.export_request(
                    self._w.view3d, path,
                    view=params.get("view") or "current",
                    width=params.get("width"),
                    height=params.get("height"),
                    transparent=bool(params.get("transparent")))
            except (ValueError, OSError) as exc:
                raise ToolError(str(exc))
            result["render_complete"] = complete
            return result
        if suffix not in (".stl", ".3mf"):
            raise ToolError(
                "Export path must end in .scad, .stl, .3mf or .png.")
        if self._w.engine.available:
            error = self._w.engine.export_mesh(self._model.to_scad(),
                                               path)
            if error:
                raise ToolError(f"OpenSCAD export failed:\n{error}")
            return {"exported": path, "format": suffix[1:],
                    "exact": True}
        if suffix == ".3mf":
            raise ToolError(
                "3MF is written by OpenSCAD and it was not found. "
                "Export .stl, or point the app at OpenSCAD "
                "(Edit > Locate OpenSCAD).")
        write_stl(mesh.tessellate(self._model.root, fn=self._fn()), path)
        return {
            "exported": path, "format": "stl", "exact": False,
            "warning": (
                "Exported with the built-in tessellator because "
                "OpenSCAD was not found. Booleans are APPROXIMATED — a "
                "difference() keeps its first operand and the holes are "
                "not cut. Do not send this to a printer; install "
                "OpenSCAD and export again."
                if mesh.uses_booleans(self._model.root) else
                "Exported with the built-in tessellator (OpenSCAD not "
                "found). This model uses no booleans, so the geometry "
                "is faithful."),
        }

    def _t_publish_to_printables(self, params) -> dict:
        from . import printables
        title = str(params.get("title", "")).strip()
        if not title:
            raise ToolError("A title is required — it names the "
                            "listing and every file in the bundle.")
        folder = params.get("folder")
        if not folder:
            base = (Path(self._w._path).parent if self._w._path
                    else Path.home() / "Documents")
            folder = base / f"{printables.slug(title)}-printables"
        formats = tuple(params.get("formats") or FORMATS)
        views = tuple(params.get("views") or DEFAULT_VIEWS)
        unknown = [v for v in views if v not in STILL_VIEWS]
        if unknown:
            raise ToolError(
                f"Unknown view(s) {', '.join(unknown)}. Choose from: "
                f"{', '.join(STILL_VIEWS)}.")
        bad = [f for f in formats if f not in FORMATS]
        if bad:
            raise ToolError(
                f"Unknown format(s) {', '.join(bad)}. Choose from: "
                f"{', '.join(FORMATS)}.")
        category = params.get("category") or DEFAULT_CATEGORY
        if category not in CATEGORIES:
            raise ToolError(
                f"Unknown category {category!r}. Choose from: "
                f"{', '.join(CATEGORIES)}.")
        origin = params.get("origin") or DEFAULT_ORIGIN
        if origin not in ORIGINS:
            raise ToolError(
                f"Unknown origin {origin!r}. Choose from: "
                f"{', '.join(ORIGINS)}.")
        bundle = printables.build_bundle(
            self._w, folder, title=title,
            description=str(params.get("description", "")),
            tags=params.get("tags") or [],
            license=str(params.get("license") or DEFAULT_LICENSE),
            formats=formats, views=views,
            summary=str(params.get("summary", "")),
            category=category, origin=origin)
        if params.get("open_browser"):
            printables.reveal(bundle["folder"])
            printables.open_upload_page()
        return {
            "folder": bundle["folder"],
            "files": [Path(f).name for f in bundle["files"]],
            "images": [Path(f).name for f in bundle["images"]],
            "summary": bundle["summary"],
            "category": bundle["category"],
            "warnings": bundle["warnings"],
            "published": False,
            "next_step": (
                "Nothing has been uploaded. Printables has no upload "
                "API, so the user finishes it: open "
                f"{printables.UPLOAD_URL} while signed in, drag in the "
                "files from the folder above, paste "
                "description.txt, and copy the remaining form fields "
                "from upload-form.txt. Tell them that, and do not "
                "describe the model as published."),
        }

    # ── Fillet ──────────────────────────────────────────────────

    def _local_tris(self, node):
        """The node's solid in its own frame (a fillet's children)."""
        from . import bake
        env = bake._codegen_env(node)
        fn = self._model.effective_fn()
        mesh._set_fn(fn)
        try:
            if node.type == "fillet":
                return [t for t, _c, _s in mesh._children_mesh(
                    node, env, None, frozenset(), False)]
            return mesh.tessellate(node, env=env, fn=fn)
        finally:
            mesh._set_fn(None)

    def _t_list_edges(self, params) -> dict:
        from . import fillet
        node = self._node(params.get("node_id"))
        try:
            min_angle = float(params.get("min_angle", fillet.MIN_ANGLE))
        except (TypeError, ValueError):
            raise ToolError("min_angle must be a number of degrees.")
        tris = self._local_tris(node)
        if not tris:
            raise ToolError(f"{node.name} has no solid to take edges from.")
        chains = fillet.chains(tris, min_angle)
        for i, c in enumerate(chains):
            c["index"] = i
        return {"node": node.id, "name": node.name, "edges": chains,
                "approximate": mesh.uses_booleans(node),
                "note": ("Edges come from the built-in mesh: a union of "
                         "overlapping shapes has no edge where they "
                         "meet, and a difference's hole has none — only "
                         "edges a single shape owns are listed.")}

    def _t_fillet_edges(self, params) -> dict:
        from . import fillet
        node = self._node(params.get("node_id"))
        if node.type == "fillet":
            target = node
        elif node.parent is not None and node.parent.type == "fillet":
            target = node.parent
        else:
            if node.parent is None:
                raise ToolError("The document root cannot be filleted.")
            target = self._model.wrap_nodes([node], "fillet")
        seeds = []
        for row in params.get("edges") or []:
            try:
                seed = [float(v) for v in row]
            except (TypeError, ValueError):
                seed = []
            if len(seed) != 6:
                raise ToolError("Each edge is 6 numbers: x1 y1 z1 x2 y2 z2.")
            seeds.append([round(v, 4) for v in seed])
        indices = params.get("chains") or []
        if indices:
            chains = fillet.chains(self._local_tris(target))
            for i in indices:
                if not isinstance(i, int) or not 0 <= i < len(chains):
                    raise ToolError(
                        f"chain index {i!r} is out of range (0-"
                        f"{len(chains) - 1}); call list_edges first.")
                seeds.append(chains[i]["seed"])
        have = [list(r) for r in (target.params.get("edges") or [])]
        for s in seeds:
            if not any(all(abs(a - b) < 1e-3 for a, b in zip(s, h))
                       for h in have):
                have.append(s)
        target.params["edges"] = have
        if params.get("radius") is not None:
            target.params["radius"] = float(params["radius"])
        if params.get("kind") in fillet.KINDS:
            target.params["kind"] = params["kind"]
        if params.get("detail") is not None:
            target.params["detail"] = max(1, int(params["detail"]))
        self._model.node_changed.emit(target)
        errors = validate(self._model.root)
        out = {"fillet": target.id, "name": target.name,
               "edges": len(have), "radius": target.params["radius"],
               "kind": target.params["kind"]}
        if target.id in errors:
            out["error"] = errors[target.id]
        out["note"] = ("The rounding shows in the exact OpenSCAD render "
                       "— call render_view after a moment; the built-in "
                       "preview cannot cut a convex edge.")
        return out

    # ── Checking ────────────────────────────────────────────────

    _APPROX_NOTE = ("The mesh is the built-in preview, which only "
                    "approximates booleans (a difference shows its first "
                    "operand, holes uncut) until the exact render lands.")

    def _check_nodes(self, params):
        from . import analysis_dialog
        ids = params.get("node_ids")
        if ids:
            nodes = self._nodes(ids)
        else:
            nodes = [n for n in self._scope().children
                     if n.visible and n.type not in ("variables",
                                                     "masters", "assign")]
            if not nodes:
                raise ToolError("Nothing to check — the scope is empty.")
        tris, approx = analysis_dialog.part_tris(self._w, nodes)
        if not tris:
            raise ToolError("Those nodes have no geometry to check.")
        return nodes, tris, approx

    def _t_mass_properties(self, params) -> dict:
        from . import analysis
        nodes, tris, approx = self._check_nodes(params)
        material = str(params.get("material") or analysis.DEFAULT_MATERIAL)
        if material not in analysis.MATERIALS:
            raise ToolError("Unknown material. Choose one of: "
                            + ", ".join(analysis.MATERIALS))
        price = float(params.get("price_per_kg") or analysis.DEFAULT_PRICE)
        p = analysis.mass_properties(tris)
        grams = analysis.mass(p["volume"], material)
        out = {"nodes": [n.id for n in nodes],
               "volume_mm3": round(p["volume"], 3),
               "area_mm2": round(p["area"], 3),
               "centre_of_mass": [round(v, 3) for v in p["centroid"]],
               "min": [round(v, 3) for v in p["min"]],
               "max": [round(v, 3) for v in p["max"]],
               "size": [round(v, 3) for v in p["size"]],
               "material": material, "mass_g": round(grams, 2),
               "cost": round(analysis.cost(grams, price), 2),
               "price_per_kg": price,
               "print_time_h_rough": round(analysis.print_time(
                   p["volume"]), 2),
               "approximate": approx}
        if approx:
            out["note"] = self._APPROX_NOTE
        return out

    def _t_check_printability(self, params) -> dict:
        from . import analysis
        nodes, tris, approx = self._check_nodes(params)
        report = analysis.print_check(
            tris,
            overhang_deg=float(params.get("overhang_deg")
                               or analysis.DEFAULT_OVERHANG),
            min_wall=float(params.get("min_wall")
                           or analysis.DEFAULT_MIN_WALL))
        out = {"nodes": [n.id for n in nodes], "summary": report["summary"],
               "checks": report["checks"],
               "overhang_fraction": round(report["overhang_fraction"], 4),
               "thinnest_wall_mm": (None if report["thinnest"] is None
                                    else round(report["thinnest"], 3)),
               "plate_area_mm2": round(report["plate_area"], 2),
               "height_mm": round(report["height"], 3),
               "approximate": approx}
        if approx:
            out["note"] = self._APPROX_NOTE
        return out

    def _t_check_interference(self, params) -> dict:
        from . import analysis, analysis_dialog
        ids = params.get("node_ids")
        if ids:
            nodes = self._nodes(ids)
        else:
            nodes = [n for _name, n in analysis_dialog.assembly_parts(
                self._w)]
        if len(nodes) < 2:
            raise ToolError("Give at least two nodes (or have two "
                            "visible parts in the assembly).")
        parts = []
        approx = False
        for n in nodes:
            tris, a = analysis_dialog.part_tris(self._w, [n])
            approx = approx or a
            parts.append((n.name, tris))
        pairs = analysis.interference(parts)
        by_name = {n.name: n.id for n in nodes}
        for p in pairs:
            p["a_id"], p["b_id"] = by_name.get(p["a"]), by_name.get(p["b"])
        out = {"pairs": pairs,
               "overlapping": sum(1 for p in pairs if p["status"] != "clear"),
               "approximate": approx}
        if approx:
            out["note"] = self._APPROX_NOTE
        return out

