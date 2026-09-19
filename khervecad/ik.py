"""Inverse kinematics — "put the hand here" instead of bone angles.

Posing by angles is how the rig stores a pose, but not how anyone (or
any assistant) thinks about one: "the left hand on the table", "the
gripper on the bolt", "the foot on the step". `solve` turns a target
point into those angles by **cyclic coordinate descent** (CCD, the
solver behind Blender's IK constraint in its simplest form): from the
last joint of the chain to the first, each one turns the effector
towards the target about its own pivot, a limited step at a time, until
the effector is within tolerance or stops improving.

The result is ordinary pose data — the human figure's `pose` rows, a
`joint` node's rx / ry / rz — so it stays editable, undoable and in the
OpenSCAD program. Two rigs:

* `HumanRig` — a `human` node: the chain is the rig's bones (shoulder
  and elbow for a hand, hip and knee for a foot), the effector a joint
  of MakeHuman's skeleton (the wrist, the ankle).
* `JointRig` — any part inside nested `joint` nodes (a robot arm, a
  crane, a desk lamp): the chain is the joints above the effector node,
  within each joint's min/max angle.

A rotation is applied in world space (Q) and written back into the
joint's own Euler angles in the frame its parent leaves it in:
R' = P⁻¹ Q P R, then decomposed like OpenSCAD's rotate([x, y, z]) =
Rz · Ry · Rx. Qt-free.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

#: a CCD step never turns a joint further than this (degrees)
MAX_STEP = 25.0
ITERATIONS = 60
#: close enough, as a fraction of the chain's length
TOLERANCE = 1e-3

#: effector aliases for the human figure: (effector joint, chain)
HUMAN_EFFECTORS = {
    "left_hand": ("lowerarm02.L____tail", ["upperarm01.L", "lowerarm01.L"]),
    "right_hand": ("lowerarm02.R____tail", ["upperarm01.R",
                                            "lowerarm01.R"]),
    "left_foot": ("lowerleg02.L____tail", ["upperleg01.L", "lowerleg01.L"]),
    "right_foot": ("lowerleg02.R____tail", ["upperleg01.R",
                                            "lowerleg01.R"]),
    "head": ("head____tail", ["neck01", "head"]),
}
#: the rig is Blender-style: +X is the figure's LEFT (it faces -Y)


# --------------------------------------------------------- 3x3 algebra

def _mm(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)]
            for i in range(3)]


def _mv(a, v):
    return [a[i][0] * v[0] + a[i][1] * v[1] + a[i][2] * v[2]
            for i in range(3)]


def _t(a):
    return [[a[j][i] for j in range(3)] for i in range(3)]


def _linear(m):
    """The rotation part of a 4x4 (any uniform scale divided out)."""
    r = [[m[i][j] for j in range(3)] for i in range(3)]
    s = math.sqrt(sum(r[i][0] ** 2 for i in range(3))) or 1.0
    return [[v / s for v in row] for row in r]


def euler_matrix(rx, ry, rz):
    from .mesh import mat_rotate
    m = mat_rotate(rx, ry, rz)
    return [[m[i][j] for j in range(3)] for i in range(3)]


def matrix_euler(r):
    """(rx, ry, rz) degrees with euler_matrix(...) == r (R = Rz Ry Rx)."""
    sy = -r[2][0]
    sy = max(-1.0, min(1.0, sy))
    ry = math.asin(sy)
    if abs(sy) < 1.0 - 1e-9:
        rx = math.atan2(r[2][1], r[2][2])
        rz = math.atan2(r[1][0], r[0][0])
    else:                                   # gimbal lock: fold into z
        rx = 0.0
        rz = math.atan2(-r[0][1], r[1][1])
    return [math.degrees(rx), math.degrees(ry), math.degrees(rz)]


def rotation_between(u, v, max_deg=180.0):
    """The shortest rotation turning direction *u* towards *v*, at most
    *max_deg* degrees (Rodrigues)."""
    lu = math.sqrt(sum(x * x for x in u))
    lv = math.sqrt(sum(x * x for x in v))
    if lu < 1e-12 or lv < 1e-12:
        return [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]
    a = [x / lu for x in u]
    b = [x / lv for x in v]
    axis = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]
    s = math.sqrt(sum(x * x for x in axis))
    c = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))
    angle = math.atan2(s, c)
    if s < 1e-12:
        return [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]
    angle = min(angle, math.radians(max_deg))
    k = [x / s for x in axis]
    ca, sa = math.cos(angle), math.sin(angle)
    x, y, z = k
    return [[ca + x * x * (1 - ca), x * y * (1 - ca) - z * sa,
             x * z * (1 - ca) + y * sa],
            [y * x * (1 - ca) + z * sa, ca + y * y * (1 - ca),
             y * z * (1 - ca) - x * sa],
            [z * x * (1 - ca) - y * sa, z * y * (1 - ca) + x * sa,
             ca + z * z * (1 - ca)]]


# ------------------------------------------------------------- solver

def solve(rig, target, iterations=ITERATIONS, max_step=MAX_STEP):
    """Pose *rig* so its effector reaches *target* (world xyz). Returns
    {"angles": {joint: [rx, ry, rz]}, "error": mm, "reached": bool,
    "reach": the chain's length}."""
    angles = {k: list(v) for k, v in rig.angles().items()}
    target = [float(v) for v in target]
    state = rig.forward(angles)
    reach = rig.length(state) or 1.0
    best = (math.dist(state["effector"], target), angles)
    for _ in range(iterations):
        for name in reversed(rig.chain):
            state = rig.forward(angles)
            p = state["pivots"][name]
            e = state["effector"]
            q = rotation_between([e[i] - p[i] for i in range(3)],
                                 [target[i] - p[i] for i in range(3)],
                                 max_step)
            frame = state["frames"][name]          # parent's rotation
            local = euler_matrix(*angles[name])
            new = _mm(_t(frame), _mm(q, _mm(frame, local)))
            rx, ry, rz = matrix_euler(new)
            lo, hi = rig.limits(name)
            angles[name] = [min(max(a, lo), hi) for a in (rx, ry, rz)]
        err = math.dist(rig.forward(angles)["effector"], target)
        if err < best[0] - 1e-9:
            best = (err, {k: list(v) for k, v in angles.items()})
        if err <= TOLERANCE * reach:
            break
    err, angles = best
    return {"angles": angles, "error": err,
            "reached": err <= max(TOLERANCE * reach, 0.5),
            "reach": reach}


# --------------------------------------------------------------- rigs

class JointRig:
    """A chain of `joint` nodes above *effector* (innermost last)."""

    def __init__(self, effector, point=None, count=0, env=None):
        from .mesh import mat_apply
        self.effector = effector
        self.env = env or {}
        chain = []
        probe = effector if effector.type == "joint" else effector.parent
        while probe is not None:
            if probe.type == "joint":
                chain.append(probe)
            probe = probe.parent
        chain.reverse()                           # outermost first
        if count:
            chain = chain[-int(count):]
        if not chain:
            raise ValueError(f"{effector.name} is not inside a joint — "
                             "wrap the moving parts in joint nodes "
                             "(outer joint = shoulder, inner = elbow)")
        self.nodes = {str(j.id): j for j in chain}
        self.chain = [str(j.id) for j in chain]
        if point is None:
            point = self._centre(effector)
        self.point = list(point)                  # effector's own frame
        self._apply = mat_apply

    def _centre(self, node):
        from . import mesh
        tris = mesh.tessellate(node) if node.children or \
            node.type != "joint" else []
        # tessellate() draws the node in its own frame (no ancestors)
        pts = [v for t in tris for v in t]
        if not pts:
            return [0.0, 0.0, 0.0]
        return [(min(p[i] for p in pts) + max(p[i] for p in pts)) / 2
                for i in range(3)]

    def angles(self):
        from .mesh import rv
        return {k: [float(rv(j.params.get(a, 0.0), self.env, 0.0))
                    for a in ("rx", "ry", "rz")]
                for k, j in self.nodes.items()}

    def limits(self, name):
        from .mesh import rv
        j = self.nodes[name]
        return (float(rv(j.params.get("min_angle", -180), self.env, -180)),
                float(rv(j.params.get("max_angle", 180), self.env, 180)))

    def forward(self, angles):
        from .mesh import ancestor_matrix, mat_apply, mat_mul, node_matrix
        saved = {k: {a: j.params.get(a, 0.0) for a in ("rx", "ry", "rz")}
                 for k, j in self.nodes.items()}
        try:
            for k, (rx, ry, rz) in angles.items():
                self.nodes[k].params.update(rx=rx, ry=ry, rz=rz)
            pivots, frames = {}, {}
            for k, j in self.nodes.items():
                up = ancestor_matrix(j, self.env)
                p = [float(j.params.get(a, 0.0) or 0.0)
                     for a in ("px", "py", "pz")]
                pivots[k] = mat_apply(up, p)
                frames[k] = _linear(up)
            m = ancestor_matrix(self.effector, self.env)
            if self.effector.type == "joint":
                m = mat_mul(m, node_matrix(self.effector, self.env))
            effector = mat_apply(m, self.point)
        finally:
            for k, v in saved.items():
                self.nodes[k].params.update(v)
        return {"pivots": pivots, "frames": frames, "effector": effector}

    def length(self, state):
        pts = [state["pivots"][k] for k in self.chain] + [state["effector"]]
        return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


class HumanRig:
    """A `human` node's arm, leg or neck."""

    def __init__(self, node, effector="left_hand", chain=None, env=None):
        from . import human
        from .mesh import rv
        self.node = node
        self.env = env or {}
        p = node.params
        num = lambda k, d: float(rv(p.get(k, d), self.env, d))   # noqa
        self.kw = dict(gender=num("gender", 0.0), age=num("age", 0.0),
                       weight=num("weight", 0.0),
                       height=num("height", 0.0))
        self.stature = num("stature", human.DEFAULT_STATURE)
        bones = human.skeleton()["bones"]
        if effector in HUMAN_EFFECTORS:
            self.joint, default_chain = HUMAN_EFFECTORS[effector]
        elif effector in bones:
            self.joint = bones[effector]["tail"]
            default_chain = [bones[effector]["parent"], effector]
        else:
            raise ValueError(
                f"No effector {effector!r}: use one of "
                f"{', '.join(HUMAN_EFFECTORS)} or a bone name")
        self.chain = list(chain or default_chain)
        for b in self.chain:
            if b not in bones:
                raise ValueError(f"No bone named {b!r}")
        self.owner = next((b for b, v in bones.items()
                           if self.joint in (v["tail"], v["head"])
                           and v["tail"] == self.joint), self.chain[-1])
        self.rows = {str(r[0]): [float(v) for v in r[1:4]]
                     for r in (p.get("pose") or [])
                     if isinstance(r, list) and len(r) == 4}
        self.macro = human.weights(**self.kw)
        self._frame = self._rest_frame()

    def _rest_frame(self):
        """(cx, lo_z, scale) human.points() stands the body with."""
        from . import human
        verts, _faces, macro = human._load()
        pts = [list(v) for v in verts]
        for name, k in self.macro.items():
            for i, (dx, dy, dz) in macro.get(name, {}).items():
                pts[i][0] += dx * k
                pts[i][1] += dy * k
                pts[i][2] += dz * k
        pts = [(q[0] * 100.0, -q[2] * 100.0, q[1] * 100.0) for q in pts]
        lo = min(q[2] for q in pts)
        hi = max(q[2] for q in pts)
        scale = self.stature / (hi - lo) if hi > lo else 1.0
        cx = (min(q[0] for q in pts) + max(q[0] for q in pts)) / 2
        return cx, lo, scale

    def angles(self):
        return {b: list(self.rows.get(b, [0.0, 0.0, 0.0]))
                for b in self.chain}

    def limits(self, name):
        return (-170.0, 170.0)

    def _world(self):
        from .mesh import ancestor_matrix
        return ancestor_matrix(self.node, self.env)

    def forward(self, angles):
        from . import human
        from .mesh import mat_apply
        rows = dict(self.rows)
        rows.update(angles)
        pose = [[b] + list(a) for b, a in rows.items() if any(a)]
        mats = human.bone_matrices(pose, self.macro)
        cx, lo, s = self._frame
        world = self._world()
        wlin = _linear(world)
        bones = human.skeleton()["bones"]

        def place(raw):
            return mat_apply(world, [(raw[0] - cx) * s, raw[1] * s,
                                     (raw[2] - lo) * s])

        def through(bone, pt):
            m = mats.get(bone)
            if m is None:
                return pt
            return mat_apply(m, pt)
        pivots, frames = {}, {}
        for b in self.chain:
            head = human.joint_position(bones[b]["head"], self.macro)
            pivots[b] = place(through(b, head))
            parent = bones[b].get("parent")
            pm = mats.get(parent) if parent else None
            frames[b] = _mm(wlin, _linear(pm)) if pm else wlin
        tip = human.joint_position(self.joint, self.macro)
        effector = place(through(self.owner, tip))
        return {"pivots": pivots, "frames": frames, "effector": effector}

    def length(self, state):
        pts = [state["pivots"][b] for b in self.chain] + [state["effector"]]
        return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))

    def pose_rows(self, angles):
        rows = dict(self.rows)
        rows.update({b: [round(v, 3) for v in a] for b, a in angles.items()})
        return [[b] + a for b, a in rows.items() if any(a)]


# ------------------------------------------------------ apply to a model

def human_in(node):
    """The `human` node *node* is or holds (a clothed, painted or
    sculpted figure wraps one), or None."""
    return next((n for n in node.walk() if n.type == "human"), None)


def in_joint(node) -> bool:
    probe = node
    while probe is not None:
        if probe.type == "joint":
            return True
        probe = probe.parent
    return False


def reach(model, node, target, effector=None, chain=None, point=None,
          env=None) -> dict:
    """Pose *node* so its effector reaches *target* (world) and write
    the angles into the document (one undo step per call). *node* is a
    human figure (effector = left_hand / right_hand / left_foot /
    right_foot / head or a bone) or a part inside `joint` nodes (the
    effector is the part itself, *point* in its own frame, *chain* the
    number of joints to use)."""
    person = human_in(node)
    if person is not None and not in_joint(node):
        rig = HumanRig(person, effector or "left_hand", chain, env)
        res = solve(rig, target)
        model.set_param(person, "pose", rig.pose_rows(res["angles"]))
        posed = {b: [round(v, 2) for v in a]
                 for b, a in res["angles"].items()}
        kind = "human"
    else:
        rig = JointRig(node, point, int(chain or 0), env)
        res = solve(rig, target)
        posed = {}
        for key, (rx, ry, rz) in res["angles"].items():
            joint = rig.nodes[key]
            for axis, value in (("rx", rx), ("ry", ry), ("rz", rz)):
                model.set_param(joint, axis, round(value, 3))
            posed[f"{joint.name} #{joint.id}"] = [round(rx, 2),
                                                  round(ry, 2), round(rz, 2)]
        kind = "joints"
    state = rig.forward(res["angles"])
    out = {"rig": kind, "posed": posed, "miss": round(res["error"], 3),
           "reached": res["reached"],
           "effector": [round(v, 3) for v in state["effector"]],
           "chain_length": round(res["reach"], 3)}
    if not res["reached"]:
        base = state["pivots"][rig.chain[0]]
        far = math.dist(base, target) - res["reach"]
        out["note"] = (f"Not reached: the target is {far:.1f} beyond the "
                       "chain's reach — move the body/base closer, or add "
                       "a joint to the chain." if far > 0 else
                       "Not reached within the joint limits — widen "
                       "min/max angle or move the target.")
    return out
