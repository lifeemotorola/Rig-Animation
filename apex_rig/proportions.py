# SPDX-License-Identifier: GPL-3.0-or-later
"""Apex Rig & Motion - anthropometric skeleton definition.

All joints are derived from a single height value plus stylisation factors, so
the rig can be rebuilt at any scale while staying anatomically coherent.
The output is a flat list of :class:`BoneSpec` consumed by :mod:`apex_rig.rig`.

Coordinate system: Blender native, +Z up, character faces -Y, character's left
is +X.  Units are metres.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from mathutils import Matrix, Quaternion, Vector

from .const import CURL_FACTORS, FINGERS, PRESETS, SPREAD_FACTORS

FWD = Vector((0.0, -1.0, 0.0))
UP = Vector((0.0, 0.0, 1.0))
SIDE = {"L": 1.0, "R": -1.0}


def _v(*args) -> Vector:
    return Vector(args)


def rotate_about(vec: Vector, axis: Vector, angle: float) -> Vector:
    return Quaternion(axis.normalized(), angle) @ vec


@dataclass
class BoneSpec:
    name: str
    head: Vector
    tail: Vector
    parent: str | None = None
    connect: bool = False
    deform: bool = True
    segments: int = 1
    radius: float = 0.03
    radius_tail: float | None = None
    collection: str = "Torso"
    color: str = "CENTER"
    widget: str | None = None
    widget_scale: float = 0.03
    widget_rotation: tuple = (0.0, 0.0, 0.0)
    roll_x: Vector | None = None
    roll_z: Vector | None = None
    lock_floor: bool = False   # keep child joints from collapsing (humanoid twist/legs)

    @property
    def length(self) -> float:
        return (self.tail - self.head).length


@dataclass
class RigOptions:
    preset: str = "FEMALE"
    height: float = 1.68
    build: float = 0.42
    head_scale: float = 1.0
    shoulder: float = 0.95
    chest: float = 0.96
    waist: float = 0.88
    hip: float = 1.07
    arm_len: float = 1.0
    leg_len: float = 1.0
    arm_angle: float = 44.0
    twist_bones: bool = False
    fingers: int = 5
    bbone: bool = True
    ik_arms: bool = True
    ik_legs: bool = True
    pole_targets: bool = True
    roll_arms: bool = True
    face: bool = True

    @classmethod
    def from_preset(cls, preset_key: str, **overrides) -> "RigOptions":
        data = dict(PRESETS.get(preset_key, PRESETS["FEMALE"]))
        data.pop("label", None)
        data.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**data)


class HumanProportions:
    """Computes every joint and bone of the Apex human rig."""

    def __init__(self, opts: RigOptions):
        self.o = opts
        self.H = float(opts.height)
        self.width = 0.80 + 0.40 * float(opts.build)   # global girth factor
        self.land: dict[str, Vector] = {}
        self.meta: dict = {}
        self.specs: list[BoneSpec] = []
        self._compute()

    # ------------------------------------------------------------------ math
    def z(self, frac: float) -> float:
        """Vertical fraction -> metres, honouring leg-length scaling."""
        H, leg = self.H, self.o.leg_len
        hip_base = 0.530
        if leg == 1.0:
            return frac * H
        hip = hip_base * leg
        if frac <= hip_base:
            return frac * leg * H
        factor = (1.0 - hip) / (1.0 - hip_base)
        return (hip + (frac - hip_base) * factor) * H

    def w(self, base: float, region: float = 1.0) -> float:
        return base * self.H * self.width * region

    # ------------------------------------------------------------- landmarks
    def _compute(self) -> None:
        o, H = self.o, self.H
        L = self.land

        # --- torso ---------------------------------------------------------
        L["pelvis"] = _v(0.0, 0.008 * H, self.z(0.535))
        L["spine1"] = _v(0.0, 0.006 * H, self.z(0.600))
        L["spine2"] = _v(0.0, 0.000, self.z(0.663))
        L["chest"] = _v(0.0, -0.004 * H, self.z(0.726))
        L["chest_top"] = _v(0.0, -0.004 * H, self.z(0.812))
        L["neck"] = _v(0.0, -0.002 * H, self.z(0.812))
        L["head"] = _v(0.0, -0.006 * H, self.z(0.880))
        L["head_top"] = _v(0.0, -0.004 * H, self.z(0.880) + 0.104 * H * o.head_scale)

        # --- shoulders / arms ---------------------------------------------
        for side, sign in SIDE.items():
            sh = _v(0.086 * H * o.shoulder * sign, -0.004 * H, self.z(0.792))
            L[f"shoulder.{side}"] = sh
            L[f"clavicle.{side}"] = _v(0.018 * H * sign, -0.012 * H, self.z(0.798))

            ang = math.radians(o.arm_angle)
            d = Vector((math.cos(ang) * sign, 0.0, -math.sin(ang)))
            d.normalize()
            L[f"arm_dir.{side}"] = d

            upper = 0.150 * H * o.arm_len
            fore = 0.145 * H * o.arm_len
            hand = 0.058 * H * o.arm_len

            elbow = sh + d * upper
            wrist = elbow + d * fore
            # natural pre-bend so the IK chain is never perfectly straight
            elbow = elbow + Vector((0.008 * H * sign, 0.018 * H, -0.004 * H))
            L[f"elbow.{side}"] = elbow
            L[f"wrist.{side}"] = wrist

            # palm normal points dorsally (projected world up)
            n = (UP - d * d.dot(UP)).normalized()
            across = n.cross(d).normalized()          # thumb -> pinky
            L[f"palm_normal.{side}"] = n
            L[f"across.{side}"] = across
            L[f"hand_dir.{side}"] = d
            L[f"hand_end.{side}"] = wrist + d * hand

            hand_width = 0.044 * H * self.width * (1.0 + (o.build - 0.5) * 0.15)
            L[f"hand_width.{side}"] = Vector((hand_width, hand_width, hand_width))

            # elbow pole: behind the elbow so the arm folds forward
            L[f"elbow_pole.{side}"] = elbow + Vector((
                0.055 * H * sign, 0.145 * H, -0.02 * H))

            # --- fingers ---------------------------------------------------
            base_line = wrist + d * hand * 0.92
            finger_defs = []
            if o.fingers >= 5:
                finger_defs = [
                    ("f_index", -0.40, -math.radians(4.0), 0.047),
                    ("f_middle", -0.13, 0.0, 0.052),
                    ("f_ring", 0.14, math.radians(4.0), 0.048),
                    ("f_pinky", 0.40, math.radians(9.0), 0.040),
                ]
            else:
                finger_defs = [
                    ("f_index", -0.34, -math.radians(3.0), 0.047),
                    ("f_middle", -0.05, 0.0, 0.052),
                    ("f_ring", 0.26, math.radians(6.0), 0.048),
                ]
            for fname, off, fan, length in finger_defs:
                base = base_line + across * (off * hand_width)
                # gentle knuckle arc: middle sits furthest from the wrist
                base += d * (hand * (0.035 - abs(off) * 0.02))
                fdir = rotate_about(d, n, fan)
                flen = length * H * o.arm_len
                L[f"finger_base.{side}.{fname}"] = base
                L[f"finger_dir.{side}.{fname}"] = fdir
                L[f"finger_len.{side}.{fname}"] = flen

            # thumb
            tbase = (base_line - d * hand * 0.55
                     - across * (0.42 * hand_width)
                     + n * (0.01 * H))
            tdir = rotate_about(d, n, -math.radians(42.0))
            tdir = rotate_about(tdir, across, math.radians(-8.0))
            tdir.normalize()
            L[f"finger_base.{side}.thumb"] = tbase
            L[f"finger_dir.{side}.thumb"] = tdir
            L[f"finger_len.{side}.thumb"] = 0.050 * H * o.arm_len

            # --- legs ------------------------------------------------------
            # femoral heads sit close to the midline: a 1.6 m human is only
            # ~18 cm wide across the hip joints, widening lower down
            hipj = _v(0.055 * H * o.hip * sign, 0.004 * H, self.z(0.528))
            knee = _v(0.049 * H * o.hip * sign, -0.030 * H, self.z(0.286))
            ankle = _v(0.047 * H * o.hip * sign, 0.010 * H, self.z(0.048))
            ball = _v(0.047 * H * o.hip * sign, -0.082 * H, self.z(0.020))
            toe_tip = _v(0.047 * H * o.hip * sign, -0.148 * H, self.z(0.014))
            L[f"hip.{side}"] = hipj
            L[f"knee.{side}"] = knee
            L[f"ankle.{side}"] = ankle
            L[f"ball.{side}"] = ball
            L[f"toe_tip.{side}"] = toe_tip
            L[f"knee_pole.{side}"] = knee + Vector((0.01 * H * sign, -0.16 * H, 0.01 * H))

        self._build_specs()

    # ------------------------------------------------------------ bone table
    def _build_specs(self) -> None:
        o, H, L = self.o, self.H, self.land
        specs = self.specs
        seg = 3 if o.bbone else 1
        seg_limb = 2 if o.bbone else 1
        w = self.width

        def add(**kw):
            specs.append(BoneSpec(**kw))

        # control: root
        add(name="root", head=_v(0, 0, 0), tail=_v(0, 0.28 * H, 0), deform=False,
            collection="Controls", color="CENTER", widget="root",
            widget_scale=0.30 * H, roll_z=_v(0, 0, 1))

        # control: cog
        add(name="cog", head=L["pelvis"] + _v(0, 0.0, -0.01 * H),
            tail=L["pelvis"] + _v(0, 0.0, 0.08 * H), parent="root", deform=False,
            collection="Controls", color="CENTER", widget="cog",
            widget_scale=0.075 * H, roll_z=FWD)

        # torso deform chain
        add(name="pelvis", head=L["pelvis"], tail=L["spine1"], parent="cog",
            deform=True, segments=seg, radius=self.w(0.072, o.hip),
            collection="Torso", color="CENTER", widget="cog", widget_scale=0.055 * H,
            roll_z=FWD, lock_floor=True)
        add(name="spine_01", head=L["spine1"], tail=L["spine2"], parent="pelvis",
            connect=True, deform=True, segments=seg, radius=self.w(0.068, o.waist),
            collection="Torso", color="CENTER", widget="ring", widget_scale=0.042 * H,
            roll_z=FWD)
        add(name="spine_02", head=L["spine2"], tail=L["chest"], parent="spine_01",
            connect=True, deform=True, segments=seg, radius=self.w(0.072, o.chest),
            collection="Torso", color="CENTER", widget="ring", widget_scale=0.046 * H,
            roll_z=FWD)
        add(name="chest", head=L["chest"], tail=L["chest_top"], parent="spine_02",
            connect=True, deform=True, segments=seg, radius=self.w(0.082, o.chest),
            collection="Torso", color="CENTER", widget="ring", widget_scale=0.058 * H,
            roll_z=FWD)
        add(name="neck", head=L["neck"], tail=L["head"], parent="chest", connect=True,
            deform=True, segments=2 if o.bbone else 1, radius=self.w(0.028),
            collection="Torso", color="CENTER", widget="ring", widget_scale=0.028 * H,
            roll_z=FWD)
        add(name="head", head=L["head"], tail=L["head_top"], parent="neck", connect=True,
            deform=True, radius=self.w(0.076, o.head_scale), radius_tail=self.w(0.02),
            collection="Torso", color="CENTER", widget="ring", widget_scale=0.062 * H,
            roll_z=FWD)

        for side, sign in SIDE.items():
            d = L[f"arm_dir.{side}"]
            n = L[f"palm_normal.{side}"]
            across = L[f"across.{side}"]
            hinge = n.cross(d).normalized()   # fingers/hand curl axis
            col = "LEFT" if side == "L" else "RIGHT"
            arm_coll = "Arms"

            shoulder = L[f"shoulder.{side}"]
            elbow = L[f"elbow.{side}"]
            wrist = L[f"wrist.{side}"]

            add(name=f"clavicle.{side}", head=L[f"clavicle.{side}"], tail=shoulder,
                parent="chest", deform=True, radius=self.w(0.032), collection=arm_coll,
                color=col, widget="diamond", widget_scale=0.022 * H, roll_z=UP)

            elbow_axis = d.cross(FWD).normalized()   # +X rotation folds forward, both sides
            add(name=f"upper_arm.{side}", head=shoulder, tail=elbow,
                parent=f"clavicle.{side}", connect=True, deform=True,
                segments=seg_limb, radius=self.w(0.033), collection=arm_coll, color=col,
                widget="diamond", widget_scale=0.026 * H, roll_x=elbow_axis)
            add(name=f"forearm.{side}", head=elbow, tail=wrist,
                parent=f"upper_arm.{side}", connect=True, deform=True,
                segments=seg_limb, radius=self.w(0.027), radius_tail=self.w(0.019),
                collection=arm_coll, color=col, widget="diamond",
                widget_scale=0.021 * H, roll_x=elbow_axis)
            add(name=f"hand.{side}", head=wrist, tail=L[f"hand_end.{side}"],
                parent=f"forearm.{side}", connect=True, deform=True,
                radius=self.w(0.021), collection=arm_coll, color=col,
                widget="box", widget_scale=0.020 * H, roll_x=hinge)

            if o.twist_bones:
                upv = (elbow - shoulder)
                fv = (wrist - elbow)
                add(name=f"upper_arm_twist.{side}",
                    head=shoulder + upv * 0.55, tail=elbow + upv * 0.05,
                    parent=f"upper_arm.{side}", deform=True, radius=self.w(0.030),
                    collection="Twists", color="EXTRA", roll_x=elbow_axis)
                add(name=f"forearm_twist.{side}",
                    head=elbow + fv * 0.45, tail=wrist + fv * 0.05,
                    parent=f"forearm.{side}", deform=True, radius=self.w(0.024),
                    collection="Twists", color="EXTRA", roll_x=elbow_axis)

            # ---- fingers --------------------------------------------------
            finger_list = [f for f in FINGERS if f[0] != "thumb"]
            if o.fingers < 5:
                finger_list = [f for f in finger_list if f[0] != "f_pinky"]
            finger_list.append(("thumb", 3))
            for fname, count in finger_list:
                base = L[f"finger_base.{side}.{fname}"]
                fdir = L[f"finger_dir.{side}.{fname}"]
                flen = L[f"finger_len.{side}.{fname}"]
                if fname == "thumb":
                    splits = (0.42, 0.33, 0.25)
                else:
                    splits = (0.45, 0.32, 0.23)
                parent = f"hand.{side}"
                cursor = base
                for i in range(count):
                    seg_len = flen * splits[i]
                    tail = cursor + fdir * seg_len
                    add(name=f"{fname}_{i + 1:02d}.{side}", head=cursor, tail=tail,
                        parent=parent, connect=(i > 0), deform=True,
                        segments=2 if o.bbone else 1,
                        radius=self.w(0.0085 if fname != "thumb" else 0.011),
                        radius_tail=self.w(0.0065), collection=arm_coll, color=col,
                        widget="ring", widget_scale=0.0075 * H, roll_x=hinge)
                    parent = f"{fname}_{i + 1:02d}.{side}"
                    cursor = tail
                    fdir = (fdir + n * (0.10 if fname != "thumb" else 0.04)).normalized()

            # ---- legs -----------------------------------------------------
            leg_coll = "Legs"
            knee_axis = _v(1, 0, 0)
            add(name=f"thigh.{side}", head=L[f"hip.{side}"], tail=L[f"knee.{side}"],
                parent="pelvis", deform=True, segments=seg_limb, radius=self.w(0.052),
                radius_tail=self.w(0.038), collection=leg_coll, color=col,
                widget="diamond", widget_scale=0.034 * H, roll_x=knee_axis)
            add(name=f"shin.{side}", head=L[f"knee.{side}"], tail=L[f"ankle.{side}"],
                parent=f"thigh.{side}", connect=True, deform=True,
                segments=seg_limb, radius=self.w(0.040), radius_tail=self.w(0.024),
                collection=leg_coll, color=col, widget="diamond",
                widget_scale=0.028 * H, roll_x=knee_axis)
            add(name=f"foot.{side}", head=L[f"ankle.{side}"], tail=L[f"ball.{side}"],
                parent=f"shin.{side}", connect=True, deform=True,
                radius=self.w(0.028), radius_tail=self.w(0.021), collection=leg_coll,
                color=col, widget="foot", widget_scale=0.032 * H, roll_x=knee_axis)
            add(name=f"toe.{side}", head=L[f"ball.{side}"], tail=L[f"toe_tip.{side}"],
                parent=f"foot.{side}", connect=True, deform=True,
                radius=self.w(0.020), radius_tail=self.w(0.013), collection=leg_coll,
                color=col, widget="toe", widget_scale=0.022 * H, roll_x=knee_axis)

            # ---- IK controls ---------------------------------------------
            hand_dir = d
            add(name=f"hand_ik.{side}", head=wrist, tail=wrist + hand_dir * (0.075 * H),
                parent="root", deform=False, collection="Controls", color="IK",
                widget="paddle", widget_scale=0.020 * H, roll_x=hinge)
            add(name=f"elbow_pole.{side}", head=L[f"elbow_pole.{side}"],
                tail=L[f"elbow_pole.{side}"] + FWD * (0.05 * H), parent="root",
                deform=False, collection="Controls", color="POLE",
                widget="sphere", widget_scale=0.016 * H, roll_z=UP)
            add(name=f"foot_ik.{side}", head=L[f"ankle.{side}"], tail=L[f"ball.{side}"],
                parent="root", deform=False, collection="Controls", color="IK",
                widget="foot", widget_scale=0.034 * H, roll_x=knee_axis)
            add(name=f"toe_ik.{side}", head=L[f"ball.{side}"], tail=L[f"toe_tip.{side}"],
                parent=f"foot_ik.{side}", deform=False, collection="Controls",
                color="IK", widget="toe", widget_scale=0.020 * H, roll_x=knee_axis)
            add(name=f"knee_pole.{side}", head=L[f"knee_pole.{side}"],
                tail=L[f"knee_pole.{side}"] + FWD * (0.05 * H), parent="root",
                deform=False, collection="Controls", color="POLE",
                widget="sphere", widget_scale=0.016 * H, roll_z=UP)

        # metadata for skinning / tools
        self.meta = {
            "height": H,
            "shoulder_z": self.z(0.792) * 0.94,
            "hip_z": self.z(0.528),
            "ankle_z": self.z(0.048),
            "hand": {s: tuple(L[f"wrist.{s}"]) for s in SIDE},
            "foot": {s: tuple(L[f"ankle.{s}"]) for s in SIDE},
        }
