# SPDX-License-Identifier: GPL-3.0-or-later
"""Apex Rig & Motion - constant data.

Everything user-visible (names, palettes, presets, motion catalogue) lives here
so the rest of the code stays declarative.
"""
from __future__ import annotations

ADDON_NAME = "Apex Rig & Motion"
ADDON_ID = "apex_rig"
VERSION = (1, 0, 0)
VERSION_STRING = "1.2.0"

RIG_ID_KEY = "apex_rig"          # marks an armature as an Apex rig
RIG_VERSION_KEY = "apex_version"
PROPS_BONE = "root"              # bone that stores all animator-facing properties
NAME_MAP_KEY = "apex_name_map"   # json canonical -> current bone name (after renaming)

WIDGET_PREFIX = "WGT-Apex-"
WIDGET_COLLECTION = "Apex Widgets"
RIG_NAME = "ApexRig"

# ---------------------------------------------------------------------------
# Bone display colors (theme palette indices, 1-20)
#   1 = red, 2 = orange, 3 = green, 4 = blue, 9 = yellow, 13 = grey
# ---------------------------------------------------------------------------
COLOR = {
    "LEFT": 1,
    "RIGHT": 4,
    "CENTER": 9,
    "IK": 2,
    "POLE": 3,
    "EXTRA": 13,
    "MCH": 13,
}

BONE_COLLECTIONS = {
    # name: (is_visible, color)
    "Controls": (True, COLOR["CENTER"]),
    "Torso": (True, COLOR["CENTER"]),
    "Arms": (True, None),
    "Legs": (True, None),
    "Twists": (False, COLOR["EXTRA"]),
}

# ---------------------------------------------------------------------------
# Custom property definitions on the root bone
#   name: (default, min, max, soft_min, soft_max, description)
# ---------------------------------------------------------------------------
PROPS = {
    "ik_arm.L": (0.0, 0.0, 1.0, 0.0, 1.0, "Arm IK/FK blend (1 = IK)"),
    "ik_arm.R": (0.0, 0.0, 1.0, 0.0, 1.0, "Arm IK/FK blend (1 = IK)"),
    "ik_leg.L": (1.0, 0.0, 1.0, 0.0, 1.0, "Leg IK/FK blend (1 = IK)"),
    "ik_leg.R": (1.0, 0.0, 1.0, 0.0, 1.0, "Leg IK/FK blend (1 = IK)"),
    "ik_stretch": (0.0, 0.0, 1.0, 0.0, 0.2, "Universal IK stretch allowance"),
    "finger_curl.L": (0.0, 0.0, 1.0, 0.0, 1.0, "Fingers curl (left)"),
    "finger_curl.R": (0.0, 0.0, 1.0, 0.0, 1.0, "Fingers curl (right)"),
    "finger_spread.L": (0.0, -1.0, 1.0, -1.0, 1.0, "Fingers spread (left)"),
    "finger_spread.R": (0.0, -1.0, 1.0, -1.0, 1.0, "Fingers spread (right)"),
    "thumb_curl.L": (0.0, 0.0, 1.0, 0.0, 1.0, "Thumb curl (left)"),
    "thumb_curl.R": (0.0, 0.0, 1.0, 0.0, 1.0, "Thumb curl (right)"),
    "twist.L": (1.0, 0.0, 1.0, 0.0, 1.0, "Twist bone influence (left)"),
    "twist.R": (1.0, 0.0, 1.0, 0.0, 1.0, "Twist bone influence (right)"),
    "pole_angle_arm.L": (-90.0, -180.0, 180.0, -180.0, 180.0, "Elbow pole angle (deg)"),
    "pole_angle_arm.R": (-90.0, -180.0, 180.0, -180.0, 180.0, "Elbow pole angle (deg)"),
    "pole_angle_leg.L": (-90.0, -180.0, 180.0, -180.0, 180.0, "Knee pole angle (deg)"),
    "pole_angle_leg.R": (-90.0, -180.0, 180.0, -180.0, 180.0, "Knee pole angle (deg)"),
}

# ---------------------------------------------------------------------------
# Body presets.  All values multiply the neutral, height-normalised skeleton.
# ---------------------------------------------------------------------------
PRESETS = {
    "FEMALE": dict(
        label="Female", height=1.68, build=0.42, head_scale=1.0,
        shoulder=0.95, chest=0.96, waist=0.88, hip=1.07,
        arm_len=1.0, leg_len=1.0, arm_angle=44.0,
    ),
    "MALE": dict(
        label="Male", height=1.80, build=0.55, head_scale=1.0,
        shoulder=1.06, chest=1.05, waist=0.98, hip=0.96,
        arm_len=1.0, leg_len=1.0, arm_angle=42.0,
    ),
    "HEAVY": dict(
        label="Heavy", height=1.76, build=0.92, head_scale=1.0,
        shoulder=1.02, chest=1.12, waist=1.22, hip=1.12,
        arm_len=1.0, leg_len=1.0, arm_angle=46.0,
    ),
    "SLIM": dict(
        label="Slim", height=1.74, build=0.22, head_scale=1.0,
        shoulder=0.94, chest=0.9, waist=0.84, hip=0.92,
        arm_len=1.02, leg_len=1.02, arm_angle=43.0,
    ),
    "HEROIC": dict(
        label="Heroic", height=1.92, build=0.62, head_scale=0.93,
        shoulder=1.14, chest=1.12, waist=0.9, hip=0.98,
        arm_len=1.03, leg_len=1.02, arm_angle=40.0,
    ),
    "CHILD": dict(
        label="Child", height=1.20, build=0.35, head_scale=1.22,
        shoulder=0.94, chest=0.96, waist=0.94, hip=0.98,
        arm_len=0.98, leg_len=0.96, arm_angle=46.0,
    ),
    "STYLIZED": dict(
        label="Stylized", height=1.70, build=0.5, head_scale=1.16,
        shoulder=1.04, chest=1.0, waist=0.95, hip=1.0,
        arm_len=1.04, leg_len=1.0, arm_angle=44.0,
    ),
    "CUSTOM": dict(
        label="Custom", height=1.75, build=0.5, head_scale=1.0,
        shoulder=1.0, chest=1.0, waist=1.0, hip=1.0,
        arm_len=1.0, leg_len=1.0, arm_angle=42.0,
    ),
}

SKIN_METHODS = (
    ("APEX", "Apex Adaptive Weights", "Mesh-derived distance weights, hierarchy aware, every bone covered"),
    ("CAPSULE", "Capsule Weights", "Bone-radius capsule falloff with Laplacian smoothing"),
    ("HEAT", "Bone Heat", "Blender's bone-heat solver (slower, needs a clean mesh)"),
    ("ENVELOPE", "Bone Envelopes", "Fast envelope-based assignment"),
)

FINGER_NAMES = ("f_index", "f_middle", "f_ring", "f_pinky")

# (finger, phalanx count)
FINGERS = (
    ("thumb", 3),
    ("f_index", 3),
    ("f_middle", 3),
    ("f_ring", 3),
    ("f_pinky", 3),
)

# per-phalanx curl multipliers (radians at curl = 1.0) - index 0 is closest to palm
CURL_FACTORS = {
    "thumb": (0.72, 0.85, 0.65),
    "f_index": (1.20, 1.35, 0.85),
    "f_middle": (1.25, 1.40, 0.90),
    "f_ring": (1.20, 1.35, 0.85),
    "f_pinky": (1.10, 1.25, 0.80),
}

# lateral fan weights for spread (positive = towards thumb side)
SPREAD_FACTORS = {
    "f_index": 0.55,
    "f_middle": 0.12,
    "f_ring": -0.35,
    "f_pinky": -0.60,
}

# ---------------------------------------------------------------------------
# Procedural motion catalogue:  id: (label, additive-friendly?, frames, description)
# ---------------------------------------------------------------------------
MOTIONS = {
    "BREATHE": ("Breathing", True, 96, "Chest / shoulder respiration with a slow 4 second cycle"),
    "WEIGHT": ("Weight Shift", True, 144, "Hip sway with counter-rotated spine and head"),
    "IDLE": ("Idle Sway", True, 180, "Organic noise-driven sway for static poses"),
    "LOOK": ("Look Around", True, 168, "Head and neck glances with smooth holds"),
    "FINGERS": ("Finger Fidget", True, 120, "Noise on finger curl properties - keeps drivers alive"),
    "SETTLE": ("Settle / Overshoot", False, 32, "One-shot settle on the selected bones"),
}

WALK_PRESETS = {
    "WALK": ("Walk", dict(
        frames=32, stride=0.42, lift=0.075, bob=0.022, sway=0.018,
        hip_yaw=4.0, hip_roll=3.0, arm_swing=17.0, elbow=12.0,
        lean=2.0, stance=0.62, toe_off=16.0, head_stabilise=0.55,
    )),
    "RUN": ("Run", dict(
        frames=24, stride=0.7, lift=0.19, bob=0.075, sway=0.01,
        hip_yaw=6.0, hip_roll=2.0, arm_swing=38.0, elbow=48.0,
        lean=9.0, stance=0.38, toe_off=30.0, head_stabilise=0.4,
    )),
    "SNEAK": ("Sneak", dict(
        frames=40, stride=0.3, lift=0.11, bob=0.05, sway=0.026,
        hip_yaw=3.0, hip_roll=2.0, arm_swing=10.0, elbow=26.0,
        lean=6.0, stance=0.7, toe_off=8.0, head_stabilise=0.7,
    )),
}

NAME_MAPS = ("NONE", "UE5", "MIXAMO", "UNITY", "VRM")

EXPORT_PRESETS = (
    ("GLTF_GLB", "glTF 2.0 (.glb)", "Game-engine ready binary glTF, deform bones only"),
    ("GLTF", "glTF 2.0 (.gltf + .bin)", "Separate glTF + binary buffer"),
    ("FBX_UE", "FBX - Unreal Engine 5", "Centimetres, Z-up handling, bake all actions"),
    ("FBX_UNITY", "FBX - Unity", "Y-up, deform bones only, bake all actions"),
    ("FBX_GENERIC", "FBX - Generic", "Standard FBX with baked animation"),
)
