"""Photoreal pictures through Blender (Cycles), when it is installed.

The preview is drawn for modelling — flat light, no bounce, no real
glass. For a listing, a report or a client, `render` hands the scene to
**Blender in the background** (``blender -b``, free, GPL; nothing is
bundled): the preview's coloured triangles go out as one glTF with a
PBR material per colour (KherveCAD's Metal / Glass / Gold / Rubber /
Emissive … mapped to metallic, roughness, transmission and emission),
and a generated script sets up the same camera as the 3D view (its yaw,
pitch, distance and field of view, or a framed preset), a sun and a
soft sky, a studio floor with the part's shadow, Cycles with denoising
(or EEVEE), and renders a PNG.

Blender is found through KHERVECAD_BLENDER, PATH and the usual install
folders (`find_blender`). Coordinates go out in METRES, Y up, as glTF
wants (Blender's importer turns them back to Z up). Only QColor is
used (to read colour names); the menu and the MCP tool (`render_photo`)
run it off the GUI thread.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import glob
import json
import math
import os
import shutil
import struct
import subprocess
import tempfile

#: the 3D view's focal length is 1.2 x its shorter side (view3d._focal)
VIEW_FOV = 2.0 * math.atan(0.5 / 1.2)
DEFAULT_TIMEOUT = 600

#: KherveCAD material -> (metallic, roughness, transmission, emission)
MATERIALS = {
    "Default": (0.0, 0.45, 0.0, 0.0),
    "Plastic": (0.0, 0.35, 0.0, 0.0),
    "Metal": (1.0, 0.28, 0.0, 0.0),
    "Matte": (0.0, 0.9, 0.0, 0.0),
    "Clay": (0.0, 0.85, 0.0, 0.0),
    "Glass": (0.0, 0.05, 1.0, 0.0),
    "Rubber": (0.0, 0.75, 0.0, 0.0),
    "Skin": (0.0, 0.55, 0.0, 0.0),
    "Gold": (1.0, 0.22, 0.0, 0.0),
    "Copper": (1.0, 0.3, 0.0, 0.0),
    "Emissive": (0.0, 0.5, 0.0, 4.0),
}
DEFAULT_COLOUR = "#b0b4ba"


def find_blender():
    """The Blender executable, or None."""
    env = os.environ.get("KHERVECAD_BLENDER")
    if env and os.path.isfile(env):
        return env
    for name in ("blender", "blender.exe"):
        hit = shutil.which(name)
        if hit:
            return hit
    patterns = [
        "/Applications/Blender*.app/Contents/MacOS/Blender",
        os.path.expanduser("~/Applications/Blender*.app/Contents/MacOS/"
                           "Blender"),
        r"C:\Program Files\Blender Foundation\Blender*\blender.exe",
        "/usr/bin/blender", "/usr/local/bin/blender",
        "/snap/bin/blender", "/opt/blender*/blender",
    ]
    for pattern in patterns:
        found = sorted(glob.glob(pattern))
        if found:
            return found[-1]
    return None


def _rgb(colour):
    from PyQt5.QtGui import QColor                    # parses every name
    c = QColor(str(colour))
    if not c.isValid():
        c = QColor(DEFAULT_COLOUR)

    def lin(v):                                       # sRGB -> linear
        v = v / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return [lin(c.red()), lin(c.green()), lin(c.blue())]


def _material(colour):
    """glTF material dict for a preview colour tuple (or None)."""
    if colour is None:
        colour = (DEFAULT_COLOUR, 1.0)
    name = str(colour[0])
    alpha = float(colour[1]) if len(colour) > 1 else 1.0
    kind = str(colour[2]) if len(colour) > 2 else "Default"
    metal, rough, trans, emit = MATERIALS.get(kind, MATERIALS["Default"])
    rgb = _rgb(name)
    mat = {"name": f"{kind} {name}",
           "pbrMetallicRoughness": {"baseColorFactor": rgb + [alpha],
                                    "metallicFactor": metal,
                                    "roughnessFactor": rough},
           "doubleSided": False}
    if alpha < 0.999 and not trans:
        mat["alphaMode"] = "BLEND"
    if trans:
        mat["extensions"] = {"KHR_materials_transmission":
                             {"transmissionFactor": trans}}
    if emit:
        mat["emissiveFactor"] = rgb
        mat.setdefault("extensions", {})["KHR_materials_emissive_strength"] \
            = {"emissiveStrength": emit}
    return mat


def write_glb(colored, path, scale=0.001):
    """*colored* = [(triangle, colour)] -> a GLB, one primitive per
    colour, metres, Y up. Returns the path."""
    groups = {}
    for tri, colour in colored:
        key = tuple(colour) if colour is not None else None
        groups.setdefault(key, []).append(tri)
    buffers = b""
    views, accessors, prims, materials, used_ext = [], [], [], [], set()
    for key, tris in groups.items():
        verts, index, faces = [], {}, []
        for tri in tris:
            for v in tri:
                p = (float(v[0]) * scale, float(v[2]) * scale,
                     -float(v[1]) * scale)
                i = index.get(p)
                if i is None:
                    i = index[p] = len(verts)
                    verts.append(p)
                faces.append(i)
        pos = b"".join(struct.pack("<3f", *v) for v in verts)
        idx = b"".join(struct.pack("<I", i) for i in faces)
        lo = [min(v[c] for v in verts) for c in range(3)]
        hi = [max(v[c] for v in verts) for c in range(3)]
        for blob, target in ((pos, 34962), (idx, 34963)):
            views.append({"buffer": 0, "byteOffset": len(buffers),
                          "byteLength": len(blob), "target": target})
            buffers += blob + b"\0" * ((4 - len(blob) % 4) % 4)
        accessors.append({"bufferView": len(views) - 2,
                          "componentType": 5126, "count": len(verts),
                          "type": "VEC3", "min": lo, "max": hi})
        accessors.append({"bufferView": len(views) - 1,
                          "componentType": 5125, "count": len(faces),
                          "type": "SCALAR"})
        mat = _material(key)
        used_ext.update(mat.get("extensions", {}))
        materials.append(mat)
        prims.append({"attributes": {"POSITION": len(accessors) - 2},
                      "indices": len(accessors) - 1, "mode": 4,
                      "material": len(materials) - 1})
    gltf = {"asset": {"version": "2.0", "generator": "KherveCAD"},
            "scene": 0, "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0, "name": "Model"}],
            "meshes": [{"primitives": prims, "name": "Model"}],
            "materials": materials, "accessors": accessors,
            "bufferViews": views,
            "buffers": [{"byteLength": len(buffers)}]}
    if used_ext:
        gltf["extensionsUsed"] = sorted(used_ext)
    js = json.dumps(gltf).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    body = (struct.pack("<II", len(js), 0x4E4F534A) + js
            + struct.pack("<II", len(buffers), 0x004E4942) + buffers)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body)
    return path


SCRIPT = r'''
import bpy, json, math, sys
from mathutils import Vector
args = json.load(open(sys.argv[sys.argv.index("--") + 1]))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=args["glb"])
scene = bpy.context.scene
meshes = [o for o in scene.objects if o.type == "MESH"]
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
lo = Vector([min(p[i] for p in pts) for i in range(3)])
hi = Vector([max(p[i] for p in pts) for i in range(3)])
centre, radius = (lo + hi) / 2, max((hi - lo).length / 2, 1e-4)
if args["engine"] == "eevee":
    for name in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = name
            break
        except TypeError:
            pass
else:
    scene.render.engine = "CYCLES"
    scene.cycles.samples = args["samples"]
    scene.cycles.use_denoising = True
    try:
        scene.cycles.device = "GPU"
    except Exception:
        pass
scene.render.resolution_x, scene.render.resolution_y = args["size"]
scene.render.resolution_percentage = 100
scene.render.film_transparent = args["transparent"]
scene.view_settings.view_transform = "AgX" if "AgX" in [
    t.identifier for t in scene.view_settings.bl_rna.properties[
        "view_transform"].enum_items] else "Filmic"
cam_data = bpy.data.cameras.new("Camera")
cam = bpy.data.objects.new("Camera", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
w, h = args["size"]
cam_data.sensor_fit = "VERTICAL" if h <= w else "HORIZONTAL"
cam_data.angle = args["fov"]
cam_data.clip_start = radius / 1000
cam_data.clip_end = radius * 1000
y, p = math.radians(args["yaw"]), math.radians(args["pitch"])
look = Vector((math.cos(p) * math.cos(y), math.cos(p) * math.sin(y),
               math.sin(p)))
target = Vector(args["target"]) if args["target"] else centre
dist = args["distance"] or radius / math.sin(args["fov"] / 2) * 1.08
cam.location = target + look * dist
cam.rotation_euler = (target - cam.location).to_track_quat(
    "-Z", "Y").to_euler()
world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.82, 0.85, 0.9, 1.0)
bg.inputs[1].default_value = 0.6
sun_data = bpy.data.lights.new("Sun", "SUN")
sun_data.energy = 3.5
sun_data.angle = math.radians(8)
sun = bpy.data.objects.new("Sun", sun_data)
scene.collection.objects.link(sun)
key = (look + Vector((-look.y, look.x, 0)) * 0.8 + Vector((0, 0, 1.4)))
sun.rotation_euler = (-key).to_track_quat("-Z", "Y").to_euler()
if args["ground"]:
    bpy.ops.mesh.primitive_plane_add(size=radius * 60,
                                     location=(centre.x, centre.y, lo.z))
    floor = bpy.context.active_object
    mat = bpy.data.materials.new("Floor")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.8, 0.8, 0.8, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.85
    floor.data.materials.append(mat)
    if args["transparent"]:
        floor.is_shadow_catcher = True
scene.render.filepath = args["out"]
scene.render.image_settings.file_format = "PNG"
bpy.ops.render.render(write_still=True)
'''


def render(colored, out, yaw=35.0, pitch=22.0, distance=None, target=None,
           size=(1600, 1200), samples=96, engine="cycles", ground=True,
           transparent=False, fov=VIEW_FOV, binary=None,
           timeout=DEFAULT_TIMEOUT):
    """Render *colored* ((triangle, colour) rows, mm) to the PNG *out*.
    *distance* / *target* in mm (None frames the model). Returns *out*;
    raises RuntimeError with Blender's own words when it fails."""
    binary = binary or find_blender()
    if not binary:
        raise RuntimeError(
            "Blender was not found. Install it (free, blender.org) or set "
            "KHERVECAD_BLENDER to its executable.")
    if not colored:
        raise RuntimeError("There is nothing to render.")
    work = tempfile.mkdtemp(prefix="kcad_photo_")
    glb = write_glb(colored, os.path.join(work, "scene.glb"))
    script = os.path.join(work, "render.py")
    with open(script, "w", encoding="utf-8") as fh:
        fh.write(SCRIPT)
    params = os.path.join(work, "args.json")
    with open(params, "w", encoding="utf-8") as fh:
        json.dump({"glb": glb, "out": os.path.abspath(out),
                   "yaw": float(yaw), "pitch": float(pitch),
                   "distance": distance / 1000.0 if distance else None,
                   "target": ([target[0] / 1000.0, target[1] / 1000.0,
                               target[2] / 1000.0] if target else None),
                   "size": [int(size[0]), int(size[1])],
                   "samples": int(samples), "engine": engine,
                   "ground": bool(ground), "transparent": bool(transparent),
                   "fov": float(fov)}, fh)
    try:
        run = subprocess.run([binary, "-b", "--factory-startup",
                              "--python", script, "--", params],
                             capture_output=True, text=True,
                             timeout=timeout)
    except subprocess.TimeoutExpired:
        shutil.rmtree(work, ignore_errors=True)
        raise RuntimeError(f"Blender took longer than {timeout} s.")
    if run.returncode != 0 or not os.path.isfile(out):
        shutil.rmtree(work, ignore_errors=True)
        tail = (run.stderr or run.stdout or "").strip().splitlines()[-8:]
        raise RuntimeError("Blender failed: " + " | ".join(tail))
    shutil.rmtree(work, ignore_errors=True)
    return out
