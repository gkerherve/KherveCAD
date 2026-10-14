"""Animated characters (Qt-free): bring a rigged, animated glTF (.glb)
character in, dress it with KherveCAD parts that ride on its bones, pose
it or scrub any of its animations, and export it back as an animated GLB
for a game — skeleton, skin and every clip kept.

* **import_character** — the GLB becomes an Object: its body as coloured
  imported meshes (one per colour, written beside the library), standing
  on z = 0, facing -Y, in real millimetres; the character's source,
  scale and bones in the Object's ``character`` parameter.
* the **bone** node (a wrapper) — "this part rides on bone X":
  ``kcad_bone(name, pivot, a, t) { children }`` turns its children about
  the bone's head (``pivot``, at rest) by ``a`` and moves them by ``t``,
  which posing fills in. A helmet in ``bone("Head")`` follows the head.
* **attach** — wraps parts in bone nodes (the nearest bone when none is
  named).
* **pose** — a clip at a time and/or bone turns: the body is re-skinned
  with the character's own weights, every bone node follows its bone.
* **export_glb** — the source GLB plus one skinned mesh of everything
  added in KherveCAD, each part bound rigidly to its bone, at rest; the
  original skeleton and all clips carried over.

No package imports at module level beyond numpy (imported when used).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import struct
from pathlib import Path

# ------------------------------------------------------------ the node

NODE_TYPES = {
    "bone": dict(
        label="Bone (rides on a character's bone)", category="operation",
        icon="mdi.bone",
        params=dict(name="", px=0.0, py=0.0, pz=0.0, rx=0.0, ry=0.0,
                    rz=0.0, tx=0.0, ty=0.0, tz=0.0),
        schema=[("name", "Bone", "str", None, None),
                ("px", "Pivot X (bone head at rest)", "float", -1e7, 1e7),
                ("py", "Pivot Y", "float", -1e7, 1e7),
                ("pz", "Pivot Z", "float", -1e7, 1e7),
                ("rx", "Pose rX°", "float", -360.0, 360.0),
                ("ry", "Pose rY°", "float", -360.0, 360.0),
                ("rz", "Pose rZ°", "float", -360.0, 360.0),
                ("tx", "Pose move X", "float", -1e7, 1e7),
                ("ty", "Pose move Y", "float", -1e7, 1e7),
                ("tz", "Pose move Z", "float", -1e7, 1e7)]),
}
TYPES = frozenset(NODE_TYPES)
LEAVES = frozenset()
WRAPPERS = frozenset(NODE_TYPES)
#: the parts keep their own colours (and are never served from the
#: by-parameters cache, which does not see the children)
COLORED = frozenset(NODE_TYPES)
TEXT_PARAMS = frozenset({"name"})

HELPER = """\
module kcad_bone(name = "", pivot = [0, 0, 0], a = [0, 0, 0], t = [0, 0, 0]) {
    // the parts riding on bone `name`, posed: turned about the bone's head
    translate(t) translate(pivot) rotate(a) translate(-pivot) children();
}"""


def preamble(root) -> list:
    if any(n.type in TYPES for n in root.walk()):
        return HELPER.split("\n")
    return []


def statement(node, fmt, fn) -> str:
    from .model import scad_str
    p = node.params

    def vec(*keys):
        return "[" + ", ".join(fmt(p.get(k, 0.0)) for k in keys) + "]"
    return (f"kcad_bone(name = {scad_str(str(p.get('name', '')))}, "
            f"pivot = {vec('px', 'py', 'pz')}, a = {vec('rx', 'ry', 'rz')}, "
            f"t = {vec('tx', 'ty', 'tz')})")


def _b_bone(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num

    def v3(key):
        v = named.get(key)
        return [_num(x) for x in v[:3]] if isinstance(v, list) and \
            len(v) >= 3 else [0.0, 0.0, 0.0]
    name = named.get("name", "")
    name = name[1:-1] if isinstance(name, str) and name.startswith('"') \
        else str(name or "")
    (px, py, pz), (rx, ry, rz), (tx, ty, tz) = v3("pivot"), v3("a"), v3("t")
    return CadNode("bone", f"Bone [{name}]" if name else "Bone",
                   dict(name=name, px=px, py=py, pz=pz, rx=rx, ry=ry, rz=rz,
                        tx=tx, ty=ty, tz=tz))


BUILDERS = {"kcad_bone": _b_bone}


def check(node, env):
    if not str(node.params.get("name", "")).strip():
        return "bone: name the bone these parts ride on"
    if not node.children:
        return "bone: put the parts that ride on the bone inside it"
    return None


def matrix(p, env=None):
    """The bone node's transform: translate(t) about-pivot rotate(a)."""
    from . import mesh
    r = lambda k: mesh.rv(p.get(k, 0.0), env)  # noqa: E731
    px, py, pz = r("px"), r("py"), r("pz")
    m = mesh.mat_mul(mesh.mat_translate(px, py, pz),
                     mesh.mat_mul(mesh.mat_rotate(r("rx"), r("ry"), r("rz")),
                                  mesh.mat_translate(-px, -py, -pz)))
    return mesh.mat_mul(mesh.mat_translate(r("tx"), r("ty"), r("tz")), m)


def tess(node, env, color, sel, selected):
    from . import mesh
    kids = mesh._children_mesh(node, env, color, sel, selected)
    p = node.params
    if not kids or all(abs(float(mesh.rv(p.get(k, 0.0), env))) < 1e-12
                       for k in ("rx", "ry", "rz", "tx", "ty", "tz")):
        return kids
    return mesh._transform_colored(matrix(p, env), kids)


# ------------------------------------------------------------ glTF

_CT = {5120: "i1", 5121: "u1", 5122: "<i2", 5123: "<u2", 5125: "<u4",
       5126: "<f4"}
_NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


class CharacterError(ValueError):
    pass


class Glb:
    """A binary glTF: JSON, buffer, accessors, the node hierarchy, skins
    and animation clips sampled at any time."""

    def __init__(self, path):
        b = Path(path).read_bytes()
        if b[:4] != b"glTF":
            raise CharacterError(f"{Path(path).name} is not a binary glTF "
                                 "(.glb) file.")
        n = struct.unpack("<I", b[12:16])[0]
        self.json = json.loads(b[20:20 + n])
        off = 20 + n
        blen = struct.unpack("<I", b[off:off + 4])[0]
        self.bin = b[off + 8:off + 8 + blen]
        self.nodes = self.json.get("nodes", [])
        self.parent = {}
        for i, nd in enumerate(self.nodes):
            for c in nd.get("children", []):
                self.parent[c] = i

    def accessor(self, i):
        import numpy as np
        a = self.json["accessors"][i]
        bv = self.json["bufferViews"][a["bufferView"]]
        dt = np.dtype(_CT[a["componentType"]])
        nc = _NC[a["type"]]
        start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        stride = bv.get("byteStride", 0) or dt.itemsize * nc
        count = a["count"]
        rows = [self.bin[start + k * stride:start + k * stride
                         + dt.itemsize * nc] for k in range(count)] \
            if stride != dt.itemsize * nc else \
            [self.bin[start:start + count * stride]]
        arr = np.frombuffer(b"".join(rows), dtype=dt).reshape(count, nc) \
            .astype(np.float64)
        if a.get("normalized"):
            arr /= float(np.iinfo(dt).max)
        return arr

    # ---- transforms

    def trs(self, i):
        nd = self.nodes[i]
        if "matrix" in nd:
            return None
        return (list(nd.get("translation", [0, 0, 0])),
                list(nd.get("rotation", [0, 0, 0, 1])),
                list(nd.get("scale", [1, 1, 1])))

    def local(self, i, over=None):
        import numpy as np
        if over and i in over:
            t, q, s = over[i]
        else:
            nd = self.nodes[i]
            if "matrix" in nd:
                return np.array(nd["matrix"], dtype=float).reshape(4, 4).T
            t, q, s = self.trs(i)
        return _compose(t, q, s)

    def world(self, over=None):
        cache = {}

        def w(i):
            if i not in cache:
                m = self.local(i, over)
                cache[i] = w(self.parent[i]) @ m if i in self.parent else m
            return cache[i]
        return [w(i) for i in range(len(self.nodes))]

    # ---- animation

    def clips(self):
        return [(_short(a.get("name") or f"Clip {k + 1}"), self.duration(k))
                for k, a in enumerate(self.json.get("animations", []))]

    def clip_index(self, name):
        names = [c[0] for c in self.clips()]
        if name in names:
            return names.index(name)
        low = [n.lower() for n in names]
        if str(name).lower() in low:
            return low.index(str(name).lower())
        raise CharacterError(f"No clip {name!r}. The clips are: "
                             + ", ".join(names))

    def duration(self, k):
        anim = self.json["animations"][k]
        return max((float(self.accessor(s["input"]).max())
                    for s in anim["samplers"]), default=0.0)

    def sample(self, k, t):
        """{node: (translation, rotation, scale)} of clip *k* at time *t*
        (seconds, wrapped into the clip)."""
        import numpy as np
        anim = self.json["animations"][k]
        dur = self.duration(k)
        if dur > 0:
            t = t % dur if t != dur else dur
        out = {}
        for ch in anim["channels"]:
            tgt = ch["target"]
            node, path = tgt.get("node"), tgt["path"]
            if node is None or path not in ("translation", "rotation",
                                            "scale"):
                continue
            s = anim["samplers"][ch["sampler"]]
            times = self.accessor(s["input"]).ravel()
            vals = self.accessor(s["output"])
            interp = s.get("interpolation", "LINEAR")
            if interp == "CUBICSPLINE":
                vals = vals.reshape(len(times), 3, -1)[:, 1]
            j = int(np.searchsorted(times, t, side="right"))
            if j <= 0:
                v = vals[0]
            elif j >= len(times):
                v = vals[-1]
            elif interp == "STEP":
                v = vals[j - 1]
            else:
                u = (t - times[j - 1]) / max(times[j] - times[j - 1], 1e-9)
                a, b = vals[j - 1], vals[j]
                if path == "rotation":
                    if float(np.dot(a, b)) < 0:
                        b = -b
                    v = a * (1 - u) + b * u
                    v = v / max(np.linalg.norm(v), 1e-12)
                else:
                    v = a * (1 - u) + b * u
            base = list(self.trs(node) or ([0, 0, 0], [0, 0, 0, 1],
                                            [1, 1, 1]))
            cur = list(out.get(node, base))
            cur[{"translation": 0, "rotation": 1, "scale": 2}[path]] = \
                [float(x) for x in v]
            out[node] = tuple(cur)
        return out

    # ---- the skinned body

    def body(self, over=None):
        """``(triangles (N,3,3), sRGB colours (N,3), joint nodes (N,3,4),
        weights (N,3,4))`` of every skinned (or plain) mesh, posed by
        *over* (rest when None)."""
        import numpy as np
        W = self.world(over)
        tris, cols, joints, weights = [], [], [], []
        images = {}
        for ni, nd in enumerate(self.nodes):
            if "mesh" not in nd:
                continue
            skin = self.json["skins"][nd["skin"]] if "skin" in nd else None
            if skin:
                ibm = self.accessor(skin["inverseBindMatrices"]) \
                    .reshape(-1, 4, 4).transpose(0, 2, 1)
                jm = np.array([W[jn] @ ibm[k]
                               for k, jn in enumerate(skin["joints"])])
                jnodes = np.array(skin["joints"])
            for prim in self.json["meshes"][nd["mesh"]]["primitives"]:
                if prim.get("mode", 4) != 4:
                    continue
                at = prim["attributes"]
                pos = self.accessor(at["POSITION"])
                ph = np.c_[pos, np.ones(len(pos))]
                if skin and "JOINTS_0" in at:
                    J = self.accessor(at["JOINTS_0"]).astype(int)
                    Wt = self.accessor(at["WEIGHTS_0"])
                    Wt /= np.maximum(Wt.sum(1, keepdims=True), 1e-9)
                    v = np.zeros((len(pos), 4))
                    for c in range(4):
                        v += Wt[:, c:c + 1] * np.einsum("nij,nj->ni",
                                                        jm[J[:, c]], ph)
                    v = v[:, :3]
                    Jn = jnodes[J]
                else:
                    v = (ph @ W[ni].T)[:, :3]
                    Jn = np.full((len(pos), 4), -1)
                    Wt = np.zeros((len(pos), 4))
                idx = (self.accessor(prim["indices"]).astype(int).ravel()
                       if "indices" in prim else np.arange(len(pos))) \
                    .reshape(-1, 3)
                tris.append(v[idx])
                joints.append(Jn[idx])
                weights.append(Wt[idx])
                cols.append(self._colours(prim, at, idx, images))
        if not tris:
            raise CharacterError("This glTF has no triangle meshes.")
        return (np.concatenate(tris), np.concatenate(cols),
                np.concatenate(joints), np.concatenate(weights))

    def _colours(self, prim, at, idx, images):
        import numpy as np
        mat = self.json["materials"][prim["material"]] \
            if "material" in prim else {}
        pbr = mat.get("pbrMetallicRoughness", {})
        factor = _lin_to_srgb(np.array(pbr.get("baseColorFactor",
                                               [1, 1, 1, 1])[:3]))
        tex = pbr.get("baseColorTexture")
        if tex is None or "TEXCOORD_0" not in at:
            return np.tile(factor, (len(idx), 1))
        ti = tex["index"]
        if ti not in images:
            images[ti] = self._image(ti)
        im = images[ti]
        if im is None:
            return np.tile(factor, (len(idx), 1))
        uv = self.accessor(at["TEXCOORD_0"])[idx].mean(1)
        h, w = im.shape[:2]
        px = (np.mod(uv[:, 0], 1) * (w - 1)).astype(int)
        py = (np.mod(uv[:, 1], 1) * (h - 1)).astype(int)
        return im[py, px] * factor

    def _image(self, ti):
        import io
        import numpy as np
        try:
            from PIL import Image
        except ImportError:
            return None
        src = self.json["textures"][ti].get("source")
        img = self.json["images"][src]
        if "bufferView" not in img:
            return None
        bv = self.json["bufferViews"][img["bufferView"]]
        data = self.bin[bv.get("byteOffset", 0):bv.get("byteOffset", 0)
                        + bv["byteLength"]]
        return np.asarray(Image.open(io.BytesIO(data)).convert("RGB"),
                          dtype=np.float64) / 255.0

    def joint_names(self):
        seen = []
        for skin in self.json.get("skins", []):
            for j in skin["joints"]:
                if j not in seen:
                    seen.append(j)
        return {j: self.nodes[j].get("name") or f"bone{j}" for j in seen}


def _short(name):
    return str(name).split("|")[-1]


def _compose(t, q, s):
    import numpy as np
    x, y, z, w = q
    r = np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    m = np.eye(4)
    m[:3, :3] = r * np.asarray(s, dtype=float)
    m[:3, 3] = t
    return m


def _lin_to_srgb(c):
    import numpy as np
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92,
                    1.055 * np.power(c, 1 / 2.4) - 0.055)


def _srgb_to_lin(c):
    import numpy as np
    c = np.asarray(c, dtype=float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _palette(cols, max_colors=12):
    """Triangle colours grouped: quantised, the biggest groups kept, the
    rest mapped to the nearest. Deterministic, so a posed body splits
    into the same parts as at rest."""
    import numpy as np
    q = np.round(cols * 15) / 15
    keys, counts = np.unique(q, axis=0, return_counts=True)
    keep = keys[np.argsort(-counts, kind="stable")[:max_colors]]
    d = ((q[:, None, :] - keep[None, :, :]) ** 2).sum(-1)
    return keep, d.argmin(1)


def _hex(c):
    return "#" + "".join(f"{int(round(float(x) * 255)):02x}"
                         for x in [min(max(v, 0.0), 1.0) for v in c])


def _write_stl(path, tris):
    import numpy as np
    tris = np.asarray(tris, dtype=np.float64)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    rec = np.zeros(len(tris), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)),
                                     ("a", "<u2")])
    rec["n"] = n
    rec["v"] = tris
    with open(path, "wb") as fh:
        fh.write(b"KherveCAD character".ljust(80, b" "))
        fh.write(struct.pack("<I", len(tris)))
        fh.write(rec.tobytes())


# ------------------------------------------------------------ the frame
# glTF is Y-up, metres-ish, facing +Z; KherveCAD is Z-up, mm, facing -Y.
# cad = (rot(g) - centre) * k with rot(x, y, z) = (x, -z, y).

def _to_cad(info):
    import numpy as np
    k, c = float(info["k"]), np.asarray(info["centre"], dtype=float)
    rot = np.array([[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]],
                   dtype=float)
    t = np.eye(4)
    t[:3, 3] = -c
    s = np.diag([k, k, k, 1.0])
    return s @ t @ rot


def _gl_points(info, pts):
    import numpy as np
    m = np.linalg.inv(_to_cad(info))
    p = np.asarray(pts, dtype=float)
    # einsum, not @: Accelerate's matmul raises false overflow warnings
    return np.einsum("ij,nj->ni", m[:3, :3], p) + m[:3, 3]


def _cad_points(info, pts):
    import numpy as np
    m = _to_cad(info)
    p = np.asarray(pts, dtype=float).reshape(-1, 3)
    return np.einsum("ij,nj->ni", m[:3, :3], p) + m[:3, 3]


def _guess_height_mm(raw):
    """A model's height in mm from its height in its own units."""
    if 0.25 < raw < 6:
        return raw * 1000.0          # metres (glTF's unit)
    if 25 < raw < 600:
        return raw * 10.0            # centimetres
    return raw


# ------------------------------------------------------------ import

INFO_KEY = "character"


def info_of(node):
    """The character block of an imported character's Object, or None."""
    while node is not None:
        info = node.params.get(INFO_KEY) if node.type == "component" \
            else None
        if isinstance(info, dict) and info.get("source"):
            return node, info
        node = node.parent
    return None


def default_parts_dir(source):
    from . import user_library
    return str(user_library.folder() / "Characters & monsters" / "meshes"
               / Path(source).stem)


def import_character(model, path, height_mm=None, name="", parts_dir=None,
                     parent=None):
    """Bring an animated character in as an Object (see the module doc).
    Returns the Object node."""
    import numpy as np
    from .model import CadNode
    path = os.path.abspath(os.path.expanduser(str(path)))
    if not os.path.exists(path):
        raise CharacterError(f"No file at {path}.")
    glb = Glb(path)
    tris, cols, _j, _w = glb.body()
    rot = np.stack([tris[..., 0], -tris[..., 2], tris[..., 1]], axis=-1) \
        .reshape(-1, 3)
    lo, hi = rot.min(0), rot.max(0)
    raw = float(hi[2] - lo[2])
    height = float(height_mm) if height_mm else _guess_height_mm(raw)
    info = {"source": path, "height_mm": round(height, 3),
            "k": height / max(raw, 1e-9),
            "centre": [float((lo[0] + hi[0]) / 2), float((lo[1] + hi[1]) / 2),
                       float(lo[2])],
            "parts_dir": os.path.abspath(parts_dir or
                                         default_parts_dir(path)),
            "clip": "", "time": 0.0, "bones": {}}
    names = glb.joint_names()
    W = glb.world()
    heads = _cad_points(info, [W[j][:3, 3] for j in names]) \
        if names else []
    info["bones"] = {names[j]: [round(float(v), 2) for v in h]
                     for j, h in zip(names, heads)}
    title = name or Path(path).stem.replace("_", " ").replace("-", " ") \
        .strip().capitalize()
    comp = CadNode("component", title, {INFO_KEY: info})
    _write_body(comp, info, glb, None)
    (parent or model.root).add(comp)
    model.structure_changed.emit()
    return comp


def _write_body(comp, info, glb, over, key="rest"):
    """Write the (posed) body as one STL per colour and point the body
    parts of *comp* at them (creating them the first time)."""
    from .model import CadNode
    tris, cols, _j, _w = glb.body(over)
    keep, which = _palette(cols)        # colours don't change with the pose
    cad = _cad_points(info, tris.reshape(-1, 3)).reshape(-1, 3, 3)
    folder = Path(info["parts_dir"])
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("pose-*.stl"):        # the previous pose's files
        if key == "rest" or not old.name.startswith(f"pose-{key}-"):
            old.unlink(missing_ok=True)
    bodies = body_parts(comp)
    for ci, col in enumerate(keep):
        part = cad[which == ci]
        if not len(part):
            continue
        fname = f"body-{ci + 1}.stl" if key == "rest" \
            else f"pose-{key}-{ci + 1}.stl"
        _write_stl(folder / fname, part)
        if ci < len(bodies):
            bodies[ci].params["path"] = str(folder / fname)
        else:
            colour = CadNode("color", f"Body colour {_hex(col)}",
                             {"color": _hex(col), "alpha": 1.0,
                              "material": "Default"})
            colour.add(CadNode("stl_import", f"Body {ci + 1}",
                               {"path": str(folder / fname)}))
            comp.add(colour, ci)


def body_parts(comp):
    """The character's own body meshes (stl_import nodes named Body n),
    in order."""
    out = [n for n in comp.walk() if n.type == "stl_import"
           and n.name.startswith("Body ")]
    return sorted(out, key=lambda n: int(n.name.split()[-1])
                  if n.name.split()[-1].isdigit() else 0)


def bones_in(comp):
    return [n for n in comp.walk() if n.type == "bone"]


# ------------------------------------------------------------ attach

def nearest_bone(info, point):
    import numpy as np
    bones = info.get("bones") or {}
    if not bones:
        raise CharacterError("This character has no bones.")
    names = list(bones)
    d = np.linalg.norm(np.asarray([bones[n] for n in names])
                       - np.asarray(point, dtype=float), axis=1)
    return names[int(d.argmin())]


def _centre(node):
    from . import mesh
    tris = mesh.tessellate(node)
    if not tris:
        return None
    pts = [v for t in tris for v in t]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return [(a + b) / 2 for a, b in zip(lo, hi)]


def attach(model, nodes, bone=None):
    """Wrap each node in a bone node riding on *bone* (or, per node, on
    the nearest bone to its centre). Returns [(bone node, bone name)]."""
    out = []
    for node in nodes:
        found = info_of(node)
        if found is None:
            raise CharacterError(f"'{node.name}' is not inside an "
                                 "imported character.")
        comp, info = found
        if node.type == "bone":
            if bone:
                node.params["name"] = bone
            out.append((node, node.params["name"]))
            continue
        if node in body_parts(comp) or (node.type == "color" and any(
                b in body_parts(comp) for b in node.walk())):
            raise CharacterError(f"'{node.name}' is the character's own "
                                 "body: it already moves with the bones.")
        name = bone
        if name and name not in info.get("bones", {}):
            raise CharacterError(f"No bone {name!r}. Some bones: "
                                 + ", ".join(list(info["bones"])[:25]))
        if not name:
            c = _centre(node)
            if c is None:
                raise CharacterError(f"'{node.name}' has no geometry.")
            name = nearest_bone(info, c)
        wrapper = model.wrap_nodes([node], "bone")
        wrapper.name = f"Bone [{name}]"
        head = info["bones"][name]
        wrapper.params.update(name=name, px=head[0], py=head[1], pz=head[2])
        out.append((wrapper, name))
    for comp in {id(info_of(w)[0]): info_of(w)[0] for w, _ in out}.values():
        _, info = info_of(comp)
        if info.get("clip") or info.get("turns"):
            pose(model, comp, info.get("clip") or None,
                 info.get("time", 0.0), info.get("turns") or {})
    model.structure_changed.emit()
    return out


# ------------------------------------------------------------ pose

def _euler_deg(R):
    """OpenSCAD rotate([a, b, c]) = Rz(c) Ry(b) Rx(a) angles of R."""
    b = -math.asin(max(-1.0, min(1.0, float(R[2][0]))))
    if abs(math.cos(b)) > 1e-6:
        a = math.atan2(float(R[2][1]), float(R[2][2]))
        c = math.atan2(float(R[1][0]), float(R[0][0]))
    else:                                     # gimbal lock
        a = math.atan2(-float(R[1][2]), float(R[1][1]))
        c = 0.0
    return [math.degrees(a), math.degrees(b), math.degrees(c)]


def _turn_quat(rx, ry, rz):
    """A quaternion (x, y, z, w) for rotate([rx, ry, rz]) degrees in the
    bone's own (glTF) frame."""
    out = [0.0, 0.0, 0.0, 1.0]
    for axis, deg in ((0, rx), (1, ry), (2, rz)):
        h = math.radians(deg) / 2
        q = [0.0, 0.0, 0.0, math.cos(h)]
        q[axis] = math.sin(h)
        out = _qmul(q, out)
    return out


def _qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz]


def pose(model, comp, clip=None, time=0.0, turns=None):
    """Pose the character: clip *clip* at *time* seconds and/or *turns*
    {bone: [rx, ry, rz]} degrees added on top. ``clip=None`` and no
    turns is the rest pose. Returns a summary."""
    import numpy as np
    found = info_of(comp)
    if found is None:
        raise CharacterError("That is not an imported character.")
    comp, info = found
    glb = Glb(info["source"])
    over = {}
    if clip:
        over = glb.sample(glb.clip_index(clip), float(time))
    by_name = {v: k for k, v in glb.joint_names().items()}
    for bone, angles in (turns or {}).items():
        if bone not in by_name:
            raise CharacterError(f"No bone {bone!r}.")
        j = by_name[bone]
        t, q, s = over.get(j) or glb.trs(j) or ([0, 0, 0], [0, 0, 0, 1],
                                                [1, 1, 1])
        a = list(angles) + [0, 0, 0]
        over[j] = (t, _qmul(q, _turn_quat(*a[:3])), s)
    rest = not over
    key = "rest" if rest else hashlib.sha1(json.dumps(
        [clip, round(float(time), 4), turns], sort_keys=True,
        default=str).encode()).hexdigest()[:10]
    _write_body(comp, info, glb, None if rest else over, key)
    W0, W1 = glb.world(), glb.world(over or None)
    C = _to_cad(info)
    Ci = np.linalg.inv(C)
    by_name_world = {n: j for j, n in glb.joint_names().items()}
    moved = 0
    for b in bones_in(comp):
        j = by_name_world.get(b.params.get("name"))
        if j is None:
            continue
        D = C @ W1[j] @ np.linalg.inv(W0[j]) @ Ci
        R, d = D[:3, :3], D[:3, 3]
        P = np.array([float(b.params.get(k, 0.0)) for k in ("px", "py",
                                                              "pz")])
        a = _euler_deg(R)
        T = d + R @ P - P
        b.params.update(rx=round(a[0], 4), ry=round(a[1], 4),
                        rz=round(a[2], 4), tx=round(float(T[0]), 4),
                        ty=round(float(T[1]), 4), tz=round(float(T[2]), 4))
        moved += 1
    info.update(clip=clip or "", time=float(time),
                turns={k: list(v) for k, v in (turns or {}).items()})
    model.structure_changed.emit()
    return {"clip": clip or None, "time": float(time),
            "bones_with_parts": moved,
            "clips": [{"name": n, "seconds": round(d, 3)}
                      for n, d in glb.clips()]}


# ------------------------------------------------------------ export

def _pad4(b, fill=b"\0"):
    return b + fill * ((4 - len(b) % 4) % 4)


def gear_of(comp):
    """[(bone name or None, node)] — everything inside the character that
    is not its own body, at its outermost level: bone nodes by their
    bone, loose parts with None (attached to the nearest bone on
    export)."""
    out = []
    body = set(id(n) for n in body_parts(comp))

    def visit(node):
        for ch in node.children:
            if ch.type == "bone":
                out.append((ch.params.get("name") or None, ch))
            elif any(id(n) in body for n in ch.walk()):
                if ch.type != "stl_import":
                    visit(ch)             # a body colour group: look inside
            else:
                out.append((None, ch))
    visit(comp)
    return out


def export_glb(model, comp, out_path):
    """The source GLB with everything added in KherveCAD bound to its
    bones, at rest, every clip kept. Returns a summary."""
    import numpy as np
    from . import mesh
    found = info_of(comp)
    if found is None:
        raise CharacterError("That is not an imported character.")
    comp, info = found
    glb = Glb(info["source"])
    j = json.loads(json.dumps(glb.json))
    W = glb.world()
    names = glb.joint_names()
    by_name = {v: k for k, v in names.items()}
    joint_nodes = list(names)
    slot = {n: i for i, n in enumerate(joint_nodes)}
    groups = {}                      # (colour, bone node) -> [triangles]
    parts = 0
    for bone, node in gear_of(comp):
        kids = node.children if node.type == "bone" else [node]
        tris = []
        for kid in kids:             # at REST: the bone node's pose left out
            tris.extend(mesh.tessellate_colored(kid))
        if not tris:
            continue
        parts += 1
        if bone is None or bone not in by_name:
            pts = [v for t, _c in tris for v in t]
            centre = [(min(p[i] for p in pts) + max(p[i] for p in pts)) / 2
                      for i in range(3)]
            bone = nearest_bone(info, centre)
        jn = by_name[bone]
        for t, c in tris:
            colour = (c[0] if c else "#808080") or "#808080"
            groups.setdefault((colour, jn), []).append(t)
    if not groups:
        raise CharacterError("Nothing has been added to this character: "
                             "put parts inside it (or in bone nodes) "
                             "first.")
    blob = bytearray(_pad4(bytes(glb.bin)))
    views, accs = j["bufferViews"], j["accessors"]

    def add(arr, comp_type, typ, target=None, minmax=False):
        nonlocal blob
        off = len(blob)
        data = np.ascontiguousarray(arr).tobytes()
        blob += _pad4(data)
        bv = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
        if target:
            bv["target"] = target
        views.append(bv)
        acc = {"bufferView": len(views) - 1, "componentType": comp_type,
               "count": int(arr.shape[0]), "type": typ}
        if minmax:
            acc["min"] = arr.min(0).tolist()
            acc["max"] = arr.max(0).tolist()
        accs.append(acc)
        return len(accs) - 1

    j.setdefault("materials", [])
    mat_of = {}
    prims = []
    by_colour = {}
    for (colour, jn), tris in groups.items():
        by_colour.setdefault(colour, []).append((jn, tris))
    for colour, items in by_colour.items():
        pos, jo = [], []
        for jn, tris in items:
            g = _gl_points(info, np.asarray(tris, dtype=float)
                           .reshape(-1, 3))
            pos.append(g)
            jo.append(np.full(len(g), slot[jn]))
        g = np.concatenate(pos).astype(np.float32)
        t = g.reshape(-1, 3, 3)
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        joints = np.zeros((len(g), 4), dtype=np.uint16)
        joints[:, 0] = np.concatenate(jo)
        weights = np.zeros((len(g), 4), dtype=np.float32)
        weights[:, 0] = 1.0
        if colour not in mat_of:
            rgb = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)] \
                if str(colour).startswith("#") and len(colour) >= 7 \
                else [0.5, 0.5, 0.5]
            j["materials"].append({
                "name": f"Gear {colour}",
                "pbrMetallicRoughness": {
                    "baseColorFactor": [*_srgb_to_lin(rgb).tolist(), 1.0],
                    "metallicFactor": 0.0, "roughnessFactor": 0.8}})
            mat_of[colour] = len(j["materials"]) - 1
        prims.append({"attributes": {
            "POSITION": add(g, 5126, "VEC3", 34962, minmax=True),
            "NORMAL": add(np.repeat(n, 3, axis=0).astype(np.float32), 5126,
                          "VEC3", 34962),
            "JOINTS_0": add(joints, 5123, "VEC4", 34962),
            "WEIGHTS_0": add(weights, 5126, "VEC4", 34962)},
            "material": mat_of[colour]})
    ibm = np.array([np.linalg.inv(W[n]).T.ravel() for n in joint_nodes],
                   dtype=np.float32)
    skins = j.setdefault("skins", [])
    skin = {"name": "KherveCAD parts", "joints": joint_nodes,
            "inverseBindMatrices": add(ibm, 5126, "MAT4")}
    if skins and skins[0].get("skeleton") is not None:
        skin["skeleton"] = skins[0]["skeleton"]
    skins.append(skin)
    j["meshes"].append({"name": "KherveCAD parts", "primitives": prims})
    j["nodes"].append({"name": "KherveCAD parts",
                       "mesh": len(j["meshes"]) - 1,
                       "skin": len(skins) - 1})
    j["scenes"][j.get("scene", 0)]["nodes"].append(len(j["nodes"]) - 1)
    j["buffers"][0]["byteLength"] = len(blob)
    j.setdefault("asset", {})["generator"] = "KherveCAD character export"
    js = _pad4(json.dumps(j, separators=(",", ":")).encode(), b" ")
    bb = _pad4(bytes(blob))
    total = 12 + 8 + len(js) + 8 + len(bb)
    out_path = os.path.abspath(os.path.expanduser(str(out_path)))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2, total))
        fh.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        fh.write(struct.pack("<II", len(bb), 0x004E4942) + bb)
    return {"path": out_path, "parts": parts,
            "triangles": int(sum(len(t) for t in groups.values())),
            "bones_used": sorted({names[jn] for _c, jn in groups}),
            "clips": [n for n, _d in glb.clips()],
            "kb": total // 1024}
