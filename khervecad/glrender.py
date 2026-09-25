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

#: surface materials the fragment shader draws from world position
#: (`surface()`): name -> pattern id, carried in the gloss-power slot as
#: a negative number. Zero extra triangles, so a whole town can wear
#: bricks; the painter fallback shows them as flat Matte.
SURFACES = {"Brick": 1, "Concrete": 2, "Render": 3, "Roof tiles": 4,
            "Slate": 5, "Stone": 6, "Bark": 7, "Leaves": 8,
            # house interiors and finishes (house_finishes.py)
            "Wall tiles": 9, "Metro tiles": 10, "Mosaic": 11,
            "Hex tiles": 12, "Marble": 13, "Floor tiles": 14,
            "Checker tiles": 15, "Terrazzo": 16, "Zellige": 17,
            "Floorboards": 18, "Parquet": 19, "Carpet": 20, "Plaster": 21,
            "Cladding": 22, "Shingles": 23, "Thatch": 24,
            "Standing seam": 25, "Solar panels": 26, "Panelling": 27,
            # upholstery (sofas, armchairs): weave, pile, grain, loops
            "Fabric": 28, "Velvet": 29, "Leather": 30, "Bouclé": 31,
            # furniture timber: flat-sawn grain, pores, veneer leaves
            "Wood": 32}
#: (gloss strength, saturation scale) of a surface: glazed tiles and
#: marble catch the light, carpet and thatch do not
SURFACE_LOOK = {"Wall tiles": (0.45, 0.95), "Metro tiles": (0.5, 0.95),
                "Mosaic": (0.4, 0.95), "Hex tiles": (0.3, 0.95),
                "Marble": (0.45, 0.9), "Floor tiles": (0.25, 0.9),
                "Checker tiles": (0.35, 0.9), "Terrazzo": (0.3, 0.9),
                "Zellige": (0.55, 1.0), "Floorboards": (0.12, 0.9),
                "Parquet": (0.15, 0.9), "Plaster": (0.0, 0.95),
                "Carpet": (0.0, 0.9), "Cladding": (0.05, 0.85),
                "Standing seam": (0.35, 0.6), "Solar panels": (0.6, 0.9),
                "Panelling": (0.1, 0.9), "Fabric": (0.0, 0.9),
                "Velvet": (0.08, 1.0), "Leather": (0.3, 0.95),
                "Bouclé": (0.0, 0.85), "Wood": (0.22, 1.0)}
#: roof coverings: their courses run up the slope, not up the world Z
ROOF_SURFACES = ("Roof tiles", "Slate", "Shingles", "Thatch",
                 "Standing seam", "Solar panels")

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
varying vec3 v_pos;
void main() {
    v_pos = a_pos;
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
varying vec3 v_pos;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x),
               f.y);
}
float fbm(vec2 p) {
    return 0.5 * noise(p) + 0.3 * noise(p * 2.03) + 0.2 * noise(p * 4.1);
}
// Surface materials drawn in world millimetres (see SURFACES): the
// pattern multiplies the face colour and, for relief, returns a darker
// joint. uv: along the wall / up it; a roof's v runs up its slope.
// a joint line of width w at the start of a cell, antialiased over one
// pixel (px mm), so thin mortar greys out instead of aliasing
float joint(float f, float w, float px) {
    return 1.0 - smoothstep(w - px, w + px, f);
}

// distance to the nearest edge of a w x h cell, and the cell index
vec3 tcell(vec2 uv, vec2 size, float stagger) {
    float row = floor(uv.y / size.y);
    float x = uv.x / size.x + stagger * mod(row, 2.0);
    vec2 f = vec2(fract(x) * size.x, fract(uv.y / size.y) * size.y);
    float e = min(min(f.x, size.x - f.x), min(f.y, size.y - f.y));
    return vec3(e, floor(x) + 0.37 * row, row);
}
const vec3 GROUT = vec3(0.86, 0.85, 0.82);
vec3 tiles(float id, vec2 uv, vec3 rgb, float px) {
    if (id == 9.0 || id == 17.0 || id == 11.0 || id == 14.0) {
        // square tiles: wall 150, zellige 100, mosaic 25, floor 600
        float s = (id == 9.0) ? 150.0 : (id == 17.0) ? 100.0
                : (id == 11.0) ? 25.0 : 600.0;
        float g = (id == 11.0) ? 1.2 : (id == 14.0) ? 1.8 : 1.4;
        vec3 c3 = tcell(uv, vec2(s), 0.0);
        float h = hash(vec2(c3.y, c3.z));
        vec3 c = rgb;
        if (id == 9.0) c *= 0.96 + 0.06 * h;
        else if (id == 17.0)
            c *= (0.72 + 0.42 * h) * (0.9 + 0.18 * noise(uv * 0.06 + h * 9.0));
        else if (id == 11.0) c *= 0.7 + 0.45 * h;
        else c *= (0.92 + 0.1 * h) * (0.94 + 0.1 * fbm(uv * 0.004));
        float bevel = (id == 14.0) ? 3.0 : (id == 11.0) ? 1.5 : 6.0;
        c *= 0.9 + 0.1 * smoothstep(0.0, bevel, c3.x);
        return mix(c, GROUT * (id == 14.0 ? 0.72 : 1.0), joint(c3.x, g, px));
    }
    if (id == 10.0) {                      // metro: 150 x 75, bevelled
        vec3 c3 = tcell(uv, vec2(150.0, 75.0), 0.5);
        vec3 c = rgb * (0.95 + 0.08 * hash(vec2(c3.y, c3.z)));
        c *= 0.72 + 0.28 * smoothstep(1.0, 9.0, c3.x);
        c += vec3(0.08) * (1.0 - smoothstep(1.5, 4.0, abs(c3.x - 5.0)));
        return mix(c, GROUT, joint(c3.x, 1.3, px));
    }
    if (id == 12.0) {                      // hexagons, 110 across
        vec2 p = uv / 110.0;
        vec2 r = vec2(1.0, 1.7320508);
        vec2 a = mod(p, r) - r * 0.5;
        vec2 b = mod(p - r * 0.5, r) - r * 0.5;
        vec2 q = dot(a, a) < dot(b, b) ? a : b;
        vec2 idx = floor(p - q + 0.5);
        vec2 aq = abs(q);
        float d = 0.5 - max(dot(aq, vec2(0.5, 0.8660254)), aq.x);
        vec3 c = rgb * (0.94 + 0.08 * hash(idx));
        return mix(c, GROUT, joint(d * 110.0, 1.6, px));
    }
    if (id == 13.0) {                      // marble slabs with veins
        vec3 c3 = tcell(uv, vec2(1200.0, 600.0), 0.0);
        vec2 o = vec2(hash(vec2(c3.y, c3.z)) * 900.0);
        vec2 w = uv + o;
        float t = w.x * 0.0025 + w.y * 0.0012 + 2.6 * fbm(w * 0.0021)
                  + 0.9 * fbm(w * 0.011);
        float vein = pow(1.0 - abs(sin(t * 3.14159)), 7.0);
        float fine = pow(1.0 - abs(sin((t * 2.7 + fbm(w * 0.03)) * 3.14159)), 16.0);
        vec3 c = rgb * (0.95 + 0.07 * fbm(w * 0.006));
        c = mix(c, rgb * vec3(0.55, 0.55, 0.58), 0.4 * vein + 0.15 * fine);
        return mix(c, rgb * 0.8, joint(c3.x, 0.8, px));
    }
    if (id == 15.0) {                      // checkerboard, 300 squares
        vec3 c3 = tcell(uv, vec2(300.0), 0.0);
        vec2 k = floor(uv / 300.0);
        float dark = mod(k.x + k.y, 2.0);
        vec3 c = mix(rgb, vec3(0.1, 0.1, 0.11), dark);
        c *= 0.95 + 0.07 * hash(k);
        return mix(c, GROUT * 0.75, joint(c3.x, 1.5, px));
    }
    // terrazzo: chips of three tones in a pale ground
    vec2 k = floor(uv / 9.0);
    float h = hash(k);
    vec3 c = rgb * (0.95 + 0.05 * fbm(uv * 0.01));
    if (h > 0.78) c = rgb * 0.55;
    else if (h > 0.7) c = mix(rgb, vec3(0.62, 0.42, 0.33), 0.6);
    else if (h > 0.64) c = rgb * 1.08;
    return c;
}
vec3 finishes(float id, vec2 uv, vec3 rgb, float px) {
    if (id == 18.0) {                      // floorboards along X
        float row = floor(uv.y / 140.0);
        float x = uv.x + hash(vec2(row, 3.0)) * 1800.0;
        float plank = floor(x / 1800.0);
        vec2 f = vec2(fract(x / 1800.0) * 1800.0, fract(uv.y / 140.0) * 140.0);
        float j = max(joint(min(f.y, 140.0 - f.y), 1.0, px),
                      joint(min(f.x, 1800.0 - f.x), 1.0, px));
        float h = hash(vec2(plank, row));
        float grain = noise(vec2(x * 0.003 + h * 50.0, uv.y * 0.12))
                      * 0.6 + noise(vec2(x * 0.02, uv.y * 0.5)) * 0.4;
        vec3 c = rgb * (0.8 + 0.3 * h) * (0.86 + 0.24 * grain);
        return mix(c, rgb * 0.35, j);
    }
    if (id == 19.0) {                      // basket-weave parquet
        vec2 k = floor(uv / 280.0);
        vec2 f = fract(uv / 280.0) * 280.0;
        bool alt = mod(k.x + k.y, 2.0) > 0.5;
        float across = alt ? f.x : f.y;
        float along = alt ? f.y : f.x;
        float plank = floor(across / 70.0);
        float fa = mod(across, 70.0);
        float e = min(min(fa, 70.0 - fa), min(min(f.x, 280.0 - f.x),
                                            min(f.y, 280.0 - f.y)));
        float h = hash(k * 7.0 + plank);
        float grain = noise(vec2(along * 0.02 + h * 30.0, across * 0.4));
        vec3 c = rgb * (0.8 + 0.3 * h) * (0.88 + 0.2 * grain);
        return mix(c, rgb * 0.4, joint(e, 0.8, px));
    }
    if (id == 20.0)                        // carpet
        return rgb * (0.9 + 0.12 * hash(floor(uv / 2.5)) + 0.1 * (fbm(uv * 0.006) - 0.5));
    if (id == 21.0)                        // painted plaster
        return rgb * (0.975 + 0.04 * fbm(uv * 0.003) + 0.012 * (hash(floor(uv / 3.0)) - 0.5));
    if (id == 22.0) {                      // weatherboard cladding
        float row = floor(uv.y / 150.0);
        float f = fract(uv.y / 150.0) * 150.0;
        float x = uv.x + hash(vec2(row, 1.0)) * 3600.0;
        float board = floor(x / 3600.0);
        float fx = fract(x / 3600.0) * 3600.0;
        float h = hash(vec2(board, row));
        vec3 c = rgb * (0.86 + 0.2 * h) * (0.9 + 0.15 * noise(vec2(x * 0.004, uv.y * 0.2)));
        c *= 0.62 + 0.38 * smoothstep(0.0, 28.0 + px, f);   // the lap's shadow
        return mix(c, rgb * 0.45, joint(min(fx, 3600.0 - fx), 1.5, px));
    }
    if (id == 27.0) {                      // tongue-and-groove panelling
        float f = fract(uv.x / 100.0) * 100.0;
        float h = hash(vec2(floor(uv.x / 100.0), 5.0));
        vec3 c = rgb * (0.85 + 0.22 * h) * (0.9 + 0.16 * noise(vec2(uv.x * 0.3, uv.y * 0.004)));
        return mix(c, rgb * 0.45, joint(min(f, 100.0 - f), 2.0, px));
    }
    if (id == 23.0) {                      // cedar shingles
        float row = floor(uv.y / 140.0);
        float fy = fract(uv.y / 140.0);
        float x = uv.x / 190.0 + hash(vec2(row, 2.0));
        float fx = fract(x) * 190.0;
        float h = hash(vec2(floor(x), row));
        vec3 c = rgb * (0.7 + 0.5 * h) * (0.85 + 0.25 * noise(vec2(uv.x * 0.08, uv.y * 0.01)));
        c *= 0.55 + 0.45 * smoothstep(0.0, 0.3 + px / 140.0, fy);
        return mix(c, rgb * 0.3, joint(min(fx, 190.0 - fx), 3.0, px));
    }
    if (id == 24.0) {                      // thatch: straw along the slope
        float f = noise(vec2(uv.x * 0.09, uv.y * 0.004)) * 0.55
                  + noise(vec2(uv.x * 0.3, uv.y * 0.012)) * 0.45;
        float course = fract(uv.y / 350.0);
        return rgb * (0.6 + 0.6 * f) * (0.75 + 0.25 * smoothstep(0.0, 0.25, course));
    }
    if (id == 25.0) {                      // standing-seam metal
        float f = fract(uv.x / 500.0) * 500.0;
        vec3 c = rgb * (0.94 + 0.08 * fbm(uv * 0.002));
        c *= 1.0 - 0.3 * joint(f, 6.0, px);
        return c + vec3(0.12) * joint(abs(f - 10.0), 3.0, px);
    }
    // solar panels: cells in aluminium-framed modules
    vec3 m = tcell(uv, vec2(1040.0, 1720.0), 0.0);
    vec3 cl = tcell(uv, vec2(173.3, 172.0), 0.0);
    vec3 c = rgb * (0.9 + 0.12 * hash(vec2(cl.y, cl.z)));
    c = mix(c, vec3(0.75, 0.78, 0.8), joint(cl.x, 1.2, px) * 0.6);
    return mix(c, vec3(0.7, 0.72, 0.74), joint(m.x, 18.0, px));
}
vec3 wood(vec2 uv, vec3 rgb, float px) {
    // veneer leaves 180 mm wide, each cut from its own part of the log
    float leaf = floor(uv.y / 180.0);
    float lh = hash(vec2(leaf, 11.0));
    float fy = fract(uv.y / 180.0) * 180.0;
    float x = uv.x + lh * 7000.0;
    // flat-sawn figure: the log's growth rings sliced at a slant, so
    // they close into arches (cathedrals) and run straight at the edge
    float arch = mod(x, 3000.0) - 1500.0;
    float wob = 45.0 * fbm(vec2(x * 0.0016, fy * 0.004 + lh * 9.0));
    float r = length(vec2(fy - 70.0 - 60.0 * lh + wob, arch * 0.05));
    float t = r / (10.0 + 6.0 * lh)
              + 0.35 * fbm(vec2(x * 0.004, fy * 0.03));
    float ring = fract(t);
    // earlywood pale, darkening through the season, a crisp boundary
    float late = pow(smoothstep(0.15, 0.97, ring), 2.2)
                 * (1.0 - smoothstep(0.97, 1.0, ring));
    late = mix(late, 0.3, clamp(px / 8.0, 0.0, 1.0));   // far: blend
    vec3 c = mix(rgb * (1.12 + 0.08 * lh), rgb * vec3(0.6, 0.53, 0.48),
                 late * 0.62);
    // colour drift of the log, and fine fibres along the grain
    c *= 0.9 + 0.2 * fbm(vec2(x * 0.0009, fy * 0.012 + lh * 4.0));
    float fibre = noise(vec2(x * 0.05, fy * 1.6));
    c *= 1.0 + 0.07 * (fibre - 0.5) * (1.0 - smoothstep(0.5, 2.5, px));
    // open pores: fine dark flecks drawn out along the grain
    float fine = 1.0 - smoothstep(0.35, 1.3, px);
    vec2 pc = vec2(x / 3.5, fy / 0.35);
    float pore = step(0.955, hash(floor(pc)))
                 * sin(fract(pc.x) * 3.14159);
    c *= 1.0 - 0.16 * pore * fine;
    // a hairline where two leaves meet
    return c * (1.0 - 0.12 * joint(min(fy, 180.0 - fy), 0.2, px) * fine);
}
vec3 upholstery(float id, vec2 uv, vec3 n, vec3 rgb, float px) {
    if (id == 28.0) {                      // woven fabric: plain weave
        float fine = 1.0 - smoothstep(0.7, 2.8, px);
        vec2 t = uv / 1.6;
        float over = mod(floor(t.x) + floor(t.y), 2.0);
        float thread = mix(sin(fract(t.x) * 3.14159),
                           sin(fract(t.y) * 3.14159), over);
        float slub = noise(vec2(uv.x * 0.04, uv.y * 0.7));
        vec3 c = rgb * (0.9 + 0.12 * fbm(uv * 0.025) + 0.08 * (slub - 0.5));
        c *= 1.0 - fine * 0.2 * (1.0 - thread);
        float fleck = smoothstep(0.72, 0.9,
                                 noise(vec2(uv.x / 7.0, uv.y / 1.8)));
        float mid = 1.0 - smoothstep(1.5, 6.0, px);
        return mix(c, c * 1.15 + 0.03, fleck * mid * 0.45);
    }
    if (id == 29.0) {                      // velvet: pile sheen at the rim
        float rim = 1.0 - abs(dot(n, normalize(v_to_eye)));
        float crush = fbm(uv * 0.012 + 2.5 * fbm(uv * 0.003));
        vec3 c = rgb * (0.7 + 0.26 * crush);
        return mix(c, min(rgb * 1.7 + 0.1, vec3(1.0)), 0.6 * pow(rim, 2.2));
    }
    if (id == 30.0) {                      // leather: pebble grain, patina
        float fine = 1.0 - smoothstep(0.5, 2.2, px);
        vec2 g = uv / 1.8;
        vec2 i = floor(g), f = fract(g);
        float d = 9.0, d2 = 9.0;
        for (int y = -1; y <= 1; y++)
            for (int x = -1; x <= 1; x++) {
                vec2 o = vec2(float(x), float(y));
                float l = length(o + vec2(hash(i + o), hash(i + o + 3.1)) - f);
                if (l < d) { d2 = d; d = l; } else if (l < d2) d2 = l;
            }
        vec3 c = rgb * (0.84 + 0.26 * fbm(uv * 0.006));
        c *= 1.0 - 0.1 * pow(fbm(uv * 0.03 + 7.0), 3.0);    // worn creases
        c *= 1.0 - fine * 0.1 * (1.0 - smoothstep(0.0, 0.2, d2 - d));
        return c * (1.0 + fine * 0.05 * (0.5 - d));          // pebbles
    }
    // boucle: knots of looped yarn, a nubbly coat
    float fine = 1.0 - smoothstep(1.0, 4.5, px);
    vec2 g = uv / 5.0;
    vec2 i = floor(g), f = fract(g);
    float d = 9.0;
    for (int y = -1; y <= 1; y++)
        for (int x = -1; x <= 1; x++) {
            vec2 o = vec2(float(x), float(y));
            d = min(d, length(o + vec2(hash(i + o), hash(i + o + 5.7)) - f));
        }
    float loop = 1.0 - smoothstep(0.1, 0.62, d);
    vec3 c = rgb * (0.9 + 0.12 * fbm(uv * 0.02) + 0.1 * (noise(uv / 12.0) - 0.5));
    return c * (1.0 - fine * (0.26 * (1.0 - loop) - 0.06));
}
vec3 surface(float id, vec3 n, vec3 rgb, float px) {
    vec3 an = abs(n);
    vec2 uv;
    bool roof = id == 4.0 || id == 5.0 || (id >= 23.0 && id <= 26.0);
    if (an.z > 0.75 && !roof) uv = v_pos.xy;
    else if (an.z > 0.97) uv = v_pos.xy;
    else {
        float along = (an.x > an.y) ? v_pos.y : v_pos.x;
        float up = v_pos.z;
        if (roof)
            up = v_pos.z / max(length(n.xy), 0.25);
        uv = vec2(along, up);
    }
    if (id == 1.0) {                       // brick, stretcher bond
        vec2 b = vec2(225.0, 75.0);
        float row = floor(uv.y / b.y);
        float x = uv.x / b.x + 0.5 * mod(row, 2.0);
        vec2 cell = vec2(floor(x), row);
        vec2 f = vec2(fract(x) * b.x, fract(uv.y / b.y) * b.y);
        float mortar = max(joint(f.x, 10.0, px), joint(f.y, 10.0, px));
        float tone = 0.78 + 0.34 * hash(cell) + 0.12 * (noise(uv * 0.08) - 0.5);
        vec3 brick = rgb * tone;
        brick *= 1.0 - 0.18 * smoothstep(55.0, 75.0, f.y);   // lower lip
        vec3 mortarc = vec3(0.74, 0.71, 0.66);
        return mix(brick, mortarc, clamp(mortar, 0.0, 1.0));
    }
    if (id == 2.0) {                       // board-marked concrete
        vec2 p = vec2(1200.0, 600.0);
        vec2 f = mod(uv, p);
        float jl = max(joint(f.x, 8.0, px), joint(f.y, 8.0, px));
        vec2 tie = abs(mod(uv + vec2(0.0, 150.0), vec2(600.0, 300.0))
                       - vec2(300.0, 150.0));
        float hole = 1.0 - step(18.0, length(tie));
        float speck = 0.9 + 0.2 * fbm(uv * 0.02) + 0.08 * (hash(floor(uv / 6.0)) - 0.5);
        vec3 c = rgb * speck;
        c *= 1.0 - 0.25 * jl - 0.4 * hole;
        return c;
    }
    if (id == 3.0) {                       // render / stucco
        return rgb * (0.9 + 0.16 * fbm(uv * 0.01) + 0.06 * (hash(floor(uv / 4.0)) - 0.5));
    }
    if (id == 4.0 || id == 5.0) {          // clay roof tiles / slate
        vec2 t = (id == 4.0) ? vec2(260.0, 190.0) : vec2(300.0, 150.0);
        float row = floor(uv.y / t.y);
        float x = uv.x / t.x + 0.5 * mod(row, 2.0);
        vec2 cell = vec2(floor(x), row);
        float fy = fract(uv.y / t.y), fx = fract(x);
        float tone = (id == 4.0 ? 0.8 + 0.3 * hash(cell)
                                : 0.85 + 0.2 * hash(cell));
        vec3 c = rgb * tone;
        c *= 0.62 + 0.38 * smoothstep(0.0, 0.35 + px / t.y, fy);        // course shadow
        if (id == 4.0) c *= 0.85 + 0.15 * sin(fx * 3.14159);  // pantile roll
        else c *= 1.0 - 0.35 * max(joint(fx * t.x, 9.0, px), joint((1.0 - fx) * t.x, 9.0, px));
        c *= 0.92 + 0.12 * fbm(uv * 0.004);                  // weathering
        return c;
    }
    if (id == 6.0) {                       // random stone
        vec2 g = uv / vec2(420.0, 260.0);
        vec2 i = floor(g), f = fract(g);
        float d = 9.0, d2 = 9.0; vec2 best = i;
        for (int y = -1; y <= 1; y++)
            for (int x = -1; x <= 1; x++) {
                vec2 o = vec2(float(x), float(y));
                vec2 pt = o + vec2(hash(i + o), hash(i + o + 7.3)) - f;
                float l = length(pt);
                if (l < d) { d2 = d; d = l; best = i + o; }
                else if (l < d2) d2 = l;
            }
        float seam = 1.0 - smoothstep(0.02, 0.09, d2 - d);
        vec3 c = rgb * (0.75 + 0.4 * hash(best)) * (0.9 + 0.2 * fbm(uv * 0.02));
        return mix(c, vec3(0.62, 0.6, 0.56), seam);
    }
    if (id == 7.0) {                       // bark: vertical furrows
        float a = atan(n.y, n.x) * 180.0;
        float f = noise(vec2(a * 0.12, v_pos.z * 0.004)) * 0.6
                  + noise(vec2(a * 0.5, v_pos.z * 0.02)) * 0.4;
        return rgb * (0.55 + 0.7 * f);
    }
    if (id == 8.0) {                       // leaves: dappled clumps
        vec2 p = vec2(v_pos.x + v_pos.z * 0.7, v_pos.y - v_pos.z * 0.5);
        float f = fbm(p * 0.006) * 0.6 + hash(floor(p / 45.0)) * 0.4;
        vec3 c = rgb * (0.55 + 0.75 * f);
        return c + vec3(0.05, 0.08, 0.0) * step(0.8, f);
    }
    if (id >= 9.0 && id <= 17.0) return tiles(id, uv, rgb, px);
    if (id == 32.0) return wood(uv, rgb, px);
    if (id >= 28.0) return upholstery(id, uv, n, rgb, px);
    if (id >= 18.0) return finishes(id, uv, rgb, px);
    return rgb;
}

void main() {
    vec3 n = normalize(v_nrm);
    float shade = abs(dot(n, u_light));
    if (u_toon > 0.5) shade = floor(shade * 3.0 + 0.5) / 3.0;
    vec3 h = normalize(u_light + v_to_eye);
    float spec = max(dot(n, h), 0.0);
    float gloss = (v_mat.w > 0.0) ? v_mat.z * pow(spec, v_mat.w)
                  : v_mat.z * pow(spec, 40.0);
    float v = v_mat.x + v_mat.y * shade;
    v = (v - 0.5) * u_gain + 0.5 + u_offset;
    if (u_cavity > 0.5) v *= v_cav;
    vec3 base = v_rgb;
    if (v_mat.w < -0.5) {
        // fade the pattern to its mean where it is finer than a few
        // pixels, or bricks and slates shimmer into moire at a distance
        float id = -v_mat.w;
        float feat = (id == 1.0) ? 75.0 : (id == 2.0) ? 300.0 :
                     (id == 3.0) ? 60.0 : (id == 4.0) ? 190.0 :
                     (id == 5.0) ? 150.0 : (id == 6.0) ? 260.0 :
                     (id == 7.0) ? 150.0 : (id == 8.0) ? 45.0 :
                     (id == 11.0) ? 25.0 : (id == 10.0) ? 75.0 :
                     (id == 14.0 || id == 13.0) ? 600.0 :
                     (id == 15.0) ? 300.0 : (id == 16.0) ? 18.0 :
                     (id == 20.0 || id == 21.0) ? 12.0 :
                     (id == 18.0 || id == 22.0 || id == 23.0) ? 140.0 :
                     (id == 25.0) ? 500.0 : (id == 29.0) ? 1e6 :
                     (id == 32.0) ? 120.0 :
                     (id >= 28.0) ? 80.0 : 100.0;
        float px = length(fwidth(v_pos));
        float fade = smoothstep(feat * 0.5, feat * 1.2, px);
        vec3 mean = v_rgb * ((id == 1.0) ? 0.93 : (id == 4.0) ? 0.82 :
                             (id == 15.0) ? 0.55 : (id == 22.0) ? 0.85 :
                             (id == 23.0) ? 0.75 : 0.95);
        base = mix(surface(id, n, v_rgb, px), mean, fade);
    }
    vec3 rgb = clamp(base * v + vec3(gloss), 0.0, 1.0);
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
        **{name: (0.52, 0.48, SURFACE_LOOK.get(name, (0.0, 0.8))[0],
                  -float(pid), SURFACE_LOOK.get(name, (0.0, 0.8))[1], 1.0)
           for name, pid in SURFACES.items()},
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
    # smooth shading: a normal per vertex, averaged over the faces that
    # meet there short of a crease (shading.vertex_normals), so a
    # sphere, a loft or a sculpted head reads as one skin, not facets
    smooth = bool(getattr(view, "smooth", False))
    vnormals = None
    if smooth:
        from .shading import vertex_normals
        vnormals = vertex_normals(mesh)
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
        rest = (r, g, b, alpha, amb, dif, gk, gp, cav)
        if vnormals is not None:
            tails = tuple(n + rest for n in vnormals[i])
            if alpha < 0.99:
                trans.append((tri, tails))
                continue
            for v, tail in zip(tri, tails):
                opaque.extend((v[0], v[1], v[2]) + tail)
            continue
        tail = (nx, ny, nz) + rest
        if alpha < 0.99:
            trans.append((tri, tail))
            continue
        for v in tri:
            opaque.extend((v[0], v[1], v[2]) + tail)
    return opaque, trans


def translucent_tails(entry):
    """The per-vertex tails of one translucent entry: three when the
    mesh was packed smooth, else the face's own repeated."""
    tri, tail = entry
    if tail and isinstance(tail[0], tuple):
        return tail
    return (tail, tail, tail)


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
               bool(view.cavity), bool(getattr(view, "smooth", False)))
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
            # an exported picture renders at a multiple of the view's
            # size (View3D.snapshot's pixel_ratio); the projection stays
            # in view units, so only the framebuffer grows
            ratio = float(getattr(view, "_pixel_ratio", 1.0) or 1.0)
            w = max(int(round(view.width() * ratio)), 1)
            h = max(int(round(view.height() * ratio)), 1)
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
        for entry in sorted(trans, key=depth, reverse=True):
            for v, tail in zip(entry[0], translucent_tails(entry)):
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
        f.glLineWidth(1.2 * float(getattr(view, "_pixel_ratio", 1.0) or 1.0))
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
