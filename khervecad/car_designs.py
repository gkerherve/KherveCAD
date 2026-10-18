"""How each car of the Car Builder is SHAPED (Qt-free data): the side
profile, plan, sections and face that `car_body` lofts and `car_build`
dresses — one design per `car_models` entry, built on a family
(`FAMILIES`) and corrected where the car differs.

Units: stations ``s`` are fractions of the overall length from the
nose; heights written as fractions are of the overall height (``nose_z``,
``cowl``, ``roof``, ``deck``, ``belt``...); names noted "mm" are
millimetres. Proportions are fitted by eye to the cars' published
dimensions and photographs; no drawing is traced or shipped.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

BASE = dict(
    # --- side profile (centre line), fractions of H; s of L
    nose_z=0.40,            # bonnet line at the nose
    hood_bulge=0.02,        # bonnet bowed up (fraction of H)
    cowl=(0.32, 0.60),      # windscreen base (s, z)
    roof=(0.46, 0.62),      # roof from .. to (s)
    roof_h=1.0,             # roof height (of H)
    roof_rise=0.02,         # the roof's own crown along its length
    screen_bow=0.025,       # windscreen bowed out
    back_bow=0.03,          # rear glass / fastback bowed out
    deck=(0.84, 0.72),      # end of the rear glass (s, z)
    deck_bulge=0.0,
    tail_z=0.70,            # top of the tail
    chin_z=0.13,            # bottom of the nose
    tail_chin_z=0.24,       # bottom of the tail
    sill=115.0,             # ground clearance at the sills (mm)
    belt=[(0.0, 0.40), (0.32, 0.56), (1.0, 0.70)],
    # --- plan: half width (of W / 2) along s
    plan=[(0.0, 0.80), (0.16, 0.95), (0.5, 0.965), (0.82, 0.99),
          (1.0, 0.92)],
    nose_round=230.0, nose_kx=0.62, nose_kz=0.55,   # mm, end fractions
    tail_round=150.0, tail_kx=0.84, tail_kz=0.80,
    # --- wheels
    fo=0.45,                # front overhang, of (L - wheelbase)
    track_w=(0.90, 0.90),   # wheel outer face, of W / 2 (no track given)
    arch_gap=28.0,          # tyre to arch (mm)
    arch_cover=45.0,        # body over the arch at the shoulder (mm)
    lip=12.0,
    belt_over=25.0,         # belt over the arch's cover (mm)
    wing_reach=420.0,       # how far a raised wing runs out (mm)               # body outside the tyre's face (mm)
    fenders=(30.0, 45.0),   # wing crests over the wheels (mm)
    # --- section
    tuck=70.0,              # flank tucks in at the bottom (mm)
    corner_r=60.0,          # bottom corner (mm)
    shoulder_drop=110.0,    # shoulder line under the belt (mm)
    shoulder_in=45.0,       # body narrows shoulder -> belt (mm)
    shoulder_sq=3.0,        # 2 round .. 6 crisp
    crest_in=110.0,         # wing crest inboard of the belt (mm)
    crest_up=0.0,
    # --- cabin
    cabin_from=0.20, cabin_to=0.95,
    screen_wrap=0.025, back_wrap=0.02,   # glass corners behind centre
    roof_crown=35.0,        # roof edge under the centre (mm)
    tumble=28.0,            # side glass leans in (degrees)
    ledge=28.0,             # glass set in from the belt (mm)
    glass_bow=14.0,
    canopy=0.0,             # cabin narrows at its ends in plan
    # --- dressing
    pillar=0.012,           # A-pillar width (of L)
    b_pillar=None,          # B-pillar station (s) or None
    quarter=None,           # side glass ends here (s); None: at the deck
    black_pillars=False,
    doors=None,             # (front shut, rear shut) stations
    engine_cover=False,     # louvred cover behind the cabin
    engine_cover_to=0.92,
    side_intake=None,       # "strakes", "scoop", "naca" or None
    hood_vents=False,
    scallop=None,           # (s from, s to, depth mm): a side cove
    line=(),                # extra (s, z) knots of an open car's top
    bumpers="body",         # "chrome" for a classic
    bumper_v=(0.30, 0.32),  # chrome bar heights in the face box
    open=False,             # a roadster: no roof, no side glass
    cockpit_to=0.66, interior="#2a1d17", interior_seat="#6b3a26",
    screen_h=330.0, screen_rake=50.0,
    rear_glass=True,
    skirt=False,
    wing=None, wing_h=230.0, wing_chord=300.0,
    exhausts=(0.32, -0.32), exhaust_v=0.16, exhaust_r=38.0,
    face=None, tail=None,
    # --- the face (fractions of the face box: u across, v up)
    lights=None, grille=None, tails=None,   # None: the catalogue's
    lamp_u=0.64, lamp_v=0.74, lamp_scale=1.0, lamp_slant=0.04,
    lamp_view="nose", popup_s=0.09,
    lamp_s=0.045, lamp_tilt=30.0,     # slim lamps: on the nose corner
    hood_full=0.45,         # how full the bonnet is between the wings
    indicators=True, indicator_v=0.34,
    grille_v=0.50, grille_w=0.9,
    intakes=(),             # (u, v, w, h) extra dark intakes
    lower_intake=1.0,       # a splitter intake, of the half width
    plate_v=0.30,
    face_extra=(), tail_extra=(),
    tail_u=0.68, tail_v=0.72, tail_scale=1.0,
    rear_plate_v=0.42,
    diffuser=1.2,
)

#: the families the catalogue's `shape` names
FAMILIES = {
    "mid": dict(
        plan=[(0.0, 0.80), (0.16, 0.95), (0.5, 0.965), (0.78, 1.0),
              (1.0, 0.88)],
        tail_round=230.0, tail_kx=0.80, tail_kz=0.78,
        shoulder_in=[(0.0, 50.0), (0.45, 60.0), (0.75, 120.0),
                     (1.0, 90.0)],
        arch_cover=30.0, belt_over=10.0, hood_bulge=0.05, hood_full=0.75,
        nose_round=170.0, nose_kx=0.70, nose_kz=0.62,
        scallop=(0.52, 0.66, 45.0), tuck=85.0),
    "wedge": dict(
        nose_z=0.30, hood_bulge=0.06, cowl=(0.30, 0.56), roof=(0.47, 0.60),
        screen_bow=0.0, back_bow=0.0, deck=(0.80, 0.76), tail_z=0.72,
        belt=[(0.0, 0.32), (0.30, 0.55), (1.0, 0.70)],
        plan=[(0.0, 0.84), (0.14, 0.95), (0.5, 0.97), (0.8, 1.0),
              (1.0, 0.94)],
        nose_round=140.0, nose_kx=0.80, nose_kz=0.60, tail_round=110.0,
        tail_kx=0.88, tail_kz=0.88, roof_crown=25.0,
        tumble=34.0, fenders=(0.0, 10.0), glass_bow=4.0, crest_in=60.0,
        arch_cover=15.0, belt_over=0.0, hood_full=0.75,
        shoulder_drop=200.0, shoulder_sq=1.2,
        shoulder_in=[(0.0, 40.0), (0.45, 80.0), (0.8, 120.0), (1.0, 100.0)],
        tuck=60.0),
    "front": dict(
        nose_z=0.47, hood_bulge=0.015, cowl=(0.44, 0.66),
        roof=(0.56, 0.70), deck=(0.86, 0.72), tail_z=0.68,
        back_bow=0.03, belt=[(0.0, 0.47), (0.44, 0.64), (1.0, 0.68)],
        cabin_from=0.36, fo=0.42, chin_z=0.16, tail_chin_z=0.26,
        fenders=(25.0, 35.0), nose_round=160.0, nose_kx=0.80,
        nose_kz=0.70, tail_round=130.0, tail_kx=0.88, tail_kz=0.85,
        tuck=50.0, shoulder_sq=4.0),
    "longnose": dict(
        nose_z=0.44, hood_bulge=0.04, cowl=(0.50, 0.68),
        roof=(0.60, 0.70), deck=(0.88, 0.62), tail_z=0.56,
        back_bow=0.05, deck_bulge=0.02,
        belt=[(0.0, 0.44), (0.5, 0.66), (1.0, 0.58)],
        plan=[(0.0, 0.62), (0.14, 0.86), (0.5, 0.96), (0.80, 0.97),
              (1.0, 0.82)],
        cabin_from=0.40, fo=0.50, nose_round=280.0, nose_kx=0.55,
        nose_kz=0.55, tail_round=260.0, tail_kx=0.70, tail_kz=0.65,
        fenders=(45.0, 55.0), shoulder_sq=2.4, chin_z=0.16),
    "rear": dict(
        nose_z=0.38, hood_bulge=0.04, cowl=(0.30, 0.62),
        roof=(0.43, 0.58), roof_rise=0.015, deck=(0.94, 0.42),
        tail_z=0.38, back_bow=0.07, deck_bulge=0.0,
        belt=[(0.0, 0.40), (0.30, 0.60), (1.0, 0.50)],
        plan=[(0.0, 0.70), (0.14, 0.92), (0.5, 0.94), (0.80, 0.99),
              (1.0, 0.84)],
        fo=0.44, nose_round=260.0, nose_kx=0.55, nose_kz=0.55,
        tail_round=260.0, tail_kx=0.62, tail_kz=0.55, shoulder_sq=2.4,
        fenders=(70.0, 60.0), crest_in=130.0, tail_chin_z=0.22,
        cabin_to=0.97, roof_crown=45.0, tumble=24.0),
    "sedan": dict(
        nose_z=0.50, hood_bulge=0.0, cowl=(0.30, 0.66), lamp_view="front",
        roof=(0.44, 0.72), deck=(0.82, 0.72), tail_z=0.72, back_bow=0.0,
        belt=[(0.0, 0.50), (0.30, 0.64), (1.0, 0.72)],
        plan=[(0.0, 0.88), (0.12, 0.97), (0.5, 0.97), (0.85, 0.98),
              (1.0, 0.95)],
        nose_round=90.0, nose_kx=0.93, nose_kz=0.86, tail_round=80.0,
        tail_kx=0.95, tail_kz=0.90, shoulder_sq=6.0, fo=0.40,
        fenders=(10.0, 10.0), roof_crown=25.0, tumble=14.0,
        chin_z=0.17, tail_chin_z=0.24, cabin_from=0.26, tuck=35.0,
        corner_r=45.0, shoulder_drop=70.0, shoulder_in=30.0, crest_in=60.0,
        glass_bow=6.0, screen_bow=0.01),
}

#: per car: what differs from its family
CARS = {
    # ---------------------------------------------------------- Porsche
    "porsche_356_speedster": dict(
        nose_z=0.38, cowl=(0.42, 0.64), deck=(0.66, 0.64), tail_z=0.40,
        line=[(0.16, 0.55), (0.86, 0.55)],
        belt=[(0.0, 0.40), (0.2, 0.58), (0.42, 0.64), (0.66, 0.65),
              (0.85, 0.58), (1.0, 0.40)],
        plan=[(0.0, 0.52), (0.12, 0.86), (0.3, 0.96), (0.6, 0.98),
              (0.85, 0.92), (1.0, 0.60)],
        fenders=(40.0, 30.0), wing_reach=520.0, cockpit_to=0.64,
        screen_h=290.0, screen_rake=42.0, nose_round=320.0,
        tail_round=320.0, nose_kx=0.5, tail_kx=0.55, lamp_u=0.62,
        lamp_v=0.86, bumpers="chrome", bumper_v=(0.24, 0.28),
        indicator_v=0.52, grille="none", lower_intake=0.0, plate_v=0.42,
        tails="round", tail_v=0.66, tail_u=0.58, diffuser=0.0,
        exhausts=(0.35,), exhaust_v=0.22),
    "porsche_911_rs": dict(
        nose_z=0.44, hood_bulge=0.03, cowl=(0.36, 0.66), roof=(0.47, 0.53),
        roof_rise=0.015, deck=(0.84, 0.66), back_bow=0.05, tail_z=0.55,
        deck_bulge=0.01,
        belt=[(0.0, 0.46), (0.36, 0.61), (0.75, 0.62), (1.0, 0.54)],
        fenders=(60.0, 70.0),
        plan=[(0.0, 0.72), (0.14, 0.90), (0.36, 0.92), (0.7, 0.98),
              (0.9, 0.97), (1.0, 0.84)],
        b_pillar=0.575, quarter=0.74, lamp_u=0.60, lamp_v=0.84,
        grille="none", intakes=[(0.55, 0.22, 0.22, 0.10)],
        lower_intake=0.0, plate_v=0.30, tails="slim", tail_v=0.70,
        tail_u=0.66, diffuser=0.0, exhausts=(-0.55,), exhaust_v=0.18),
    "porsche_930_turbo": dict(
        nose_z=0.44, hood_bulge=0.03, cowl=(0.36, 0.66), roof=(0.47, 0.53),
        roof_rise=0.015, deck=(0.84, 0.66), back_bow=0.05, tail_z=0.56,
        belt=[(0.0, 0.46), (0.36, 0.61), (0.75, 0.62), (1.0, 0.56)],
        fenders=(60.0, 110.0), wing_reach=520.0,
        plan=[(0.0, 0.70), (0.14, 0.86), (0.36, 0.87), (0.62, 0.96),
              (0.8, 1.0), (1.0, 0.92)],
        b_pillar=0.575, quarter=0.74, lamp_u=0.58, lamp_v=0.84,
        grille="none", intakes=[(0.55, 0.22, 0.22, 0.10)],
        lower_intake=0.0, plate_v=0.30, tails="bar", tail_u=0.98,
        tail_v=0.70, diffuser=0.0, exhausts=(-0.55,), exhaust_v=0.18),
    "porsche_959": dict(
        nose_z=0.38, hood_bulge=0.03, cowl=(0.35, 0.64), roof=(0.47, 0.53),
        deck=(0.86, 0.72), back_bow=0.03, tail_z=0.70,
        belt=[(0.0, 0.40), (0.35, 0.60), (0.8, 0.66), (1.0, 0.66)],
        fenders=(55.0, 85.0), lights="round", lamp_scale=0.8, lamp_u=0.6,
        lamp_v=0.80, grille="intake", grille_v=0.26, grille_w=1.0,
        lower_intake=0.0, plate_v=None, tails="bar", tail_u=0.98,
        side_intake="scoop", b_pillar=0.575, quarter=0.76),
    "porsche_carrera_gt": dict(
        nose_z=0.30, hood_bulge=0.02, cowl=(0.34, 0.58), roof=(0.45, 0.54),
        deck=(0.72, 0.76), back_bow=0.01, tail_z=0.76,
        belt=[(0.0, 0.32), (0.34, 0.56), (0.7, 0.72), (1.0, 0.74)],
        fenders=(41.0, 47.0), rear_glass=False, engine_cover=True,
        engine_cover_to=0.90, canopy=0.25, lamp_u=0.66, lamp_v=0.80,
        lamp_scale=0.8, lamp_slant=-0.02, grille="intake", grille_v=0.30,
        grille_w=0.55, intakes=[(0.62, 0.32, 0.36, 0.30)],
        lower_intake=0.0, plate_v=None, side_intake="scoop", tails="slim",
        tail_v=0.70, wing="lip", exhausts=(0.12, -0.12), exhaust_v=0.40),
    "porsche_918": dict(
        nose_z=0.30, hood_bulge=0.02, cowl=(0.33, 0.58), roof=(0.44, 0.54),
        deck=(0.80, 0.76), back_bow=0.04, tail_z=0.75,
        belt=[(0.0, 0.32), (0.33, 0.56), (0.7, 0.72), (1.0, 0.74)],
        fenders=(44.0, 47.0), lamp_u=0.66, lamp_v=0.80, lamp_scale=0.8,
        grille="intake", grille_v=0.30, grille_w=0.55,
        intakes=[(0.62, 0.32, 0.36, 0.30)], lower_intake=0.0,
        plate_v=None, side_intake="scoop", tails="bar", tail_u=0.98,
        tail_scale=0.5, tail_v=0.76, wing="lip", exhausts=()),
    # -------------------------------------------------------------- BMW
    "bmw_507": dict(
        nose_z=0.46, cowl=(0.52, 0.64), deck=(0.74, 0.64), tail_z=0.50,
        line=[(0.2, 0.60), (0.9, 0.58)],
        belt=[(0.0, 0.48), (0.5, 0.64), (0.75, 0.65), (1.0, 0.52)],
        fenders=(40.0, 35.0), cockpit_to=0.74, screen_h=300.0,
        lights="round", lamp_u=0.72, lamp_v=0.70, grille="kidney",
        grille_v=0.48, bumpers="chrome", bumper_v=(0.22, 0.25),
        plate_v=None, lower_intake=0.0, tails="slim", tail_v=0.62,
        tail_scale=0.6, diffuser=0.0, rear_plate_v=0.48),
    "bmw_m1": dict(
        nose_z=0.30, cowl=(0.33, 0.56), roof=(0.47, 0.60), deck=(0.82, 0.70),
        back_bow=0.0, tail_z=0.68,
        belt=[(0.0, 0.32), (0.33, 0.53), (1.0, 0.64)],
        rear_glass=False, engine_cover=True, engine_cover_to=0.84,
        lights="popup", lamp_u=0.66, lamp_v=0.52, grille="kidney",
        grille_v=0.45, plate_v=0.18, lower_intake=0.0, tails="slim",
        tail_v=0.66, diffuser=0.0, fenders=(10.0, 15.0)),
    "bmw_m3_e30": dict(
        nose_z=0.50, cowl=(0.33, 0.65), roof=(0.45, 0.70), deck=(0.80, 0.72),
        tail_z=0.74, back_bow=0.0,
        belt=[(0.0, 0.50), (0.33, 0.63), (1.0, 0.70)],
        fenders=(25.0, 35.0), b_pillar=0.585, quarter=0.745,
        lamp_u=0.70, lamp_v=0.64, grille_v=0.62, plate_v=0.30,
        lower_intake=0.9, indicator_v=0.30, tail_v=0.66, tail_u=0.64,
        diffuser=0.0, wing="lip", exhausts=(-0.5,), exhaust_v=0.12),
    "bmw_i8": dict(
        nose_z=0.33, cowl=(0.30, 0.58), roof=(0.45, 0.58), deck=(0.82, 0.72),
        back_bow=0.02, tail_z=0.70, lamp_v=0.74, grille_v=0.50,
        plate_v=0.24, intakes=[(0.70, 0.30, 0.22, 0.22)], tail_v=0.70,
        black_pillars=True, fenders=(40.0, 50.0), exhausts=()),
    "bmw_m8": dict(
        nose_z=0.52, cowl=(0.42, 0.66), roof=(0.53, 0.66), deck=(0.88, 0.74),
        back_bow=0.05, tail_z=0.72,
        belt=[(0.0, 0.52), (0.42, 0.66), (1.0, 0.72)],
        lamp_v=0.72, lamp_u=0.70, grille_v=0.50,
        intakes=[(0.74, 0.28, 0.24, 0.22)], lower_intake=0.7,
        plate_v=0.22, tail_v=0.70, exhausts=(0.6, 0.48, -0.48, -0.6),
        exhaust_r=34.0),
    # --------------------------------------------------------- Mercedes
    "mercedes_300sl": dict(
        nose_z=0.44, hood_bulge=0.04, cowl=(0.52, 0.66), roof=(0.60, 0.70),
        deck=(0.82, 0.60), back_bow=0.06, tail_z=0.48, deck_bulge=0.02,
        belt=[(0.0, 0.46), (0.52, 0.64), (0.8, 0.62), (1.0, 0.50)],
        fenders=(55.0, 40.0), lights="round", lamp_u=0.68, lamp_v=0.68,
        grille="oval", grille_v=0.40, grille_w=0.95, bumpers="chrome",
        bumper_v=(0.18, 0.22), plate_v=None, lower_intake=0.0,
        quarter=0.75, tails="vertical", tail_u=0.80, tail_v=0.60,
        diffuser=0.0, rear_plate_v=0.45),
    "mercedes_190e_evo2": dict(
        nose_z=0.54, cowl=(0.33, 0.68), roof=(0.46, 0.72), deck=(0.80, 0.74),
        tail_z=0.76, b_pillar=0.58, quarter=0.75, lights="slim",
        lamp_u=0.68, lamp_v=0.66, lamp_slant=0.0, grille="star",
        grille_v=0.66, grille_w=0.55, plate_v=0.30, wing="wing",
        wing_h=170.0, fenders=(40.0, 50.0), tail_v=0.70, diffuser=0.0),
    "mercedes_sls": dict(
        nose_z=0.48, cowl=(0.50, 0.66), roof=(0.58, 0.66), deck=(0.88, 0.66),
        back_bow=0.05, tail_z=0.62, lamp_v=0.74, lamp_u=0.70,
        grille="star", grille_v=0.48, grille_w=1.0,
        intakes=[(0.74, 0.26, 0.22, 0.22)], plate_v=0.20, tail_v=0.72),
    "mercedes_amg_gt": dict(
        nose_z=0.46, cowl=(0.50, 0.66), roof=(0.58, 0.64), deck=(0.92, 0.66),
        back_bow=0.06, tail_z=0.62, lamp_v=0.74, lamp_u=0.70,
        grille="star", grille_v=0.48, grille_w=0.80,
        intakes=[(0.74, 0.26, 0.22, 0.22)], plate_v=0.18, tail_v=0.70),
    "mercedes_amg_one": dict(
        nose_z=0.32, cowl=(0.31, 0.58), roof=(0.44, 0.56), deck=(0.84, 0.74),
        tail_z=0.72, fenders=(44.0, 44.0), lamp_v=0.78, grille="star",
        grille_v=0.40, grille_w=0.45, intakes=[(0.66, 0.28, 0.30, 0.30)],
        plate_v=None, side_intake="scoop", wing_h=250.0, tails="bar",
        tail_u=0.95, tail_scale=0.6),
    # ---------------------------------------------------------- Ferrari
    "ferrari_testarossa": dict(
        nose_z=0.30, cowl=(0.33, 0.56), roof=(0.46, 0.58), deck=(0.70, 0.80),
        back_bow=-0.02, tail_z=0.80,
        belt=[(0.0, 0.32), (0.33, 0.54), (0.6, 0.72), (1.0, 0.76)],
        engine_cover=True, engine_cover_to=0.94, rear_glass=False,
        side_intake="strakes", popup_s=0.08, lamp_v=0.48,
        grille="intake", grille_v=0.26, grille_w=1.4, lower_intake=0.0,
        plate_v=None, tails="bar", tail_u=0.98, tail_scale=1.6,
        tail_v=0.66, exhausts=(0.30, 0.22, -0.22, -0.30)),
    "ferrari_f40": dict(
        nose_z=0.28, cowl=(0.33, 0.55), roof=(0.46, 0.58), deck=(0.80, 0.84),
        back_bow=-0.03, tail_z=0.84, hood_bulge=0.0,
        belt=[(0.0, 0.30), (0.33, 0.53), (0.66, 0.72), (1.0, 0.80)],
        fenders=(30.0, 40.0), rear_glass=False, engine_cover=True,
        engine_cover_to=0.80, side_intake="naca", popup_s=0.08,
        lamp_v=0.46, grille="intake", grille_v=0.22, grille_w=1.0,
        lower_intake=0.0, plate_v=None, tails="round", tail_v=0.60,
        tail_u=0.78, wing_h=40.0, wing_chord=360.0,
        exhausts=(0.12, 0.0, -0.12), exhaust_v=0.30),
    "ferrari_enzo": dict(
        nose_z=0.28, cowl=(0.32, 0.56), roof=(0.46, 0.56), deck=(0.82, 0.76),
        back_bow=0.02, tail_z=0.74, fenders=(47.0, 38.0), lamp_v=0.78,
        lamp_slant=0.08, grille="intake", grille_v=0.20, grille_w=0.4,
        intakes=[(0.55, 0.22, 0.34, 0.24)], lower_intake=0.0, plate_v=None,
        side_intake="scoop", tails="round", tail_v=0.70, tail_u=0.80,
        exhausts=(0.16, -0.16), exhaust_v=0.35),
    "ferrari_laferrari": dict(
        nose_z=0.28, cowl=(0.32, 0.55), roof=(0.45, 0.56), deck=(0.84, 0.76),
        back_bow=0.03, tail_z=0.74, fenders=(50.0, 41.0), lamp_v=0.78,
        lamp_slant=0.08, grille="intake", grille_v=0.22, grille_w=0.5,
        intakes=[(0.6, 0.24, 0.30, 0.24)], lower_intake=0.0, plate_v=None,
        side_intake="scoop", tails="round", tail_v=0.72, tail_u=0.82,
        exhausts=(0.0,), exhaust_v=0.40, exhaust_r=50.0),
    # ------------------------------------------------------ Lamborghini
    "lamborghini_miura": dict(
        nose_z=0.36, hood_bulge=0.03, cowl=(0.36, 0.60), roof=(0.47, 0.56),
        deck=(0.86, 0.70), back_bow=0.04, tail_z=0.66, fenders=(55.0, 60.0),
        rear_glass=False, engine_cover=True, engine_cover_to=0.86,
        lamp_u=0.62, lamp_v=0.82, grille="intake", grille_v=0.25,
        grille_w=1.1, lower_intake=0.0, plate_v=None, side_intake="naca",
        tails="slim", tail_v=0.62, bumpers="chrome", bumper_v=(0.12, 0.2)),
    "lamborghini_countach": dict(
        nose_z=0.24, hood_bulge=0.0, cowl=(0.33, 0.58), roof=(0.45, 0.60),
        deck=(0.72, 0.80), back_bow=0.0, tail_z=0.76,
        belt=[(0.0, 0.26), (0.30, 0.50), (0.6, 0.66), (1.0, 0.70)],
        side_intake="naca", popup_s=0.10,
        lamp_v=0.50, grille="intake", grille_v=0.30, grille_w=0.7,
        lower_intake=0.0, plate_v=None, tails="slim", tail_v=0.68,
        engine_cover=True, engine_cover_to=0.94, rear_glass=True),
    "lamborghini_diablo": dict(
        nose_z=0.28, cowl=(0.31, 0.55), roof=(0.45, 0.58), deck=(0.82, 0.76),
        back_bow=-0.01, tail_z=0.72, side_intake="scoop", popup_s=0.08,
        lamp_v=0.55, grille="intake", grille_v=0.26, grille_w=1.0,
        lower_intake=0.0, plate_v=None, tails="slim", tail_v=0.70),
    "lamborghini_aventador": dict(
        nose_z=0.30, cowl=(0.30, 0.55), roof=(0.44, 0.58), deck=(0.84, 0.76),
        back_bow=0.0, tail_z=0.72, lamp_v=0.76, lamp_slant=0.10,
        grille="intake", grille_v=0.22, grille_w=0.5,
        intakes=[(0.62, 0.24, 0.34, 0.30)], lower_intake=0.0, plate_v=None,
        side_intake="scoop", engine_cover=True, engine_cover_to=0.84,
        rear_glass=True, tails="slim", tail_v=0.70),
    "lamborghini_huracan": dict(
        nose_z=0.30, cowl=(0.31, 0.56), roof=(0.45, 0.58), deck=(0.84, 0.74),
        back_bow=0.0, tail_z=0.70, lamp_v=0.76, lamp_slant=0.10,
        grille="intake", grille_v=0.22, grille_w=0.5,
        intakes=[(0.62, 0.24, 0.34, 0.30)], lower_intake=0.0, plate_v=None,
        side_intake="scoop", tails="slim", tail_v=0.70),
    # ---------------------------------------- McLaren, Bugatti, Pagani...
    "mclaren_f1": dict(
        nose_z=0.33, cowl=(0.32, 0.58), roof=(0.45, 0.58), deck=(0.84, 0.76),
        tail_z=0.74, canopy=0.25, lamp_v=0.74, lamp_scale=0.7,
        grille="intake", grille_v=0.26, grille_w=0.8, lower_intake=0.0,
        plate_v=None, side_intake="scoop", tails="round", tail_v=0.64),
    "mclaren_p1": dict(
        nose_z=0.30, cowl=(0.31, 0.56), roof=(0.45, 0.58), deck=(0.86, 0.80),
        tail_z=0.78, canopy=0.25, fenders=(38.0, 33.0), lamp_v=0.78,
        lamp_slant=-0.06, grille="intake", grille_v=0.24, grille_w=0.6,
        intakes=[(0.66, 0.26, 0.30, 0.30)], lower_intake=0.0, plate_v=None,
        side_intake="scoop", tails="bar", tail_u=0.98, tail_scale=0.5,
        tail_v=0.82, wing_h=180.0, exhausts=(0.0,), exhaust_v=0.55,
        exhaust_r=55.0),
    "mclaren_720s": dict(
        nose_z=0.30, cowl=(0.31, 0.56), roof=(0.45, 0.60), deck=(0.88, 0.78),
        back_bow=0.04, tail_z=0.76, canopy=0.25, lamp_v=0.74,
        lamp_scale=0.9, intakes=[(0.62, 0.62, 0.20, 0.20)],
        grille="intake", grille_v=0.22, grille_w=0.6, lower_intake=0.0,
        plate_v=None, side_intake="scoop", tails="slim", tail_v=0.74,
        exhausts=(0.2, -0.2), exhaust_v=0.40),
    "bugatti_veyron": dict(
        nose_z=0.38, hood_bulge=0.03, cowl=(0.32, 0.60), roof=(0.46, 0.56),
        deck=(0.80, 0.78), back_bow=0.0, tail_z=0.76, fenders=(38.0, 38.0),
        lamp_v=0.72, lamp_u=0.66, grille_v=0.50, intakes=[
            (0.62, 0.25, 0.30, 0.26)], lower_intake=0.0, plate_v=None,
        side_intake="scoop", engine_cover=True, engine_cover_to=0.92,
        rear_glass=False, tails="bar", tail_u=0.95, tail_scale=0.5,
        tail_v=0.70, exhausts=(0.0,), exhaust_v=0.30, exhaust_r=60.0),
    "bugatti_chiron": dict(
        nose_z=0.38, hood_bulge=0.03, cowl=(0.32, 0.60), roof=(0.46, 0.56),
        deck=(0.82, 0.76), back_bow=0.0, tail_z=0.74, fenders=(38.0, 38.0),
        lamp_v=0.70, lamp_u=0.62, grille_v=0.50, intakes=[
            (0.64, 0.25, 0.30, 0.26)], lower_intake=0.0, plate_v=None,
        side_intake="scoop", tails="bar", tail_u=0.98, tail_scale=0.4,
        tail_v=0.74, exhausts=(0.12, 0.04, -0.04, -0.12), exhaust_v=0.20),
    "pagani_zonda": dict(
        nose_z=0.32, cowl=(0.30, 0.56), roof=(0.44, 0.58), deck=(0.80, 0.74),
        tail_z=0.72, canopy=0.35, lights="twin", lamp_v=0.74, lamp_u=0.68,
        grille="intake", grille_v=0.24, grille_w=0.9, lower_intake=0.0,
        plate_v=None, side_intake="scoop", tails="round", tail_v=0.64,
        exhausts=(0.05, -0.05, 0.05, -0.05), exhaust_v=0.40),
    "pagani_huayra": dict(
        nose_z=0.34, cowl=(0.30, 0.57), roof=(0.44, 0.58), deck=(0.82, 0.74),
        tail_z=0.72, canopy=0.35, lights="twin", lamp_v=0.74, lamp_u=0.66,
        grille="intake", grille_v=0.24, grille_w=0.8, lower_intake=0.0,
        plate_v=None, side_intake="scoop", tails="round", tail_v=0.66,
        exhausts=(0.06, -0.06), exhaust_v=0.42),
    "koenigsegg_agera": dict(
        nose_z=0.32, cowl=(0.31, 0.57), roof=(0.44, 0.58), deck=(0.84, 0.76),
        tail_z=0.74, canopy=0.2, lamp_v=0.74, grille="intake",
        grille_v=0.24, grille_w=0.9, lower_intake=0.0, plate_v=None,
        side_intake="scoop", tails="round", tail_v=0.66, wing_h=200.0),
    "ford_gt40": dict(
        nose_z=0.38, hood_bulge=0.04, cowl=(0.37, 0.66), roof=(0.48, 0.60),
        deck=(0.80, 0.80), back_bow=0.0, tail_z=0.78, fenders=(33.0, 38.0),
        tail_kx=0.95, tail_kz=0.92, tail_round=60.0, lights="round",
        lamp_u=0.66, lamp_v=0.78, grille="oval", grille_v=0.30,
        grille_w=0.55, lower_intake=0.0, plate_v=None, tails="round",
        tail_v=0.66, side_intake="scoop", exhausts=(0.4, -0.4),
        exhaust_v=0.30),
    "ford_gt": dict(
        nose_z=0.32, cowl=(0.30, 0.56), roof=(0.44, 0.58), deck=(0.82, 0.76),
        tail_z=0.74, fenders=(38.0, 41.0), canopy=0.3, lamp_v=0.78,
        lamp_slant=0.08, grille="intake", grille_v=0.30, grille_w=0.8,
        lower_intake=0.0, plate_v=None, side_intake="scoop",
        tails="round", tail_v=0.66, exhausts=(0.0,), exhaust_v=0.40,
        exhaust_r=48.0),
    "jaguar_etype": dict(
        nose_z=0.40, hood_bulge=0.05, cowl=(0.53, 0.66), roof=(0.61, 0.70),
        deck=(0.88, 0.62), back_bow=0.05, tail_z=0.50, fenders=(50.0, 45.0),
        lights="round", lamp_u=0.66, lamp_v=0.66, grille="oval",
        grille_v=0.36, grille_w=0.45, lower_intake=0.0, plate_v=None,
        bumpers="chrome", bumper_v=(0.36, 0.26), quarter=0.80,
        tails="slim", tail_v=0.52, tail_scale=0.5, tail_u=0.74,
        diffuser=0.0, rear_plate_v=0.40, exhausts=(0.06, -0.06),
        exhaust_v=0.12, exhaust_r=28.0),
    "aston_db5": dict(
        nose_z=0.50, cowl=(0.46, 0.68), roof=(0.56, 0.72), deck=(0.82, 0.70),
        back_bow=0.03, tail_z=0.64, lights="round", lamp_u=0.68,
        lamp_v=0.66, grille="aston", grille_v=0.42, lower_intake=0.0,
        plate_v=None, bumpers="chrome", bumper_v=(0.22, 0.22),
        b_pillar=0.64, quarter=0.74, tails="round", tail_v=0.60,
        diffuser=0.0, rear_plate_v=0.40, exhausts=(0.4,), exhaust_v=0.12,
        exhaust_r=30.0),
    "audi_r8": dict(
        nose_z=0.34, cowl=(0.32, 0.58), roof=(0.46, 0.60), deck=(0.84, 0.76),
        tail_z=0.76, lamp_v=0.76, grille="audi", grille_v=0.40,
        intakes=[(0.70, 0.28, 0.24, 0.24)], lower_intake=0.0, plate_v=0.30,
        side_intake="scoop", tails="slim", tail_v=0.72,
        exhausts=(0.6, -0.6), exhaust_v=0.18),
    "corvette_c8": dict(
        nose_z=0.32, cowl=(0.31, 0.57), roof=(0.45, 0.60), deck=(0.86, 0.80),
        tail_z=0.78, lamp_v=0.76, lamp_slant=0.08, grille="intake",
        grille_v=0.26, grille_w=0.7, intakes=[(0.66, 0.26, 0.26, 0.26)],
        lower_intake=0.0, plate_v=None, side_intake="scoop", tails="slim",
        tail_v=0.70, exhausts=(0.3, 0.2, -0.2, -0.3), exhaust_v=0.18),
    "nissan_gtr": dict(
        nose_z=0.54, cowl=(0.32, 0.66), roof=(0.46, 0.72), deck=(0.84, 0.76),
        back_bow=0.04, tail_z=0.76, b_pillar=0.585, quarter=0.76,
        lamp_v=0.70, lamp_u=0.70, grille="intake", grille_v=0.42,
        grille_w=0.80, lower_intake=0.0, plate_v=0.32, tails="round",
        tail_v=0.70, tail_u=0.70, wing_h=60.0,
        exhausts=(0.7, 0.6, -0.6, -0.7), exhaust_r=40.0),
}


def design(key: str, spec: dict) -> dict:
    out = dict(BASE)
    out.update(FAMILIES.get(spec.get("shape", "mid"), {}))
    if spec.get("open"):
        out["open"] = True
    out.update(CARS.get(key, {}))
    return out
