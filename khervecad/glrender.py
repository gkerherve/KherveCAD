"""Hardware rendering of the model faces for the 3D preview.

The preview is a `QWidget` painted with `QPainter`: grid, platform and
shadow, axes, anchors, pick highlights and the selection tint are all
drawn there. The *faces* used to be too — a painter's algorithm in BSP
order, which is exact when a tree can be built and approximate when it
cannot (threads, big meshes), with no anti-aliasing and no per-pixel
light. This module draws the faces with OpenGL instead, into an
offscreen multisampled framebuffer with a **depth buffer**, and hands
back a `QImage` the widget lays under its overlays. Occlusion is then
exact at any mesh size, edges are anti-aliased, and orbiting a million
triangles costs one draw call.

Everything else stays as it was, and `View3D` falls back to the
painter whenever this module cannot deliver (no OpenGL, a context or
shader that fails, the see-through Wireframe / X-ray styles which the
painter draws better).

The projection reproduces `View3D._project` exactly — same camera
basis, focal length, near plane and orthographic scale — so the GL
image and the QPainter overlays line up to the pixel.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
from array import array

from PyQt5.QtGui import QColor

#: the render styles GL draws; the rest keep the painter
STYLES = {"Shaded", "Matte", "Clay", "Toon", "Brushed metal", "Gold",
          "Copper", "Glass", "Rubber", "Skin", "Emissive"}

GL_FLOAT = 0x1406
GL_TRIANGLES = 0x0004
GL_LINES = 0x0001
GL_DEPTH_TEST = 0x0B71
GL_BLEND = 0x0BE2
GL_LEQUAL = 0x0203
GL_LESS = 0x0201
GL_SRC_ALPHA = 0x0302
GL_ONE_MINUS_SRC_ALPHA = 0x0303
GL_ONE = 1
GL_COLOR_BUFFER_BIT = 0x4000
GL_DEPTH_BUFFER_BIT = 0x0100
GL_POLYGON_OFFSET_FILL = 0x8037
GL_MULTISAMPLE = 0x809D
GL_LINE_SMOOTH = 0x0B20

#: floats per vertex: position 3, normal 3, colour 3, alpha 1,
#: material (ambient, diffuse, gloss strength, gloss power) 4, cavity 1
STRIDE = 15

VERTEX = """
#version 120
attribute vec3 a_pos;
attribute vec3 a_nrm;
attribute vec3 a_rgb;
attribute float a_alpha;
attribute vec4 a_mat;
attribute float a_cav;
uniform vec3 u_eye, u_right, u_up, u_fwd;
uniform float u_focal, u_hw, u_hh, u_near, u_far, u_ortho, u_scale;
varying vec3 v_nrm;
varying vec3 v_rgb;
varying float v_alpha;
varying vec4 v_mat;
varying float v_cav;
varying vec3 v_to_eye;
void main() {
    vec3 d = a_pos - u_eye;
    float cx = dot(d, u_right);
    float cy = dot(d, u_up);
    float cz = dot(d, u_fwd);
    if (u_ortho > 0.5) {
        gl_Position = vec4(u_scale * cx / u_hw, u_scale * cy / u_hh,
                           cz / u_far, 1.0);
    } else {
        float zc = (cz * (u_far + u_near) - 2.0 * u_far * u_near)
                   / (u_far - u_near);
        gl_Position = vec4(u_focal * cx / u_hw, u_focal * cy / u_hh,
                           zc, cz);
    }
    v_nrm = a_nrm;
    v_rgb = a_rgb;
    v_alpha = a_alpha;
    v_mat = a_mat;
    v_cav = a_cav;
    v_to_eye = (u_ortho > 0.5) ? -u_fwd : normalize(u_eye - a_pos);
}
"""

FRAGMENT = """
#version 120
uniform vec3 u_light;
uniform float u_gain, u_offset, u_cavity, u_toon;
varying vec3 v_nrm;
varying vec3 v_rgb;
varying float v_alpha;
varying vec4 v_mat;
varying float v_cav;
varying vec3 v_to_eye;
void main() {
    vec3 n = normalize(v_nrm);
    float shade = abs(dot(n, u_light));
    if (u_toon > 0.5) shade = floor(shade * 3.0 + 0.5) / 3.0;
    vec3 h = normalize(u_light + v_to_eye);
    float spec = max(dot(n, h), 0.0);
    float gloss = v_mat.z * pow(spec, v_mat.w);
    float v = v_mat.x + v_mat.y * shade;
    v = (v - 0.5) * u_gain + 0.5 + u_offset;
    if (u_cavity > 0.5) v *= v_cav;
    vec3 rgb = clamp(v_rgb * v + vec3(gloss), 0.0, 1.0);
    float a = v_alpha;
    if (v_alpha < 0.99) a = clamp(v_alpha + 0.4 * gloss, 0.0, 1.0);
    gl_FragColor = vec4(rgb, a);
}
"""

LINE_VERTEX = """
#version 120
attribute vec3 a_pos;
uniform vec3 u_eye, u_right, u_up, u_fwd;
uniform float u_focal, u_hw, u_hh, u_near, u_far, u_ortho, u_scale;
void main() {
    vec3 d = a_pos - u_eye;
    float cx = dot(d, u_right);
    float cy = dot(d, u_up);
    float cz = dot(d, u_fwd);
    if (u_ortho > 0.5) {
        gl_Position = vec4(u_scale * cx / u_hw, u_scale * cy / u_hh,
                           cz / u_far, 1.0);
    } else {
        float zc = (cz * (u_far + u_near) - 2.0 * u_far * u_near)
                   / (u_far - u_near);
        gl_Position = vec4(u_focal * cx / u_hw, u_focal * cy / u_hh,
                           zc, cz);
    }
}
"""

LINE_FRAGMENT = """
#version 120
uniform vec4 u_color;
void main() { gl_FragColor = u_color; }
"""


# ------------------------------------------------------------ materials

def material(style):
    """(ambient, diffuse, gloss strength, gloss power, saturation scale,
    value scale) reproducing View3D._style_color for *style*."""
    return {
        "Matte": (0.62, 0.30, 0.0, 1.0, 0.5, 1.0),
        "Clay": (0.50, 0.45, 0.0, 1.0, 0.0, 1.0),
        "Toon": (0.45, 0.55, 0.0, 1.0, 0.95, 1.0),
        "Brushed metal": (0.28, 0.45, 0.70, 16.0, 0.22, 1.0),
        "Gold": (0.32, 0.50, 0.65, 20.0, 0.0, 1.0),
        "Copper": (0.30, 0.50, 0.65, 20.0, 0.0, 1.0),
        "Glass": (0.55, 0.35, 0.60, 24.0, 0.55, 1.0),
        "Rubber": (0.12, 0.38, 0.0, 1.0, 0.85, 1.0),
        "Skin": (0.58, 0.32, 0.08, 4.0, 0.9, 1.0),
        "Emissive": (1.0, 0.0, 0.0, 1.0, 1.0, 1.0),
    }.get(style, (0.30, 0.70, 0.45, 10.0, 1.1, 1.0))          # Shaded


def _rgb(style, face_color, base):
    """The face's colour with the style's hue/saturation rules applied
    (the painter's per-face HSV maths, done once at upload)."""
    if face_color is not None and face_color[0]:
        own = QColor(face_color[0])
        hue, sat, val = max(own.hueF(), 0.0), own.saturationF(), own.valueF()
        alpha = max(min(float(face_color[1]), 1.0), 0.15)
    else:
        hue = base.hueF() if base.hueF() >= 0 else 0.58
        sat, val, alpha = base.saturationF() * 0.75, 1.0, 1.0
    amb, dif, gk, gp, sat_k, _vk = material(style)
    if style == "Clay":
        hue, sat = 0.07, 0.20
    elif style == "Gold":
        hue, sat = 0.125, 0.72
    elif style == "Copper":
        hue, sat = 0.045, 0.68
    else:
        sat = min(sat * sat_k, 1.0)
    if style == "Glass":
        alpha = min(alpha, 0.45)
    elif style == "Emissive":
        val = max(val, 0.9)
    c = QColor.fromHsvF(hue, sat, val)
    return c.redF(), c.greenF(), c.blueF(), alpha, (amb, dif, gk, gp)


def build_vertices(view, mesh, colors, info=None):
    """The interleaved float array for *mesh* under the view's style,
    materials and (when on) cavity terms, plus the index ranges of the
    opaque and translucent triangles: (data, opaque_count, trans)."""
    from .style import tokens
    from .view3d import MATERIAL_STYLES
    base = QColor(tokens()["select"])
    style = view.style
    cache = {}
    opaque, trans = array("f"), []
    cavity = info.cavity if info is not None else None
    for i, tri in enumerate(mesh):
        fc = colors[i] if colors else None
        face_style = style
        if fc is not None and len(fc) > 2:
            face_style = MATERIAL_STYLES.get(fc[2], style)
        key = (face_style, fc)
        got = cache.get(key)
        if got is None:
            got = cache[key] = _rgb(face_style, fc, base)
        r, g, b, alpha, (amb, dif, gk, gp) = got
        a, bb, c = tri
        ux, uy, uz = bb[0] - a[0], bb[1] - a[1], bb[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        l2 = nx * nx + ny * ny + nz * nz
        if l2 < 1e-24:
            continue
        inv = l2 ** -0.5
        nx *= inv; ny *= inv; nz *= inv
        cav = 1.0
        if cavity is not None:
            from .shading import multiplier
            cav = multiplier(cavity[i], 0.5)
        tail = (nx, ny, nz, r, g, b, alpha, amb, dif, gk, gp, cav)
        if alpha < 0.99:
            trans.append((tri, tail))
            continue
        for v in tri:
            opaque.extend((v[0], v[1], v[2]) + tail)
    return opaque, trans


# -------------------------------------------------------------- renderer

class GLRenderer:
    """One offscreen OpenGL context for the whole app, framebuffers per
    size, vertex buffers per mesh. `render(view)` returns the QImage of
    the faces (transparent background) or None when GL is unusable."""

    def __init__(self):
        self.ok = None                  # None: untried, False: gave up
        self.ctx = self.surface = self.funcs = None
        self.program = self.line_program = None
        self._fbo = self._plain = None
        self._fbo_size = None
        self._buffers = {}              # cache key -> (QOpenGLBuffer, n)
        self._lines = {}                # cache key -> (QOpenGLBuffer, n)
        self.error = ""

    # --------------------------------------------------------- set-up
    def _init(self):
        from PyQt5.QtGui import (QOffscreenSurface, QOpenGLContext,
                                 QOpenGLShader, QOpenGLShaderProgram,
                                 QOpenGLVersionProfile)
        try:
            ctx = QOpenGLContext()
            if not ctx.create():
                raise RuntimeError("no OpenGL context")
            surface = QOffscreenSurface()
            surface.setFormat(ctx.format())
            surface.create()
            if not ctx.makeCurrent(surface):
                raise RuntimeError("cannot make the context current")
            profile = QOpenGLVersionProfile()
            profile.setVersion(2, 1)
            funcs = ctx.versionFunctions(profile)
            if funcs is None:
                raise RuntimeError("OpenGL 2.1 functions unavailable")
            funcs.initializeOpenGLFunctions()

            def program(vs, fs, attrs):
                p = QOpenGLShaderProgram()
                if not p.addShaderFromSourceCode(QOpenGLShader.Vertex, vs) \
                        or not p.addShaderFromSourceCode(
                            QOpenGLShader.Fragment, fs):
                    raise RuntimeError(f"shader: {p.log()}")
                for i, name in enumerate(attrs):
                    p.bindAttributeLocation(name, i)
                if not p.link():
                    raise RuntimeError(f"link: {p.log()}")
                return p
            self.program = program(
                VERTEX, FRAGMENT,
                ["a_pos", "a_nrm", "a_rgb", "a_alpha", "a_mat", "a_cav"])
            self.line_program = program(LINE_VERTEX, LINE_FRAGMENT,
                                        ["a_pos"])
            self.ctx, self.surface, self.funcs = ctx, surface, funcs
            self.ok = True
        except Exception as exc:                       # any GL trouble
            self.error = str(exc)
            self.ok = False
        return self.ok

    def available(self):
        if self.ok is None:
            self._init()
        return bool(self.ok)

    def _framebuffers(self, w, h):
        from PyQt5.QtGui import (QOpenGLFramebufferObject,
                                 QOpenGLFramebufferObjectFormat)
        if self._fbo_size != (w, h):
            fmt = QOpenGLFramebufferObjectFormat()
            fmt.setSamples(4)
            fmt.setAttachment(QOpenGLFramebufferObject.Depth)
            self._fbo = QOpenGLFramebufferObject(w, h, fmt)
            self._plain = QOpenGLFramebufferObject(w, h)
            self._fbo_size = (w, h)
        return self._fbo, self._plain

    # ---------------------------------------------------------- buffers
    def _buffer(self, view, mesh, colors, info):
        from PyQt5.QtGui import QOpenGLBuffer
        key = (id(mesh), len(mesh), id(colors), view.style,
               bool(view.cavity))
        got = self._buffers.get(key)
        if got is not None:
            return got
        data, trans = build_vertices(view, mesh, colors, info)
        buf = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
        buf.create()
        buf.bind()
        raw = data.tobytes()
        buf.allocate(raw, len(raw))
        buf.release()
        if len(self._buffers) >= 3:
            for old, _n, _t in self._buffers.values():
                old.destroy()
            self._buffers.clear()
        entry = (buf, len(data) // STRIDE, trans)
        self._buffers[key] = entry
        return entry

    def _line_buffer(self, view, mesh, info):
        from PyQt5.QtGui import QOpenGLBuffer
        key = (id(mesh), len(mesh))
        got = self._lines.get(key)
        if got is not None:
            return got
        data = array("f")
        seen = set()
        for segs in info.creases.values():
            for p, q in segs:
                k = (round(p[0], 5), round(p[1], 5), round(p[2], 5),
                     round(q[0], 5), round(q[1], 5), round(q[2], 5))
                if k in seen:
                    continue
                seen.add(k)
                data.extend((p[0], p[1], p[2], q[0], q[1], q[2]))
        buf = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
        buf.create()
        buf.bind()
        raw = data.tobytes()
        buf.allocate(raw, max(len(raw), 4))
        buf.release()
        if len(self._lines) >= 3:
            for old, _n in self._lines.values():
                old.destroy()
            self._lines.clear()
        entry = (buf, len(data) // 3)
        self._lines[key] = entry
        return entry

    # ------------------------------------------------------------ render
    def _camera_uniforms(self, prog, view, eye, right, up, forward):
        w, h = max(view.width(), 1), max(view.height(), 1)
        ortho = view.projection == "Orthographic"
        near = max(view.NEAR_PLANE, view.distance * 0.001)
        far = max(view.distance * 20.0, 1000.0)
        prog.setUniformValue("u_eye", *[float(c) for c in eye])
        prog.setUniformValue("u_right", *[float(c) for c in right])
        prog.setUniformValue("u_up", *[float(c) for c in up])
        prog.setUniformValue("u_fwd", *[float(c) for c in forward])
        prog.setUniformValue("u_focal", float(view._focal()))
        prog.setUniformValue("u_hw", float(w) / 2.0)
        prog.setUniformValue("u_hh", float(h) / 2.0)
        prog.setUniformValue("u_near", float(near))
        prog.setUniformValue("u_far", float(far))
        prog.setUniformValue("u_ortho", 1.0 if ortho else 0.0)
        prog.setUniformValue(
            "u_scale", float(view._focal() / max(view.distance, 1e-6)))

    def render(self, view, mesh, colors, info, eye, right, up, forward,
               light, edges_color=None):
        """The faces of *mesh* as the view sees them, or None."""
        if not self.available() or not mesh:
            return None
        from PyQt5.QtGui import QOpenGLFramebufferObject
        try:
            ctx, f = self.ctx, self.funcs
            if not ctx.makeCurrent(self.surface):
                return None
            w, h = max(view.width(), 1), max(view.height(), 1)
            fbo, plain = self._framebuffers(w, h)
            fbo.bind()
            f.glViewport(0, 0, w, h)
            f.glClearColor(0.0, 0.0, 0.0, 0.0)
            f.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            f.glEnable(GL_DEPTH_TEST)
            f.glDepthFunc(GL_LESS)
            f.glEnable(GL_MULTISAMPLE)
            f.glEnable(GL_BLEND)
            # colour blends by alpha, alpha accumulates: the image comes
            # back premultiplied, and the plain blend gave a glass face
            # over the clear an alpha of a*a with a colour of a*rgb — an
            # invalid premultiplied pixel Qt painted as saturated noise
            f.glBlendFuncSeparate(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
                                  GL_ONE, GL_ONE_MINUS_SRC_ALPHA)
            prog = self.program
            prog.bind()
            self._camera_uniforms(prog, view, eye, right, up, forward)
            prog.setUniformValue("u_light", *[float(c) for c in light])
            lighting = view._light()
            gain, offset = lighting if lighting else (1.0, 0.0)
            prog.setUniformValue("u_gain", float(gain))
            prog.setUniformValue("u_offset", float(offset))
            prog.setUniformValue("u_cavity", 1.0 if (view.cavity and info)
                                 else 0.0)
            prog.setUniformValue("u_toon", 1.0 if view.style == "Toon"
                                 else 0.0)
            buf, count, trans = self._buffer(view, mesh, colors, info)
            buf.bind()
            fsize = 4
            stride = STRIDE * fsize
            for loc, off, size in ((0, 0, 3), (1, 3, 3), (2, 6, 3),
                                   (3, 9, 1), (4, 10, 4), (5, 14, 1)):
                prog.enableAttributeArray(loc)
                prog.setAttributeBuffer(loc, GL_FLOAT, off * fsize, size,
                                        stride)
            f.glEnable(GL_POLYGON_OFFSET_FILL)
            f.glPolygonOffset(1.0, 1.0)
            if count:
                f.glDrawArrays(GL_TRIANGLES, 0, count)
            buf.release()
            if trans:
                self._draw_translucent(prog, trans, eye, forward)
            f.glDisable(GL_POLYGON_OFFSET_FILL)
            for loc in range(6):
                prog.disableAttributeArray(loc)
            prog.release()
            if edges_color is not None and info is not None:
                self._draw_lines(view, mesh, info, eye, right, up, forward,
                                 edges_color)
            fbo.release()
            QOpenGLFramebufferObject.blitFramebuffer(plain, fbo)
            image = plain.toImage()
            ctx.doneCurrent()
            return image
        except Exception as exc:
            self.error = str(exc)
            self.ok = False
            return None

    def _draw_translucent(self, prog, trans, eye, forward):
        """See-through faces after the opaque ones, back to front, depth
        writes off so they blend over each other."""
        from PyQt5.QtGui import QOpenGLBuffer
        f = self.funcs

        def depth(item):
            a, b, c = item[0]
            cx = (a[0] + b[0] + c[0]) / 3.0 - eye[0]
            cy = (a[1] + b[1] + c[1]) / 3.0 - eye[1]
            cz = (a[2] + b[2] + c[2]) / 3.0 - eye[2]
            return cx * forward[0] + cy * forward[1] + cz * forward[2]
        data = array("f")
        for tri, tail in sorted(trans, key=depth, reverse=True):
            for v in tri:
                data.extend((v[0], v[1], v[2]) + tail)
        buf = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
        buf.create()
        buf.bind()
        raw = data.tobytes()
        buf.allocate(raw, len(raw))
        fsize = 4
        stride = STRIDE * fsize
        for loc, off, size in ((0, 0, 3), (1, 3, 3), (2, 6, 3),
                               (3, 9, 1), (4, 10, 4), (5, 14, 1)):
            prog.setAttributeBuffer(loc, GL_FLOAT, off * fsize, size, stride)
        f.glDepthMask(False)
        f.glDrawArrays(GL_TRIANGLES, 0, len(data) // STRIDE)
        f.glDepthMask(True)
        buf.release()
        buf.destroy()

    def _draw_lines(self, view, mesh, info, eye, right, up, forward,
                    color):
        f = self.funcs
        buf, count = self._line_buffer(view, mesh, info)
        if not count:
            return
        prog = self.line_program
        prog.bind()
        self._camera_uniforms(prog, view, eye, right, up, forward)
        prog.setUniformValue("u_color", color.redF(), color.greenF(),
                             color.blueF(), 1.0)
        buf.bind()
        prog.enableAttributeArray(0)
        prog.setAttributeBuffer(0, GL_FLOAT, 0, 3, 12)
        f.glDepthFunc(GL_LEQUAL)
        f.glLineWidth(1.2)
        f.glDrawArrays(GL_LINES, 0, count)
        f.glDepthFunc(GL_LESS)
        prog.disableAttributeArray(0)
        buf.release()
        prog.release()


_RENDERER = None


def renderer():
    global _RENDERER
    if _RENDERER is None:
        _RENDERER = GLRenderer()
    return _RENDERER


def light_direction(forward):
    """The painter's fixed light, as View3D.paintEvent builds it."""
    light = (0.35, -0.5, 0.75)
    norm = math.sqrt(sum(c * c for c in light))
    return tuple(c / norm for c in light)
