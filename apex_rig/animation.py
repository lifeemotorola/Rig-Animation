# SPDX-License-Identifier: GPL-3.0-or-later
"""Apex Rig & Motion - procedural animation engine.

Every motion is created the way an animator would do it: a handful of pose
keys on the *controls* (cog, ik feet, hands, torso bones and the root custom
properties), Bezier interpolation and a CYCLES modifier for loops.  Nothing is
baked to a deform skeleton, so the result stays fully editable.

The module also ships retiming / offset / mirror / cycle helpers used by the
operators and by the motion-path tools.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import bpy
from mathutils import Euler, Matrix, Vector

from . import utils
from .const import MOTIONS, PROPS, WALK_PRESETS

DEG = math.pi / 180.0


# ---------------------------------------------------------------------------
# Pose primitives
# ---------------------------------------------------------------------------
@dataclass
class Pose:
    """A rotation/translation delta expressed in intuitive world axes.

    ``rot``  - XYZ euler in degrees, applied in the bone's parent space
    ``loc``  - metres along the armature world axes
    ``axis`` - optional (axis, degrees) rotation applied before ``rot``
    """
    rot: tuple = (0.0, 0.0, 0.0)
    loc: tuple = (0.0, 0.0, 0.0)
    axis: tuple | None = None

    def matrix(self, pb) -> Matrix:
        rest3 = pb.bone.matrix_local.to_3x3()
        rot = Euler((self.rot[0] * DEG, self.rot[1] * DEG, self.rot[2] * DEG),
                    "XYZ").to_matrix()
        if self.axis is not None:
            axis_vec, angle = self.axis
            rot = Matrix.Rotation(angle * DEG, 3, Vector(axis_vec)) @ rot
        local_rot = rest3.inverted() @ rot @ rest3
        local_loc = rest3.inverted() @ Vector(self.loc)
        return Matrix.Translation(local_loc) @ local_rot.to_4x4()


def set_pose(arm, entries: dict, key: bool = False, frame: float | None = None,
             only: set | None = None) -> None:
    """Apply a ``{bone_name: Pose}`` mapping to the rig."""
    ordered = sorted(entries.items(),
                     key=lambda kv: utils.bone_depth(arm.pose.bones[kv[0]])
                     if kv[0] in arm.pose.bones else 0)
    for name, pose in ordered:
        if only is not None and name not in only:
            continue
        pb = arm.pose.bones.get(name)
        if pb is None:
            continue
        pb.matrix_basis = pose.matrix(pb)
        if key and frame is not None:
            _key_bone(pb, frame)


def _key_bone(pb, frame: float) -> None:
    pb.keyframe_insert("location", frame=frame, group=pb.name)
    if pb.rotation_mode == "QUATERNION":
        pb.keyframe_insert("rotation_quaternion", frame=frame, group=pb.name)
    elif pb.rotation_mode == "AXIS_ANGLE":
        pb.keyframe_insert("rotation_axis_angle", frame=frame, group=pb.name)
    else:
        pb.keyframe_insert("rotation_euler", frame=frame, group=pb.name)


def clear_pose_channels(arm, bones=None) -> None:
    """Reset location/rotation of the given bones (all by default)."""
    for pb in arm.pose.bones:
        if bones and pb.name not in bones:
            continue
        pb.location = (0.0, 0.0, 0.0)
        if pb.rotation_mode == "QUATERNION":
            pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        else:
            pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)


# ---------------------------------------------------------------------------
# Action helpers
# ---------------------------------------------------------------------------
def _all_fcurves(action, slot):
    return utils.action_fcurves(action, slot)


def smooth_curves(action, slot, interpolation: str = "BEZIER",
                  handle: str = "AUTO_CLAMPED") -> None:
    for fc in _all_fcurves(action, slot):
        for kp in fc.keyframe_points:
            kp.interpolation = interpolation
            if interpolation == "BEZIER":
                kp.handle_left_type = handle
                kp.handle_right_type = handle
        fc.update()


def add_cycle_modifier(action, slot) -> int:
    count = 0
    for fc in _all_fcurves(action, slot):
        if any(m.type == "CYCLES" for m in fc.modifiers):
            continue
        mod = fc.modifiers.new("CYCLES")
        mod.mode_before = "REPEAT"
        mod.mode_after = "REPEAT"
        count += 1
    return count


def remove_cycle_modifiers(action, slot) -> int:
    count = 0
    for fc in _all_fcurves(action, slot):
        for mod in list(fc.modifiers):
            if mod.type == "CYCLES":
                fc.modifiers.remove(mod)
                count += 1
    return count


def write_prop_curve(action, slot, prop: str, frames, values,
                     bone: str = "root") -> None:
    path = f'pose.bones["{bone}"]["{prop}"]'
    utils.write_curve(action, slot, path, 0, frames, values, interpolation="BEZIER")


def _slug(text: str) -> str:
    return "".join(ch if (ch.isalnum() or ch in "-_") else "_" for ch in text).strip("_")


def _new_action(arm, name: str):
    action, slot = utils.new_action_for(arm, name)
    return action, slot


def _finish(arm, action, slot, loop: bool, smooth: bool = True):
    if smooth:
        smooth_curves(action, slot)
    if loop:
        add_cycle_modifier(action, slot)
        try:
            action.use_frame_range = True
            rng = utils.action_range(action)
            action.frame_start, action.frame_end = rng
            action.use_cyclic = True
        except Exception:
            pass
    try:
        action.asset_mark()
        action.asset_data.description = "Apex Rig & Motion procedural action"
    except Exception:
        pass
    arm.animation_data.action = action
    try:
        arm.animation_data.action_slot = slot
    except Exception:
        pass
    utils.refresh(arm)
    return action


# ---------------------------------------------------------------------------
# Motion catalogue
# ---------------------------------------------------------------------------
def _sin(phase, amp=1.0, offset=0.0):
    return math.sin(phase * math.tau + offset) * amp


def _ease(t):
    return utils.smoothstep(utils.clamp(t, 0.0, 1.0))


def motion_breathing(arm):
    frames = MOTIONS["BREATHE"][2]
    keys = {}
    steps = 12
    for i in range(steps + 1):
        p = i / steps
        f = 1 + p * frames
        s = math.sin(p * math.tau)
        keys[f] = {
            "chest": Pose(rot=(-1.1 * s, 0, 0)),
            "spine_02": Pose(rot=(-0.55 * s, 0, 0)),
            "spine_01": Pose(rot=(-0.25 * s, 0, 0)),
            "neck": Pose(rot=(0.75 * s, 0, 0)),
            "head": Pose(rot=(0.35 * s, 0, 0)),
            "clavicle.L": Pose(rot=(0, -1.6 * s, 0)),
            "clavicle.R": Pose(rot=(0, 1.6 * s, 0)),
            "cog": Pose(loc=(0, 0, 0.0022 * s)),
        }
    return keys, {}, frames, True


def motion_weight(arm):
    frames = MOTIONS["WEIGHT"][2]
    keys = {}
    steps = 12
    for i in range(steps + 1):
        p = i / steps
        f = 1 + p * frames
        s = math.sin(p * math.tau)
        c = math.cos(p * math.tau)
        keys[f] = {
            "cog": Pose(loc=(0.026 * s, 0, -0.008 * abs(s)),
                        rot=(0, 1.2 * s, 1.6 * s)),
            "pelvis": Pose(rot=(0, 2.4 * s, -2.2 * s)),
            "spine_01": Pose(rot=(0, -0.8 * s, 1.0 * s)),
            "spine_02": Pose(rot=(0, -0.7 * s, 1.1 * s)),
            "chest": Pose(rot=(0.6 * c, -0.6 * s, 0.9 * s)),
            "neck": Pose(rot=(0, 0.4 * s, -0.8 * s)),
            "head": Pose(rot=(0.4 * c, -0.3 * s, -1.4 * s)),
        }
    return keys, {}, frames, True


def motion_idle(arm):
    frames = MOTIONS["IDLE"][2]
    keys = {}
    steps = 24
    for i in range(steps + 1):
        p = i / steps
        f = 1 + p * frames
        a = p * math.tau
        sway = math.sin(a)
        breathe = math.sin(a * 2.0)
        drift = math.sin(a * 0.5) * 0.6 + math.sin(a * 1.5) * 0.4
        noise = math.sin(a * 3.17) * 0.35 + math.sin(a * 5.31) * 0.2
        keys[f] = {
            "cog": Pose(loc=(0.006 * sway, 0, -0.002 * abs(sway)),
                        rot=(0.3 * breathe, 0.5 * sway, 0.8 * sway)),
            "pelvis": Pose(rot=(0, 0.8 * sway, -1.0 * sway)),
            "spine_01": Pose(rot=(0.2 * breathe, -0.3 * sway, 0.4 * sway)),
            "spine_02": Pose(rot=(0.35 * breathe, -0.3 * sway, 0.5 * sway)),
            "chest": Pose(rot=(-0.5 * breathe, -0.25 * sway, 0.4 * sway)),
            "neck": Pose(rot=(0.3 * breathe, 0.2 * drift, -0.4 * sway)),
            "head": Pose(rot=(0.2 * breathe + 0.2 * noise, 0.35 * drift,
                              -0.6 * sway + 0.3 * noise)),
            "clavicle.L": Pose(rot=(0, -0.8 * breathe, 0)),
            "clavicle.R": Pose(rot=(0, 0.8 * breathe, 0)),
        }
    return keys, {}, frames, True


def motion_look(arm):
    frames = MOTIONS["LOOK"][2]
    # keyed glances with holds: (phase, yaw, pitch, tilt)
    beats = [
        (0.00, 0.0, 0.0, 0.0),
        (0.14, 0.0, 0.0, 0.0),
        (0.24, 26.0, -3.0, -3.0),
        (0.38, 26.0, -2.0, -3.0),
        (0.48, -6.0, 4.0, 2.0),
        (0.58, -22.0, 5.0, 4.0),
        (0.72, -22.0, 4.0, 3.5),
        (0.86, 2.0, -1.0, -1.0),
        (1.00, 0.0, 0.0, 0.0),
    ]
    keys = {}
    for phase, yaw, pitch, tilt in beats:
        f = 1 + phase * frames
        keys[f] = {
            "head": Pose(rot=(pitch, tilt * 0.6, yaw * 0.62)),
            "neck": Pose(rot=(pitch * 0.4, tilt * 0.4, yaw * 0.38)),
            "chest": Pose(rot=(0, 0, yaw * 0.10)),
            "spine_02": Pose(rot=(0, 0, yaw * 0.06)),
        }
    return keys, {}, frames, True


def motion_fingers(arm):
    frames = MOTIONS["FINGERS"][2]
    keys = {}
    steps = 20
    for i in range(steps + 1):
        p = i / steps
        f = 1 + p * frames
        a = p * math.tau
        curl_l = 0.30 + 0.26 * math.sin(a) + 0.10 * math.sin(a * 3.1)
        curl_r = 0.30 + 0.26 * math.sin(a + 1.2) + 0.10 * math.sin(a * 2.7)
        keys[f] = {}
        props = {}
        keys[f]["__props__"] = props
        props["finger_curl.L"] = utils.clamp(curl_l, 0.0, 1.0)
        props["finger_curl.R"] = utils.clamp(curl_r, 0.0, 1.0)
        props["finger_spread.L"] = 0.18 * math.sin(a * 1.7)
        props["finger_spread.R"] = 0.18 * math.sin(a * 1.7 + 0.8)
        props["thumb_curl.L"] = 0.22 + 0.18 * math.sin(a * 2.3)
        props["thumb_curl.R"] = 0.22 + 0.18 * math.sin(a * 2.3 + 1.1)
    return keys, {}, frames, True


def motion_settle(arm):
    frames = MOTIONS["SETTLE"][2]
    keys = {}
    taps = [(0.0, 1.0), (0.18, -0.55), (0.38, 0.28), (0.58, -0.12),
            (0.78, 0.05), (1.0, 0.0)]
    for phase, amp in taps:
        f = 1 + phase * frames
        keys[f] = {
            "cog": Pose(rot=(2.4 * amp, 0, 0), loc=(0, 0, -0.012 * amp)),
            "spine_01": Pose(rot=(-1.1 * amp, 0, 0)),
            "spine_02": Pose(rot=(-0.9 * amp, 0, 0)),
            "chest": Pose(rot=(-0.8 * amp, 0, 0)),
            "neck": Pose(rot=(1.4 * amp, 0, 0)),
            "head": Pose(rot=(1.6 * amp, 0, 0)),
        }
    return keys, {}, frames, False


# ---------------------------------------------------------------------------
# Locomotion
# ---------------------------------------------------------------------------
def _foot_cycle(p, stance, stride, lift, toe_off, heel):
    """Return (y, z, foot_pitch_deg, toe_pitch_deg) for one foot."""
    p = p % 1.0
    if p < stance:
        t = p / stance
        y = -stride * 0.5 + stride * t
        z = 0.0
        # heel strike -> flat -> toe off
        if t < 0.18:
            pitch = -heel * (1.0 - _ease(t / 0.18))
        elif t > 0.72:
            pitch = toe_off * _ease((t - 0.72) / 0.28)
        else:
            pitch = 0.0
        toe = 0.0
    else:
        t = (p - stance) / (1.0 - stance)
        y = stride * 0.5 - stride * _ease(t)
        z = lift * math.sin(math.pi * t) ** 1.15
        pitch = -heel * 0.4 + (toe_off * 0.25) * math.sin(math.pi * t)
        toe = -toe_off * 0.35 * math.sin(math.pi * t)
    return y, z, pitch, toe


def _locomotion(arm, preset_key: str):
    label, cfg = WALK_PRESETS[preset_key]
    frames = int(cfg["frames"])
    height = max((b.tail_local.z for b in arm.data.bones), default=1.7)
    scale = height / 1.75
    stride = cfg["stride"] * scale
    lift = cfg["lift"] * scale
    bob = cfg["bob"] * scale
    sway = cfg["sway"] * scale

    # --- reach analysis: the hips must drop enough for the stride ----------
    thigh = arm.data.bones.get("thigh.L")
    shin = arm.data.bones.get("shin.L")
    leg = 0.0
    if thigh and shin:
        leg = (thigh.head_local - shin.tail_local).length
    max_crouch = leg * 0.20
    half = stride * 0.5
    if leg > 1e-4 and half > 0.0:
        needed = leg - math.sqrt(max(leg * leg - half * half, 1e-8))
        crouch = min(needed + 0.008 * scale, max_crouch)
        if needed > max_crouch:      # stride too long for a natural crouch
            stride = 2.0 * math.sqrt(max(leg * leg - (leg - max_crouch) ** 2, 1e-8))
            crouch = max_crouch
            half = stride * 0.5
    else:
        crouch = 0.0

    keys = {}
    for f in range(1, frames + 2):
        p = (f - 1) / frames
        a = p * math.tau
        yl, zl, pl, tol = _foot_cycle(p, cfg["stance"], stride, lift,
                                      cfg["toe_off"], cfg["toe_off"] * 0.55)
        yr, zr, pr, tor = _foot_cycle(p + 0.5, cfg["stance"], stride, lift,
                                      cfg["toe_off"], cfg["toe_off"] * 0.55)
        bob_z = -crouch - bob * (0.5 - 0.5 * math.cos(2 * a))
        lean = cfg["lean"]
        keys[f] = {
            "cog": Pose(loc=(sway * math.sin(a), 0.0, bob_z),
                        rot=(lean * 0.55, cfg["hip_roll"] * -math.sin(a) * 0.5,
                             cfg["hip_yaw"] * math.sin(a) * 0.35)),
            "pelvis": Pose(rot=(lean * 0.2, cfg["hip_roll"] * -math.sin(a),
                                cfg["hip_yaw"] * math.sin(a))),
            "spine_01": Pose(rot=(lean * 0.15, cfg["hip_roll"] * 0.25 * math.sin(a),
                                  -cfg["hip_yaw"] * 0.35 * math.sin(a))),
            "spine_02": Pose(rot=(lean * 0.15, cfg["hip_roll"] * 0.2 * math.sin(a),
                                  -cfg["hip_yaw"] * 0.45 * math.sin(a))),
            "chest": Pose(rot=(lean * 0.1, cfg["hip_roll"] * 0.15 * math.sin(a),
                               -cfg["hip_yaw"] * 0.55 * math.sin(a))),
            "neck": Pose(rot=(-lean * cfg["head_stabilise"],
                              -cfg["hip_roll"] * 0.2 * math.sin(a),
                              cfg["hip_yaw"] * 0.25 * math.sin(a))),
            "head": Pose(rot=(-lean * cfg["head_stabilise"] * 1.2, 0.0,
                              cfg["hip_yaw"] * 0.2 * math.sin(a))),
            "foot_ik.L": Pose(loc=(0.0, yl, zl), rot=(pl, 0.0, 0.0)),
            "foot_ik.R": Pose(loc=(0.0, yr, zr), rot=(pr, 0.0, 0.0)),
            "toe_ik.L": Pose(rot=(tol, 0.0, 0.0)),
            "toe_ik.R": Pose(rot=(tor, 0.0, 0.0)),
            "upper_arm.L": Pose(rot=(-cfg["arm_swing"] * math.sin(a), 0, 0)),
            "upper_arm.R": Pose(rot=(cfg["arm_swing"] * math.sin(a), 0, 0)),
            "forearm.L": Pose(rot=(cfg["elbow"] * (0.55 + 0.45 * math.sin(a)), 0, 0)),
            "forearm.R": Pose(rot=(cfg["elbow"] * (0.55 - 0.45 * math.sin(a)), 0, 0)),
        }
    return keys, {"ik_leg.L": 1.0, "ik_leg.R": 1.0,
                  "ik_arm.L": 0.0, "ik_arm.R": 0.0}, frames, True


def motion_walk(arm):
    return _locomotion(arm, "WALK")


def motion_run(arm):
    return _locomotion(arm, "RUN")


def motion_sneak(arm):
    return _locomotion(arm, "SNEAK")


BUILDERS = {
    "BREATHE": motion_breathing,
    "WEIGHT": motion_weight,
    "IDLE": motion_idle,
    "LOOK": motion_look,
    "FINGERS": motion_fingers,
    "SETTLE": motion_settle,
    "WALK": motion_walk,
    "RUN": motion_run,
    "SNEAK": motion_sneak,
}


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------
def _basis_channels(pb, pose: Pose):
    """Decompose a Pose into local location / rotation channels for *pb*."""
    m = pose.matrix(pb)
    loc = tuple(m.to_translation())
    if pb.rotation_mode == "QUATERNION":
        q = m.to_quaternion()
        return loc, ("rotation_quaternion", (q.w, q.x, q.y, q.z))
    e = m.to_euler(pb.rotation_mode if pb.rotation_mode in {"XYZ", "XZY", "YXZ",
                                                            "YZX", "ZXY", "ZYX"} else "XYZ")
    return loc, ("rotation_euler", (e.x, e.y, e.z))


def _write_bone_curves(action, slot, pb_name: str, frames, locs, rots,
                       rot_path: str) -> None:
    path = f'pose.bones["{pb_name}"].'
    for i in range(3):
        utils.write_curve(action, slot, path + "location", i, frames,
                          [v[i] for v in locs], interpolation="BEZIER")
    n = len(rots[0]) if rots else 0
    if n == 4:
        # keep quaternions on the same hemisphere so Bezier interpolation is short
        fixed = []
        prev = None
        for q in rots:
            if prev is not None and sum(a * b for a, b in zip(prev, q)) < 0.0:
                q = tuple(-c for c in q)
            fixed.append(q)
            prev = q
        rots = fixed
    for i in range(n):
        utils.write_curve(action, slot, path + rot_path, i, frames,
                          [v[i] for v in rots], interpolation="BEZIER")


def create_motion(arm, key: str, start: float = 1.0, loop: bool | None = None,
                  name: str | None = None):
    """Author the motion *key* as an editable action on the rig controls.

    Curves are written directly (no per-frame depsgraph evaluation), so the
    result is deterministic, fast and independent of the current scene frame.
    """
    if key not in BUILDERS:
        raise KeyError(f"Unknown motion '{key}'")
    utils.ensure_object_mode()
    keys, props, frames, default_loop = BUILDERS[key](arm)
    if loop is None:
        loop = default_loop
    label = MOTIONS[key][0] if key in MOTIONS else WALK_PRESETS[key][0]
    action_name = name or f"Apex_{_slug(label)}"
    action, slot = _new_action(arm, action_name)
    offset = start - 1.0

    # collect per-bone key lists
    bone_data: dict[str, dict] = {}
    prop_data: dict[str, list] = {}
    for frame in sorted(keys):
        entries = {k: v for k, v in keys[frame].items() if not k.startswith("__")}
        prop_values = dict(keys[frame].get("__props__", {}))
        prop_values.update(props)
        for bone_name, pose in entries.items():
            pb = arm.pose.bones.get(bone_name)
            if pb is None:
                continue
            loc, (rot_path, rot) = _basis_channels(pb, pose)
            data = bone_data.setdefault(bone_name, {"frames": [], "locs": [],
                                                    "rots": [], "path": rot_path})
            data["frames"].append(frame + offset)
            data["locs"].append(loc)
            data["rots"].append(tuple(rot))
        for prop_name, value in prop_values.items():
            prop_data.setdefault(prop_name, []).append((frame + offset, float(value)))

    for bone_name, data in bone_data.items():
        _write_bone_curves(action, slot, bone_name, data["frames"], data["locs"],
                           data["rots"], data["path"])
    for prop_name, pairs in prop_data.items():
        pairs.sort()
        first_frame = start
        last_frame = start + frames
        values = [v for _f, v in pairs]
        if loop and len(values) > 1 and abs(values[0] - values[-1]) > 1e-6:
            values.append(values[0])
            pairs = pairs + [(last_frame, values[0])]
        write_prop_curve(action, slot, prop_name, [f for f, _v in pairs], values)

    # guarantee a key at the loop boundary on every curve
    if loop:
        for fc in _all_fcurves(action, slot):
            if len(fc.keyframe_points) >= 2:
                first = fc.keyframe_points[0]
                last = fc.keyframe_points[-1]
                if abs(last.co.x - (start + frames)) > 1e-4:
                    last.co.x = start + frames

    _finish(arm, action, slot, loop)
    try:
        action["apex_motion"] = key
        action["apex_loop"] = bool(loop)
        action["apex_frames"] = int(frames)
    except Exception:
        pass
    utils.refresh(arm)
    return action


def get_motion_action(arm, key: str):
    for act in bpy.data.actions:
        if act.get("apex_motion") == key:
            return act
    return None


def next_free_frame(arm) -> float:
    """First frame after every strip already on the NLA."""
    ad = getattr(arm, "animation_data", None)
    if ad is None or not ad.nla_tracks:
        return 1.0
    ends = [strip.frame_end for tr in ad.nla_tracks for strip in tr.strips]
    return (max(ends) + 1.0) if ends else 1.0


def push_action_to_nla(arm, action, track_name: str | None = None,
                       start: float | None = None, blend: str = "REPLACE",
                       mute: bool = False, clear_active: bool = True):
    slot = action.slots[0] if len(action.slots) else utils.ensure_slot(action)
    rng = utils.action_range(action)
    if start is None:
        start = rng[0]
    strip = utils.add_nla_strip(arm, action, slot,
                                name=track_name or action.name,
                                blend=blend, start=start,
                                track_name=track_name or action.name,
                                mute=mute)
    try:
        strip.action_frame_start = rng[0]
        strip.action_frame_end = rng[1]
    except Exception:
        pass
    if clear_active:
        ad = getattr(arm, "animation_data", None)
        if ad is not None and ad.action is action:
            ad.action = None
    return strip


# ---------------------------------------------------------------------------
# Action utilities (used by operators/panels)
# ---------------------------------------------------------------------------
def retime_action(action, factor: float, origin: float | None = None) -> None:
    """Scale every key in time around *origin* (default: first key)."""
    curves = utils.action_fcurves(action)
    if not curves:
        return
    start = origin if origin is not None else min(fc.range()[0] for fc in curves)
    for fc in curves:
        for kp in fc.keyframe_points:
            kp.co.x = start + (kp.co.x - start) * factor
            kp.handle_left.x = start + (kp.handle_left.x - start) * factor
            kp.handle_right.x = start + (kp.handle_right.x - start) * factor
        fc.update()


def offset_action(action, frames: float) -> None:
    for fc in utils.action_fcurves(action):
        for kp in fc.keyframe_points:
            kp.co.x += frames
            kp.handle_left.x += frames
            kp.handle_right.x += frames
        fc.update()


MIRROR_X = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0)).to_4x4()


def _write_pose_matrices(arm, action, slot, frames, matrices, interpolation="LINEAR"):
    """Write armature-space pose matrices as local pose-bone channels."""
    bones = list(arm.pose.bones)
    depth = {pb.name: utils.bone_depth(pb) for pb in bones}
    ordered = sorted(matrices.keys(), key=lambda n: depth.get(n, 0))
    for name in ordered:
        pb = arm.pose.bones.get(name)
        if pb is None:
            continue
        rest = pb.bone.matrix_local
        rest_local = (pb.parent.bone.matrix_local.inverted() @ rest
                      if pb.parent is not None else rest)
        locs, quats = [], []
        prev = None
        for frame_index in range(len(frames)):
            pose_matrix = matrices[name][frame_index]
            parent_pose = (matrices[pb.parent.name][frame_index]
                           if pb.parent is not None and pb.parent.name in matrices
                           else (pb.parent.matrix if pb.parent is not None else None))
            if parent_pose is not None:
                basis = (parent_pose @ rest_local).inverted() @ pose_matrix
            else:
                basis = rest.inverted() @ pose_matrix
            locs.append(tuple(basis.translation))
            q = basis.to_quaternion()
            vals = (q.w, q.x, q.y, q.z)
            if prev is not None and sum(a * b for a, b in zip(prev, vals)) < 0.0:
                vals = tuple(-c for c in vals)
            prev = vals
            quats.append(vals)
        path = f'pose.bones["{name}"].'
        for i in range(3):
            utils.write_curve(action, slot, path + "location", i, frames,
                              [v[i] for v in locs], interpolation=interpolation)
        for i in range(4):
            utils.write_curve(action, slot, path + "rotation_quaternion", i, frames,
                              [v[i] for v in quats], interpolation=interpolation)


def _sample_action(arm, action, frames, slot=None):
    """Evaluate *action* and return {bone: [armature-space matrices]}."""
    ad = arm.animation_data or arm.animation_data_create()
    previous = ad.action
    ad.action = action
    try:
        if slot is not None:
            ad.action_slot = slot
    except Exception:
        pass
    scene = bpy.context.scene
    matrices = {pb.name: [] for pb in arm.pose.bones}
    for frame in frames:
        scene.frame_set(int(round(frame)))
        bpy.context.view_layer.update()
        for pb in arm.pose.bones:
            matrices[pb.name].append(pb.matrix.copy())
    ad.action = previous
    utils.refresh(arm)
    return matrices



def bake_pose_to_mesh(context, arm, suffix: str = "_Posed") -> list:
    """Freeze the current pose: one static mesh per skinned mesh, with the
    armature modifier applied (BlenRig's 'bake current pose to mesh')."""
    depsgraph = context.evaluated_depsgraph_get()
    depsgraph.update()
    out = []
    for mesh_obj in utils.meshes_of_armature(arm):
        evaluated = mesh_obj.evaluated_get(depsgraph)
        me = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True,
                                             depsgraph=depsgraph)
        new_obj = bpy.data.objects.new(mesh_obj.name + suffix, me)
        new_obj.matrix_world = mesh_obj.matrix_world.copy()
        targets = list(mesh_obj.users_collection) or [context.scene.collection]
        for coll in targets:
            coll.objects.link(new_obj)
        out.append(new_obj)
    return out


def bake_action(arm, action, name: str, frame_start: float, frame_end: float,
                step: float = 1.0, visual: bool = True):
    """Bake every pose bone of *arm* from *action* into a new editable action."""
    frames = []
    f = frame_start
    while f <= frame_end + 1e-6:
        frames.append(f)
        f += step
    if not frames:
        raise RuntimeError("Empty bake range")
    slot = action.slots[0] if len(action.slots) else None
    matrices = _sample_action(arm, action, frames, slot)
    if not visual:
        # non-visual bake keeps the local channels and only resamples them
        matrices = None
    new_action, new_slot = utils.new_action_for(arm, name)
    if matrices is not None:
        _write_pose_matrices(arm, new_action, new_slot, frames, matrices)
    try:
        new_action["apex_baked_from"] = action.name
    except Exception:
        pass
    ad = arm.animation_data
    ad.action = action
    utils.refresh(arm)
    return new_action


def mirror_action(arm, action, name: str = "", frame_offset: int = 0):
    """Create a mirrored copy of *action* (left <-> right, X negated)."""
    slot = action.slots[0] if len(action.slots) else None
    start, end = utils.action_range(action)
    frames = list(range(int(start), int(end) + 1))
    if not frames:
        raise RuntimeError("Action has no keys")
    matrices = _sample_action(arm, action, frames, slot)
    mirrored = {}
    for pb in arm.pose.bones:
        counterpart = utils.mirror_name(pb.name)
        if counterpart != pb.name and counterpart in matrices:
            mirrored[pb.name] = [MIRROR_X @ m @ MIRROR_X for m in matrices[counterpart]]
        else:
            mirrored[pb.name] = [MIRROR_X @ m @ MIRROR_X for m in matrices[pb.name]]
    new_name = name or (action.name + "_Mirror")
    new_action, new_slot = utils.new_action_for(arm, new_name)
    out_frames = [f + frame_offset for f in frames]
    _write_pose_matrices(arm, new_action, new_slot, out_frames, mirrored)

    # mirrored custom properties (IK/FK switches, pole angles, curls)
    bag = utils.action_channelbag(action, slot, create=False)
    if bag is not None:
        by_path = {}
        for fc in bag.fcurves:
            if fc.data_path.startswith('pose.bones["root"]["'):
                prop = fc.data_path.split('["')[-1].rstrip('"]')
                by_path[prop] = fc
        for prop, fc in by_path.items():
            target = prop[:-2] + (".R" if prop.endswith(".L") else ".L") \
                if prop.endswith((".L", ".R")) else prop
            frames_in = [kp.co.x + frame_offset for kp in fc.keyframe_points]
            values = [kp.co.y for kp in fc.keyframe_points]
            utils.write_curve(new_action, new_slot,
                              f'pose.bones["root"]["{target}"]', 0,
                              frames_in, values, interpolation="BEZIER")
    try:
        new_action["apex_mirrored_from"] = action.name
    except Exception:
        pass
    utils.refresh(arm)
    return new_action


def clear_animation(arm) -> None:
    arm.animation_data_clear()
    clear_pose_channels(arm)
    for pb in arm.pose.bones:
        for key in list(pb.keys()):
            if key in PROPS:
                pb[key] = PROPS[key][0]
    utils.refresh(arm)


def motion_preview_frames(arm):
    """Return {key: (action, start, end)} for every motion already built."""
    result = {}
    for act in bpy.data.actions:
        key = act.get("apex_motion")
        if not key:
            continue
        rng = utils.action_range(act)
        result[key] = (act, rng[0], rng[1])
    return result
