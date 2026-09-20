"""Mesh from a photo: a single picture turned into a 3D surface by an
image-to-3D model, then imported like any mesh.

Two hosted services and a local command are supported, all through
urllib (no SDKs): **Tripo** (api.tripo3d.ai v2 OpenAPI: upload the
picture, start an ``image_to_model`` task, poll, download), **Meshy**
(api.meshy.ai ``/openapi/v1/image-to-3d`` with the picture as a data
URI, poll, download) and a **local command** — any script that takes
``{image}`` and writes ``{output}`` (Hunyuan3D, TripoSR, TRELLIS run
locally). What comes back is GLB, OBJ or STL; ``parse_glb`` reads the
glTF binary (JSON + BIN chunk, triangle primitives, node transforms)
and ``to_stl`` writes the STL the app imports, scaled to a size in
millimetres and stood on the floor.

The result is a plausible surface from ONE view — the far side is
guessed — which is exactly what the sculpt node is for afterwards.
Qt-free; the dialog and the MCP tool live elsewhere.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import shlex
import struct
import subprocess
import time
import urllib.request
from pathlib import Path

BACKENDS = ("tripo", "meshy", "local")
#: environment variables the keys fall back to
KEY_ENV = {"tripo": "TRIPO_API_KEY", "meshy": "MESHY_API_KEY"}
TRIPO_URL = "https://api.tripo3d.ai/v2/openapi"
MESHY_URL = "https://api.meshy.ai/openapi/v1"
#: how long a hosted generation may take
TIMEOUT_S = 600.0
POLL_S = 3.0


class Photo3DError(RuntimeError):
    pass


# ------------------------------------------------------------ HTTP

def _request(url, data=None, headers=None, method=None, opener=None,
             timeout=60.0):
    """A JSON reply (dict) — or raw bytes when the body is not JSON."""
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    open_ = opener or urllib.request.urlopen
    try:
        with open_(req, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:          # pragma: no cover
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise Photo3DError(f"{url}: HTTP {exc.code} {detail}") from None
    except OSError as exc:
        raise Photo3DError(f"{url}: {exc}") from None
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return body


def _multipart(field, path):
    boundary = "----KherveCAD" + str(int(time.time() * 1000))
    ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; "
            f'name="{field}"; filename="{Path(path).name}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n").encode() \
        + Path(path).read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def _data_uri(path):
    ctype = mimetypes.guess_type(str(path))[0] or "image/png"
    return f"data:{ctype};base64," + base64.b64encode(
        Path(path).read_bytes()).decode("ascii")


def _download(url, out_path, opener=None):
    data = _request(url, opener=opener, timeout=300.0)
    if isinstance(data, dict):
        data = json.dumps(data).encode()
    Path(out_path).write_bytes(data)
    return str(out_path)


# ------------------------------------------------------- backends

def _poll(fetch, done, failed, deadline, sleep, progress):
    while True:
        state = fetch()
        if done(state):
            return state
        if failed(state):
            raise Photo3DError(f"the generation failed: {state}")
        if time.monotonic() > deadline:
            raise Photo3DError("the generation timed out")
        if progress:
            progress(state)
        sleep(POLL_S)


def generate_tripo(image, out_dir, key, opener=None, sleep=time.sleep,
                   progress=None, timeout=TIMEOUT_S):
    """Tripo v2 OpenAPI: upload → image_to_model task → poll → GLB."""
    if not key:
        raise Photo3DError("Tripo needs an API key (platform.tripo3d.ai).")
    auth = {"Authorization": f"Bearer {key}"}
    body, ctype = _multipart("file", image)
    up = _request(f"{TRIPO_URL}/upload", body,
                  dict(auth, **{"Content-Type": ctype}), "POST", opener)
    token = (up.get("data") or {}).get("image_token") if isinstance(
        up, dict) else None
    if not token:
        raise Photo3DError(f"Tripo did not accept the picture: {up}")
    ext = Path(image).suffix.lower().lstrip(".") or "png"
    ext = "jpeg" if ext == "jpg" else ext
    task = _request(f"{TRIPO_URL}/task", json.dumps({
        "type": "image_to_model",
        "file": {"type": ext, "file_token": token}}).encode(),
        dict(auth, **{"Content-Type": "application/json"}), "POST", opener)
    task_id = (task.get("data") or {}).get("task_id") if isinstance(
        task, dict) else None
    if not task_id:
        raise Photo3DError(f"Tripo did not start the task: {task}")
    deadline = time.monotonic() + timeout

    def fetch():
        r = _request(f"{TRIPO_URL}/task/{task_id}", headers=auth,
                     opener=opener)
        return r.get("data") or {} if isinstance(r, dict) else {}
    state = _poll(fetch, lambda s: s.get("status") == "success",
                  lambda s: s.get("status") in ("failed", "cancelled",
                                                "banned", "expired",
                                                "unknown"),
                  deadline, sleep, progress)
    out = state.get("output") or {}
    url = out.get("pbr_model") or out.get("model") or out.get("base_model")
    if not url:
        raise Photo3DError(f"Tripo finished without a model: {state}")
    return _download(url, Path(out_dir) / f"{Path(image).stem}_tripo.glb",
                     opener)


def generate_meshy(image, out_dir, key, opener=None, sleep=time.sleep,
                   progress=None, timeout=TIMEOUT_S):
    """Meshy: image-to-3d with the picture as a data URI → poll → GLB."""
    if not key:
        raise Photo3DError("Meshy needs an API key (meshy.ai).")
    headers = {"Authorization": f"Bearer {key}",
               "Content-Type": "application/json"}
    task = _request(f"{MESHY_URL}/image-to-3d", json.dumps({
        "image_url": _data_uri(image), "should_texture": False,
        "topology": "triangle", "should_remesh": True}).encode(),
        headers, "POST", opener)
    task_id = task.get("result") if isinstance(task, dict) else None
    if not task_id:
        raise Photo3DError(f"Meshy did not start the task: {task}")
    deadline = time.monotonic() + timeout

    def fetch():
        r = _request(f"{MESHY_URL}/image-to-3d/{task_id}", headers=headers,
                     opener=opener)
        return r if isinstance(r, dict) else {}
    state = _poll(fetch, lambda s: s.get("status") == "SUCCEEDED",
                  lambda s: s.get("status") in ("FAILED", "CANCELED"),
                  deadline, sleep, progress)
    urls = state.get("model_urls") or {}
    for kind in ("glb", "obj", "stl"):
        if urls.get(kind):
            return _download(urls[kind], Path(out_dir)
                             / f"{Path(image).stem}_meshy.{kind}", opener)
    raise Photo3DError(f"Meshy finished without a model: {state}")


def _split(command):
    """The command's words. POSIX rules would eat the backslashes of a
    Windows path (C:\tools\gen.exe), so Windows splits without them and
    strips the quotes that mode leaves on."""
    if os.name != "nt":
        return shlex.split(command)
    return [w[1:-1] if len(w) > 1 and w[0] == w[-1] and w[0] in "\"'" else w
            for w in shlex.split(command, posix=False)]


def generate_local(image, out_dir, command, run=subprocess.run,
                   timeout=TIMEOUT_S):
    """Run *command* with ``{image}`` and ``{output}`` filled in; the
    output is whatever mesh file the command writes at ``{output}`` —
    a GLB, OBJ or STL (the extension in the template decides)."""
    if not command or "{output}" not in command:
        raise Photo3DError("The local command must name {output} (and "
                           "usually {image}), e.g. "
                           "python gen.py --image {image} --out {output}")
    out = Path(out_dir) / f"{Path(image).stem}_generated.glb"
    if ".obj" in command or ".stl" in command:
        out = out.with_suffix(".obj" if ".obj" in command else ".stl")
    args = [a.replace("{image}", str(image)).replace("{output}", str(out))
            for a in _split(command)]
    if out.exists():                 # never mistake last time's file
        out.unlink()                 # for this run's
    try:
        result = run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Photo3DError(f"the command failed: {exc}") from None
    if getattr(result, "returncode", 0) != 0:
        raise Photo3DError(
            f"the command exited {result.returncode}: "
            f"{(result.stderr or result.stdout or '')[-400:]}")
    if not out.is_file():
        raise Photo3DError(f"the command wrote no file at {out}")
    return str(out)


def generate(image, out_dir, backend="tripo", key="", command="",
             opener=None, sleep=time.sleep, progress=None,
             run=subprocess.run):
    """The mesh file made from *image* by *backend*."""
    if not Path(image).is_file():
        raise Photo3DError(f"No such picture: {image}")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    if backend == "tripo":
        return generate_tripo(image, out_dir, key, opener, sleep, progress)
    if backend == "meshy":
        return generate_meshy(image, out_dir, key, opener, sleep, progress)
    if backend == "local":
        return generate_local(image, out_dir, command, run)
    raise Photo3DError(f"Unknown backend {backend!r}; choose one of "
                       f"{', '.join(BACKENDS)}.")


# ------------------------------------------------------------- GLB

_GLB_MAGIC = 0x46546C67
_CTYPES = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2),
           5125: ("I", 4), 5126: ("f", 4)}
_COUNTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def _accessor(gltf, bin_, index):
    acc = gltf["accessors"][index]
    view = gltf["bufferViews"][acc["bufferView"]]
    fmt, size = _CTYPES[acc["componentType"]]
    n = _COUNTS[acc["type"]]
    stride = view.get("byteStride") or size * n
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    out = []
    for i in range(acc["count"]):
        at = start + i * stride
        out.append(struct.unpack_from("<" + fmt * n, bin_, at))
    return out


def _matmul(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)]
            for r in range(4)]


def _node_matrix(node):
    if "matrix" in node:                     # column-major in glTF
        m = node["matrix"]
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    t = node.get("translation", [0, 0, 0])
    q = node.get("rotation", [0, 0, 0, 1])
    s = node.get("scale", [1, 1, 1])
    x, y, z, w = q
    rot = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
           [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
           [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return [[rot[r][c] * s[c] for c in range(3)] + [t[r]] for r in range(3)] \
        + [[0, 0, 0, 1]]


def parse_glb(path) -> list:
    """Triangles of a glTF binary: every triangle primitive of every
    mesh a scene node instances, node transforms applied."""
    data = Path(path).read_bytes()
    if len(data) < 12 or struct.unpack_from("<I", data, 0)[0] != _GLB_MAGIC:
        raise Photo3DError(f"{path} is not a GLB file")
    at, gltf, bin_ = 12, None, b""
    while at + 8 <= len(data):
        length, kind = struct.unpack_from("<II", data, at)
        chunk = data[at + 8:at + 8 + length]
        if kind == 0x4E4F534A:
            gltf = json.loads(chunk.decode("utf-8"))
        elif kind == 0x004E4942:
            bin_ = chunk
        at += 8 + length
    if gltf is None:
        raise Photo3DError(f"{path} holds no glTF JSON")
    tris = []

    def mesh_tris(mesh_index, m):
        for prim in gltf["meshes"][mesh_index].get("primitives", []):
            if prim.get("mode", 4) != 4 or "POSITION" not in prim["attributes"]:
                continue
            pos = _accessor(gltf, bin_, prim["attributes"]["POSITION"])
            if "indices" in prim:
                idx = [i[0] for i in _accessor(gltf, bin_, prim["indices"])]
            else:
                idx = list(range(len(pos)))
            pts = [tuple(sum(m[r][c] * p[c] for c in range(3)) + m[r][3]
                         for r in range(3)) for p in pos]
            for k in range(0, len(idx) - 2, 3):
                tris.append((pts[idx[k]], pts[idx[k + 1]], pts[idx[k + 2]]))

    def visit(index, parent_m):
        node = gltf["nodes"][index]
        m = _matmul(parent_m, _node_matrix(node))
        if "mesh" in node:
            mesh_tris(node["mesh"], m)
        for child in node.get("children", []):
            visit(child, m)
    identity = [[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]
    scenes = gltf.get("scenes") or []
    roots = scenes[gltf.get("scene", 0)].get("nodes", []) if scenes else \
        list(range(len(gltf.get("nodes", []))))
    if not gltf.get("nodes"):
        for i in range(len(gltf.get("meshes", []))):
            mesh_tris(i, identity)
    for r in roots:
        visit(r, identity)
    return tris


def write_glb(tris, path):
    """A minimal GLB of *tris* (one mesh, one node) — for tests and for
    handing a surface to another tool."""
    verts, index, faces = [], {}, []
    for tri in tris:
        for v in tri:
            k = tuple(float(c) for c in v)
            i = index.get(k)
            if i is None:
                i = index[k] = len(verts)
                verts.append(k)
            faces.append(i)
    pos = b"".join(struct.pack("<3f", *v) for v in verts)
    idx = b"".join(struct.pack("<I", i) for i in faces)
    lo = [min(v[c] for v in verts) for c in range(3)] if verts else [0, 0, 0]
    hi = [max(v[c] for v in verts) for c in range(3)] if verts else [0, 0, 0]
    gltf = {"asset": {"version": "2.0"}, "scene": 0,
            "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0},
                                        "indices": 1, "mode": 4}]}],
            "accessors": [{"bufferView": 0, "componentType": 5126,
                           "count": len(verts), "type": "VEC3",
                           "min": lo, "max": hi},
                          {"bufferView": 1, "componentType": 5125,
                           "count": len(faces), "type": "SCALAR"}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0,
                             "byteLength": len(pos)},
                            {"buffer": 0, "byteOffset": len(pos),
                             "byteLength": len(idx)}],
            "buffers": [{"byteLength": len(pos) + len(idx)}]}
    js = json.dumps(gltf).encode()
    js += b" " * (-len(js) % 4)
    bin_ = pos + idx
    bin_ += b"\0" * (-len(bin_) % 4)
    total = 12 + 8 + len(js) + 8 + len(bin_)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<III", _GLB_MAGIC, 2, total))
        fh.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        fh.write(struct.pack("<II", len(bin_), 0x004E4942) + bin_)
    return str(path)


# ---------------------------------------------------------- to STL

def to_stl(mesh_path, size_mm=None, stand=True, out_path=None) -> str:
    """The STL beside *mesh_path* the app imports: scaled so the longest
    side is *size_mm* (a generated GLB is metres and Y-up; parse_mesh
    turns it Z-up), centred on the origin in X/Y and stood on Z = 0."""
    from .engine import parse_mesh, write_stl
    path = Path(mesh_path)
    tris = parse_mesh(str(path))                 # a GLB comes back Z-up
    if not tris:
        raise Photo3DError(f"{path.name} holds no triangles")
    lo = [min(v[c] for t in tris for v in t) for c in range(3)]
    hi = [max(v[c] for t in tris for v in t) for c in range(3)]
    span = max(hi[c] - lo[c] for c in range(3)) or 1.0
    k = float(size_mm) / span if size_mm else 1.0
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    z0 = lo[2] if stand else 0.0
    tris = [tuple(((v[0] - cx) * k, (v[1] - cy) * k, (v[2] - z0) * k)
                  for v in t) for t in tris]
    out = Path(out_path) if out_path else path.with_suffix(".stl")
    if out == path:
        out = path.with_name(path.stem + "_import.stl")
    write_stl(tris, str(out), path.stem)
    return str(out)
