"""The map import: GeoTIFF reading, OSM -> spec, LiDAR heights and
trees, footprint buildings, measured terrain, light detail and specs
from files — all offline, with fake downloaders.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import math
import struct
import urllib.parse
import zlib

import pytest

from khervecad import (city, city_footprint, geo, geotiff, lidar,
                       map_import, mesh, osm_import)

LAT0, LON0 = 51.1326, 0.2187


# ---------------------------------------------------------------- tiffs
def make_tiff(values, transform, compress=False, nodata=None, bo=">"):
    """A one-band float32 GeoTIFF (strip per row block)."""
    h, w = len(values), len(values[0])
    raw = b"".join(struct.pack(bo + "f" * w, *row) for row in values)
    data = zlib.compress(raw) if compress else raw
    entries = []

    def tag(t, typ, count, payload):
        entries.append((t, typ, count, payload))

    header = 8
    a, b_, c, d, e, f = transform
    matrix = struct.pack(bo + "16d", a, b_, 0, c, d, e, 0, f, 0, 0, 0, 0,
                         0, 0, 0, 1)
    nd = (f"{nodata}".encode() + b"\0") if nodata is not None else None
    n_tags = 11 + (1 if nd else 0)
    ifd_size = 2 + 12 * n_tags + 4
    extra_off = header + ifd_size
    matrix_off = extra_off
    nd_off = matrix_off + len(matrix)
    data_off = nd_off + (len(nd) if nd else 0)
    tag(256, 3, 1, w)
    tag(257, 3, 1, h)
    tag(258, 3, 1, 32)
    tag(259, 3, 1, 8 if compress else 1)
    tag(262, 3, 1, 1)
    tag(273, 4, 1, data_off)
    tag(277, 3, 1, 1)
    tag(278, 3, 1, h)
    tag(279, 4, 1, len(data))
    tag(339, 3, 1, 3)
    tag(34264, 12, 16, matrix_off)
    if nd:
        tag(42113, 2, len(nd), nd_off)
    out = bytearray((b"II" if bo == "<" else b"MM") + struct.pack(
        bo + "HI", 42, header))
    out += struct.pack(bo + "H", n_tags)
    for t, typ, count, payload in entries:
        if typ == 3:
            out += struct.pack(bo + "HHI", t, typ, count) + struct.pack(
                bo + "HH", payload, 0)
        else:
            out += struct.pack(bo + "HHII", t, typ, count, payload)
    out += struct.pack(bo + "I", 0)
    out += matrix
    if nd:
        out += nd
    out += data
    return bytes(out)


@pytest.mark.parametrize("compress", [False, True])
@pytest.mark.parametrize("bo", ["<", ">"])
def test_geotiff_reads_values_and_georeference(compress, bo):
    vals = [[float(r * 10 + c) for c in range(5)] for r in range(4)]
    data = make_tiff(vals, (1.0, 0.0, 100.0, 0.0, -1.0, 50.0), compress,
                     nodata=-9999, bo=bo)
    r = geotiff.read(data)
    assert (r.width, r.height) == (5, 4)
    assert r.values[2][3] == 23.0
    assert r.nodata == -9999
    # pixel (col 3, row 2) centre is world (103.5, 47.5)
    assert r.sample(103.5, 47.5) == pytest.approx(23.0)
    assert r.sample(103.0, 47.5) == pytest.approx(22.5)
    assert r.sample(500.0, 47.5) is None


def test_geotiff_rejects_non_tiff():
    with pytest.raises(geotiff.GeoTiffError):
        geotiff.read(b"<html>error</html>")


# ------------------------------------------------------------ projection
def test_projection_round_trip_and_scale():
    p = geo.Projection(LAT0, LON0)
    lat, lon = p.to_latlon(123456.0, -65432.0)
    x, y = p.to_local(lat, lon)
    assert (x, y) == (pytest.approx(123456.0), pytest.approx(-65432.0))
    # one degree of latitude is ~111.2 km at 51 N
    assert p.m_lat == pytest.approx(111250, rel=0.002)
    s, w, n, e = geo.bbox_from({"center": [LAT0, LON0], "radius_m": 100})
    x0, y0 = p.to_local(s, w)
    assert x0 == pytest.approx(-100000, rel=1e-3)
    with pytest.raises(geo.GeoError):
        geo.bbox_from({})


# ------------------------------------------------------------------- osm
def _node(p, x, y):
    lat, lon = p.to_latlon(x, y)
    return {"lat": lat, "lon": lon}


def fake_osm(p):
    """An L-shaped house with tags, a plain house, a road crossing the
    box edge, a tree and a small wood."""
    L = [(0, 0), (12000, 0), (12000, 6000), (5000, 6000), (5000, 10000),
         (0, 10000), (0, 0)]
    box_house = [(30000, 0), (40000, 0), (40000, 8000), (30000, 8000),
                 (30000, 0)]
    wood = [(-60000, -60000), (-30000, -60000), (-30000, -30000),
            (-60000, -30000), (-60000, -60000)]
    return {"elements": [
        {"type": "way", "id": 1, "tags": {"building": "house",
                                          "building:levels": "2",
                                          "roof:shape": "flat",
                                          "name": "The L"},
         "geometry": [_node(p, x, y) for x, y in L]},
        {"type": "way", "id": 2, "tags": {"building": "yes"},
         "geometry": [_node(p, x, y) for x, y in box_house]},
        {"type": "way", "id": 3, "tags": {"highway": "residential",
                                          "name": "Dornden Drive"},
         "geometry": [_node(p, x, y) for x, y in
                      [(-500000, -20000), (0, -20000), (50000, -20000)]]},
        {"type": "node", "id": 4, "tags": {"natural": "tree"},
         **_node(p, 20000, 20000)},
        {"type": "way", "id": 5, "tags": {"natural": "wood"},
         "geometry": [_node(p, x, y) for x, y in wood]},
    ]}


def test_osm_to_spec_outlines_roads_trees():
    bbox = geo.bbox_from({"center": [LAT0, LON0], "radius_m": 100})
    p = geo.projection_for(bbox)
    spec = osm_import.to_spec(fake_osm(p), bbox)
    by_id = {b["osm_id"]: b for b in spec["buildings"]}
    L = by_id[1]
    assert len(L["footprint"]) == 6
    assert L["floors"] == 2 and L["height"] == 6000
    assert L["roof"] == "flat" and L["name"] == "The L"
    assert L["style"] == "house"
    assert max(L["w"], L["d"]) == pytest.approx(12000, abs=5)
    # the footprint keeps its area in the building's frame
    area = abs(osm_import._area(L["footprint"]))
    assert area == pytest.approx(12000 * 6000 + 5000 * 4000, rel=0.01)
    assert by_id[2]["roof"] in ("gable", "hip")
    # the road is clipped to the box (100 m each way)
    (road,) = spec["roads"]
    assert road["kind"] == "street"
    assert min(pt[0] for pt in road["points"]) >= -100100
    assert len([t for t in spec["trees"]]) > 1          # tree + wood
    assert "OpenStreetMap" in spec["geo"]["attribution"]


def test_clip_polyline_splits_a_road_that_leaves_and_returns():
    pieces = osm_import.clip_polyline(
        [(-5, 0), (5, 0), (5, 20), (0, 20), (0, 5)], (-10, -10, 10, 10))
    assert len(pieces) == 2


# --------------------------------------------------------------- lidar
def lidar_opener(p, bbox, ground=lambda x, y: 100.0 + x / 50000.0,
                 things=()):
    """A fake WCS: DTM = a gentle east slope; DSM adds boxes of
    (x0, y0, x1, y1, height_m) and round tree crowns (x, y, r, h)."""
    s, w, n, e = bbox

    def opener(url):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        subsets = q["subset"]
        la = [float(v) for v in subsets[0][4:-1].split(",")]
        lo = [float(v) for v in subsets[1][5:-1].split(",")]
        dsm = "DSM" in q["CoverageId"][0]
        cols, rows = 60, 60
        dlon = (lo[1] - lo[0]) / cols
        dlat = (la[1] - la[0]) / rows
        vals = []
        for r in range(rows):
            row = []
            for c in range(cols):
                lat = la[1] - (r + 0.5) * dlat
                lon = lo[0] + (c + 0.5) * dlon
                x, y = p.to_local(lat, lon)
                v = ground(x, y)
                if dsm:
                    for t in things:
                        if len(t) == 5:
                            if t[0] <= x <= t[2] and t[1] <= y <= t[3]:
                                v += t[4]
                        else:
                            d = math.hypot(x - t[0], y - t[1])
                            if d < t[2]:
                                v += t[3] * (1 - (d / t[2]) ** 2)
                row.append(v)
            vals.append(row)
        return make_tiff(vals, (dlon, 0.0, lo[0], 0.0, -dlat, la[1]))
    return opener


def test_lidar_ground_building_shape_and_trees():
    bbox = geo.bbox_from({"center": [LAT0, LON0], "radius_m": 60})
    p = geo.projection_for(bbox)
    opener = lidar_opener(p, bbox, things=[
        (-20000, -20000, -10000, -10000, 5.0),        # a 5 m flat block
        (30000, 30000, 7000, 12.0)])                  # a 12 m tree
    h = lidar.Heights(bbox, p, opener=opener)
    rows, base, missing = h.ground_grid(-60000, -60000, 120000, 120000, 12)
    assert missing == 0
    # the slope: 2.4 m over 120 m, relative to the lowest point
    assert rows[0][-1] - rows[0][0] == pytest.approx(2400, abs=150)
    eave, ridge = h.building_shape([(-20000, -20000), (-10000, -20000),
                                    (-10000, -10000), (-20000, -10000)])
    assert ridge == pytest.approx(5000, abs=600)
    trees = h.detect_trees(-60000, -60000, 60000, 60000, footprints=[
        [(-20000, -20000), (-10000, -20000), (-10000, -10000),
         (-20000, -10000)]])
    assert len(trees) == 1
    t = trees[0]
    assert math.hypot(t["x"] - 30000, t["y"] - 30000) < 2500
    assert t["height"] == pytest.approx(12000, abs=1500)
    assert lidar.tree_kind(t["height"], t["crown"]) in (
        "oak", "maple", "lime", "birch", "spruce")


def test_import_map_offline_builds_a_measured_village():
    bbox = geo.bbox_from({"center": [LAT0, LON0], "radius_m": 100})
    p = geo.projection_for(bbox)
    things = [(0, 0, 12000, 10000, 7.0), (30000, 0, 40000, 8000, 8.0),
              (-40000, 40000, 5000, 14.0)]
    spec, report, ref = map_import.import_map(
        {"center": [LAT0, LON0], "radius_m": 100},
        osm_opener=lambda url, body: json.dumps(fake_osm(p)).encode(),
        lidar_opener=lidar_opener(p, bbox, things=things))
    assert ref is None and "lidar_error" not in report
    assert spec["terrain"]["kind"] == "heights"
    assert report["lidar_trees"] >= 1 and report["buildings_measured"] == 1
    plain = next(b for b in spec["buildings"] if b["osm_id"] == 2)
    assert plain["height"] >= 2300
    built = city.build(spec)
    assert set(built["nodes"]) >= {"City ground", "City roads",
                                   "City buildings", "City trees"}
    tris = mesh.tessellate(built["nodes"]["City buildings"])
    assert tris


def test_import_map_survives_a_lidar_failure():
    bbox = geo.bbox_from({"center": [LAT0, LON0], "radius_m": 100})
    p = geo.projection_for(bbox)

    def broken(url):
        return b"<ServiceException/>"
    spec, report, _ = map_import.import_map(
        {"center": [LAT0, LON0], "radius_m": 100},
        osm_opener=lambda url, body: json.dumps(fake_osm(p)).encode(),
        lidar_opener=broken)
    assert "lidar_error" in report and "terrain" not in spec
    city.build(spec)


# ------------------------------------------------ buildings and detail
def test_footprint_building_follows_its_outline():
    L = [[-6000, -5000], [6000, -5000], [6000, 1000], [-1000, 1000],
         [-1000, 5000], [-6000, 5000]]
    spec = {"buildings": [dict(style="house", x=0, y=0, w=12000, d=10000,
                               footprint=L, height=5500, roof="gable",
                               detail="full")]}
    node = city.build(dict(spec, detail="full"))["nodes"]["City buildings"]
    tris = mesh.tessellate(node)
    zs = [v[2] for t in tris for v in t]
    # an L fills 70 % of its rectangle: a flat roof, not a hull over it
    assert max(zs) < 5500 + 600
    # nothing stands in the missing corner (x > 0, y > 1 m, below roof)
    corner = [v for t in tris for v in t
              if v[0] > 500 and v[1] > 2000 and 100 < v[2] < 5000]
    assert not corner


def test_low_detail_is_much_lighter():
    rect = [[-5000, -4000], [5000, -4000], [5000, 4000], [-5000, 4000]]
    b = [dict(style="house", x=i * 20000, y=0, w=10000, d=8000,
              footprint=rect, floors=2, roof="hip") for i in range(6)]
    full = mesh.tessellate(city.build({"buildings": b, "detail": "full"})[
        "nodes"]["City buildings"])
    low = mesh.tessellate(city.build({"buildings": b, "detail": "low"})[
        "nodes"]["City buildings"])
    assert len(low) * 5 < len(full)
    assert city_footprint.auto_detail("auto", 151) == "low"
    trees = [dict(kind="oak", x=i * 9000, y=0) for i in range(3)]
    full_t = mesh.tessellate(city.build({"trees": trees})["nodes"][
        "City trees"])
    low_t = mesh.tessellate(city.build({"trees": trees, "detail": "low"})[
        "nodes"]["City trees"])
    assert len(low_t) * 3 < len(full_t)


def test_measured_terrain_levels_the_ground():
    rows = [[i * 500.0 for i in range(5)] for _ in range(5)]
    spec = {"terrain": {"kind": "heights", "rows": rows, "x0": -40000,
                        "y0": -40000, "length": 80000, "width": 80000},
            "buildings": [dict(style="house", x=0, y=0)]}
    r = city.build(spec)
    tris = mesh.tessellate(r["nodes"]["City ground"])
    assert max(v[2] for t in tris for v in t) == pytest.approx(2000, abs=1)
    with pytest.raises(city.CityError):
        city.build({"terrain": {"kind": "heights", "rows": [[1, 2]]},
                    "buildings": [dict(style="house")]})


def test_spec_round_trips_through_a_file(tmp_path):
    spec = {"buildings": [dict(style="house", x=0, y=0)],
            "roads": [dict(kind="lane", points=[[0, -9000], [20000, -9000]])]}
    path = tmp_path / "village.json"
    map_import.save_spec(spec, str(path))
    assert map_import.load_spec(str(path)) == spec
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2]")
    with pytest.raises(map_import.MapImportError):
        map_import.load_spec(str(bad))


def test_roughness_changes_the_generated_ground():
    from khervecad import terrain

    def bumpiness(r):
        hs, _ = terrain.height_field("hills", 48, 300000, 300000, 30000, 3, r)
        return sum(abs(row[i + 1] - row[i]) for row in hs
                   for i in range(len(row) - 1))
    smooth, middle, rough = bumpiness(0.0), bumpiness(0.5), bumpiness(1.0)
    assert smooth < middle < rough
    # 0.5 is the landscape as it was before the setting existed
    old, _ = terrain.height_field("hills", 16, 100000, 100000, 20000, 2)
    same, _ = terrain.height_field("hills", 16, 100000, 100000, 20000, 2, 0.5)
    assert old == same
    spec = city.build({"terrain": {"kind": "hills", "roughness": 0.9},
                       "buildings": [dict(style="house")]})["spec"]
    assert spec["terrain"]["roughness"] == 0.9
