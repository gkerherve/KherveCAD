"""Meshes in named, coloured parts (Qt-free): read an OBJ (its groups and
materials, colours from the .mtl beside it) or a glTF binary (its nodes and
materials) as separate parts, and write the document as a glTF binary with
one named node per part and a material per colour.

Import goes through ``cadexchange_ui.place_parts`` like a STEP file: one
Object named after the file, a coloured group per part, so a car comes in
as body, glass, wheels... instead of one grey lump. Export lets a game (or
any 3D program) pick the parts out again by name.

glTF is Y-up and in metres; KherveCAD is Z-up in the document's unit:
(x, y, z) in glTF is (x, -z, y) here, times 1000 for millimetres.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

from .cadexchange import Part, Report, _display_name, _first_color, _hex, _parse_color, _unique_names

PART_EXTS = (".obj", ".glb")
_GLB_MAGIC = 0x46546C67


# ================================================================ import

def read_parts(path) -> list[Part]:
    """Every named part of an OBJ or GLB, triangles in millimetres (Z up).
    A file with a single group gives one part: the caller then imports it
    the plain way."""
    path = str(path)
    ext = Path(path).suffix.lower()
    if ext == ".obj":
        parts = _read_obj(path)
    elif ext == ".glb":
        parts = _read_glb(path)
    else:
        raise ValueError(f"{ext} does not hold named parts.")
    parts = [p for p in parts if p.tris]
    _unique_names(parts)
    return parts


def _read_mtl(path: Path) -> dict:
    """Material name -> "#rrggbb" from an .mtl file (Kd, the diffuse colour)."""
    colours, name = {}, None
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return colours
    for line in text.splitlines():
        bits = line.split()
        if not bits:
            continue
        if bits[0] == "newmtl" and len(bits) > 1:
            name = " ".join(bits[1:])
        elif bits[0] == "Kd" and name and len(bits) >= 4:
            try:
                colours[name] = _hex([float(b) for b in bits[1:4]])
            except ValueError:
                pass
    return colours


def _read_obj(path: str) -> list[Part]:
    folder = Path(path).parent
    colours: dict = {}
    verts: list = []
    parts: dict = {}
    group, material = "part", None
    for raw in Path(path).read_text(errors="replace").splitlines():
        bits = raw.split()
        if not bits:
            continue
        key = bits[0]
        if key == "v" and len(bits) >= 4:
            verts.append(tuple(float(b) for b in bits[1:4]))
        elif key in ("o", "g"):
            group = " ".join(bits[1:]) or group
        elif key == "usemtl":
            material = " ".join(bits[1:]) or None
        elif key == "mtllib":
            colours.update(_read_mtl(folder / " ".join(bits[1:])))
        elif key == "f" and len(bits) >= 4:
            ids = []
            for b in bits[1:]:
                i = int(b.split("/")[0])
                ids.append(i - 1 if i > 0 else len(verts) + i)
            pts = [verts[i] for i in ids]
            p = parts.get((group, material))
            if p is None:
                p = parts[(group, material)] = Part(group, None)
                p.material = material
            for k in range(1, len(pts) - 1):
                p.tris.append((pts[0], pts[k], pts[k + 1]))
    out = list(parts.values())
    for p in out:
        p.color = colours.get(getattr(p, "material", None) or "", None)
    return out


def _chunks(data: bytes):
    gltf, bin_ = None, b""
    at = 12
    while at + 8 <= len(data):
        length, kind = struct.unpack_from("<II", data, at)
        chunk = data[at + 8:at + 8 + length]
        if kind == 0x4E4F534A:
            gltf = json.loads(chunk.decode("utf-8"))
        elif kind == 0x004E4942:
            bin_ = chunk
        at += 8 + length
    return gltf, bin_


def _read_glb(path: str) -> list[Part]:
    from .photo3d import _accessor, _matmul, _node_matrix
    data = Path(path).read_bytes()
    if len(data) < 12 or struct.unpack_from("<I", data, 0)[0] != _GLB_MAGIC:
        raise ValueError(f"{Path(path).name} is not a GLB file.")
    gltf, bin_ = _chunks(data)
    if gltf is None:
        raise ValueError(f"{Path(path).name} holds no glTF JSON.")
    materials = gltf.get("materials", [])
    parts: list[Part] = []

    def colour(index):
        if index is None or index >= len(materials):
            return None
        f = materials[index].get("pbrMetallicRoughness", {}).get("baseColorFactor")
        return _hex(f[:3]) if f else None

    def visit(index, parent_m, inherited):
        node = gltf["nodes"][index]
        m = _matmul(parent_m, _node_matrix(node))
        name = node.get("name") or inherited
        if "mesh" in node:
            mesh = gltf["meshes"][node["mesh"]]
            name = name or mesh.get("name") or f"Part {len(parts) + 1}"
            prims = [p for p in mesh.get("primitives", [])
                     if p.get("mode", 4) == 4 and "POSITION" in p["attributes"]]
            for n, prim in enumerate(prims):
                pos = _accessor(gltf, bin_, prim["attributes"]["POSITION"])
                idx = ([i[0] for i in _accessor(gltf, bin_, prim["indices"])]
                       if "indices" in prim else list(range(len(pos))))
                pts = [tuple(sum(m[r][c] * p[c] for c in range(3)) + m[r][3]
                             for r in range(3)) for p in pos]
                part = Part(name if len(prims) == 1 else f"{name} {n + 1}",
                            colour(prim.get("material")))
                for k in range(0, len(idx) - 2, 3):
                    part.tris.append((pts[idx[k]], pts[idx[k + 1]],
                                      pts[idx[k + 2]]))
                parts.append(part)
        for child in node.get("children", []):
            visit(child, m, name)

    identity = [[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]
    scene = gltf.get("scenes", [{}])[gltf.get("scene", 0)] \
        if gltf.get("scenes") else {"nodes": list(range(len(gltf.get("nodes", []))))}
    for index in scene.get("nodes", []):
        visit(index, identity, None)
    # glTF is Y-up in metres (a model under 50 units across is taken as
    # metres, a bigger one as already in millimetres)
    pts = [v for p in parts for t in p.tris for v in t]
    span = max((max(v[i] for v in pts) - min(v[i] for v in pts)
                for i in range(3)), default=0.0)
    k = 1000.0 if 0 < span < 50 else 1.0
    for p in parts:
        p.tris = [tuple((v[0] * k, -v[2] * k, v[1] * k) for v in t)
                  for t in p.tris]
    return parts


# ================================================================ export

_PLACEMENT = ("x", "y", "z", "rx", "ry", "rz")


def _placed(node) -> bool:
    for key in _PLACEMENT:
        try:
            if abs(float(node.params.get(key, 0) or 0)) > 1e-9:
                return True
        except (TypeError, ValueError):
            return True        # an expression: keep the Object whole
    try:
        return abs(float(node.params.get("scale", 1) or 1) - 1) > 1e-9
    except (TypeError, ValueError):
        return True


def _export_parts(root):
    """(name, node) for every part: an Object at the origin is split into
    its own parts (a car's body, glass, wheels...); anything else is one."""
    for child in root.children:
        if child.type in ("assign", "variables") or not child.visible:
            continue
        kids = [c for c in child.children
                if c.visible and c.type not in ("assign", "variables")]
        if child.type == "component" and len(kids) > 1 and not _placed(child):
            for kid in kids:
                yield _display_name(kid), kid, child
        else:
            yield _display_name(child), child, None


def write_glb(root, path, fn=None, unit_mm=1.0) -> Report:
    """The document as a glTF binary: a node per part, named as in the
    tree, its triangles split by colour into primitives with materials."""
    from . import mesh
    k = unit_mm / 1000.0                       # document unit -> metres
    report = Report()
    buf = bytearray()
    accessors, views, meshes, nodes, materials = [], [], [], [], []
    mat_index: dict = {}
    mesh._set_fn(fn)
    mesh._set_refs(root)
    try:
        env: dict = {}
        for child in root.children:
            if child.type == "assign":
                mesh._apply_assign(child, env)
        for name, node, owner in _export_parts(root):
            local = dict(env)
            if owner is not None:
                for c in owner.children:
                    if c.type == "assign":
                        mesh._apply_assign(c, local)
            base = None
            if owner is not None and _first_color(node) is None:
                base = _first_color(owner)
            rows = mesh._tess(node, local,
                              (base, 1.0) if base else None, frozenset(), False)
            if not rows:
                continue
            by_colour: dict = {}
            for tri, c, _s in rows:
                key = (c[0], float(c[1])) if c else (None, 1.0)
                by_colour.setdefault(key, []).append(tri)
            prims = []
            for (col, alpha), tris in by_colour.items():
                if (col, alpha) not in mat_index:
                    rgb = _parse_color(col) or (0.74, 0.76, 0.8)
                    mat = {"name": str(col or "default"),
                           "pbrMetallicRoughness": {
                               "baseColorFactor": [*rgb, max(0.0, min(1.0, alpha))],
                               "metallicFactor": 0.0, "roughnessFactor": 0.6},
                           "doubleSided": True}
                    if alpha < 1:
                        mat["alphaMode"] = "BLEND"
                    mat_index[(col, alpha)] = len(materials)
                    materials.append(mat)
                pos, nor = [], []
                for t in tris:
                    p = [(v[0] * k, v[2] * k, -v[1] * k) for v in t]
                    u = [p[1][i] - p[0][i] for i in range(3)]
                    w = [p[2][i] - p[0][i] for i in range(3)]
                    n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2],
                         u[0] * w[1] - u[1] * w[0]]
                    ln = sum(x * x for x in n) ** 0.5 or 1.0
                    for v in p:
                        pos.extend(v)
                        nor.extend(x / ln for x in n)
                count = len(pos) // 3
                lo = [min(pos[i::3]) for i in range(3)]
                hi = [max(pos[i::3]) for i in range(3)]
                for data, extra in ((pos, {"min": lo, "max": hi}), (nor, {})):
                    while len(buf) % 4:
                        buf.append(0)
                    off = len(buf)
                    buf += struct.pack(f"<{len(data)}f", *data)
                    views.append({"buffer": 0, "byteOffset": off,
                                  "byteLength": len(data) * 4, "target": 34962})
                    accessors.append({"bufferView": len(views) - 1,
                                      "componentType": 5126, "count": count,
                                      "type": "VEC3", **extra})
                prims.append({"attributes": {"POSITION": len(accessors) - 2,
                                             "NORMAL": len(accessors) - 1},
                              "material": mat_index[(col, alpha)]})
            meshes.append({"name": name, "primitives": prims})
            nodes.append({"name": name, "mesh": len(meshes) - 1})
            report.parts += 1
            report.faceted += 1
            report.faceted_names.append(name)
    finally:
        mesh._set_fn(None)
        mesh._clear_refs()
    if not nodes:
        raise ValueError("There is nothing visible to export.")
    gltf = {"asset": {"version": "2.0", "generator": "KherveCAD"},
            "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}],
            "nodes": nodes, "meshes": meshes, "materials": materials,
            "accessors": accessors, "bufferViews": views,
            "buffers": [{"byteLength": len(buf)}]}
    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    js += b" " * (-len(js) % 4)
    buf += b"\0" * (-len(buf) % 4)
    out = struct.pack("<III", _GLB_MAGIC, 2, 12 + 8 + len(js) + 8 + len(buf))
    out += struct.pack("<II", len(js), 0x4E4F534A) + js
    out += struct.pack("<II", len(buf), 0x004E4942) + bytes(buf)
    Path(path).write_bytes(out)
    return report
