# SPDX-License-Identifier: GPL-3.0-or-later
"""Apex Rig & Motion - pose library and posing primitives.

Poses are authored the way an animator thinks: *aim* an arm at a direction,
drop the hips, keep the feet planted (IK), curl the fingers.  Every pose is a
plain function of the rig, so it works on any proportion, any scale and any
naming, and can be keyed into an action afterwards.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Quaternion, Vector

from . import utils

DEG = math.pi / 180.0


# ---------------------------------------------------------------------------
# Posing primitives
# ---------------------------------------------------------------------------
def aim_bone(arm, bone_name: str, direction, roll_hint=None) -> None:
    """Rotate a bone in world space so it points along *direction*."""
    pb = arm.pose.bones.get(bone_name)
    if pb is None:
        return
    target = Vector(direction)
    if target.length < 1e-8:
        return
    target.normalize()
    current = (pb.tail - pb.head)
    if current.length < 1e-8:
        return
    rotation = current.normalized().rotation_difference(target)
    matrix = pb.matrix.copy()
    rotated = (rotation.to_matrix().to_4x4() @ matrix.to_3x3().to_4x4())
    if roll_hint is not None:
        # align the bone's local Z with the hint as closely as possible
        hint = Vector(roll_hint).normalized()
        x_axis = rotated.col[0].to_3d()
        z_axis = x_axis.cross(target).normalized()
        if hint.dot(z_axis) < 0:
            z_axis = -z_axis
    pb.matrix = Matrix.Translation(matrix.translation) @ rotated
    bpy.context.view_layer.update()


def rotate_bone(arm, bone_name: str, axis, degrees: float) -> None:
    """Rotate a bone around a world axis (about its own head)."""
    pb = arm.pose.bones.get(bone_name)
    if pb is None:
        return
    matrix = pb.matrix.copy()
    rotation = Matrix.Rotation(degrees * DEG, 4, Vector(axis).normalized())
    pb.matrix = (Matrix.Translation(matrix.translation) @ rotation
                 @ Matrix.Translation(-matrix.translation) @ matrix)
    bpy.context.view_layer.update()


def move_bone(arm, bone_name: str, offset) -> None:
    pb = arm.pose.bones.get(bone_name)
    if pb is None:
        return
    matrix = pb.matrix.copy()
    matrix.translation = matrix.translation + Vector(offset)
    pb.matrix = matrix
    bpy.context.view_layer.update()


def place_bone_head(arm, bone_name: str, position) -> None:
    pb = arm.pose.bones.get(bone_name)
    if pb is None:
        return
    matrix = pb.matrix.copy()
    matrix.translation = Vector(position)
    pb.matrix = matrix
    bpy.context.view_layer.update()


def rest_head(arm, bone_name: str) -> Vector:
    bone = arm.data.bones.get(bone_name)
    return (arm.matrix_world @ bone.head_local) if bone else Vector()


def foot_home(arm, side: str) -> Vector:
    """World position of where a foot rests on the floor."""
    bone = arm.data.bones.get(f"foot_ik.{side}")
    if bone is None:
        return Vector()
    return arm.matrix_world @ bone.head_local


# ---------------------------------------------------------------------------
# Pose definitions
# ---------------------------------------------------------------------------
def _set_props(arm, values: dict) -> None:
    props = arm.pose.bones.get("root")
    if props is None:
        return
    for key, value in values.items():
        if key in props.keys():
            props[key] = value


def pose_rest(arm) -> None:
    pass


def pose_tpose(arm) -> None:
    props = arm.pose.bones.get("root")
    if props is not None:
        props["ik_arm.L"] = 0.0
        props["ik_arm.R"] = 0.0
    utils.refresh(arm)
    for side, sign in (("L", 1.0), ("R", -1.0)):
        aim_bone(arm, f"upper_arm.{side}", (sign, 0.0, 0.0))
        aim_bone(arm, f"forearm.{side}", (sign, 0.0, 0.0))
        aim_bone(arm, f"hand.{side}", (sign, 0.0, 0.0))
        _set_props(arm, {f"finger_spread.{side}": 0.25})


def pose_relaxed(arm) -> None:
    """Natural stand: arms slightly in, fingers softly curled."""
    props = arm.pose.bones.get("root")
    if props is not None:
        props["ik_arm.L"] = 0.0
        props["ik_arm.R"] = 0.0
    utils.refresh(arm)
    for side, sign in (("L", 1.0), ("R", -1.0)):
        aim_bone(arm, f"upper_arm.{side}", (sign * 0.30, 0.03, -1.0))
        aim_bone(arm, f"forearm.{side}", (sign * 0.16, -0.28, -1.0))
        aim_bone(arm, f"hand.{side}", (sign * 0.10, -0.32, -1.0))
    for side in ("L", "R"):
        _set_props(arm, {f"finger_curl.{side}": 0.28, f"thumb_curl.{side}": 0.2})
    _set_props(arm, {"finger_spread.L": 0.05, "finger_spread.R": 0.05})


def pose_combat(arm) -> None:
    """Boxing guard: hips turned, arms up, knees loaded."""
    props = arm.pose.bones.get("root")
    if props is not None:
        props["ik_leg.L"] = 1.0
        props["ik_leg.R"] = 1.0
        props["ik_arm.L"] = 0.0
        props["ik_arm.R"] = 0.0
    utils.refresh(arm)
    move_bone(arm, "cog", (0.0, 0.0, -0.14))
    rotate_bone(arm, "cog", (0, 0, 1), -14.0)
    rotate_bone(arm, "spine_01", (0, 0, 1), 8.0)
    rotate_bone(arm, "spine_02", (0, 0, 1), 10.0)
    rotate_bone(arm, "chest", (0, 0, 1), 8.0)
    rotate_bone(arm, "head", (0, 0, 1), 14.0)
    # stagger the feet
    left = foot_home(arm, "L")
    right = foot_home(arm, "R")
    place_bone_head(arm, "foot_ik.L", left + Vector((0.03, -0.20, 0.0)))
    place_bone_head(arm, "foot_ik.R", right + Vector((-0.02, 0.16, 0.0)))
    # guard
    for side, sign in (("L", 1.0), ("R", -1.0)):
        aim_bone(arm, f"upper_arm.{side}", (sign * 0.30, -0.55, -0.75))
        aim_bone(arm, f"forearm.{side}", (-sign * 0.35, -0.55, 0.75))
        aim_bone(arm, f"hand.{side}", (-sign * 0.30, -0.75, 0.55))
        _set_props(arm, {f"finger_curl.{side}": 0.95, f"thumb_curl.{side}": 0.85,
                         f"finger_spread.{side}": 0.0})


def pose_crouch(arm) -> None:
    """Deep crouch with the feet planted and the arms forward for balance."""
    props = arm.pose.bones.get("root")
    if props is not None:
        props["ik_leg.L"] = 1.0
        props["ik_leg.R"] = 1.0
        props["ik_arm.L"] = 0.0
        props["ik_arm.R"] = 0.0
    utils.refresh(arm)
    move_bone(arm, "cog", (0.0, 0.10, -0.24))
    rotate_bone(arm, "spine_01", (1, 0, 0), -14.0)
    rotate_bone(arm, "spine_02", (1, 0, 0), -10.0)
    rotate_bone(arm, "chest", (1, 0, 0), -6.0)
    rotate_bone(arm, "head", (1, 0, 0), 26.0)
    for side, sign in (("L", 1.0), ("R", -1.0)):
        aim_bone(arm, f"upper_arm.{side}", (sign * 0.42, -0.85, -0.35))
        aim_bone(arm, f"forearm.{side}", (sign * 0.18, -0.95, 0.25))
        aim_bone(arm, f"hand.{side}", (sign * 0.1, -0.9, 0.42))
        _set_props(arm, {f"finger_curl.{side}": 0.45})


def pose_jump(arm) -> None:
    """Airborne: hips up, knees tucked, arms reaching up."""
    props = arm.pose.bones.get("root")
    if props is not None:
        props["ik_leg.L"] = 1.0
        props["ik_leg.R"] = 1.0
        props["ik_arm.L"] = 0.0
        props["ik_arm.R"] = 0.0
    utils.refresh(arm)
    move_bone(arm, "cog", (0.0, 0.0, 0.34))
    rotate_bone(arm, "spine_01", (1, 0, 0), 6.0)
    rotate_bone(arm, "head", (1, 0, 0), -10.0)
    for side in ("L", "R"):
        home = foot_home(arm, side)
        place_bone_head(arm, f"foot_ik.{side}",
                        home + Vector((0.0, -0.06, 0.34)))
    for side, sign in (("L", 1.0), ("R", -1.0)):
        aim_bone(arm, f"upper_arm.{side}", (sign * 0.55, -0.35, 1.0))
        aim_bone(arm, f"forearm.{side}", (sign * 0.25, -0.20, 1.0))
        aim_bone(arm, f"hand.{side}", (sign * 0.2, -0.3, 1.0))
        _set_props(arm, {f"finger_spread.{side}": 0.6})


def pose_wave(arm) -> None:
    """Friendly wave: right arm up, head tilted."""
    props = arm.pose.bones.get("root")
    if props is not None:
        props["ik_arm.L"] = 0.0
        props["ik_arm.R"] = 0.0
        props["ik_leg.L"] = 1.0
        props["ik_leg.R"] = 1.0
    utils.refresh(arm)
    aim_bone(arm, "upper_arm.L", (0.45, -0.20, -1.0))
    aim_bone(arm, "forearm.L", (0.30, -0.45, -1.0))
    aim_bone(arm, "hand.L", (0.25, -0.5, -1.0))
    aim_bone(arm, "upper_arm.R", (-0.55, -0.25, 1.0))
    aim_bone(arm, "forearm.R", (-0.35, -0.10, 1.0))
    aim_bone(arm, "hand.R", (-0.55, -0.10, 1.0))
    rotate_bone(arm, "head", (0, 0, 1), -12.0)
    _set_props(arm, {"finger_spread.R": 0.85, "finger_curl.R": 0.0,
                     "thumb_curl.R": 0.15, "finger_curl.L": 0.3})


def pose_hero_landing(arm) -> None:
    """Superhero landing: one knee down, one fist to the ground."""
    props = arm.pose.bones.get("root")
    if props is not None:
        props["ik_leg.L"] = 1.0
        props["ik_leg.R"] = 1.0
        props["ik_arm.L"] = 0.0
        props["ik_arm.R"] = 1.0
    utils.refresh(arm)
    move_bone(arm, "cog", (0.0, 0.08, -0.40))
    rotate_bone(arm, "spine_01", (1, 0, 0), -18.0)
    rotate_bone(arm, "spine_02", (1, 0, 0), -12.0)
    rotate_bone(arm, "head", (1, 0, 0), 34.0)
    left = foot_home(arm, "L")
    right = foot_home(arm, "R")
    place_bone_head(arm, "foot_ik.L", left + Vector((0.16, -0.30, 0.0)))
    place_bone_head(arm, "foot_ik.R", right + Vector((-0.10, 0.42, 0.0)))
    rotate_bone(arm, "toe_ik.R", (1, 0, 0), -38.0)
    # right fist to the floor
    fist = arm.matrix_world @ Vector((-0.30, -0.34, 0.14))
    place_bone_head(arm, "hand_ik.R", fist)
    aim_bone(arm, "hand.R", (0.2, -0.5, -1.0))
    # left arm back for balance
    aim_bone(arm, "upper_arm.L", (0.85, 0.35, 0.25))
    aim_bone(arm, "forearm.L", (0.65, 0.75, 0.05))
    _set_props(arm, {"finger_curl.R": 0.95, "thumb_curl.R": 0.9,
                     "finger_curl.L": 0.6})


def pose_sit(arm) -> None:
    """Seated on an invisible ledge - hips back, knees at 90 degrees."""
    props = arm.pose.bones.get("root")
    if props is not None:
        props["ik_leg.L"] = 1.0
        props["ik_leg.R"] = 1.0
        props["ik_arm.L"] = 0.0
        props["ik_arm.R"] = 0.0
    utils.refresh(arm)
    move_bone(arm, "cog", (0.0, 0.14, -0.30))
    rotate_bone(arm, "pelvis", (1, 0, 0), -6.0)
    rotate_bone(arm, "spine_01", (1, 0, 0), -4.0)
    for side in ("L", "R"):
        home = foot_home(arm, side)
        place_bone_head(arm, f"foot_ik.{side}",
                        home + Vector((0.0, -0.34, 0.0)))
    for side, sign in (("L", 1.0), ("R", -1.0)):
        aim_bone(arm, f"upper_arm.{side}", (sign * 0.35, -0.25, -1.0))
        aim_bone(arm, f"forearm.{side}", (sign * 0.15, -0.85, -0.35))
        aim_bone(arm, f"hand.{side}", (sign * 0.1, -0.95, -0.1))
        _set_props(arm, {f"finger_curl.{side}": 0.35})


def pose_look_back(arm) -> None:
    """Over-the-shoulder look, weight on one leg."""
    props = arm.pose.bones.get("root")
    if props is not None:
        props["ik_leg.L"] = 1.0
        props["ik_leg.R"] = 1.0
        props["ik_arm.L"] = 0.0
        props["ik_arm.R"] = 0.0
    utils.refresh(arm)
    move_bone(arm, "cog", (0.05, 0.0, -0.05))
    rotate_bone(arm, "pelvis", (0, 0, 1), 10.0)
    rotate_bone(arm, "spine_01", (0, 0, 1), 16.0)
    rotate_bone(arm, "spine_02", (0, 0, 1), 16.0)
    rotate_bone(arm, "chest", (0, 0, 1), 14.0)
    rotate_bone(arm, "neck", (0, 0, 1), 18.0)
    rotate_bone(arm, "head", (0, 0, 1), 26.0)
    rotate_bone(arm, "head", (1, 0, 0), -6.0)
    for side, sign in (("L", 1.0), ("R", -1.0)):
        aim_bone(arm, f"upper_arm.{side}", (sign * 0.35, 0.05, -1.0))
        aim_bone(arm, f"forearm.{side}", (sign * 0.25, -0.35, -1.0))
        _set_props(arm, {f"finger_curl.{side}": 0.3})


POSE_LIBRARY = {
    "A_POSE": ("A-Pose (rest)", pose_rest),
    "T_POSE": ("T-Pose", pose_tpose),
    "RELAXED": ("Relaxed Stand", pose_relaxed),
    "COMBAT": ("Combat Guard", pose_combat),
    "CROUCH": ("Crouch", pose_crouch),
    "JUMP": ("Jump", pose_jump),
    "WAVE": ("Wave", pose_wave),
    "HERO": ("Hero Landing", pose_hero_landing),
    "SIT": ("Seated", pose_sit),
    "LOOK_BACK": ("Look Back", pose_look_back),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def clear_pose(arm) -> None:
    from .animation import clear_pose_channels
    from .const import PROPS

    clear_pose_channels(arm)
    props = arm.pose.bones.get("root")
    if props is not None:
        for name, spec in PROPS.items():
            if name not in props.keys():
                continue
            keep = name.startswith("pole_angle")
            if keep:
                continue          # pole angles are rig-specific: leave them
            props[name] = spec[0]
    utils.refresh(arm)


def apply_pose(rig, key: str, reset: bool = True) -> None:
    """Apply a library pose to an Apex rig (``rig`` is a Rig or an armature)."""
    arm = getattr(rig, "obj", rig)
    if key not in POSE_LIBRARY:
        raise KeyError(f"Unknown pose '{key}'")
    if reset:
        clear_pose(arm)
    POSE_LIBRARY[key][1](arm)
    utils.refresh(arm)


def pose_names():
    return [(key, label) for key, (label, _fn) in POSE_LIBRARY.items()]


def key_pose(rig, key: str, frame: float | None = None, name: str | None = None):
    """Apply a pose and key every control into a new action."""
    arm = getattr(rig, "obj", rig)
    from . import rig as rigmod

    apply_pose(arm, key, reset=True)
    frame = bpy.context.scene.frame_current if frame is None else frame
    label = POSE_LIBRARY[key][0]
    from .const import PROPS

    action = bpy.data.actions.new(utils.unique_name(name or f"Apex_Pose_{label}",
                                                   bpy.data.actions))
    action.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = action
    slot = utils.ensure_slot(action, id_type="OBJECT", name=arm.name)
    arm.animation_data.action_slot = slot
    for pb in arm.pose.bones:
        pb.keyframe_insert("location", frame=frame, group=pb.name)
        if pb.rotation_mode == "QUATERNION":
            pb.keyframe_insert("rotation_quaternion", frame=frame, group=pb.name)
        else:
            pb.keyframe_insert("rotation_euler", frame=frame, group=pb.name)
    props = arm.pose.bones.get("root")
    if props is not None:
        for prop in PROPS:
            if prop in props.keys():
                props.keyframe_insert(f'["{prop}"]', frame=frame, group="Apex Props")
    return action
