kcad_fillet(radius = 2, kind = "round", detail = 6, edges = [], faces = [[-11.6631, 3.3333, 19.3313, 0.4886, 0, 0.8725]], cuts = [], adds = []) {
    rotate([90, 0, 0]) {
        linear_extrude(height=20, center=true) {
            kcad_regions(seeds = [[-11.6631, 14.6907]], inside = [[]], points = [], paths = []) {
                kcad_constraints = "[{\"kind\":\"length\",\"refs\":[\"0.l\"],\"value\":14.0},{\"kind\":\"length\",\"refs\":[\"2.l\"],\"value\":25.0},{\"kind\":\"coincident\",\"refs\":[\"1.p1\",\"0.p2\"]},{\"kind\":\"coincident\",\"refs\":[\"1.p2\",\"2.p1\"]},{\"kind\":\"coincident\",\"refs\":[\"2.p2\",\"0.p1\"]},{\"kind\":\"vertical\",\"refs\":[\"0.l\"]},{\"kind\":\"horizontal\",\"refs\":[\"2.l\"]},{\"kind\":\"fix\",\"refs\":[\"0.p1\"],\"at\":[-20.0,10.0]}]";
                hull() { translate([-20, 10]) circle(d=0.2, $fn=32); translate([-20, 24]) circle(d=0.2, $fn=32); };
                hull() { translate([-20, 24]) circle(d=0.2, $fn=32); translate([5, 10]) circle(d=0.2, $fn=32); };
                hull() { translate([5, 10]) circle(d=0.2, $fn=32); translate([-20, 10]) circle(d=0.2, $fn=32); };
            }
        }
    }
    translate([-30, -15, 0]) linear_extrude(height=10) square([60, 30]);
}
