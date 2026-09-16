"""Import a real place as a City Builder design (Qt-free except the
aerial photo).

`import_map(params)` is the whole pipeline behind the `import_map` MCP
tool:

1. the area: ``center`` [lat, lon] + ``radius_m``, or ``bbox``;
2. OpenStreetMap (`osm_import`): roads, real building outlines, heights
   and roof shapes from the tags, mapped trees and woods;
3. ``heights`` "lidar" (England): the ground as a measured height field
   (the City Builder levels roads and pads on it), and every building
   whose map entry has no height measured from the surface model — the
   eaves under the roof top, since the survey sees the ridge;
4. ``trees`` "lidar": tree tops found in the canopy height model replace
   the mapped trees (woods included) — each with its measured height and
   a species that fits its shape; "osm" keeps the map's; "both"; "none";
5. ``detail``: "auto" (low past 150 buildings), "low" or "full";
6. ``aerial``: the photo of the area saved beside the document (or in
   the temp folder) and laid on the ground as a reference image.

The spec it returns is ordinary City Builder JSON — `save_spec` writes
it, `load_spec` reads it back, and build_city takes it (or its path)
without anything passing through a chat.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
import math
import os
import tempfile

from . import geo, lidar, osm_import

MAX_CELLS = 128


class MapImportError(RuntimeError):
    """The place could not be imported (the message says why)."""


def _world_outline(b):
    """A building's footprint in local mm (placed and turned)."""
    a = math.radians(float(b.get("rz") or 0.0))
    c, s = math.cos(a), math.sin(a)
    fp = b.get("footprint") or [[-b["w"] / 2, -b["d"] / 2],
                                [b["w"] / 2, -b["d"] / 2],
                                [b["w"] / 2, b["d"] / 2],
                                [-b["w"] / 2, b["d"] / 2]]
    return [(b["x"] + x * c - y * s, b["y"] + x * s + y * c) for x, y in fp]


def import_map(params, osm_opener=None, lidar_opener=None,
               aerial_opener=None, aerial_dir=None, log=None):
    """The spec for a real area plus a report (see module doc). Returns
    (spec, report, reference) — reference is the aerial image dict or
    None."""
    log = log or (lambda msg: None)
    try:
        bbox = geo.bbox_from(params)
    except geo.GeoError as exc:
        raise MapImportError(str(exc))
    proj = geo.projection_for(bbox)
    report = {"bbox": list(bbox), "center": [proj.lat0, proj.lon0],
              "sources": [osm_import.ATTRIBUTION]}
    heights = params.get("heights", "lidar")
    trees = params.get("trees", "auto")
    if trees == "auto":
        trees = "lidar" if heights == "lidar" else "osm"

    log("Downloading OpenStreetMap…")
    kwargs = {"opener": osm_opener} if osm_opener else {}
    try:
        data = osm_import.fetch(bbox, **kwargs)
    except osm_import.OsmError as exc:
        raise MapImportError(str(exc))
    spec = osm_import.to_spec(data, bbox, seed=int(params.get("seed") or 1),
                              trees=trees in ("osm", "both"),
                              woods=trees in ("osm", "both"))
    if params.get("name"):
        spec["name"] = params["name"]
    report.update(roads=len(spec["roads"]), buildings=len(spec["buildings"]),
                  osm_trees=len(spec["trees"]))

    x0, y0 = proj.to_local(bbox[0], bbox[1])
    x1, y1 = proj.to_local(bbox[2], bbox[3])
    if heights == "lidar" or trees in ("lidar", "both"):
        hk = {"opener": lidar_opener} if lidar_opener else {}
        survey = lidar.Heights(bbox, proj, **hk)
        try:
            if heights == "lidar":
                log("Downloading LiDAR ground (DTM)…")
                n = max(8, min(MAX_CELLS, int(max(x1 - x0, y1 - y0)
                                             / 6000.0)))
                rows, base, missing = survey.ground_grid(
                    x0, y0, x1 - x0, y1 - y0, n)
                spec["terrain"] = dict(kind="heights", rows=rows, x0=x0,
                                       y0=y0, length=x1 - x0,
                                       width=y1 - y0,
                                       source="Environment Agency LiDAR "
                                              "DTM 1 m")
                report.update(ground_base_m=round(base, 2),
                              relief_m=round(max(max(r) for r in rows)
                                             / 1000.0, 2),
                              ground_cells=n, ground_gaps=missing)
                log("Measuring buildings (DSM)…")
                measured = 0
                for b in spec["buildings"]:
                    if b.get("height"):
                        continue
                    shape = survey.building_shape(_world_outline(b))
                    if shape is None:
                        continue
                    eave, ridge = shape
                    eave = max(2300.0, eave)
                    rise = ridge - eave
                    if b.get("roof") in ("gable", "hip"):
                        if rise < 800.0:
                            b["roof"] = "flat"
                        else:
                            b["roof_pitch"] = round(min(55.0, max(
                                12.0, math.degrees(math.atan2(
                                    rise, b["d"] / 2)))), 1)
                    elif rise > 1500.0 and b.get("style") in ("house",
                                                              "terrace"):
                        b["roof"] = "hip" if abs(b["w"] - b["d"]) < 3000 \
                            else "gable"
                        b["roof_pitch"] = round(min(55.0, max(12.0, math.degrees(
                            math.atan2(rise, b["d"] / 2)))), 1)
                    b["height"] = round(eave)
                    b["floors"] = max(1, round(eave / 2700.0))
                    measured += 1
                report["buildings_measured"] = measured
            if trees in ("lidar", "both"):
                log("Finding trees in the canopy (DSM - DTM)…")
                found = survey.detect_trees(
                    x0, y0, x1, y1,
                    footprints=[_world_outline(b) for b in spec["buildings"]],
                    step=float(params.get("tree_step_m") or 1.5) * 1000.0)
                for t in found:
                    spec["trees"].append(dict(
                        kind=lidar.tree_kind(t["height"], t["crown"]),
                        x=round(t["x"]), y=round(t["y"]),
                        height=round(t["height"])))
                report["lidar_trees"] = len(found)
            report["sources"].append(
                "Environment Agency LiDAR composite 1 m (Open Government "
                "Licence)")
        except lidar.LidarError as exc:
            report["lidar_error"] = str(exc)
            spec.pop("terrain", None)
    spec["detail"] = params.get("detail", "auto")
    reference = None
    if params.get("aerial"):
        from . import aerial
        folder = aerial_dir or tempfile.gettempdir()
        path = os.path.join(folder, "map-aerial-{:.5f}-{:.5f}.png".format(
            proj.lat0, proj.lon0))
        log("Downloading aerial photographs…")
        ak = {"opener": aerial_opener} if aerial_opener else {}
        try:
            wpx, hpx, zoom = aerial.fetch(bbox, path, **ak)
            reference = aerial.reference_for(bbox, proj, path)
            report.update(aerial=path, aerial_pixels=[wpx, hpx],
                          aerial_zoom=zoom)
            report["sources"].append(aerial.ATTRIBUTION)
        except aerial.AerialError as exc:
            report["aerial_error"] = str(exc)
    spec.setdefault("geo", {})["sources"] = report["sources"]
    return spec, report, reference


def save_spec(spec, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(spec, f, separators=(",", ":"))
    return os.path.getsize(path)


def load_spec(path):
    try:
        with open(path, encoding="utf-8") as f:
            spec = json.load(f)
    except (OSError, ValueError) as exc:
        raise MapImportError(f"Could not read a city spec from {path!r}: "
                             f"{exc}")
    if not isinstance(spec, dict):
        raise MapImportError("A city spec file holds one JSON object")
    return spec
