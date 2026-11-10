"""Draw ``packaging/khervecad.png``, the app mark, from a real solid.

The part is a pillow-block bracket — a base plate with two counterbored
bolt holes and rounded corners, an upright with a bored boss and a
two gussets — built with Manifold (the library KherveCAD previews with),
rendered isometric through a small numpy z-buffer with flat shading and
outlines found where the normal or depth jumps. Then run
``make_icon.py`` (Windows .ico); macOS builds the .icns from the PNG.

    .venv/bin/python packaging/draw_icon.py

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from pathlib import Path

import numpy as np
from manifold3d import CrossSection, Manifold
from PIL import Image, ImageDraw, ImageFilter, ImageFont

_HERE = Path(__file__).resolve().parent
SIZE = 1024
SS = 2                      # supersampling
FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def part() -> Manifold:
    seg = 96
    # Base plate 120 x 64 x 14, vertical corners rounded r 8.
    r = 8
    plate = CrossSection.square([120 - 2 * r, 64 - 2 * r]).translate([r, r]).offset(
        r, circular_segments=seg).extrude(14)
    # Upright on the back edge, with a round top.
    up = (CrossSection.square([64, 34]) + CrossSection.circle(32, seg).translate([32, 34]))
    upright = up.extrude(18).rotate([90, 0, 0]).translate([28, 64, 14])
    boss = Manifold.cylinder(26, 22, 22, seg).rotate([-90, 0, 0]).translate([60, 38, 48])
    # Gussets either side of the upright.
    rib = CrossSection([[(0, 0), (22, 0), (0, 26)]]).extrude(8) \
        .rotate([90, 0, 0]).rotate([0, 0, 90]).mirror([0, 1, 0])
    ribs = rib.translate([30, 46, 14]) + rib.translate([82, 46, 14])
    body = plate + upright + boss + ribs
    bore = Manifold.cylinder(80, 13, 13, seg).rotate([-90, 0, 0]).translate([60, 0, 48])
    holes = Manifold()
    for x in (14, 106):
        holes += Manifold.cylinder(40, 5.5, 5.5, seg).translate([x, 22, -5])
        holes += Manifold.cylinder(10, 9.5, 9.5, seg).translate([x, 22, 10])
    return body - bore - holes


def render(m: Manifold, px: int):
    mesh = m.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3].astype(float)
    f = np.asarray(mesh.tri_verts)
    v -= (v.min(0) + v.max(0)) / 2
    # Isometric from the front-right-top: view looks along -d.
    yaw, pitch = np.radians(-35), np.radians(30)
    right = np.array([np.cos(yaw), np.sin(yaw), 0])
    fwd = np.array([-np.sin(yaw) * np.cos(pitch), np.cos(yaw) * np.cos(pitch), -np.sin(pitch)])
    upv = np.cross(right, fwd)
    sx, sy, sz = v @ right, v @ upv, v @ fwd
    span = max(sx.max() - sx.min(), sy.max() - sy.min())
    k = px * 0.92 / span
    X = (sx - (sx.max() + sx.min()) / 2) * k + px / 2
    Y = px / 2 - (sy - (sy.max() + sy.min()) / 2) * k
    Z = sz
    tri = v[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    light = np.array([-0.35, -0.55, 0.76]); light /= np.linalg.norm(light)
    shade = 0.42 + 0.58 * np.clip(n @ light, 0, 1) + 0.12 * np.clip(n[:, 2], 0, 1)
    zbuf = np.full((px, px), np.inf)
    ibuf = np.full((px, px), -1)
    for t, (a, b, c) in enumerate(f):
        if n[t] @ fwd > 0:
            continue
        xs, ys, zs = X[[a, b, c]], Y[[a, b, c]], Z[[a, b, c]]
        x0, x1 = int(max(xs.min(), 0)), int(min(xs.max() + 1, px))
        y0, y1 = int(max(ys.min(), 0)), int(min(ys.max() + 1, px))
        if x0 >= x1 or y0 >= y1:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1) + .5, np.arange(y0, y1) + .5)
        d = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
        if abs(d) < 1e-9:
            continue
        w0 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / d
        w1 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / d
        w2 = 1 - w0 - w1
        ins = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        z = w0 * zs[0] + w1 * zs[1] + w2 * zs[2]
        sub = zbuf[y0:y1, x0:x1]
        win = ins & (z < sub)
        sub[win] = z[win]
        ibuf[y0:y1, x0:x1][win] = t
    hit = ibuf >= 0
    # Brushed steel-grey, a touch cool.
    s = np.where(hit, shade[ibuf], 0)
    base = np.array([205, 210, 218], float)
    rgb = np.clip(s[..., None] * base, 0, 255)
    # Outlines: normal jumps (creases) and silhouettes.
    nb = np.where(hit[..., None], n[ibuf], 0)
    edge = np.zeros((px, px), bool)
    for dy, dx in ((0, 1), (1, 0)):
        a_n, b_n = nb[:px - dy, :px - dx], nb[dy:, dx:]
        a_h, b_h = hit[:px - dy, :px - dx], hit[dy:, dx:]
        crease = (a_h & b_h) & ((a_n * b_n).sum(-1) < 0.82)
        sil = a_h ^ b_h
        e = crease | sil
        edge[:px - dy, :px - dx] |= e
    rgb[edge] = (45, 48, 56)
    alpha = np.where(hit | edge, 255, 0).astype(np.uint8)
    img = np.dstack([rgb.astype(np.uint8), alpha])
    return Image.fromarray(img, "RGBA")


def background(px: int) -> Image.Image:
    yy, xx = np.mgrid[0:px, 0:px] / px
    t = np.clip(yy, 0, 1)
    top, bot = np.array([228, 72, 78]), np.array([140, 16, 24])
    g = top * (1 - t[..., None]) + bot * t[..., None]
    glow = np.exp(-(((xx - .55) / .35) ** 2 + ((yy - .25) / .25) ** 2))
    g = g + glow[..., None] * np.array([18, 30, 30])
    grad = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    mask = Image.new("L", (px, px), 0)
    m = int(px * 0.045)
    ImageDraw.Draw(mask).rounded_rectangle([m, m, px - m, px - m], radius=int(px * .2), fill=255)
    out = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)
    ImageDraw.Draw(out).rounded_rectangle([m, m, px - m, px - m], radius=int(px * .2),
                                          outline=(110, 30, 40, 255), width=int(px * .008))
    return out


def main() -> None:
    px = SIZE * SS
    img = background(px)
    model = render(part(), int(px * 0.62))
    shadow = Image.new("RGBA", model.size, (60, 0, 5, 0))
    shadow.putalpha(model.getchannel("A").point(lambda a: a * 0.45))
    shadow = shadow.filter(ImageFilter.GaussianBlur(px * 0.012))
    ox, oy = (px - model.width) // 2, int(px * 0.06)
    img.alpha_composite(shadow, (ox + int(px * .012), oy + int(px * .02)))
    img.alpha_composite(model, (ox, oy))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, int(px * 0.215))
    text = "kCAD"
    w = d.textlength(text, font=font)
    tx, ty = (px - w) / 2, px * 0.685
    d.text((tx + px * .008, ty + px * .01), text, font=font, fill=(100, 10, 18, 255))
    d.text((tx, ty), text, font=font, fill=(255, 255, 255, 255))
    out = _HERE / "khervecad.png"
    img.resize((SIZE, SIZE), Image.LANCZOS).save(out)
    print(out)


if __name__ == "__main__":
    main()
