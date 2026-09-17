"""The Car Builder (car_models / car_wheels / car_build): every car
builds, validates, uses no boolean, stands on its wheels and comes out
at its published size.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest

from khervecad import car_build, car_models, car_wheels, library, mesh
from khervecad.model import validate


def _extent(node, fn=16):
    tris = mesh.tessellate(node, fn=fn)
    assert tris
    xs = [p[0] for t in tris for p in t]
    ys = [p[1] for t in tris for p in t]
    zs = [p[2] for t in tris for p in t]
    return (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs),
            min(zs))


@pytest.mark.parametrize("key", sorted(car_models.CARS))
def test_every_car_builds_at_its_published_size(key):
    node = car_build.build_car(key)
    assert not validate(node)
    assert "difference" not in {n.type for n in node.walk()}
    car = car_models.CARS[key]
    w, length, h, floor = _extent(node)
    assert floor == pytest.approx(0.0, abs=1.0)          # on its wheels
    # lamps, the plate and the splitter stand proud of the body
    assert length == pytest.approx(car["L"], rel=0.03)
    assert car["W"] * 0.95 <= w <= car["W"] + 450    # mirrors stand out
    assert h <= car["H"] * 1.25                          # wings stand proud
    assert h >= car["H"] * 0.9


def test_tyre_size_reads_a_published_size():
    width, ratio, diameter = car_wheels.tyre_size("245/35 ZR20")
    assert (width, ratio) == (245.0, 0.35)
    assert diameter == pytest.approx(20 * 25.4 + 2 * 245 * 0.35)


@pytest.mark.parametrize("rim", sorted(car_wheels.RIMS))
def test_every_rim_style_builds(rim):
    node = car_build.build_car("porsche_911_rs", dict(rim=rim))
    assert not validate(node)
    assert _extent(node)[0] > 1000


@pytest.mark.parametrize("tyre", sorted(car_wheels.TYRES))
def test_a_tyre_style_keeps_the_overall_diameter(tyre):
    """A tyre style changes the sidewall, not the rolling radius: the
    car keeps its ride height."""
    node = car_build.build_car("bmw_m3_e30", dict(tyre=tyre))
    assert not validate(node)
    assert _extent(node)[2] == pytest.approx(
        _extent(car_build.build_car("bmw_m3_e30"))[2], rel=0.02)


def test_a_scale_model_is_the_car_divided():
    small = car_build.build_car("ferrari_f40", dict(scale=1 / 18))
    assert _extent(small)[1] == pytest.approx(
        car_models.CARS["ferrari_f40"]["L"] / 18, rel=0.03)


def test_every_car_is_a_part_library_part():
    for key in car_models.CARS:
        part = library.PARTS[f"car_{key}"]
        assert part["category"] == car_build.CATEGORY
        assert part["colors"][0] in car_models.PAINTS
    assert "BMW" in library.PARTS["car_bmw_m1"]["label"]


def test_the_paint_choice_reaches_the_body():
    node = car_build.build_car("porsche_930_turbo", dict(paint="Giallo"))
    colours = {n.params.get("color") for n in node.walk()
               if n.type == "color"}
    assert car_models.PAINTS["Giallo"] in colours


def test_measured_profiles_are_sane_curves():
    """The blueprint-measured curves (car_profiles) are normalised and
    the right way round, whether or not the builder follows them yet."""
    from khervecad import car_profiles
    assert car_profiles.PROFILES
    for key, prof in car_profiles.PROFILES.items():
        assert key in car_models.CARS
        assert len(prof["roof"]) == len(prof["floor"]) == 60
        assert 0.9 <= max(prof["roof"]) <= 1.0
        assert min(prof["floor"]) >= 0.0
        assert max(prof["roof"]) > max(prof["floor"])
        if prof["width"]:
            assert 0.9 <= max(prof["width"]) <= 1.0
