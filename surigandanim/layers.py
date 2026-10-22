# SPDX-License-Identifier: GPL-3.0-or-later
"""Apex bone layers and body/face picker.

Layer model follows BlenRig (GPL-3, Juan Pablo Bouza, Sav Martin, Zebus3d,
Jorge Hernandez-Melendez): every layer is an armature bone collection, the
built-in layers are protected from removal, and the picker selects a whole
body region from a button grid instead of hunting for bones in the viewport.
"""
from __future__ import annotations

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator

from . import rig as rigmod
from .const import BONE_COLLECTIONS

FACE_LAYER = "Face"
BUILTIN_LAYERS = tuple(BONE_COLLECTIONS) + (FACE_LAYER,)

# key, label, side ("L"/"R"/None), bone-name prefixes.  Prefixes match the
# real rig names, e.g. "f_index_01.L", "upper_arm.R", "toe_ik.L".
REGIONS = (
    ("HEAD", "Head", None, ("head", "neck", "jaw", "chin", "tongue")),
    ("TORSO", "Torso", None, ("cog", "pelvis", "spine", "chest")),
    ("ARM_L", "Arm L", "L", ("clavicle", "upper_arm", "forearm", "hand", "elbow_pole")),
    ("ARM_R", "Arm R", "R", ("clavicle", "upper_arm", "forearm", "hand", "elbow_pole")),
    ("HAND_L", "Hand L", "L", ("hand", "f_", "thumb_")),
    ("HAND_R", "Hand R", "R", ("hand", "f_", "thumb_")),
    ("LEG_L", "Leg L", "L", ("thigh", "shin", "knee_pole", "foot", "toe")),
    ("LEG_R", "Leg R", "R", ("thigh", "shin", "knee_pole", "foot", "toe")),
    ("FACE", "Face", None, None),  # uses the Face layer
)


def _side_of(name: str):
    if name.endswith(".L"):
        return "L"
    if name.endswith(".R"):
        return "R"
    return None


def region_bones(arm, key: str) -> list:
    """Return the bones that belong to a picker region on this armature."""
    spec = next((r for r in REGIONS if r[0] == key), None)
    if spec is None:
        return []
    _key, _label, side, prefixes = spec
    if prefixes is None:
        coll = arm.data.collections.get(FACE_LAYER)
        return list(coll.bones) if coll is not None else []
    result = []
    for bone in arm.data.bones:
        if side is not None and _side_of(bone.name) != side:
            continue
        if side is None and _side_of(bone.name) is not None:
            continue
        base = bone.name[:-2] if side else bone.name
        if any(base == p or base.startswith(p) for p in prefixes):
            result.append(bone)
    return result


def _rig_arm(context):
    rig = rigmod.get_rig()
    return rig.obj if rig is not None else None


class APEX_OT_pick_region(Operator):
    bl_idname = "apex.pick_region"
    bl_label = "Pick Region"
    bl_description = "Select every control of a body region and show its layer"
    bl_options = {"REGISTER", "UNDO"}

    region: StringProperty(default="HEAD")

    def execute(self, context):
        arm = _rig_arm(context)
        if arm is None:
            self.report({"ERROR"}, "Build or select an Apex rig first")
            return {"CANCELLED"}
        bones = region_bones(arm, self.region)
        if not bones:
            self.report({"WARNING"}, f"No controls found for {self.region}")
            return {"CANCELLED"}
        # selection lives on pose bones in Blender 5 (Bone has no select flag)
        for pb in arm.pose.bones:
            pb.select = False
        for bone in bones:
            # a picked control must be visible, otherwise it cannot be used
            for coll in bone.collections:
                coll.is_visible = True
            arm.pose.bones[bone.name].select = True
        arm.data.bones.active = bones[0]
        context.view_layer.objects.active = arm
        self.report({"INFO"}, f"Picked {len(bones)} bones")
        return {"FINISHED"}


class APEX_OT_layer_solo(Operator):
    bl_idname = "apex.layer_solo"
    bl_label = "Solo Layer"
    bl_description = "Show only this layer"

    layer: StringProperty()

    def execute(self, context):
        arm = _rig_arm(context)
        if arm is None:
            return {"CANCELLED"}
        for coll in arm.data.collections:
            coll.is_visible = coll.name == self.layer
        return {"FINISHED"}


class APEX_OT_layers_visibility(Operator):
    bl_idname = "apex.layers_visibility"
    bl_label = "Show / Hide All Layers"
    bl_description = "Show or hide every bone layer"

    visible: BoolProperty(default=True)

    def execute(self, context):
        arm = _rig_arm(context)
        if arm is None:
            return {"CANCELLED"}
        for coll in arm.data.collections:
            coll.is_visible = self.visible
        return {"FINISHED"}


class APEX_OT_layer_assign(Operator):
    bl_idname = "apex.layer_assign"
    bl_label = "Assign Selected to Layer"
    bl_description = "Move the selected bones into this layer"

    layer: StringProperty()

    def execute(self, context):
        arm = _rig_arm(context)
        coll = arm.data.collections.get(self.layer) if arm is not None else None
        if coll is None:
            self.report({"ERROR"}, "Layer not found")
            return {"CANCELLED"}
        count = 0
        for pb in arm.pose.bones:
            if pb.select:
                coll.assign(pb.bone)
                count += 1
        self.report({"INFO"}, f"Assigned {count} bones to {self.layer}")
        return {"FINISHED"}


class APEX_OT_layer_add(Operator):
    bl_idname = "apex.layer_add"
    bl_label = "Add Layer"
    bl_description = "Add a new custom bone layer"

    def execute(self, context):
        arm = _rig_arm(context)
        if arm is None:
            return {"CANCELLED"}
        n = 1
        while arm.data.collections.get(f"Layer {n}") is not None:
            n += 1
        arm.data.collections.new(f"Layer {n}")
        return {"FINISHED"}


class APEX_OT_layer_remove(Operator):
    bl_idname = "apex.layer_remove"
    bl_label = "Remove Layer"
    bl_description = "Remove a custom bone layer (built-in layers are protected)"

    layer: StringProperty()

    def execute(self, context):
        arm = _rig_arm(context)
        if arm is None:
            return {"CANCELLED"}
        if self.layer in BUILTIN_LAYERS:
            self.report({"INFO"}, "Built-in layers cannot be removed")
            return {"CANCELLED"}
        coll = arm.data.collections.get(self.layer)
        if coll is None:
            return {"CANCELLED"}
        arm.data.collections.remove(coll)
        return {"FINISHED"}


CLASSES = (
    APEX_OT_pick_region,
    APEX_OT_layer_solo,
    APEX_OT_layers_visibility,
    APEX_OT_layer_assign,
    APEX_OT_layer_add,
    APEX_OT_layer_remove,
)


def register():
    for cls in CLASSES:
        try:
            bpy.utils.register_class(cls)
        except RuntimeError:
            pass


def unregister():
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
