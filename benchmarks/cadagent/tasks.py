"""The CAD-agent benchmark: design briefs, reference programs and checks.

Every task is a brief written the way an engineer would ask for a part,
an OpenSCAD reference that meets it (used to validate the checks and to
give the expected volume), and checks evaluated on the agent's result:

    ("box", lo, hi, tol)      world bounding box of everything visible
    ("solid", [x, y, z])      that point lies inside material
    ("empty", [x, y, z])      that point lies outside material
    ("volume", rel_tol)       total volume within rel_tol of the reference
    ("watertight",)           every part is a closed solid
    ("overhang", deg)         printable without supports at that angle
    ("min_wall", mm)          no wall thinner than mm
    ("parts", n)              at least n separate top-level parts
    ("clear",)                no two top-level parts intersect

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

FRAME = ("Units are millimetres. Unless stated otherwise, centre the part "
         "on the origin in x and y and stand it on z = 0.")

TASKS = [
    # ---------------------------------------------------------- tier 1
    dict(id="plate_hole", tier=1,
         brief="A flat plate 60 x 40 x 5 (x by y by z) with one 10 mm "
               "diameter hole through its centre.",
         ref="difference(){translate([-30,-20,0])cube([60,40,5]);"
             "translate([0,0,-1])cylinder(h=7,d=10,$fn=64);}",
         checks=[("box", [-30, -20, 0], [30, 20, 5], 0.5),
                 ("empty", [0, 0, 2.5]), ("solid", [20, 0, 2.5]),
                 ("solid", [0, 15, 2.5]), ("volume", 0.03)]),
    dict(id="l_bracket", tier=1,
         brief="An L-bracket. The base is a plate spanning x from -25 to "
               "25, y from 0 to 30 and z from 0 to 5. The upright spans "
               "the same x, y from 0 to 5 and z from 0 to 40. Drill two "
               "6 mm holes vertically through the base at (x, y) = "
               "(-15, 20) and (15, 20).",
         ref="difference(){union(){translate([-25,0,0])cube([50,30,5]);"
             "translate([-25,0,0])cube([50,5,40]);}"
             "for(x=[-15,15])translate([x,20,-1])cylinder(h=7,d=6,$fn=48);}",
         checks=[("box", [-25, 0, 0], [25, 30, 40], 0.5),
                 ("empty", [-15, 20, 2.5]), ("empty", [15, 20, 2.5]),
                 ("solid", [0, 20, 2.5]), ("solid", [0, 2.5, 30]),
                 ("empty", [0, 20, 20]), ("volume", 0.03)]),
    dict(id="tube", tier=1,
         brief="A tube 50 mm tall with outside diameter 30 and inside "
               "diameter 20, its axis along z.",
         ref="difference(){cylinder(h=50,d=30,$fn=96);"
             "translate([0,0,-1])cylinder(h=52,d=20,$fn=96);}",
         checks=[("box", [-15, -15, 0], [15, 15, 50], 0.5),
                 ("empty", [0, 0, 25]), ("solid", [12.5, 0, 25]),
                 ("solid", [0, -12.5, 5]), ("empty", [15.5, 0, 25]),
                 ("volume", 0.03)]),
    dict(id="counterbore", tier=1,
         brief="A block 40 x 40 x 20 with a counterbored hole for an M6 "
               "cap screw down its centre: a 6.5 mm through hole and an "
               "11 mm counterbore 6 mm deep from the top face.",
         ref="difference(){translate([-20,-20,0])cube([40,40,20]);"
             "translate([0,0,-1])cylinder(h=22,d=6.5,$fn=48);"
             "translate([0,0,14])cylinder(h=7,d=11,$fn=48);}",
         checks=[("box", [-20, -20, 0], [20, 20, 20], 0.5),
                 ("empty", [0, 0, 10]), ("empty", [4.5, 0, 17]),
                 ("solid", [4.5, 0, 5]), ("solid", [10, 0, 10]),
                 ("volume", 0.03)]),
    dict(id="stepped_shaft", tier=1,
         brief="A stepped shaft along z made of three coaxial cylinders: "
               "diameter 20 for the first 30 mm from z = 0, then diameter "
               "14 for 20 mm, then diameter 10 for the last 15 mm.",
         ref="cylinder(h=30,d=20,$fn=96);translate([0,0,30])"
             "cylinder(h=20,d=14,$fn=96);translate([0,0,50])"
             "cylinder(h=15,d=10,$fn=96);",
         checks=[("box", [-10, -10, 0], [10, 10, 65], 0.5),
                 ("solid", [9, 0, 15]), ("empty", [9, 0, 40]),
                 ("solid", [6, 0, 40]), ("empty", [6, 0, 58]),
                 ("solid", [4, 0, 58]), ("volume", 0.03)]),
    dict(id="hex_nut", tier=1,
         brief="An M8 hex nut: 13 mm across flats, 6.5 mm thick, with an "
               "8 mm plain bore. Put two of the flats parallel to the x "
               "axis.",
         ref="difference(){cylinder(h=6.5,r=13/sqrt(3),$fn=6);"
             "translate([0,0,-1])cylinder(h=8.5,d=8,$fn=48);}",
         checks=[("box", [-7.51, -6.5, 0], [7.51, 6.5, 6.5], 0.4),
                 ("empty", [0, 0, 3]), ("solid", [5, 0, 3]),
                 ("solid", [0, 5.5, 3]), ("empty", [0, 6.8, 3]),
                 ("volume", 0.03)]),
    dict(id="washer", tier=1,
         brief="An M10 flat washer: outside diameter 20, hole 10.5, "
               "thickness 2.",
         ref="difference(){cylinder(h=2,d=20,$fn=96);"
             "translate([0,0,-1])cylinder(h=4,d=10.5,$fn=96);}",
         checks=[("box", [-10, -10, 0], [10, 10, 2], 0.3),
                 ("empty", [0, 0, 1]), ("solid", [7.5, 0, 1]),
                 ("volume", 0.03)]),
    dict(id="mounting_plate", tier=1,
         brief="A mounting plate 80 x 60 x 6 with four 5 mm holes, one "
               "near each corner, at (x, y) = (+-32, +-22).",
         ref="difference(){translate([-40,-30,0])cube([80,60,6]);"
             "for(x=[-32,32],y=[-22,22])translate([x,y,-1])"
             "cylinder(h=8,d=5,$fn=48);}",
         checks=[("box", [-40, -30, 0], [40, 30, 6], 0.5),
                 ("empty", [32, 22, 3]), ("empty", [-32, 22, 3]),
                 ("empty", [32, -22, 3]), ("empty", [-32, -22, 3]),
                 ("solid", [0, 0, 3]), ("volume", 0.03)]),
    dict(id="slot_plate", tier=1,
         brief="A plate 70 x 30 x 4 with one slot through it, centred on "
               "the plate and running along x: 8 mm wide, its round ends' "
               "centres 20 mm apart.",
         ref="difference(){translate([-35,-15,0])cube([70,30,4]);"
             "hull()for(x=[-10,10])translate([x,0,-1])"
             "cylinder(h=6,d=8,$fn=48);}",
         checks=[("box", [-35, -15, 0], [35, 15, 4], 0.5),
                 ("empty", [0, 0, 2]), ("empty", [13, 0, 2]),
                 ("solid", [16, 0, 2]), ("solid", [0, 6, 2]),
                 ("volume", 0.03)]),
    dict(id="dome_shell", tier=1,
         brief="A hollow hemispherical dome: outer radius 25, wall 3 mm, "
               "open at the bottom, its flat rim on z = 0.",
         ref="difference(){sphere(r=25,$fn=96);sphere(r=22,$fn=96);"
             "translate([-30,-30,-30])cube([60,60,30]);}",
         checks=[("box", [-25, -25, 0], [25, 25, 25], 0.6),
                 ("empty", [0, 0, 10]), ("solid", [0, 0, 23.5]),
                 ("solid", [23.5, 0, 2]), ("volume", 0.04)]),
    # ---------------------------------------------------------- tier 2
    dict(id="open_box", tier=2,
         brief="An open-topped box to 3D print: outside 50 x 40 x 30, "
               "walls and floor 2 mm thick. It must be one closed solid.",
         ref="difference(){translate([-25,-20,0])cube([50,40,30]);"
             "translate([-23,-18,2])cube([46,36,30]);}",
         checks=[("box", [-25, -20, 0], [25, 20, 30], 0.5),
                 ("empty", [0, 0, 15]), ("solid", [24, 0, 15]),
                 ("solid", [0, 0, 1]), ("watertight",),
                 ("overhang", 46), ("volume", 0.03)]),
    dict(id="horizontal_hole", tier=2,
         brief="A block 40 x 20 x 20 with a horizontal 8 mm hole along y "
               "through its centre (axis at x = 0, z = 10). It will be "
               "printed standing as modelled, so it must print without "
               "supports: no downward face steeper than 45 degrees.",
         ref="difference(){translate([-20,-10,0])cube([40,20,20]);"
             "translate([0,0,10])rotate([90,0,0])linear_extrude(height=22,"
             "center=true)hull(){circle(d=8,$fn=48);translate([0,4*sqrt(2)])"
             "rotate(45)square(0.01,center=true);}}",
         checks=[("box", [-20, -10, 0], [20, 10, 20], 0.5),
                 ("empty", [0, 0, 10]), ("empty", [0, 5, 7]),
                 ("solid", [10, 0, 10]), ("overhang", 46),
                 ("watertight",)]),
    dict(id="shelf_bracket", tier=2,
         brief="A shelf bracket printed in this orientation without "
               "supports. A wall spans x 0..5, y -10..10, z 0..40. An arm "
               "on top spans x 0..30, the same y, z 35..40. Support the "
               "arm with a 45 degree gusset underneath so nothing "
               "overhangs more than 45 degrees.",
         ref="translate([0,-10,0])cube([5,20,40]);"
             "translate([0,-10,35])cube([30,20,5]);"
             "rotate([90,0,0])linear_extrude(height=20,center=true)"
             "polygon([[5,10],[5,35],[30,35]]);",
         checks=[("box", [0, -10, 0], [30, 10, 40], 0.5),
                 ("solid", [25, 0, 37]), ("solid", [2.5, 0, 5]),
                 ("solid", [15, 0, 28]), ("empty", [25, 0, 10]),
                 ("overhang", 46)]),
    dict(id="thin_cup", tier=2,
         brief="A cup to print: outside diameter 40, height 60, wall and "
               "floor 1.2 mm thick, open at the top. One closed solid.",
         ref="difference(){cylinder(h=60,d=40,$fn=96);"
             "translate([0,0,1.2])cylinder(h=60,d=37.6,$fn=96);}",
         checks=[("box", [-20, -20, 0], [20, 20, 60], 0.5),
                 ("empty", [0, 0, 30]), ("solid", [19.4, 0, 30]),
                 ("solid", [0, 0, 0.6]), ("watertight",),
                 ("min_wall", 0.8), ("volume", 0.05)]),
    dict(id="key_tag", tier=2,
         brief="A key tag 3 mm thick: a 50 x 20 plate whose two short ends "
               "are full semicircles (so 50 is the overall length, along "
               "x), with a 5 mm hole whose centre is 6 mm from the left "
               "end, on the centre line.",
         ref="difference(){hull()for(x=[-15,15])translate([x,0,0])"
             "cylinder(h=3,d=20,$fn=96);translate([-19,0,-1])"
             "cylinder(h=5,d=5,$fn=48);}",
         checks=[("box", [-25, -10, 0], [25, 10, 3], 0.4),
                 ("empty", [-19, 0, 1.5]), ("solid", [0, 0, 1.5]),
                 ("solid", [24, 0, 1.5]), ("empty", [24, 9, 1.5]),
                 ("watertight",), ("volume", 0.03)]),
    dict(id="chamfered_peg", tier=2,
         brief="A peg of diameter 10 and height 30 along z with a 1 mm "
               "x 45 degree chamfer on its bottom edge, so the first "
               "layer does not flare.",
         ref="cylinder(h=1,d1=8,d2=10,$fn=96);translate([0,0,1])"
             "cylinder(h=29,d=10,$fn=96);",
         checks=[("box", [-5, -5, 0], [5, 5, 30], 0.3),
                 ("empty", [4.7, 0, 0.2]), ("solid", [4.6, 0, 5]),
                 ("solid", [0, 0, 0.1]), ("overhang", 46)]),
    dict(id="hook", tier=2,
         brief="A wall hook printed flat on its back, 5 mm thick (z 0..5): "
               "a back plate x -10..10, y 0..60 with a 4 mm screw hole at "
               "(0, 50), and a hook arm along the bottom edge, y 0..8, "
               "that rises from the plate to z = 25 at y 0..8 (a block "
               "x -10..10, y 0..8, z 0..25).",
         ref="difference(){union(){translate([-10,0,0])cube([20,60,5]);"
             "translate([-10,0,0])cube([20,8,25]);}"
             "translate([0,50,-1])cylinder(h=7,d=4,$fn=48);}",
         checks=[("box", [-10, 0, 0], [10, 60, 25], 0.5),
                 ("empty", [0, 50, 2.5]), ("solid", [0, 30, 2.5]),
                 ("solid", [0, 4, 20]), ("empty", [0, 30, 20]),
                 ("overhang", 46), ("volume", 0.03)]),
    # ---------------------------------------------------------- tier 3
    dict(id="stack", tier=3,
         brief="Two separate parts: a base block 40 x 40 x 10 (z 0..10) "
               "and a smaller block 20 x 20 x 20 standing centred on top "
               "of it (z 10..30). Make each its own object.",
         ref="module Base(){translate([-20,-20,0])cube([40,40,10]);}"
             "module Top(){translate([-10,-10,10])cube([20,20,20]);}"
             "Base();Top();",
         checks=[("box", [-20, -20, 0], [20, 20, 30], 0.5),
                 ("parts", 2), ("solid", [15, 15, 5]),
                 ("solid", [0, 0, 25]), ("empty", [15, 15, 15])]),
    dict(id="shaft_housing", tier=3,
         brief="Two parts that must not touch: a housing block 40 x 40 x "
               "20 (z 0..20) with a 22 mm vertical bore through its "
               "centre, and a 20 mm shaft 40 long passing through the "
               "bore from z = -10 to z = 30.",
         ref="module Housing(){difference(){translate([-20,-20,0])"
             "cube([40,40,20]);translate([0,0,-1])"
             "cylinder(h=22,d=22,$fn=96);}}"
             "module Shaft(){translate([0,0,-10])cylinder(h=40,d=20,$fn=96);}"
             "Housing();Shaft();",
         checks=[("box", [-20, -20, -10], [20, 20, 30], 0.5),
                 ("parts", 2), ("clear",), ("solid", [0, 0, 25]),
                 ("solid", [15, 0, 10]), ("empty", [10.5, 0, 10])]),
    dict(id="flange_bolts", tier=3,
         brief="A bolted flange pair: two discs of diameter 80 and 10 mm "
               "thick, stacked (z 0..10 and 10..20), each with four 9 mm "
               "holes on a 60 mm pitch circle at 0, 90, 180 and 270 "
               "degrees. Put an 8 mm bolt (a plain cylinder, z -5..25) "
               "through each hole. Discs and bolts are separate parts "
               "and must not intersect.",
         ref="module Disc(){difference(){cylinder(h=10,d=80,$fn=96);"
             "for(a=[0:90:270])rotate(a)translate([30,0,-1])"
             "cylinder(h=12,d=9,$fn=48);}}"
             "module Bolts(){for(a=[0:90:270])rotate(a)translate([30,0,-5])"
             "cylinder(h=30,d=8,$fn=48);}"
             "Disc();translate([0,0,10])Disc();Bolts();",
         checks=[("box", [-40, -40, -5], [40, 40, 25], 0.5),
                 ("parts", 3), ("clear",), ("solid", [30, 0, 22]),
                 ("solid", [0, 30, -3]), ("solid", [20, 0, 15]),
                 ("empty", [34.3, 0, 5])]),
    dict(id="box_lid", tier=3,
         brief="A box and its lid as two parts. Box: outside 60 x 40 x 20 "
               "(z 0..20), open top, 2 mm walls and floor. Lid: a 60 x 40 "
               "x 3 plate on top (z 20..23) with a lip on its underside "
               "that fits inside the box with 0.2 mm clearance all round, "
               "3 mm deep (z 17..20) and 1.5 mm thick. Lid and box must "
               "not intersect.",
         ref="module Box(){difference(){translate([-30,-20,0])"
             "cube([60,40,20]);translate([-28,-18,2])cube([56,36,20]);}}"
             "module Lid(){translate([-30,-20,20])cube([60,40,3]);"
             "difference(){translate([-27.8,-17.8,17])cube([55.6,35.6,3]);"
             "translate([-26.3,-16.3,16])cube([52.6,32.6,5]);}}"
             "Box();Lid();",
         checks=[("box", [-30, -20, 0], [30, 20, 23], 0.5),
                 ("parts", 2), ("clear",), ("solid", [0, 0, 21.5]),
                 ("solid", [27, 0, 18.5]), ("empty", [0, 0, 10]),
                 ("solid", [29, 0, 10])]),
    dict(id="pins_plate", tier=3,
         brief="A plate 60 x 20 x 5 with three 6.4 mm holes at x = -20, 0 "
               "and 20 on its centre line, and three separate 6 mm pins, "
               "each 15 long (z 0..15), standing in the holes. The pins "
               "must not intersect the plate.",
         ref="module Plate(){difference(){translate([-30,-10,0])"
             "cube([60,20,5]);for(x=[-20,0,20])translate([x,0,-1])"
             "cylinder(h=7,d=6.4,$fn=48);}}"
             "module Pin(){cylinder(h=15,d=6,$fn=48);}"
             "Plate();for(x=[-20,0,20])translate([x,0,0])Pin();",
         checks=[("box", [-30, -10, 0], [30, 10, 15], 0.5),
                 ("parts", 4), ("clear",), ("solid", [20, 0, 12]),
                 ("solid", [-20, 0, 12]), ("solid", [10, 0, 2.5])]),
    dict(id="bolt_washers", tier=3,
         brief="A bolt with three washers as separate parts. Bolt: a head "
               "of diameter 13, z 0..5, and a shank of diameter 8, z "
               "5..45. Washers: outside diameter 16, hole 8.4, 2 mm "
               "thick, stacked on the shank from z = 5 (z 5..7, 7..9, "
               "9..11). Nothing may intersect.",
         ref="module Bolt(){cylinder(h=5,d=13,$fn=48);translate([0,0,5])"
             "cylinder(h=40,d=8,$fn=48);}"
             "module Washer(){difference(){cylinder(h=2,d=16,$fn=64);"
             "translate([0,0,-1])cylinder(h=4,d=8.4,$fn=64);}}"
             "Bolt();for(z=[5,7,9])translate([0,0,z])Washer();",
         checks=[("box", [-8, -8, 0], [8, 8, 45], 0.5),
                 ("parts", 2), ("clear",), ("solid", [7, 0, 8]),
                 ("solid", [0, 0, 40]), ("empty", [7, 0, 20])]),
    dict(id="table", tier=3,
         brief="A small table: a top 100 x 60 x 5 at z 70..75 and four "
               "5 x 5 legs from the floor to the top, their outer faces "
               "flush with the top's edges.",
         ref="translate([-50,-30,70])cube([100,60,5]);"
             "for(x=[-50,45],y=[-30,25])translate([x,y,0])cube([5,5,70]);",
         checks=[("box", [-50, -30, 0], [50, 30, 75], 0.5),
                 ("solid", [0, 0, 72]), ("solid", [-47.5, -27.5, 35]),
                 ("solid", [47.5, 27.5, 35]), ("empty", [0, 0, 35]),
                 ("empty", [-40, -20, 35]), ("volume", 0.03)]),
    dict(id="ladder", tier=3,
         brief="A ladder lying flat: two side rails 10 x 10 in section, "
               "300 long along y (y 0..300), their centres at x = -100 "
               "and x = 100, z 0..10; and six round rungs of diameter 8 "
               "along x between the rails' inner faces, at y = 25, 75, "
               "125, 175, 225, 275, their axes at z = 5.",
         ref="for(x=[-105,95])translate([x,0,0])cube([10,300,10]);"
             "for(y=[25:50:275])translate([-95,y,5])rotate([0,90,0])"
             "cylinder(h=190,d=8,$fn=32);",
         checks=[("box", [-105, 0, 0], [105, 300, 10], 0.5),
                 ("solid", [0, 25, 5]), ("solid", [0, 275, 5]),
                 ("solid", [0, 125, 5]), ("empty", [0, 50, 5]),
                 ("solid", [100, 150, 5]), ("volume", 0.04)]),
]
