"""The Car Builder's catalogue (Qt-free): classic and modern sports and
super cars from their PUBLISHED figures — length, width, height,
wheelbase and the factory tyre sizes front and rear — plus a body SHAPE
(`SHAPES`, the side profile as fractions of length and height) and the
details that make a make read (lights, grille, wing, factory wheels and
paint). `car_build` turns an entry into geometry.

Dimensions are the manufacturers' brochure figures as commonly quoted;
the shapes are hand-fitted proportions, not traced from drawings.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

#: side profile as fractions: body top z (of H) at the nose, the cowl
#: (windscreen base), the deck (cabin back) and the tail; stations (of
#: L from the nose) of the windscreen base, roof front, roof rear and
#: cabin back; plan width at nose and tail (of W); cabin width and
#: tumblehome; front overhang (of L - wheelbase); fender bulges
SHAPES = {
    "mid": dict(nose=0.40, cowl=0.58, deck=0.70, tail=0.68,
                ws=0.28, rf=0.43, rr=0.55, cb=0.78,
                nose_w=0.74, tail_w=0.90, cabin=0.74, tumble=0.76,
                fo=0.46, fenders=True),
    "wedge": dict(nose=0.34, cowl=0.55, deck=0.72, tail=0.74,
                  ws=0.25, rf=0.42, rr=0.55, cb=0.74,
                  nose_w=0.80, tail_w=0.96, cabin=0.72, tumble=0.78,
                  fo=0.45, fenders=False),
    "front": dict(nose=0.46, cowl=0.62, deck=0.68, tail=0.66,
                  ws=0.44, rf=0.57, rr=0.70, cb=0.85,
                  nose_w=0.80, tail_w=0.90, cabin=0.78, tumble=0.80,
                  fo=0.42, fenders=True),
    "longnose": dict(nose=0.46, cowl=0.68, deck=0.66, tail=0.58,
                     ws=0.48, rf=0.59, rr=0.72, cb=0.88,
                     nose_w=0.70, tail_w=0.82, cabin=0.80, tumble=0.80,
                     fo=0.48, fenders=True),
    "rear": dict(nose=0.42, cowl=0.60, deck=0.60, tail=0.56,
                 ws=0.29, rf=0.42, rr=0.58, cb=0.95,
                 nose_w=0.76, tail_w=0.86, cabin=0.76, tumble=0.78,
                 fo=0.44, fenders=True),
    "sedan": dict(nose=0.52, cowl=0.66, deck=0.72, tail=0.72,
                  ws=0.30, rf=0.43, rr=0.72, cb=0.82,
                  nose_w=0.90, tail_w=0.95, cabin=0.86, tumble=0.86,
                  fo=0.40, fenders=False),
}

PAINTS = {
    "Rosso Corsa": "#bd1a1f", "Guards red": "#c8102e",
    "Giallo": "#f1c21b", "Arancio": "#ea6a14", "Verde Mantis": "#5bb02c",
    "British racing green": "#1f4a2f", "Estoril blue": "#1f4f9e",
    "Gulf blue": "#8cc4e6", "Silver": "#c3c7cc", "White": "#f1f1ec",
    "Black": "#18191c", "Grey": "#6d7278", "Cream": "#e8dfc6",
    "Midnight blue": "#1d2a4a",
}

#: key -> make, model, year, L, W, H, wheelbase, front tyre, rear tyre,
#: shape, lights, grille, tail lights, wing, rim, paint, (overrides)
_ROWS = [
    # Porsche
    ("porsche_356_speedster", "Porsche", "356 A Speedster", 1955,
     3950, 1660, 1220, 2100, "165/80 R15", "165/80 R15", "rear",
     "round", "none", "round", "none", "Steel with hubcap", "Silver",
     dict(open=True, nose=0.40, cowl=0.55, deck=0.58, tail=0.50,
          ws=0.40, rf=0.43, rr=0.45, cb=0.46)),
    ("porsche_911_rs", "Porsche", "911 Carrera RS 2.7", 1973,
     4102, 1652, 1320, 2271, "185/70 R15", "215/60 R15", "rear",
     "round", "none", "slim", "ducktail", "Fuchs", "White", {}),
    ("porsche_930_turbo", "Porsche", "911 Turbo (930)", 1978,
     4291, 1775, 1320, 2272, "205/55 R16", "225/50 R16", "rear",
     "round", "none", "bar", "whale", "Fuchs", "Guards red", {}),
    ("porsche_959", "Porsche", "959", 1986,
     4260, 1840, 1280, 2300, "235/45 R17", "255/40 R17", "rear",
     "round", "intake", "bar", "hoop", "Monoblock", "Silver", {}),
    ("porsche_carrera_gt", "Porsche", "Carrera GT", 2004,
     4613, 1921, 1166, 2730, "265/35 R19", "335/30 R20", "mid",
     "slim", "intake", "slim", "none", "Centre lock", "Silver", {}),
    ("porsche_918", "Porsche", "918 Spyder", 2013,
     4643, 1940, 1167, 2730, "265/35 R20", "325/30 R21", "mid",
     "slim", "intake", "bar", "wing", "Centre lock", "Silver", {}),
    # BMW
    ("bmw_507", "BMW", "507 Roadster", 1956,
     4380, 1650, 1250, 2480, "185/80 R16", "185/80 R16", "longnose",
     "round", "kidney", "slim", "none", "Steel with hubcap", "White",
     dict(open=True, rf=0.53, rr=0.55, cb=0.56)),
    ("bmw_m1", "BMW", "M1", 1978,
     4361, 1824, 1140, 2560, "205/55 R16", "225/50 R16", "wedge",
     "popup", "kidney", "slim", "none", "Turbine", "White", {}),
    ("bmw_m3_e30", "BMW", "M3 (E30)", 1986,
     4345, 1680, 1370, 2562, "205/55 R15", "205/55 R15", "sedan",
     "twin", "kidney", "slim", "lip", "Mesh (BBS)", "Estoril blue", {}),
    ("bmw_i8", "BMW", "i8", 2014,
     4689, 1942, 1293, 2800, "195/50 R20", "215/45 R20", "mid",
     "slim", "kidney", "slim", "none", "Y spoke", "White",
     dict(ws=0.30, rr=0.60, cb=0.85)),
    ("bmw_m8", "BMW", "M8 Competition Coupé", 2019,
     4867, 1907, 1362, 2827, "275/35 R20", "285/35 R20", "front",
     "slim", "kidney", "slim", "lip", "Y spoke", "Black", {}),
    # Mercedes
    ("mercedes_300sl", "Mercedes-Benz", "300 SL Gullwing", 1954,
     4520, 1790, 1300, 2400, "185/80 R15", "185/80 R15", "longnose",
     "round", "star", "round", "none", "Steel with hubcap", "Silver", {}),
    ("mercedes_190e_evo2", "Mercedes-Benz", "190 E 2.5-16 Evo II", 1990,
     4487, 1706, 1361, 2665, "245/40 R17", "245/40 R17", "sedan",
     "slim", "star", "slim", "wing", "Five spoke", "Midnight blue", {}),
    ("mercedes_sls", "Mercedes-Benz", "SLS AMG", 2010,
     4638, 1939, 1262, 2680, "265/35 R19", "295/30 R20", "longnose",
     "slim", "star", "slim", "none", "Ten spoke", "Silver", {}),
    ("mercedes_amg_gt", "Mercedes-Benz", "AMG GT", 2015,
     4546, 1939, 1288, 2630, "265/35 R19", "295/30 R20", "longnose",
     "slim", "star", "slim", "lip", "Ten spoke", "Grey", {}),
    ("mercedes_amg_one", "Mercedes-Benz", "AMG ONE", 2022,
     4756, 2010, 1261, 2720, "285/35 R19", "335/30 R20", "mid",
     "slim", "star", "slim", "wing", "Centre lock", "Silver", {}),
    # Ferrari
    ("ferrari_testarossa", "Ferrari", "Testarossa", 1984,
     4485, 1976, 1130, 2550, "225/50 R16", "255/50 R16", "wedge",
     "popup", "intake", "bar", "none", "Five spoke", "Rosso Corsa", {}),
    ("ferrari_f40", "Ferrari", "F40", 1987,
     4358, 1970, 1124, 2450, "245/40 R17", "335/35 R17", "wedge",
     "slim", "intake", "round", "wing", "Five spoke", "Rosso Corsa",
     dict(rr=0.52, cb=0.80)),
    ("ferrari_enzo", "Ferrari", "Enzo", 2002,
     4702, 2035, 1147, 2650, "245/35 R19", "345/35 R19", "mid",
     "slim", "intake", "round", "lip", "Five spoke", "Rosso Corsa", {}),
    ("ferrari_laferrari", "Ferrari", "LaFerrari", 2013,
     4702, 1992, 1116, 2650, "265/30 R19", "345/30 R20", "mid",
     "slim", "intake", "round", "lip", "Y spoke", "Rosso Corsa", {}),
    # Lamborghini
    ("lamborghini_miura", "Lamborghini", "Miura P400", 1966,
     4360, 1780, 1050, 2500, "205/70 R15", "205/70 R15", "mid",
     "round", "intake", "slim", "none", "Turbine", "Arancio", {}),
    ("lamborghini_countach", "Lamborghini", "Countach LP400", 1974,
     4140, 1890, 1070, 2450, "205/70 R14", "215/70 R14", "wedge",
     "popup", "intake", "slim", "none", "Turbine", "Giallo", {}),
    ("lamborghini_diablo", "Lamborghini", "Diablo", 1990,
     4460, 2040, 1105, 2650, "245/40 R17", "335/35 R17", "wedge",
     "popup", "intake", "slim", "none", "Five spoke", "Verde Mantis", {}),
    ("lamborghini_aventador", "Lamborghini", "Aventador LP700-4", 2011,
     4780, 2030, 1136, 2700, "255/35 R19", "335/30 R20", "wedge",
     "slim", "intake", "slim", "none", "Y spoke", "Arancio", {}),
    ("lamborghini_huracan", "Lamborghini", "Huracán LP610-4", 2014,
     4459, 1924, 1165, 2620, "245/35 R20", "305/30 R20", "wedge",
     "slim", "intake", "slim", "none", "Y spoke", "Verde Mantis", {}),
    # McLaren, Bugatti, Pagani, Koenigsegg
    ("mclaren_f1", "McLaren", "F1", 1992,
     4287, 1820, 1140, 2718, "235/45 R17", "315/45 R17", "mid",
     "slim", "intake", "round", "none", "Five spoke", "Silver", {}),
    ("mclaren_p1", "McLaren", "P1", 2013,
     4588, 1946, 1188, 2670, "245/35 R19", "315/30 R20", "mid",
     "slim", "intake", "bar", "wing", "Ten spoke", "Arancio", {}),
    ("mclaren_720s", "McLaren", "720S", 2017,
     4543, 1930, 1196, 2670, "245/35 R19", "305/30 R20", "mid",
     "slim", "intake", "slim", "lip", "Ten spoke", "Arancio", {}),
    ("bugatti_veyron", "Bugatti", "Veyron 16.4", 2005,
     4462, 1998, 1204, 2710, "265/30 R20", "365/30 R21", "mid",
     "slim", "horseshoe", "bar", "lip", "Monoblock", "Midnight blue", {}),
    ("bugatti_chiron", "Bugatti", "Chiron", 2016,
     4544, 2038, 1212, 2711, "285/30 R20", "355/25 R21", "mid",
     "slim", "horseshoe", "bar", "lip", "Monoblock", "Estoril blue", {}),
    ("pagani_zonda", "Pagani", "Zonda C12 S", 2002,
     4395, 2055, 1151, 2730, "255/35 R18", "335/30 R19", "mid",
     "round", "intake", "round", "wing", "Centre lock", "Silver", {}),
    ("pagani_huayra", "Pagani", "Huayra", 2012,
     4605, 2036, 1169, 2795, "255/35 R20", "335/30 R21", "mid",
     "round", "intake", "round", "none", "Centre lock", "Silver", {}),
    ("koenigsegg_agera", "Koenigsegg", "Agera R", 2011,
     4293, 2050, 1120, 2662, "265/35 R19", "345/30 R20", "mid",
     "slim", "intake", "round", "wing", "Turbine", "White", {}),
    # Others
    ("ford_gt40", "Ford", "GT40 Mk I", 1964,
     4029, 1778, 1029, 2413, "185/65 R15", "225/60 R15", "mid",
     "round", "intake", "round", "lip", "Mesh (BBS)", "Gulf blue", {}),
    ("ford_gt", "Ford", "GT", 2017,
     4763, 2004, 1110, 2710, "245/35 R20", "325/30 R20", "mid",
     "slim", "intake", "round", "lip", "Y spoke", "Estoril blue", {}),
    ("jaguar_etype", "Jaguar", "E-Type Series 1", 1961,
     4453, 1657, 1219, 2438, "185/80 R15", "185/80 R15", "longnose",
     "round", "intake", "round", "none", "Mesh (BBS)",
     "British racing green", {}),
    ("aston_db5", "Aston Martin", "DB5", 1963,
     4570, 1680, 1340, 2490, "185/80 R15", "185/80 R15", "front",
     "round", "intake", "slim", "none", "Mesh (BBS)", "Silver", {}),
    ("audi_r8", "Audi", "R8 V10", 2015,
     4426, 1940, 1240, 2650, "245/30 R20", "305/30 R20", "mid",
     "slim", "intake", "slim", "none", "Y spoke", "Grey", {}),
    ("corvette_c8", "Chevrolet", "Corvette C8", 2020,
     4630, 1934, 1234, 2722, "245/35 R19", "305/30 R20", "mid",
     "slim", "intake", "slim", "lip", "Five spoke", "Arancio", {}),
    ("nissan_gtr", "Nissan", "GT-R (R35)", 2007,
     4710, 1895, 1370, 2780, "255/40 R20", "285/35 R20", "sedan",
     "slim", "intake", "round", "wing", "Ten spoke", "Grey",
     dict(rr=0.64, cb=0.84)),
]

CARS = {}
for (_key, _make, _model, _year, _L, _W, _H, _wb, _tf, _tr, _shape,
     _lights, _grille, _tails, _wing, _rim, _paint, _over) in _ROWS:
    CARS[_key] = dict(make=_make, model=_model, year=_year, L=_L, W=_W,
                      H=_H, wb=_wb, tyre_front=_tf, tyre_rear=_tr,
                      shape=_shape, lights=_lights, grille=_grille,
                      tails=_tails, wing=_wing, rim=_rim, paint=_paint,
                      **_over)


def label(key: str) -> str:
    car = CARS[key]
    return f"{car['make']} {car['model']} ({car['year']})"


def makes() -> dict:
    """make -> [keys], catalogue order."""
    out = {}
    for key, car in CARS.items():
        out.setdefault(car["make"], []).append(key)
    return out


def profile(key: str) -> dict:
    """The car's shape fractions: its SHAPE preset with its overrides."""
    car = CARS[key]
    out = dict(SHAPES[car["shape"]])
    out.update({k: v for k, v in car.items() if k in out or k == "open"})
    out.setdefault("open", False)
    return out
