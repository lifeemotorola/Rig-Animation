# SPDX-License-Identifier: GPL-3.0-or-later
"""Apex Rig & Motion - facial rig.

A production-style FACS-ish face built on top of the Apex skeleton:

* 32 deform bones (jaw, chin, tongue, lips, corners, brows, lids, cheeks, nose,
  eyeballs) laid out automatically from the head bone, so they fit any head
  size / proportion the rig is built with.
* 26 animator-facing control properties that live on the ``root`` bone, exactly
  like the body controls, so they key, bake, retarget and export like any other
  channel.
* Spatial face weighting that carves the deformable face region out of a body
  mesh (mannequin or your own character) without disturbing the rest of the skin.
* Ten expressions authored from the controls (picture-selectable in the UI) and
  ``apply_expression`` / ``key_expression`` helpers.

Everything is plain data plus drivers, so it evaluates with auto-run disabled.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

from . import utils

FACE_VERSION = 1
FACE_KEY = "apex_face"
PROP_PREFIX = "face_"

# ---------------------------------------------------------------------------
# Control properties (stored on the root bone, like the body controls)
#   name: (default, min, max, soft_min, soft_max, description)
# ---------------------------------------------------------------------------
FACE_PROPS = {
    "jaw_open": (0.0, 0.0, 1.0, 0.0, 1.0, "Jaw open (0 = closed, 1 = wide)"),
    "jaw_side": (0.0, -1.0, 1.0, -1.0, 1.0, "Jaw slide left / right"),
    "jaw_thrust": (0.0, -1.0, 1.0, -1.0, 1.0, "Jaw forward / backward"),
    "chin_raise": (0.0, -1.0, 1.0, -1.0, 1.0, "Chin up / down"),
    "lip_up_raise": (0.0, 0.0, 1.0, 0.0, 1.0, "Upper lip raise (snarl)"),
    "lip_low_drop": (0.0, 0.0, 1.0, 0.0, 1.0, "Lower lip drop (open mouth)"),
    "lip_roll_up": (0.0, 0.0, 1.0, 0.0, 1.0, "Upper lip roll out"),
    "lip_roll_low": (0.0, 0.0, 1.0, 0.0, 1.0, "Lower lip roll out"),
    "mouth_smile.L": (0.0, 0.0, 1.0, 0.0, 1.0, "Mouth corner up (left)"),
    "mouth_smile.R": (0.0, 0.0, 1.0, 0.0, 1.0, "Mouth corner up (right)"),
    "mouth_frown.L": (0.0, 0.0, 1.0, 0.0, 1.0, "Mouth corner down (left)"),
    "mouth_frown.R": (0.0, 0.0, 1.0, 0.0, 1.0, "Mouth corner down (right)"),
    "mouth_pucker": (0.0, 0.0, 1.0, 0.0, 1.0, "Lips forward / pursed"),
    "mouth_stretch.L": (0.0, 0.0, 1.0, 0.0, 1.0, "Mouth stretch sideways (left)"),
    "mouth_stretch.R": (0.0, 0.0, 1.0, 0.0, 1.0, "Mouth stretch sideways (right)"),
    "cheek_raise.L": (0.0, 0.0, 1.0, 0.0, 1.0, "Cheek raise (left)"),
    "cheek_raise.R": (0.0, 0.0, 1.0, 0.0, 1.0, "Cheek raise (right)"),
    "brow_raise.L": (0.0, 0.0, 1.0, 0.0, 1.0, "Outer brow raise (left)"),
    "brow_raise.R": (0.0, 0.0, 1.0, 0.0, 1.0, "Outer brow raise (right)"),
    "brow_inner_up": (0.0, 0.0, 1.0, 0.0, 1.0, "Inner brow raise (sadness)"),
    "brow_furrow": (0.0, 0.0, 1.0, 0.0, 1.0, "Brow furrow (anger)"),
    "blink.L": (0.0, 0.0, 1.0, 0.0, 1.0, "Eyelid close (left)"),
    "blink.R": (0.0, 0.0, 1.0, 0.0, 1.0, "Eyelid close (right)"),
    "squint.L": (0.0, 0.0, 1.0, 0.0, 1.0, "Lower lid raise (left)"),
    "squint.R": (0.0, 0.0, 1.0, 0.0, 1.0, "Lower lid raise (right)"),
    "eye_look_x": (0.0, -1.0, 1.0, -1.0, 1.0, "Eyes look left / right"),
    "eye_look_y": (0.0, -1.0, 1.0, -1.0, 1.0, "Eyes look up / down"),
    "eye_converge": (0.0, 0.0, 1.0, 0.0, 1.0, "Eye convergence (focus near)"),
    "nose_wrinkle": (0.0, 0.0, 1.0, 0.0, 1.0, "Nose wrinkle (disgust)"),
    "nose_flare.L": (0.0, 0.0, 1.0, 0.0, 1.0, "Nostril flare (left)"),
    "nose_flare.R": (0.0, 0.0, 1.0, 0.0, 1.0, "Nostril flare (right)"),
    "tongue_out": (0.0, 0.0, 1.0, 0.0, 1.0, "Tongue out"),
}

# ---------------------------------------------------------------------------
# Bone layout
#   The head bone is the reference frame: ``u`` is its length (skull base ->
#   crown).  Positions are (x, y, z) in metres relative to that frame, scaled by
#   ``u / 0.175`` so the face fits any head size.
#   kind: "muscle" bones point up with local +Z facing backwards, so local
#   translation maps to world (side, up, -forward) for every bone.
# ---------------------------------------------------------------------------
_R = 1.0        # placeholder, positions below are already in *u* fractions


def _p(x, y, z):
    return Vector((x, y, z))


# name, parent, head, tail, deform, radius
FACE_BONES = [
    # hinge + mandible ------------------------------------------------
    ("jaw", "head", _p(0.0, 0.006, 0.079), _p(0.0, -0.042, 0.028), True, 0.030),
    ("chin", "jaw", _p(0.0, -0.060, 0.026), _p(0.0, -0.062, 0.042), True, 0.020),
    ("tongue", "jaw", _p(0.0, -0.034, 0.050), _p(0.0, -0.056, 0.044), True, 0.012),
    # lips -------------------------------------------------------------
    ("lip_up", "head", _p(0.0, -0.062, 0.070), _p(0.0, -0.064, 0.080), True, 0.013),
    ("lip_low", "jaw", _p(0.0, -0.062, 0.056), _p(0.0, -0.064, 0.046), True, 0.013),
    ("lip_up.L", "head", _p(0.016, -0.056, 0.070), _p(0.016, -0.058, 0.080), True, 0.010),
    ("lip_up.R", "head", _p(-0.016, -0.056, 0.070), _p(-0.016, -0.058, 0.080), True, 0.010),
    ("lip_low.L", "jaw", _p(0.016, -0.056, 0.056), _p(0.016, -0.058, 0.046), True, 0.010),
    ("lip_low.R", "jaw", _p(-0.016, -0.056, 0.056), _p(-0.016, -0.058, 0.046), True, 0.010),
    ("mouth_corner.L", "head", _p(0.030, -0.046, 0.062), _p(0.030, -0.050, 0.072), True, 0.013),
    ("mouth_corner.R", "head", _p(-0.030, -0.046, 0.062), _p(-0.030, -0.050, 0.072), True, 0.013),
    # brows -------------------------------------------------------------
    ("brow.L", "head", _p(0.030, -0.052, 0.104), _p(0.030, -0.054, 0.114), True, 0.012),
    ("brow.R", "head", _p(-0.030, -0.052, 0.104), _p(-0.030, -0.054, 0.114), True, 0.012),
    ("brow_in.L", "head", _p(0.012, -0.056, 0.106), _p(0.012, -0.058, 0.116), True, 0.010),
    ("brow_in.R", "head", _p(-0.012, -0.056, 0.106), _p(-0.012, -0.058, 0.116), True, 0.010),
    # eyelids ------------------------------------------------------------
    ("lid_up.L", "head", _p(0.030, -0.055, 0.090), _p(0.030, -0.057, 0.100), True, 0.012),
    ("lid_up.R", "head", _p(-0.030, -0.055, 0.090), _p(-0.030, -0.057, 0.100), True, 0.012),
    ("lid_low.L", "head", _p(0.030, -0.055, 0.076), _p(0.030, -0.057, 0.070), True, 0.010),
    ("lid_low.R", "head", _p(-0.030, -0.055, 0.076), _p(-0.030, -0.057, 0.070), True, 0.010),
    # cheeks / nose -------------------------------------------------------
    ("cheek.L", "head", _p(0.042, -0.036, 0.074), _p(0.042, -0.038, 0.084), True, 0.020),
    ("cheek.R", "head", _p(-0.042, -0.036, 0.074), _p(-0.042, -0.038, 0.084), True, 0.020),
    ("nose", "head", _p(0.0, -0.062, 0.084), _p(0.0, -0.064, 0.094), True, 0.014),
    ("nose_flare.L", "head", _p(0.014, -0.066, 0.076), _p(0.014, -0.068, 0.086), True, 0.010),
    ("nose_flare.R", "head", _p(-0.014, -0.066, 0.076), _p(-0.014, -0.068, 0.086), True, 0.010),
    # eyeballs (rotate the eye meshes) ------------------------------------
    ("eye.L", "head", _p(0.029, -0.050, 0.086), _p(0.029, -0.070, 0.086), True, 0.014),
    ("eye.R", "head", _p(-0.029, -0.050, 0.086), _p(-0.029, -0.070, 0.086), True, 0.014),
]

FACE_BONE_NAMES = [spec[0] for spec in FACE_BONES]
MUSCLE_BONES = [name for name in FACE_BONE_NAMES if not name.startswith("eye.")]
EYE_BONES = ("eye.L", "eye.R")

# how far above / below the head origin the face lives (in *u* fractions)
FACE_Z_LOW = 0.005
FACE_Z_HIGH = 0.125


# ---------------------------------------------------------------------------
# Layout maths
# ---------------------------------------------------------------------------
def _head_frame(arm) -> tuple[Vector, float, float]:
    """Return (head origin, scale, forward sign) for this armature."""
    bone = arm.data.bones.get("head")
    if bone is None:
        return Vector((0.0, 0.0, 1.5)), 1.0, -1.0
    origin = bone.head_local.copy()
    length = bone.length if bone.length > 1e-4 else 0.175
    scale = length / 0.175
    return origin, scale, -1.0     # characters face -Y in Apex


def face_positions(arm) -> dict[str, tuple[Vector, Vector]]:
    """World-space head/tail for every face bone."""
    origin, scale, front = _head_frame(arm)
    out = {}
    for name, _parent, head, tail, _deform, _radius in FACE_BONES:
        h = Vector((head.x * scale, front * abs(head.y) * scale, head.z * scale))
        t = Vector((tail.x * scale, front * abs(tail.y) * scale, tail.z * scale))
        out[name] = (origin + h, origin + t)
    return out


def has_face(arm) -> bool:
    return arm is not None and arm.data.bones.get("jaw") is not None and \
        arm.data.bones.get("lip_up") is not None


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------
def add_face_bones(arm, context=None) -> list[str]:
    """Add the facial bone set + controls to an existing Apex armature."""
    from .const import PROPS_BONE

    if has_face(arm):
        _ensure_props(arm)
        return list(FACE_BONE_NAMES)

    head = arm.data.bones.get("head")
    if head is None:
        raise RuntimeError("Face rig needs a 'head' bone")

    positions = face_positions(arm)
    utils.ensure_object_mode()
    utils.set_active(arm)
    bpy.ops.object.mode_set(mode="EDIT")
    edit_bones = arm.data.edit_bones
    created = {}
    # parents must exist first: iterative resolution
    pending = list(FACE_BONES)
    guard = 0
    while pending and guard < 100:
        guard += 1
        remaining = []
        for name, parent, _h, _t, deform, radius in pending:
            if parent not in ("head",) and parent not in created:
                remaining.append((name, parent, _h, _t, deform, radius))
                continue
            if name in edit_bones:
                created[name] = edit_bones[name]
                continue
            eb = edit_bones.new(name)
            eb.head, eb.tail = positions[name]
            eb.use_deform = bool(deform)
            eb.use_connect = False
            eb.parent = created.get(parent) or arm.data.edit_bones.get(parent)
            eb.head_radius = eb.tail_radius = max(1e-4, radius)
            if name.startswith("eye."):
                eb.align_roll(Vector((0.0, 0.0, 1.0)))
            elif name in ("jaw", "chin", "tongue", "lip_low", "lip_low.L", "lip_low.R"):
                eb.align_roll(Vector((0.0, 0.0, 1.0)))
            else:
                # muscles: +Y up, +Z backwards -> local (x, y, z) = (side, up, -forward)
                eb.align_roll(Vector((0.0, 1.0, 0.0)))
            created[name] = eb
        pending = remaining
    bpy.ops.object.mode_set(mode="OBJECT")

    _tag(arm)
    _ensure_props(arm)
    _setup_rotation_modes(arm)
    _setup_collection(arm)
    _setup_drivers(arm)
    _setup_locks(arm)
    arm[FACE_KEY] = FACE_VERSION
    utils.refresh(arm)
    return list(FACE_BONE_NAMES)


def _tag(arm) -> None:
    arm[FACE_KEY] = FACE_VERSION


def _ensure_props(arm) -> None:
    from .const import PROPS_BONE

    props_name = arm.get(PROPS_BONE + "_bone", PROPS_BONE)
    pb = arm.pose.bones.get(props_name)
    if pb is None:
        return
    for name, (default, mn, mx, smn, smx, desc) in FACE_PROPS.items():
        if name in pb.keys():
            continue
        utils.set_idprop(pb, name, float(default), minv=mn, maxv=mx,
                         soft_min=smn, soft_max=smx, description=desc)


def _setup_rotation_modes(arm) -> None:
    for name in FACE_BONE_NAMES:
        pb = arm.pose.bones.get(name)
        if pb is not None:
            pb.rotation_mode = "XYZ"


def _setup_collection(arm) -> None:
    coll = arm.data.collections.get("Face")
    if coll is None:
        coll = arm.data.collections.new("Face")
        try:
            coll.color_set = "THEME04"
        except Exception:
            pass
    for name in FACE_BONE_NAMES:
        bone = arm.data.bones.get(name)
        if bone is not None and name not in coll.bones:
            coll.assign(bone)


def _setup_locks(arm) -> None:
    for name in FACE_BONE_NAMES:
        pb = arm.pose.bones.get(name)
        if pb is None:
            continue
        pb.lock_scale = (True, True, True)
        if name.startswith("eye."):
            pb.lock_location = (True, True, True)


# ---------------------------------------------------------------------------
# Drivers: control properties -> bone channels
# ---------------------------------------------------------------------------
def _prop_bone(arm) -> str:
    from .const import PROPS_BONE

    return arm.get(PROPS_BONE + "_bone", PROPS_BONE)


def _drive(arm, bone, path, index, terms):
    """terms: list of (prop_name, factor). Multi-prop sums are supported."""
    pb = arm.pose.bones.get(bone)
    if pb is None:
        return
    variables = []
    expression = []
    for i, (prop, factor) in enumerate(terms):
        var = f"c{i}"
        variables.append((var, arm, utils.prop_bone_path(_prop_bone(arm), prop)))
        if abs(factor - 1.0) < 1e-9:
            expression.append(var)
        else:
            expression.append(f"{var}*{factor:.6f}")
    utils.add_driver(pb, path, index, "+".join(expression), variables)


def _setup_drivers(arm) -> None:
    U = 1.0 / 175.0        # metres per 0.175 m of head length, times ~1 cm units
    # Everything is expressed in metres of head length: 0.175 m head -> unit 1

    # jaw hinge: rotate about local X (chin swings down / back)
    _drive(arm, "jaw", "rotation_euler", 0, [("jaw_open", -0.42)])
    _drive(arm, "jaw", "rotation_euler", 2, [("jaw_side", 0.16)])
    _drive(arm, "jaw", "location", 2, [("jaw_thrust", -0.010)])

    # chin
    _drive(arm, "chin", "location", 1, [("chin_raise", 0.009), ("lip_low_drop", -0.006)])
    _drive(arm, "chin", "location", 2, [("chin_raise", -0.003)])

    # lips
    _drive(arm, "lip_up", "location", 1, [("lip_up_raise", 0.0080), ("jaw_open", -0.0020)])
    _drive(arm, "lip_up", "location", 2, [("lip_roll_up", 0.0050), ("mouth_pucker", 0.0060)])
    _drive(arm, "lip_low", "location", 1, [("lip_low_drop", -0.0105), ("jaw_open", 0.0040)])
    _drive(arm, "lip_low", "location", 2, [("lip_roll_low", 0.0050), ("mouth_pucker", 0.0055)])
    for side, suffix in (("L", ".L"), ("R", ".R")):
        _drive(arm, f"lip_up.{side}", "location", 1,
               [("lip_up_raise", 0.0045), (f"mouth_smile.{side}", 0.0020)])
        _drive(arm, f"lip_up.{side}", "location", 0,
               [(f"mouth_stretch.{side}", 0.0035), ("mouth_pucker", -0.0030)])
        _drive(arm, f"lip_low.{side}", "location", 1,
               [("lip_low_drop", -0.0060), (f"mouth_frown.{side}", -0.0030)])
        _drive(arm, f"lip_low.{side}", "location", 0,
               [(f"mouth_stretch.{side}", 0.0035), ("mouth_pucker", -0.0030)])

        # corners: up for smile, down for frown, forward for pucker
        sign = 1.0 if side == "L" else -1.0
        _drive(arm, f"mouth_corner.{side}", "location", 1,
               [(f"mouth_smile.{side}", 0.0095), (f"mouth_frown.{side}", -0.0075)])
        _drive(arm, f"mouth_corner.{side}", "location", 0,
               [(f"mouth_smile.{side}", 0.0030 * sign),
                (f"mouth_frown.{side}", -0.0015 * sign),
                ("mouth_pucker", -0.0045 * sign)])
        _drive(arm, f"mouth_corner.{side}", "location", 2,
               [("mouth_pucker", 0.0080)])

        # brows
        _drive(arm, f"brow.{side}", "location", 1,
               [(f"brow_raise.{side}", 0.0125), ("brow_furrow", -0.0045)])
        _drive(arm, f"brow_in.{side}", "location", 1,
               [("brow_inner_up", 0.0110), ("brow_furrow", -0.0058)])
        _drive(arm, f"brow_in.{side}", "location", 0, [("brow_furrow", -0.0030 * sign)])

        # eyelids
        _drive(arm, f"lid_up.{side}", "location", 1,
               [(f"blink.{side}", -0.0170), (f"squint.{side}", -0.0045)])
        _drive(arm, f"lid_low.{side}", "location", 1,
               [(f"squint.{side}", 0.0075), (f"blink.{side}", 0.0040)])

        # cheeks / nose wings
        _drive(arm, f"cheek.{side}", "location", 1,
               [(f"cheek_raise.{side}", 0.0105), (f"mouth_smile.{side}", 0.0055)])
        _drive(arm, f"cheek.{side}", "location", 0,
               [(f"mouth_smile.{side}", 0.0020 * sign)])
        _drive(arm, f"nose_flare.{side}", "location", 0,
               [(f"nose_flare.{side}", 0.0030 * sign)])
        _drive(arm, f"nose_flare.{side}", "location", 1,
               [("nose_wrinkle", 0.0025)])

    _drive(arm, "nose", "location", 1, [("nose_wrinkle", 0.0075)])
    _drive(arm, "nose", "location", 2, [("nose_wrinkle", -0.0020)])

    # tongue
    _drive(arm, "tongue", "location", 2, [("tongue_out", -0.0140)])
    _drive(arm, "tongue", "rotation_euler", 0, [("jaw_open", 0.12)])

    # eyeballs: local Y is the forward axis, so X = pitch, Z = yaw
    for side in ("L", "R"):
        sign = 1.0 if side == "L" else -1.0
        _drive(arm, f"eye.{side}", "rotation_euler", 2,
               [("eye_look_x", 0.60 * sign), ("eye_converge", 0.10 * sign)])
        _drive(arm, f"eye.{side}", "rotation_euler", 0,
               [("eye_look_y", -0.60)])


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------
def set_face(arm, values: dict) -> None:
    """Set facial control properties (unknown keys are ignored)."""
    from .const import PROPS_BONE

    pb = arm.pose.bones.get(_prop_bone(arm))
    if pb is None:
        return
    for name, value in values.items():
        if name not in FACE_PROPS or name not in pb.keys():
            continue
        default, mn, mx = FACE_PROPS[name][0], FACE_PROPS[name][1], FACE_PROPS[name][2]
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        pb[name] = max(mn, min(mx, value))


def get_face(arm) -> dict:
    pb = arm.pose.bones.get(_prop_bone(arm))
    if pb is None:
        return {}
    return {name: float(pb[name]) for name in FACE_PROPS if name in pb.keys()}


def reset_face(arm) -> None:
    set_face(arm, {name: spec[0] for name, spec in FACE_PROPS.items()})
    utils.refresh(arm)


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------
EXPRESSIONS = {
    "NEUTRAL": ("Neutral", {}),
    "SMILE": ("Smile", {
        "mouth_smile.L": 0.95, "mouth_smile.R": 0.95,
        "cheek_raise.L": 0.65, "cheek_raise.R": 0.65,
        "squint.L": 0.35, "squint.R": 0.35,
        "brow_raise.L": 0.15, "brow_raise.R": 0.15,
        "lip_up_raise": 0.18, "lip_low_drop": 0.12,
    }),
    "LAUGH": ("Laugh", {
        "mouth_smile.L": 1.0, "mouth_smile.R": 1.0,
        "cheek_raise.L": 0.95, "cheek_raise.R": 0.95,
        "jaw_open": 0.55, "lip_low_drop": 0.5, "lip_up_raise": 0.35,
        "squint.L": 0.75, "squint.R": 0.75,
        "blink.L": 0.35, "blink.R": 0.35,
        "brow_raise.L": 0.35, "brow_raise.R": 0.35,
    }),
    "ANGRY": ("Angry", {
        "brow_furrow": 1.0, "brow_inner_up": 0.15,
        "lip_up_raise": 0.4, "lip_low_drop": 0.25,
        "mouth_frown.L": 0.55, "mouth_frown.R": 0.55,
        "mouth_pucker": 0.35, "jaw_open": 0.12,
        "squint.L": 0.4, "squint.R": 0.4,
        "nose_wrinkle": 0.45,
    }),
    "SURPRISED": ("Surprised", {
        "brow_raise.L": 1.0, "brow_raise.R": 1.0, "brow_inner_up": 0.8,
        "jaw_open": 0.62, "lip_low_drop": 0.55, "lip_up_raise": 0.3,
        "blink.L": 0.0, "blink.R": 0.0,
    }),
    "SAD": ("Sad", {
        "brow_inner_up": 1.0, "mouth_frown.L": 0.8, "mouth_frown.R": 0.8,
        "chin_raise": -0.25, "lip_low_drop": 0.2,
        "eye_look_y": -0.35,
    }),
    "DISGUST": ("Disgust", {
        "nose_wrinkle": 1.0, "nose_flare.L": 0.6, "nose_flare.R": 0.6,
        "lip_up_raise": 0.85, "brow_furrow": 0.7,
        "mouth_frown.L": 0.4, "mouth_frown.R": 0.4, "squint.L": 0.5, "squint.R": 0.5,
    }),
    "WINK": ("Wink", {
        "blink.L": 1.0, "squint.L": 0.6,
        "mouth_smile.L": 0.7, "mouth_smile.R": 0.45,
        "brow_raise.L": 0.5, "cheek_raise.L": 0.5,
    }),
    "KISS": ("Kiss", {
        "mouth_pucker": 1.0, "lip_roll_up": 0.6, "lip_roll_low": 0.6,
        "jaw_open": 0.08, "cheek_raise.L": 0.3, "cheek_raise.R": 0.3,
        "brow_raise.L": 0.2, "brow_raise.R": 0.2,
    }),
    "SHOUT": ("Shout", {
        "jaw_open": 0.85, "lip_low_drop": 0.7, "lip_up_raise": 0.45,
        "mouth_stretch.L": 0.7, "mouth_stretch.R": 0.7,
        "brow_furrow": 0.8, "brow_raise.L": 0.3, "brow_raise.R": 0.3,
        "squint.L": 0.35, "squint.R": 0.35,
    }),
    "TALK": ("Talk", {
        "jaw_open": 0.28, "lip_low_drop": 0.25, "mouth_stretch.L": 0.25,
        "mouth_stretch.R": 0.25, "lip_up_raise": 0.1,
        "brow_raise.L": 0.1, "brow_raise.R": 0.1,
    }),
}

EXPRESSION_ORDER = list(EXPRESSIONS.keys())


def apply_expression(arm, key: str) -> None:
    if key not in EXPRESSIONS:
        raise KeyError(f"Unknown expression '{key}'")
    reset_face(arm)
    set_face(arm, EXPRESSIONS[key][1])
    utils.refresh(arm)


def key_expression(arm, key: str, frame: float | None = None, name: str | None = None):
    """Apply an expression and key every face control into a new action."""
    frame = bpy.context.scene.frame_current if frame is None else frame
    label = EXPRESSIONS[key][0] if key in EXPRESSIONS else key
    apply_expression(arm, key)
    action = bpy.data.actions.new(utils.unique_name(name or f"Apex_Face_{label}",
                                                   bpy.data.actions))
    action.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = action
    try:
        arm.animation_data.action_slot = action.slots[0] if action.slots else \
            action.slots.new(id_type="OBJECT", name=arm.name)
    except Exception:
        pass
    pb = arm.pose.bones.get(_prop_bone(arm))
    if pb is not None:
        for prop in FACE_PROPS:
            if prop in pb.keys():
                pb.keyframe_insert(data_path=f'["{prop}"]', frame=frame)
    return action


# ---------------------------------------------------------------------------
# Eyes
# ---------------------------------------------------------------------------
def add_eyes(context, arm, radius: float | None = None) -> list[bpy.types.Object]:
    """Build two eyeballs bound to the ``eye.L`` / ``eye.R`` bones."""
    if not has_face(arm):
        raise RuntimeError("Add the face rig before the eyes")
    positions = face_positions(arm)
    origin, scale, front = _head_frame(arm)
    radius = radius or 0.0132 * scale
    made = []
    for side in ("L", "R"):
        name = f"ApexEye.{side}"
        old = bpy.data.objects.get(name)
        if old is not None:
            bpy.data.objects.remove(old, do_unlink=True)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32,
                                             radius=radius, location=(0, 0, 0))
        eye = context.view_layer.objects.active
        eye.name = name
        eye.data.name = name
        for poly in eye.data.polygons:
            poly.use_smooth = True
        _eye_materials(eye)
        head, _tail = positions[f"eye.{side}"]
        eye.location = head
        eye.parent = arm
        eye.matrix_parent_inverse = arm.matrix_world.inverted()
        group = eye.vertex_groups.new(name=f"eye.{side}")
        group.add(list(range(len(eye.data.vertices))), 1.0, "REPLACE")
        mod = eye.modifiers.new("Apex Eyes", "ARMATURE")
        mod.object = arm
        mod.use_deform_preserve_volume = False
        eye["apex_eye"] = side
        made.append(eye)
    utils.set_active(arm)
    return made


def _eye_materials(eye) -> None:
    sclera = bpy.data.materials.get("Apex Eye White")
    if sclera is None:
        sclera = bpy.data.materials.new("Apex Eye White")
        sclera.use_nodes = True
        bsdf = sclera.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.92, 0.90, 0.88, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.32
    iris = bpy.data.materials.get("Apex Iris")
    if iris is None:
        iris = bpy.data.materials.new("Apex Iris")
        iris.use_nodes = True
        bsdf = iris.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.16, 0.10, 0.055, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.18
    pupil = bpy.data.materials.get("Apex Pupil")
    if pupil is None:
        pupil = bpy.data.materials.new("Apex Pupil")
        pupil.use_nodes = True
        bsdf = pupil.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.01, 0.01, 0.01, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.1
    eye.data.materials.append(sclera)
    eye.data.materials.append(iris)
    eye.data.materials.append(pupil)
    for poly in eye.data.polygons:
        direction = poly.center.normalized()
        # angle away from the forward (-Y) axis decides sclera / iris / pupil
        angle = math.degrees(math.acos(max(-1.0, min(1.0, -direction.y))))
        if angle < 11.0:
            poly.material_index = 2          # pupil
        elif angle < 30.0:
            poly.material_index = 1          # iris


# ---------------------------------------------------------------------------
# Weighting
# ---------------------------------------------------------------------------
def face_weight_region(arm) -> tuple[float, float, float]:
    """(z_low, z_high, radius) of the deformable face region."""
    origin, scale, _front = _head_frame(arm)
    return (origin.z + FACE_Z_LOW * scale, origin.z + FACE_Z_HIGH * scale,
            0.062 * scale)


def apply_face_weights(mesh_obj, arm, strength: float = 1.0) -> dict:
    """Carve face weights out of the body weights.

    Vertices close to a face muscle get an inverse-distance blend of the face
    bones, feathered into their existing head/neck weights so there is no seam.
    """
    import numpy as np

    from . import deform, skin

    if not has_face(arm) or mesh_obj is None or mesh_obj.type != "MESH":
        return {"verts": 0, "face_verts": 0}

    names = [b.name for b in arm.data.bones if b.use_deform]
    matrix = deform._read_weights(mesh_obj, names)
    lookup = {name: i for i, name in enumerate(names)}

    mesh_co = np.empty(len(mesh_obj.data.vertices) * 3, dtype=np.float64)
    mesh_obj.data.vertices.foreach_get("co", mesh_co)
    mesh_co = mesh_co.reshape(-1, 3)
    world = np.array(mesh_obj.matrix_world)
    arm_world = np.array(arm.matrix_world)
    if not np.allclose(world, arm_world):
        to_arm = np.linalg.inv(arm_world) @ world
        co = mesh_co @ to_arm[:3, :3].T + to_arm[:3, 3]
    else:
        co = mesh_co

    positions = face_positions(arm)
    origin, scale, _front = _head_frame(arm)
    z_low, z_high, radius = face_weight_region(arm)
    muscles = [name for name in MUSCLE_BONES if name in lookup]
    if not muscles:
        return {"verts": len(co), "face_verts": 0}

    # distance to every muscle bone (segment distance on tiny bones is fine)
    distances = np.empty((len(co), len(muscles)), dtype=np.float32)
    for idx, name in enumerate(muscles):
        head, tail = positions[name]
        d, _t = skin._dist_to_segment(co, np.array(head[:]), np.array(tail[:]))
        distances[:, idx] = d

    nearest = distances.min(axis=1)
    in_zone = (co[:, 2] > z_low) & (co[:, 2] < z_high) & \
              (np.abs(co[:, 0]) < radius * 1.9) & \
              (co[:, 1] < origin.y + 0.02 * scale)

    # a single mask drives everything: distance to the nearest muscle, faded
    # out above the brow and below the jawline, and only on the front of the head
    low, high = 0.006 * scale, 0.032 * scale
    mask_all = np.clip((high - nearest) / max(high - low, 1e-6), 0.0, 1.0) ** 1.4
    # long, smooth gradients: a short ramp across a ~1.7 cm voxel mesh tears
    fade_low = origin.z + 0.030 * scale
    fade_high = origin.z + 0.070 * scale
    vertical = np.clip((co[:, 2] - fade_low) / max(fade_high - fade_low, 1e-6), 0.0, 1.0)
    vertical = vertical * vertical * (3.0 - 2.0 * vertical)      # smoothstep
    frontal = np.clip((origin.y + 0.020 * scale - co[:, 1]) / (0.060 * scale), 0.0, 1.0)
    frontal = 0.35 + 0.65 * frontal
    mask_all *= vertical * frontal * float(strength)
    mask_all[~in_zone] = 0.0

    # (1) strip face weights the generic pass may have put outside the face,
    #     which is what used to drag the neck along with the jaw
    for name in MUSCLE_BONES:
        if name in lookup:
            matrix[:, lookup[name]] *= mask_all

    face_verts = np.where(mask_all > 0.02)[0]
    if len(face_verts):
        d = distances[face_verts]
        influence = 1.0 / np.maximum(d, 0.0025 * scale) ** 2.4
        influence *= (d < 0.038 * scale)
        total = influence.sum(axis=1)
        safe = total > 0
        influence[safe] /= total[safe, None]
        mask = mask_all[face_verts]
        matrix[face_verts] *= (1.0 - mask)[:, None]
        xs = co[face_verts, 0]
        zs = co[face_verts, 2]
        # the mandible lets go at the jaw angle so the cheek and ear do not tear
        lateral = np.clip((0.047 * scale + origin.x - np.abs(xs)) / (0.013 * scale),
                          0.0, 1.0)
        jaw_family = {"jaw", "chin", "tongue", "lip_low", "lip_low.L", "lip_low.R"}
        for idx, name in enumerate(muscles):
            col = lookup[name]
            weight = influence[:, idx] * mask
            if name in jaw_family:
                weight = weight * lateral
            matrix[face_verts, col] += weight

    # head verts not driven by the face keep a full head weight
    if "head" in lookup:
        orphan = matrix.sum(axis=1) <= 1e-6
        matrix[orphan, lookup["head"]] = 1.0

    # keep 4 influences and normalise
    order = np.argsort(-matrix, axis=1)[:, :4]
    pruned = np.zeros_like(matrix)
    rows = np.arange(len(matrix))
    for slot in range(order.shape[1]):
        pruned[rows, order[:, slot]] = matrix[rows, order[:, slot]]
    sums = pruned.sum(axis=1, keepdims=True)
    sums[sums <= 1e-9] = 1.0
    pruned /= sums
    # local Laplacian smoothing inside the face zone: removes creases where
    # neighbouring muscles meet without touching the rest of the body
    try:
        from . import deform as _deform
        edges = _deform._edges_array(mesh_obj) if hasattr(_deform, "_edges_array") else None
        if edges is not None and len(edges):
            face_set = np.zeros(len(pruned), dtype=bool)
            face_set[face_verts] = True
            for _ in range(3):
                a, b = edges[:, 0], edges[:, 1]
                keep = face_set[a] & face_set[b]
                if not keep.any():
                    break
                acc = pruned.copy()
                np.add.at(acc, a[keep], pruned[b[keep]])
                np.add.at(acc, b[keep], pruned[a[keep]])
                counts = np.ones(len(pruned))
                np.add.at(counts, a[keep], 1.0)
                np.add.at(counts, b[keep], 1.0)
                smoothed = acc / counts[:, None]
                blend = 0.5
                pruned[face_set] = (1.0 - blend) * pruned[face_set] + \
                    blend * smoothed[face_set]
                sums2 = pruned.sum(axis=1, keepdims=True)
                sums2[sums2 <= 1e-9] = 1.0
                pruned /= sums2
    except Exception as exc:
        utils.log.debug("face weight smoothing skipped: %s", exc)

    skin._assign_weights(mesh_obj, names, pruned)
    return {"verts": int(len(co)), "face_verts": int(len(face_verts)),
            "muscles": len(muscles)}


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def face_report(arm, mesh_obj=None) -> dict:
    info = {
        "bones": len(FACE_BONE_NAMES),
        "muscles": len(MUSCLE_BONES),
        "controls": len(FACE_PROPS),
        "expressions": len(EXPRESSIONS),
        "eyes": [ob.name for ob in bpy.data.objects if ob.get("apex_eye")],
    }
    if mesh_obj is not None and has_face(arm):
        from . import deform
        names = [b.name for b in arm.data.bones if b.use_deform]
        matrix = deform._read_weights(mesh_obj, names)
        lookup = {name: i for i, name in enumerate(names)}
        empty = [name for name in MUSCLE_BONES
                 if name in lookup and float(matrix[:, lookup[name]].max(initial=0.0)) < 0.02]
        info["muscles_without_weights"] = empty
    return info

def add_mouth_interior(context, arm):
    """A dark mouth cavity, revealed when the jaw opens."""
    if not has_face(arm):
        return None
    origin, scale, front = _head_frame(arm)
    name = "ApexMouth"
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=1.0,
                                         location=(0, 0, 0))
    mouth = context.view_layer.objects.active
    mouth.name = name
    mouth.data.name = name
    mouth.scale = (0.0125 * scale, 0.0075 * scale, 0.0095 * scale)
    mouth.location = (origin.x, origin.y + front * 0.0565 * scale,
                      origin.z + 0.0640 * scale)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=True)
    for poly in mouth.data.polygons:
        poly.use_smooth = True
    mat = bpy.data.materials.get("Apex Mouth Interior")
    if mat is None:
        mat = bpy.data.materials.new("Apex Mouth Interior")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.055, 0.012, 0.014, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.55
    mouth.data.materials.append(mat)
    mouth.parent = arm
    mouth.matrix_parent_inverse = arm.matrix_world.inverted()
    group = mouth.vertex_groups.new(name="head")
    group.add(list(range(len(mouth.data.vertices))), 1.0, "REPLACE")
    mod = mouth.modifiers.new("Apex Mouth", "ARMATURE")
    mod.object = arm
    mouth["apex_mouth"] = True
    utils.set_active(arm)
    return mouth
