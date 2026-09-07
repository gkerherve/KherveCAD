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
from pathlib import Path

from PyQt5.QtCore import QBuffer, QByteArray, Qt

from . import anchors, document, mates, mesh
from .mcp_schema import ORIENTATIONS, WRAP_TYPES
from .mcp_server import IMAGE_KEY
from .model import CONTAINER_TYPES, NODE_TYPES, validate

#: Cap on a rendered preview, so one look at the model stays cheap.
_DEFAULT_RENDER_WIDTH = 900


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
        model = self._model
        if params.get("node_id"):
            node = self._node(params["node_id"])
            code = model.subtree_scad(node)
            scope = node.name
        else:
            code = model.to_scad()
            scope = "whole document"
        return {"scope": scope, "lines": len(code.splitlines()),
                "code": code}

    def _t_render_view(self, params) -> dict:
        win = self._w
        which = str(params.get("view", "3d")).lower()
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
        pixmap = widget.grab()
        if pixmap.isNull() or pixmap.width() < 2:
            raise ToolError(
                "The view has no size to render — the window may be "
                "minimised.")
        limit = int(params.get("max_width") or _DEFAULT_RENDER_WIDTH)
        if pixmap.width() > limit:
            pixmap = pixmap.scaledToWidth(limit, Qt.SmoothTransformation)
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QBuffer.WriteOnly)
        pixmap.save(buffer, "PNG")
        buffer.close()
        return {IMAGE_KEY: base64.b64encode(bytes(data)).decode("ascii"),
                "view": which,
                "showing": (win.view3d.source if which == "3d" else
                            "sketch / assembly view"),
                "width": pixmap.width(), "height": pixmap.height()}

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
        wrappers = self._model.set_color(nodes, color, alpha)
        return {"colored": [w.id for w in wrappers], "color": color,
                "alpha": alpha}

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
        return {"global_segments": int(model.global_fn),
                "global_segments_on": bool(model.global_fn_on)}

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
        if suffix != ".stl":
            raise ToolError("Export path must end in .scad or .stl.")
        if self._w.engine.available:
            error = self._w.engine.export_stl(self._model.to_scad(),
                                              path)
            if error:
                raise ToolError(f"OpenSCAD export failed:\n{error}")
            return {"exported": path, "format": "stl", "exact": True}
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
