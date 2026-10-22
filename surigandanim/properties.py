# SPDX-License-Identifier: GPL-3.0-or-later
"""SuRigandAnim - user settings (scene property group)."""
from __future__ import annotations

import bpy
from bpy.props import (BoolProperty, EnumProperty, FloatProperty, IntProperty,
                       StringProperty)
from bpy.types import PropertyGroup

from .const import MOTIONS, NAME_MAPS, PRESETS, SKIN_METHODS, WALK_PRESETS

PRESET_ITEMS = [(key, data["label"], f"{data['height']:.2f} m base height")
                for key, data in PRESETS.items()]

MOTION_ITEMS = [(key, data[0], data[3]) for key, data in MOTIONS.items()] + \
               [(key, data[0], f"{data[1]['frames']} frame locomotion cycle")
                for key, data in WALK_PRESETS.items()]

SKIN_ITEMS = [(key, label, description) for key, label, description in SKIN_METHODS]

EXPORT_ITEMS = [
    ("GLTF_GLB", "glTF 2.0 (.glb)", "Game-engine ready binary glTF"),
    ("GLTF", "glTF 2.0 (.gltf)", "glTF with separate .bin buffer"),
    ("FBX_UE", "FBX - Unreal Engine 5", "Centimetres, Z-up handling, all actions"),
    ("FBX_UNITY", "FBX - Unity", "Y-up, deform bones only"),
    ("FBX_GENERIC", "FBX - Generic", "Standard FBX with baked animation"),
]

NAME_MAP_ITEMS = [
    ("NONE", "Blender (keep names)", "Leave the Apex bone names untouched"),
    ("UE5", "Unreal Engine 5", "pelvis / spine_01 / clavicle_l / upperarm_l ..."),
    ("MIXAMO", "Mixamo", "mixamorig:Hips / LeftArm / LeftUpLeg ..."),
    ("UNITY", "Unity Humanoid", "Hips / Spine / LeftUpperArm / LeftUpLeg ..."),
    ("VRM", "VRM / VRoid", "hips / spine / leftUpperArm / leftUpperLeg ..."),
]


class ApexSettings(PropertyGroup):
    # ------------------------------------------------- realistic body
    rb_gender: FloatProperty(name="Gender", default=0.5, min=0.0, max=1.0,
                             description="0 = female, 1 = male")
    rb_muscle: FloatProperty(name="Muscle", default=0.5, min=0.0, max=1.0,
                             description="0.5 = average")
    rb_weight: FloatProperty(name="Weight", default=0.5, min=0.0, max=1.0,
                             description="0.5 = average")
    # ------------------------------------------------------------- build
    preset: EnumProperty(name="Preset", items=PRESET_ITEMS, default="FEMALE",
                         description="Body proportion preset")
    height: FloatProperty(name="Height (m)", default=1.68, min=0.5, max=3.0,
                          description="Total standing height in metres")
    build: FloatProperty(name="Build", default=0.42, min=0.0, max=1.0,
                         description="Girth factor: 0 = very slim, 1 = very heavy")
    head_scale: FloatProperty(name="Head", default=1.0, min=0.6, max=1.8,
                              description="Head size multiplier")
    shoulder: FloatProperty(name="Shoulders", default=0.95, min=0.6, max=1.6)
    chest: FloatProperty(name="Chest", default=0.96, min=0.6, max=1.6)
    waist: FloatProperty(name="Waist", default=0.88, min=0.6, max=1.6)
    hip: FloatProperty(name="Hips", default=1.07, min=0.6, max=1.6)
    arm_len: FloatProperty(name="Arm Length", default=1.0, min=0.7, max=1.3)
    leg_len: FloatProperty(name="Leg Length", default=1.0, min=0.7, max=1.3)
    arm_angle: FloatProperty(name="A-Pose Angle", default=44.0, min=10.0, max=80.0,
                             description="Arm angle below horizontal")
    fingers: IntProperty(name="Fingers", default=5, min=3, max=5,
                         description="Number of separated fingers (excluding thumb)")
    twist_bones: BoolProperty(name="Twist Bones", default=False,
                              description="Add upper-arm / forearm twist helpers")
    bbone: BoolProperty(name="B-Bone Segments", default=True,
                        description="Segment spine and limb bones for smoother deformation")
    ik_arms: BoolProperty(name="Arm IK", default=True)
    ik_legs: BoolProperty(name="Leg IK", default=True)
    pole_targets: BoolProperty(name="Pole Targets", default=True,
                               description="Add knee / elbow pole targets and calibrate them")

    # ------------------------------------------------------------- body + skin
    skin_method: EnumProperty(name="Skinning", items=SKIN_ITEMS, default="APEX")
    smooth_iterations: IntProperty(name="Smooth Passes", default=4, min=0, max=20)
    max_influences: IntProperty(name="Max Influences", default=4, min=1, max=8)

    # ------------------------------------------------------------- animation
    motion: EnumProperty(name="Motion", items=MOTION_ITEMS, default="BREATHE")
    motion_start: IntProperty(name="Start Frame", default=1, min=1)
    motion_loop: BoolProperty(name="Loop", default=True)
    motion_use_default_loop: BoolProperty(name="Auto Loop", default=True,
                                          description="Use the motion's natural loop setting")
    motion_push_nla: BoolProperty(name="Push to NLA", default=True,
                                  description="Store the action on its own NLA track")
    motion_mute: BoolProperty(name="Mute Track", default=False)

    # ------------------------------------------------------------- retarget
    name_map: EnumProperty(name="Detect Style", items=NAME_MAP_ITEMS, default="MIXAMO")
    retarget_scale: BoolProperty(name="Match Scale", default=True,
                                 description="Scale source motion to the Apex rig height")
    retarget_start: IntProperty(name="Frame Offset", default=0)
    retarget_keep_ik: BoolProperty(name="Keep IK Controls", default=False,
                                   description="Leave IK/FK props untouched instead of keying FK")

    # ------------------------------------------------------------- export
    export_preset: EnumProperty(name="Format", items=EXPORT_ITEMS, default="GLTF_GLB")
    export_path: StringProperty(name="File", default="//apex_character.glb",
                                subtype="FILE_PATH")
    export_selection: BoolProperty(name="Selected Only", default=True)
    export_bake_actions: BoolProperty(name="Bake All Actions", default=True,
                                      description="Bake every NLA action before exporting")
    export_def_only: BoolProperty(name="Deform Bones Only", default=True)
    export_apply: BoolProperty(name="Apply Modifiers", default=False)

    # ------------------------------------------------------------- own character
    fit_facing: EnumProperty(
        name="Facing", default="AUTO",
        items=[("AUTO", "Auto Detect", "Measure the facing from the feet"),
               ("FRONT_NEG_Y", "-Y (Blender front)", "Character looks along -Y"),
               ("FRONT_POS_Y", "+Y", "Character looks along +Y"),
               ("FRONT_POS_X", "+X", "Character looks along +X"),
               ("FRONT_NEG_X", "-X", "Character looks along -X")],
        description="Forward direction of the character in world space")
    fit_prefer_skeleton: BoolProperty(
        name="Use Existing Skeleton", default=True,
        description="If the mesh is already rigged, read the joint positions from "
                    "that skeleton instead of guessing them from the mesh")
    fit_refine: BoolProperty(
        name="Fit Proportions", default=True,
        description="Adjust the rig's leg length and A-pose angle to the character")
    fit_skin: BoolProperty(
        name="Skin Afterwards", default=True,
        description="Bind the character to the new rig with Apex capsule weights")
    fit_replace_rig: BoolProperty(
        name="Replace Existing Rig", default=True,
        description="Remove armature modifiers, parenting and vertex groups of any "
                    "previous skeleton before binding")
    detected_summary: StringProperty(name="Detected", default="")
    detected_height: FloatProperty(name="Height", default=0.0, unit="LENGTH")
    detected_arm_angle: FloatProperty(name="Arm Angle", default=0.0)
    detected_leg_len: FloatProperty(name="Leg Length", default=1.0)
    detected_facing: StringProperty(name="Facing", default="")
    detected_source: StringProperty(name="Source", default="")
    detected_fit: StringProperty(name="Fit", default="")

    # ------------------------------------------------------------- deform / reports
    preserve_volume: BoolProperty(name="Preserve Volume", default=True,
                                  description="Dual quaternion skinning (keeps volume)")
    deform_report: StringProperty(name="Deform Report", default="")
    deform_details: StringProperty(name="Deform Details", default="")

    # ------------------------------------------------------------- misc ui
    show_advanced: BoolProperty(name="Advanced", default=False)
    pole_angle_step: FloatProperty(name="Pole Step", default=5.0, min=1.0, max=45.0)

    # ------------------------------------------------------------------ live
    live_port: IntProperty(name="Port", default=8770, min=1024, max=65535,
                           description="Port the phone connects to")
    live_url: StringProperty(name="Address", default="",
                             description="Open this address on your phone")
    live_token: StringProperty(name="PIN", default="",
                               description="Optional access code appended to the URL")
    live_head: BoolProperty(name="Drive Head", default=True,
                            description="Use the phone to rotate the neck and head")
    live_smooth: FloatProperty(name="Smoothing", default=0.55, min=0.0, max=0.95,
                               description="0 = raw tracking, 0.95 = very smooth")
    live_frames: IntProperty(name="Frames", default=0, min=0)
    live_fps: FloatProperty(name="FPS", default=0.0, min=0.0)
    live_clients: IntProperty(name="Clients", default=0, min=0)


CLASSES = (ApexSettings,)


def register():
    if not ApexSettings.is_registered:
        bpy.utils.register_class(ApexSettings)
    if not hasattr(bpy.types.Scene, "apex_settings"):
        bpy.types.Scene.apex_settings = bpy.props.PointerProperty(type=ApexSettings)


def unregister():
    if hasattr(bpy.types.Scene, "apex_settings"):
        del bpy.types.Scene.apex_settings
    if ApexSettings.is_registered:
        bpy.utils.unregister_class(ApexSettings)


def settings(context=None) -> ApexSettings:
    """Return the scene settings, self-healing if the class was unregistered."""
    context = context or bpy.context
    scene = context.scene
    if not hasattr(scene, "apex_settings"):
        if not ApexSettings.is_registered:
            bpy.utils.register_class(ApexSettings)
        if not hasattr(bpy.types.Scene, "apex_settings"):
            bpy.types.Scene.apex_settings = bpy.props.PointerProperty(type=ApexSettings)
    return scene.apex_settings


def apply_preset(settings_obj, key: str) -> None:
    data = PRESETS.get(key)
    if not data:
        return
    for field in ("height", "build", "head_scale", "shoulder", "chest", "waist",
                  "hip", "arm_len", "leg_len", "arm_angle"):
        if hasattr(settings_obj, field):
            setattr(settings_obj, field, float(data[field]))
    settings_obj.preset = key


def rig_options(settings_obj):
    from .proportions import RigOptions
    return RigOptions(
        preset=settings_obj.preset,
        height=settings_obj.height,
        build=settings_obj.build,
        head_scale=settings_obj.head_scale,
        shoulder=settings_obj.shoulder,
        chest=settings_obj.chest,
        waist=settings_obj.waist,
        hip=settings_obj.hip,
        arm_len=settings_obj.arm_len,
        leg_len=settings_obj.leg_len,
        arm_angle=settings_obj.arm_angle,
        fingers=settings_obj.fingers,
        twist_bones=settings_obj.twist_bones,
        bbone=settings_obj.bbone,
        ik_arms=settings_obj.ik_arms,
        ik_legs=settings_obj.ik_legs,
        pole_targets=settings_obj.pole_targets,
    )
