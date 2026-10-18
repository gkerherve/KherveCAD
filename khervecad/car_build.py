"""The Car Builder's geometry (Qt-free): a `car_models` entry, its
design (`car_designs`) and the builder's choices (paint, rim, tyre,
finish, caliper, scale) -> one coloured union of closed polyhedra, true
size in mm, front towards -Y, wheels on z = 0, centred on X and Y.

The body is `car_body.Body`: one smooth loft with real wheel openings.
Its glass, pillars, wheel wells and shut lines are laid on it in its
own surface coordinates, and its face — lamps, grille, intakes, number
plate, tail lights — is projected onto it (`car_dress`), so nothing
floats and nothing is cut: no boolean, and the preview is exact.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from . import car_designs, car_dress, car_models, car_wheels
from .car_body import Body
from .landmark_kit import Kit
from .model import CadNode

SCALES = {"1:18": 1 / 18, "Full-size": 1.0, "1:43": 1 / 43, "1:10": 0.1}

DEFAULTS = dict(paint="", rim="", tyre="As delivered", finish="Silver",
                caliper="Red", scale=1.0)


class Car:
    """One car: its catalogue entry, design, options and body."""

    def __init__(self, key, options=None):
        self.key = key
        self.spec = car_models.CARS[key]
        o = dict(DEFAULTS)
        o.update({k: v for k, v in (options or {}).items()
                  if v not in (None, "")})
        self.options = o
        self.d = car_designs.design(key, self.spec)
        self.wheels = [car_wheels.tyre_size(t) for t in
                       (self.spec["tyre_front"], self.spec["tyre_rear"])]
        self.body = Body(self.spec, self.d, self.wheels)

    def paint(self):
        o = self.options
        paint = str(car_models.PAINTS.get(o["paint"], o["paint"]))
        if not paint.startswith("#"):
            paint = car_models.PAINTS[self.spec["paint"]]
        return paint

    def build(self) -> CadNode:
        kit = Kit()
        paint = self.paint()
        self.body.add_to(kit.mesh(paint, "Plastic"))
        car_dress.dress(kit, self, paint)
        group = kit.node(label_of(self.key))
        for i in (0, 1):
            group.add(self._wheel_pair(i))
        scale = float(self.options.get("scale") or 1.0)
        if abs(scale - 1.0) > 1e-9:
            wrap = CadNode("scale", group.name, dict(x=scale, y=scale,
                                                     z=scale))
            wrap.add(group)
            return wrap
        return group

    def _wheel_pair(self, i) -> CadNode:
        o = self.options
        tw, ratio, D = self.wheels[i]
        tyre_ratio, tread = car_wheels.TYRES.get(
            o["tyre"], car_wheels.TYRES["As delivered"])
        rim = o["rim"] or self.spec["rim"]
        pair = CadNode("union", "Front wheels" if i == 0 else "Rear wheels")
        for side in (-1, 1):
            kit = Kit()
            car_wheels.build_wheel(kit, D, tw, tyre_ratio or ratio, tread,
                                   rim, o["finish"], o["caliper"])
            wheel = kit.node(("Right " if side > 0 else "Left ")
                             + ("front" if i == 0 else "rear"))
            rot = CadNode("rotate", wheel.name, dict(x=0.0, y=90.0 * side,
                                                     z=0.0))
            rot.add(wheel)
            move = CadNode("translate", wheel.name, dict(
                x=side * self.body.wheel_x[i], y=self.body.axles[i],
                z=D / 2))
            move.add(rot)
            pair.add(move)
        return pair


def label_of(key: str) -> str:
    car = car_models.CARS[key]
    return f"{car['make']} {car['model']}"


def build_car(key: str, options: dict | None = None) -> CadNode:
    """The car *key* with the builder's *options*, as one node."""
    return Car(key, options).build()


# ------------------------------------------------------- Part Library

def _part_builder(key):
    def build(dims):
        size = dims.get("_size") or "Full-size"
        scale = float(dims.get("scale") or SCALES.get(size, 1.0))
        return build_car(key, dict(paint=dims.get("_color", ""),
                                   scale=scale))
    return build


CATEGORY = "Cars"


def category_of(key: str) -> str:
    return CATEGORY


PARTS = {
    f"car_{key}": dict(
        label=car_models.label(key), category=category_of(key),
        sizes={name: dict(scale=v) for name, v in SCALES.items()},
        fields=[("scale", "Scale")],
        colors=[car["paint"]] + [n for n in car_models.PAINTS
                                 if n != car["paint"]],
        build=_part_builder(key))
    for key, car in car_models.CARS.items()
}
