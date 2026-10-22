# SPDX-License-Identifier: GPL-3.0-or-later
"""Apex Rig & Motion - operators."""
from __future__ import annotations

import os

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import Operator

from . import (animation, deform, export, face, fit, live, makehuman, mocap, poses,
               properties, rig as rigmod, skin, ui_icons, utils)
from .const import MOTIONS, PROPS, WALK_PRESETS

LIMB_ITEMS = (
    ("arm", "Arms", "Arms"),
    ("leg", "Legs", "Legs"),
)
SIDE_ITEMS = (
    ("L", "Left", "Left side"),
    ("R", "Right", "Right side"),
    ("BOTH", "Both", "Both sides"),
)


def _rig_from_context(context, require=True):
    obj = context.active_object
    rig = rigmod.get_rig(obj if obj and obj.type == "ARMATURE" else None)
    if rig is None:
        obj = utils.active_armature(require_apex=True)
        rig = rigmod.get_rig(obj) if obj else None
    if rig is None and require:
        raise RuntimeError("Select an Apex rig first")
    return rig


def _selected_meshes(context):
    return [ob for ob in context.selected_objects if ob.type == "MESH"]


class _ApexOp(Operator):
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode in {"OBJECT", "POSE"}


# ---------------------------------------------------------------------------
# Rig creation
# ---------------------------------------------------------------------------
class APEX_OT_apply_preset(_ApexOp):
    bl_idname = "apex.apply_preset"
    bl_label = "Apply Preset"
    bl_description = "Load a proportion preset into the build settings"

    preset: EnumProperty(items=[
        ("FEMALE", "Female", ""), ("MALE", "Male", ""), ("HEAVY", "Heavy", ""),
        ("SLIM", "Slim", ""), ("HEROIC", "Heroic", ""), ("CHILD", "Child", ""),
        ("STYLIZED", "Stylized", ""), ("CUSTOM", "Custom", "")])

    def execute(self, context):
        properties.apply_preset(properties.settings(context), self.preset)
        return {"FINISHED"}


class APEX_OT_build_rig(_ApexOp):
    bl_idname = "apex.build_rig"
    bl_label = "Build Apex Rig"
    bl_description = "Create a fully featured Apex human control rig"

    def execute(self, context):
        st = properties.settings(context)
        opts = properties.rig_options(st)
        try:
            result = rigmod.build_rig(context, opts)
        except Exception as exc:
            self.report({"ERROR"}, f"Rig build failed: {exc}")
            utils.log.exception("build failed")
            return {"CANCELLED"}
        arm = result.arm
        utils.set_active(arm)
        coll = arm.data.collections.get("Controls")
        if coll:
            coll.is_visible = True
        self.report({"INFO"}, f"Apex rig built: {len(arm.data.bones)} bones")
        return {"FINISHED"}


class APEX_OT_delete_rig(_ApexOp):
    bl_idname = "apex.delete_rig"
    bl_label = "Delete Apex Rig"
    bl_description = "Remove the active Apex rig and its widget objects"

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        rigmod.delete_rig(rig.obj)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Existing character workflow
# ---------------------------------------------------------------------------
def _character_meshes(context):
    """Selected meshes, or every mesh bound to the selected armature."""
    meshes = [ob for ob in context.selected_objects if ob.type == "MESH"]
    if meshes:
        return meshes
    active = context.active_object
    if active is not None and active.type == "ARMATURE":
        return utils.meshes_of_armature(active)
    return []


def _store_analysis(st, info):
    st.detected_summary = info.summary()
    st.detected_height = info.height
    st.detected_arm_angle = info.arm_angle
    st.detected_leg_len = info.leg_len
    st.detected_facing = info.facing_key
    st.detected_source = info.source


class APEX_OT_analyze_character(_ApexOp):
    bl_idname = "apex.analyze_character"
    bl_label = "Analyze Character"
    bl_description = ("Measure the selected character: height, floor, facing, arm "
                      "angle and leg length")

    def execute(self, context):
        st = properties.settings(context)
        meshes = _character_meshes(context)
        if not meshes:
            self.report({"ERROR"}, "Select your character mesh first")
            return {"CANCELLED"}
        try:
            info = fit.analyze(meshes, facing_pref=st.fit_facing,
                               prefer_skeleton=st.fit_prefer_skeleton)
        except Exception as exc:
            utils.log.exception("character analysis failed")
            self.report({"ERROR"}, f"Analysis failed: {exc}")
            return {"CANCELLED"}
        _store_analysis(st, info)
        for line in info.warnings:
            self.report({"INFO"}, line)
        self.report({"INFO"}, info.summary())
        return {"FINISHED"}


class APEX_OT_rig_character(_ApexOp):
    bl_idname = "apex.rig_character"
    bl_label = "Rig My Character"
    bl_description = ("Build an Apex rig fitted to the selected character and skin "
                      "it - height, facing, floor and A-pose are matched")

    def execute(self, context):
        st = properties.settings(context)
        meshes = _character_meshes(context)
        if not meshes:
            self.report({"ERROR"}, "Select your character mesh first")
            return {"CANCELLED"}
        opts = properties.rig_options(st)
        try:
            built, info, stats = fit.rig_character(
                context, meshes, opts,
                facing_pref=st.fit_facing,
                refine=st.fit_refine,
                skin_method=st.skin_method,
                smooth_iterations=st.smooth_iterations,
                max_influences=st.max_influences,
                prefer_skeleton=st.fit_prefer_skeleton,
                bind=st.fit_skin)
        except Exception as exc:
            utils.log.exception("rig_character failed")
            self.report({"ERROR"}, f"Could not rig the character: {exc}")
            return {"CANCELLED"}
        _store_analysis(st, info)
        arm = built.arm
        report = fit.joint_report(arm, meshes)
        st.detected_fit = (f"{report.get('inside', 0)}/{report.get('bones', 0)} "
                           f"joints inside") if report else ""
        for line in info.warnings:
            self.report({"INFO"}, line)
        self.report({"INFO"}, f"Rigged {len(meshes)} mesh(es) · {info.summary()}")
        if report:
            self.report({"INFO"}, st.detected_fit)
        return {"FINISHED"}


class APEX_OT_fit_rig(_ApexOp):
    bl_idname = "apex.fit_rig"
    bl_label = "Fit Rig To Character"
    bl_description = ("Move, rotate and scale the existing Apex rig so it matches "
                      "the selected character mesh")

    def execute(self, context):
        st = properties.settings(context)
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        meshes = [ob for ob in context.selected_objects
                  if ob.type == "MESH" and ob is not rig.obj]
        if not meshes:
            meshes = utils.meshes_of_armature(rig.obj)
        if not meshes:
            self.report({"ERROR"}, "Select the character mesh as well")
            return {"CANCELLED"}
        try:
            info = fit.analyze(meshes, facing_pref=st.fit_facing,
                               prefer_skeleton=False)
            result = fit.fit_armature(rig.obj, info, scale=True)
        except Exception as exc:
            utils.log.exception("fit_rig failed")
            self.report({"ERROR"}, f"Could not fit the rig: {exc}")
            return {"CANCELLED"}
        _store_analysis(st, info)
        utils.refresh(rig.obj)
        self.report({"INFO"}, f"Rig fitted (scale {result['scale']:.3f}) · {info.summary()}")
        return {"FINISHED"}


class APEX_OT_check_fit(_ApexOp):
    bl_idname = "apex.check_fit"
    bl_label = "Check Fit"
    bl_description = "Report how many rig joints are inside the character mesh"

    def execute(self, context):
        st = properties.settings(context)
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        meshes = _character_meshes(context) or utils.meshes_of_armature(rig.obj)
        if not meshes:
            self.report({"ERROR"}, "No meshes to check")
            return {"CANCELLED"}
        report = fit.joint_report(rig.obj, meshes)
        summary = (f"{report['inside']}/{report['bones']} joints inside, "
                   f"max bone-to-surface {report['max_distance']} m")
        if report["outside"]:
            summary += f" · outside: {[n for n, _d in report['outside']]}"
        if report.get("finger_outside"):
            summary += f" · {report['finger_outside']} finger bones outside"
        st.detected_fit = summary
        self.report({"INFO"}, summary)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Poses (picture buttons)
# ---------------------------------------------------------------------------
class APEX_OT_apply_pose(_ApexOp):
    bl_idname = "apex.apply_pose"
    bl_label = "Apply Pose"
    bl_description = "Pose the rig from the library"

    pose: EnumProperty(items=[(k, v[0], "") for k, v in poses.POSE_LIBRARY.items()],
                       default="RELAXED")
    reset: BoolProperty(name="Reset First", default=True)

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        try:
            poses.apply_pose(rig, self.pose, reset=self.reset)
        except Exception as exc:
            utils.log.exception("pose failed")
            self.report({"ERROR"}, f"Pose failed: {exc}")
            return {"CANCELLED"}
        return {"FINISHED"}


class APEX_OT_key_pose(_ApexOp):
    bl_idname = "apex.key_pose"
    bl_label = "Key Pose"
    bl_description = "Apply a library pose and key it as a new action"

    pose: EnumProperty(items=[(k, v[0], "") for k, v in poses.POSE_LIBRARY.items()],
                       default="RELAXED")

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        action = poses.key_pose(rig, self.pose)
        self.report({"INFO"}, f"Keyed pose into {action.name}")
        return {"FINISHED"}


class APEX_OT_clear_pose_op(_ApexOp):
    bl_idname = "apex.clear_pose_op"
    bl_label = "Clear Pose"
    bl_description = "Reset every bone and rig property to rest"

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        poses.clear_pose(rig.obj)
        return {"FINISHED"}


class APEX_OT_build_realistic(_ApexOp):
    bl_idname = "apex.build_realistic"
    bl_label = "Build Realistic Body"
    bl_description = ("Create a realistic adult body from the MakeHuman data, "
                      "fit an Apex rig to it and skin it")

    preset: EnumProperty(items=[(k, v[0], "") for k, v in makehuman.PRESETS.items()],
                         default="REAL_MALE")

    def execute(self, context):
        st = properties.settings(context)
        if self.preset == "REAL_CUSTOM":
            gender, muscle, weight = st.rb_gender, st.rb_muscle, st.rb_weight
        else:
            _, gender, muscle, weight = makehuman.PRESETS[self.preset]
        try:
            for ob in list(context.selected_objects):
                ob.select_set(False)
            body = makehuman.build_object(context, self.preset.lower(), gender,
                                          muscle, weight)
            body.select_set(True)
            context.view_layer.objects.active = body
            opts = properties.rig_options(st)
            built, info, stats = fit.rig_character(
                context, [body], opts,
                facing_pref=st.fit_facing, refine=st.fit_refine,
                skin_method=st.skin_method, smooth_iterations=st.smooth_iterations,
                max_influences=st.max_influences, prefer_skeleton=False, bind=True)
        except Exception as exc:
            utils.log.exception("build_realistic failed")
            self.report({"ERROR"}, f"Could not build the realistic body: {exc}")
            return {"CANCELLED"}
        _store_analysis(st, info)
        report = fit.joint_report(built.arm, [body])
        st.detected_fit = (f"{report.get('inside', 0)}/{report.get('bones', 0)} "
                           f"joints inside") if report else ""
        self.report({"INFO"}, f"Realistic body rigged · {info.summary()}")
        return {"FINISHED"}


class APEX_OT_preview_motion(_ApexOp):
    bl_idname = "apex.preview_motion"
    bl_label = "Preview Motion"
    bl_description = ("Add the selected motion to the rig and play it in the "
                      "viewport (press Space or Esc to stop)")

    def execute(self, context):
        st = properties.settings(context)
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        try:
            action = animation.create_motion(rig.obj, st.motion, start=1.0)
        except Exception as exc:
            utils.log.exception("preview motion failed")
            self.report({"ERROR"}, f"Motion failed: {exc}")
            return {"CANCELLED"}
        start, end = utils.action_range(action)
        scene = context.scene
        scene.frame_start = int(start)
        scene.frame_end = max(int(end), int(start) + 1)
        scene.frame_set(int(start))
        if not context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()
        self.report({"INFO"}, f"Previewing {action.name} ({int(end - start)} frames)")
        return {"FINISHED"}


class APEX_OT_add_motion_pick(_ApexOp):
    bl_idname = "apex.add_motion_pick"
    bl_label = "Add Motion"
    bl_description = "Generate a motion on the active rig"

    motion: StringProperty(default="WALK")

    def execute(self, context):
        st = properties.settings(context)
        st.motion = self.motion
        return bpy.ops.apex.add_motion()


# ---------------------------------------------------------------------------
# Deformation toolkit
# ---------------------------------------------------------------------------
class APEX_OT_preserve_volume(_ApexOp):
    bl_idname = "apex.preserve_volume"
    bl_label = "Preserve Volume"
    bl_description = ("Dual-quaternion skinning: stops shoulders, elbows and knees "
                      "from collapsing")

    enabled: BoolProperty(default=True)

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        count = deform.set_preserve_volume(rig.obj, self.enabled)
        st = properties.settings(context)
        st.preserve_volume = self.enabled
        self.report({"INFO"}, f"Preserve volume {'on' if self.enabled else 'off'} "
                              f"for {count} modifier(s)")
        return {"FINISHED"}


class APEX_OT_corrective_smooth(_ApexOp):
    bl_idname = "apex.corrective_smooth"
    bl_label = "Corrective Smooth"
    bl_description = "Add a deformation-aware smoothing modifier after the skin"

    factor: FloatProperty(name="Factor", default=0.5, min=0.0, max=1.0)
    iterations: IntProperty(name="Iterations", default=10, min=0, max=60)

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        meshes = _selected_meshes(context) or utils.meshes_of_armature(rig.obj)
        count = 0
        for ob in meshes:
            deform.add_corrective_smooth(ob, factor=self.factor,
                                         iterations=self.iterations)
            count += 1
        self.report({"INFO"}, f"Corrective smooth added to {count} mesh(es)")
        return {"FINISHED"}


class APEX_OT_remove_corrective(_ApexOp):
    bl_idname = "apex.remove_corrective"
    bl_label = "Remove Corrective Smooth"
    bl_description = "Remove Apex corrective smoothing modifiers"

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        meshes = _selected_meshes(context) or utils.meshes_of_armature(rig.obj)
        count = sum(deform.remove_corrective_smooth(ob) for ob in meshes)
        self.report({"INFO"}, f"Removed {count} modifier(s)")
        return {"FINISHED"}


class APEX_OT_weight_op(_ApexOp):
    bl_idname = "apex.weight_op"
    bl_label = "Weight Tool"
    bl_description = "Edit weights of the bound meshes"

    tool: EnumProperty(items=(("SMOOTH", "Smooth", "Blur the weights"),
                              ("SYMMETRIZE", "Symmetrize", "Mirror one side onto the other"),
                              ("CLEAN", "Clean", "Limit to 4 influences and normalize"),
                              ("HEATMAP", "Heatmap", "Colour vertices by dominant bone"),
                              ("RESTORE", "Restore Coverage", "Give every bone geometry again")),
                       default="SMOOTH")
    iterations: IntProperty(name="Iterations", default=3, min=1, max=30)
    factor: FloatProperty(name="Strength", default=0.5, min=0.05, max=1.0)
    direction: EnumProperty(name="Direction", default="L_TO_R",
                            items=(("L_TO_R", "Left to Right", ""),
                                   ("R_TO_L", "Right to Left", "")))

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        meshes = _selected_meshes(context) or utils.meshes_of_armature(rig.obj)
        # dedicated props (eyes, mouth interior) only own one bone each, so they
        # would report every other bone as "unweighted": audit the real skin only
        props_meshes = [ob for ob in meshes
                        if ob.get("apex_eye") or ob.get("apex_mouth")]
        skin_meshes = [ob for ob in meshes if ob not in props_meshes]
        meshes = skin_meshes or meshes
        if not meshes:
            self.report({"WARNING"}, "No skinned meshes found")
            return {"CANCELLED"}
        lines = []
        for ob in meshes:
            if self.tool == "SMOOTH":
                deform.smooth_weights(ob, iterations=self.iterations,
                                      factor=self.factor)
            elif self.tool == "SYMMETRIZE":
                deform.symmetrize_weights(ob, direction=self.direction)
            elif self.tool == "CLEAN":
                deform.clean_weights(ob)
            elif self.tool == "HEATMAP":
                info = deform.weight_heatmap(ob, rig.obj)
                lines.append(f"{ob.name}: {info['verts']} verts, "
                             f"{info['colors']} bone colours")
                continue
            else:
                deform.ensure_bone_coverage(ob, rig.obj)
            lines.append(f"{ob.name}: done")
        self.report({"INFO"}, " · ".join(lines))
        return {"FINISHED"}


class APEX_OT_deform_check(_ApexOp):
    bl_idname = "apex.deform_check"
    bl_label = "Check Deformation"
    bl_description = ("Stress-pose the rig and measure which bones fail to move "
                      "their vertices (also samples the current action)")

    check_animation: BoolProperty(name="Check Animation", default=True)

    def execute(self, context):
        st = properties.settings(context)
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        meshes = _selected_meshes(context) or utils.meshes_of_armature(rig.obj)
        # dedicated props (eyes, mouth interior) only own one bone each, so they
        # would report every other bone as "unweighted": audit the real skin only
        props_meshes = [ob for ob in meshes
                        if ob.get("apex_eye") or ob.get("apex_mouth")]
        skin_meshes = [ob for ob in meshes if ob not in props_meshes]
        meshes = skin_meshes or meshes
        if not meshes:
            self.report({"WARNING"}, "No skinned meshes found")
            return {"CANCELLED"}
        worst = []
        empty_all = []
        stalled_all = []
        static_anim = []
        anim_frames = 0
        for ob in meshes:
            report = deform.deform_check(rig.obj, ob)
            empty_all += report["empty_bones"]
            stalled_all += report["stalled_bones"]
            worst += report["weakest"]
            if self.check_animation and rig.obj.animation_data is not None \
                    and rig.obj.animation_data.action is not None:
                coverage = deform.animation_coverage(rig.obj, ob)
                anim_frames = max(anim_frames, coverage["frames"])
                static_anim += [name for name in coverage["static_bones"]
                                if name not in static_anim]
        worst.sort(key=lambda kv: kv[1])
        prop_note = (f" · {len(props_meshes)} prop mesh(es)" if props_meshes else "")
        st.deform_report = (f"{len(meshes)} mesh(es){prop_note} · "
                            f"{len(empty_all)} bones without weights · "
                            f"{len(stalled_all)} bones that do not move their verts")
        details = [f"empty: {', '.join(empty_all[:6])}" if empty_all else "empty: none",
                   f"stalled: {', '.join(stalled_all[:6])}" if stalled_all else "stalled: none",
                   "weakest movers: " + ", ".join(
                       f"{n} {d * 100:.1f} cm" for n, d in worst[:4])]
        if anim_frames:
            details.insert(0, f"{anim_frames} sampled frames · "
                              f"{len(static_anim)} bones static in the action"
                              + (f" ({', '.join(static_anim[:6])})" if static_anim else ""))
        st.deform_details = "; ".join(details)
        self.report({"INFO"}, st.deform_report)
        if empty_all:
            self.report({"WARNING"}, f"Bones without weights: {empty_all[:8]}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Skinning
# ---------------------------------------------------------------------------
class APEX_OT_pick_skin_method(_ApexOp):
    bl_idname = "apex.pick_skin_method"
    bl_label = "Skinning Method"
    bl_description = "Choose the weight method (picture buttons)"

    method: StringProperty(default="APEX")

    def execute(self, context):
        st = properties.settings(context)
        st.skin_method = self.method
        return {"FINISHED"}


class APEX_OT_skin_selected(_ApexOp):
    bl_idname = "apex.skin_selected"
    bl_label = "Skin Selected Meshes"
    bl_description = "Bind selected meshes to the active rig and generate weights"

    def execute(self, context):
        st = properties.settings(context)
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        meshes = _selected_meshes(context)
        if not meshes:
            self.report({"WARNING"}, "Select at least one mesh")
            return {"CANCELLED"}
        total = 0
        for ob in meshes:
            try:
                stats = skin.skin_mesh(rig.obj, ob, method=st.skin_method,
                                       smooth_iterations=st.smooth_iterations,
                                       max_influences=st.max_influences)
                total += stats.get("verts", 0)
            except Exception as exc:
                utils.log.exception("skinning failed for %s", ob.name)
                self.report({"ERROR"}, f"{ob.name}: {exc}")
                return {"CANCELLED"}
        self.report({"INFO"}, f"Skinned {len(meshes)} mesh(es), {total} vertices")
        return {"FINISHED"}


class APEX_OT_unbind_meshes(_ApexOp):
    bl_idname = "apex.unbind_meshes"
    bl_label = "Unbind Meshes"
    bl_description = "Remove armature modifiers and vertex groups from bound meshes"

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        count = skin.unbind_meshes(rig.obj)
        self.report({"INFO"}, f"Unbound {count} modifier(s)")
        return {"FINISHED"}


class APEX_OT_weight_report(_ApexOp):
    bl_idname = "apex.weight_report"
    bl_label = "Check Weights"
    bl_description = "Validate weights of selected meshes (or all bound meshes)"

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        meshes = _selected_meshes(context) or utils.meshes_of_armature(rig.obj)
        # dedicated props (eyes, mouth interior) only own one bone each, so they
        # would report every other bone as "unweighted": audit the real skin only
        props_meshes = [ob for ob in meshes
                        if ob.get("apex_eye") or ob.get("apex_mouth")]
        skin_meshes = [ob for ob in meshes if ob not in props_meshes]
        meshes = skin_meshes or meshes
        if not meshes:
            self.report({"WARNING"}, "No skinned meshes found")
            return {"CANCELLED"}
        lines = []
        for ob in meshes:
            rep = skin.weight_report(ob, rig.obj)
            lines.append(f"{ob.name}: {rep['verts']} verts, "
                         f"{rep['unweighted']} unweighted, "
                         f"{rep['over_four_influences']} over-4, "
                         f"{rep['not_normalised']} unnormalised")
        utils.log.info(" | ".join(lines))
        self.report({"INFO"}, lines[0] if len(lines) == 1 else lines[0] + " ...")
        for line in lines:
            self.report({"INFO"}, line)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Pose tools
# ---------------------------------------------------------------------------
class APEX_OT_snap(_ApexOp):
    bl_idname = "apex.snap"
    bl_label = "Snap IK / FK"
    bl_description = "Snap between IK and FK without changing the pose"

    mode: EnumProperty(name="Mode", items=(
        ("IK_TO_FK", "IK to FK", "Bake the IK pose into the FK chain"),
        ("FK_TO_IK", "FK to IK", "Move the IK controls onto the FK pose"),
    ), default="IK_TO_FK")
    limb: EnumProperty(name="Limb", items=LIMB_ITEMS, default="arm")
    side: EnumProperty(name="Side", items=SIDE_ITEMS, default="BOTH")

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        sides = ("L", "R") if self.side == "BOTH" else (self.side,)
        for side in sides:
            if self.mode == "IK_TO_FK":
                rig.snap_ik_to_fk(self.limb, side)
            else:
                rig.snap_fk_to_ik(self.limb, side)
        return {"FINISHED"}


class APEX_OT_toggle_ik(_ApexOp):
    bl_idname = "apex.toggle_ik"
    bl_label = "Toggle IK"
    bl_description = "Switch a limb between IK and FK"

    limb: EnumProperty(name="Limb", items=LIMB_ITEMS, default="arm")
    side: EnumProperty(name="Side", items=SIDE_ITEMS, default="BOTH")

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        sides = ("L", "R") if self.side == "BOTH" else (self.side,)
        for side in sides:
            # snapping keeps the silhouette when switching
            if rig.get_prop(f"ik_{self.limb}.{side}") > 0.5:
                rig.snap_ik_to_fk(self.limb, side)
            else:
                rig.snap_fk_to_ik(self.limb, side)
        return {"FINISHED"}


class APEX_OT_mirror_pose(_ApexOp):
    bl_idname = "apex.mirror_pose"
    bl_label = "Mirror Pose"
    bl_description = "Mirror the current pose across the character's X axis"

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        rig.mirror_pose()
        return {"FINISHED"}


class APEX_OT_reset_pose(_ApexOp):
    bl_idname = "apex.reset_pose"
    bl_label = "Reset Pose"
    bl_description = "Clear the pose and restore default rig properties"

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        utils.clear_pose(rig.obj, prop_defaults=True)
        utils.refresh(rig.obj)
        return {"FINISHED"}


class APEX_OT_key_controls(_ApexOp):
    bl_idname = "apex.key_controls"
    bl_label = "Key Controls"
    bl_description = "Insert location/rotation keys on control bones"

    scope: EnumProperty(name="Scope", items=(
        ("CONTROLS", "Controls", "Only non-deform controls"),
        ("SELECTED", "Selected", "Selected bones"),
        ("ALL", "All Bones", "Every pose bone"),
    ), default="CONTROLS")
    include_props: BoolProperty(name="Include Rig Properties", default=True)

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        if context.mode != "POSE":
            utils.set_active(rig.obj)
            try:
                bpy.ops.object.mode_set(mode="POSE")
            except Exception:
                pass
        scene = context.scene
        frame = scene.frame_current
        count = 0
        bones = []
        for pb in rig.obj.pose.bones:
            if self.scope == "CONTROLS" and rig.obj.data.bones[pb.name].use_deform:
                continue
            if self.scope == "SELECTED" and not pb.bone.select:
                continue
            bones.append(pb)
        for pb in bones:
            pb.keyframe_insert("location", frame=frame, group=pb.name)
            if pb.rotation_mode == "QUATERNION":
                pb.keyframe_insert("rotation_quaternion", frame=frame, group=pb.name)
            elif pb.rotation_mode == "AXIS_ANGLE":
                pb.keyframe_insert("rotation_axis_angle", frame=frame, group=pb.name)
            else:
                pb.keyframe_insert("rotation_euler", frame=frame, group=pb.name)
            count += 1
        if self.include_props:
            props_pb = rig.props_bone
            if props_pb is not None:
                for name in PROPS:
                    if name in props_pb.keys():
                        props_pb.keyframe_insert(f'["{name}"]', frame=frame,
                                                 group="Apex Props")
        self.report({"INFO"}, f"Keyed {count} bones on frame {frame}")
        return {"FINISHED"}


class APEX_OT_select_controls(_ApexOp):
    bl_idname = "apex.select_controls"
    bl_label = "Select Controls"
    bl_description = "Select every control bone of the active rig"

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        utils.set_active(rig.obj)
        if context.mode != "POSE":
            try:
                bpy.ops.object.mode_set(mode="POSE")
            except Exception:
                pass
        for pb in rig.obj.pose.bones:
            pb.bone.select = not pb.bone.use_deform
        return {"FINISHED"}


class APEX_OT_collection_visibility(_ApexOp):
    bl_idname = "apex.collection_visibility"
    bl_label = "Show Bone Collection"
    bl_description = "Toggle visibility of a bone collection on the active rig"

    collection: StringProperty(default="Controls")
    visible: BoolProperty(default=True)

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        rig.collection_visibility(self.collection, self.visible)
        return {"FINISHED"}


class APEX_OT_pole_step(_ApexOp):
    bl_idname = "apex.pole_step"
    bl_label = "Nudge Pole Angle"
    bl_description = "Rotate the IK pole by a few degrees to avoid knee pops"

    limb: EnumProperty(name="Limb", items=LIMB_ITEMS, default="leg")
    side: EnumProperty(name="Side", items=SIDE_ITEMS, default="BOTH")
    step: FloatProperty(name="Step", default=5.0, min=-90.0, max=90.0)

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        sides = ("L", "R") if self.side == "BOTH" else (self.side,)
        for side in sides:
            prop = f"pole_angle_{self.limb}.{side}"
            rig.set_prop(prop, rig.get_prop(prop) + self.step)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Animation
# ---------------------------------------------------------------------------
class APEX_OT_add_motion(_ApexOp):
    bl_idname = "apex.add_motion"
    bl_label = "Add Motion"
    bl_description = "Generate a procedural motion on the active rig"

    def execute(self, context):
        st = properties.settings(context)
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        loop = None if st.motion_use_default_loop else st.motion_loop
        try:
            action = animation.create_motion(rig.obj, st.motion, start=st.motion_start,
                                             loop=loop)
        except Exception as exc:
            utils.log.exception("motion failed")
            self.report({"ERROR"}, f"Motion failed: {exc}")
            return {"CANCELLED"}
        if st.motion_push_nla:
            try:
                start = max(float(st.motion_start), animation.next_free_frame(rig.obj))
                animation.push_action_to_nla(rig.obj, action, start=start,
                                             mute=st.motion_mute)
            except Exception as exc:
                utils.log.warning("NLA push failed: %s", exc)
        start, end = utils.action_range(action)
        scene = context.scene
        scene.frame_start = int(min(scene.frame_start, start))
        scene.frame_end = int(max(scene.frame_end, end))
        self.report({"INFO"}, f"Created {action.name} ({int(end - start)} frames)")
        return {"FINISHED"}


class APEX_OT_clear_animation(_ApexOp):
    bl_idname = "apex.clear_animation"
    bl_label = "Clear Animation"
    bl_description = "Remove actions, NLA tracks and reset the pose"

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        animation.clear_animation(rig.obj)
        return {"FINISHED"}


class APEX_OT_push_action_nla(_ApexOp):
    bl_idname = "apex.push_action_nla"
    bl_label = "Push Action to NLA"
    bl_description = "Store the active action on its own NLA track"

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        ad = rig.obj.animation_data
        if ad is None or ad.action is None:
            self.report({"WARNING"}, "The rig has no active action")
            return {"CANCELLED"}
        animation.push_action_to_nla(rig.obj, ad.action)
        self.report({"INFO"}, f"Pushed {ad.action.name} to the NLA")
        return {"FINISHED"}


class APEX_OT_bake_controls(_ApexOp):
    bl_idname = "apex.bake_controls"
    bl_label = "Bake Controls"
    bl_description = "Bake every control channel of the current pose into a new action"

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        action, _slot = rig.bake_control_rig()
        self.report({"INFO"}, f"Baked controls into {action.name}")
        return {"FINISHED"}


class APEX_OT_bake_animation(_ApexOp):
    bl_idname = "apex.bake_animation"
    bl_label = "Bake Action"
    bl_description = ("Bake the active action to deform bones (visual keying) for "
                      "engines that do not support constraints")

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        ad = rig.obj.animation_data
        if ad is None or ad.action is None:
            self.report({"WARNING"}, "The rig has no active action")
            return {"CANCELLED"}
        start, end = utils.action_range(ad.action)
        baked = animation.bake_action(rig.obj, ad.action, ad.action.name + "_Baked",
                                      start, end)
        self.report({"INFO"}, f"Baked {ad.action.name} -> {baked.name}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Renaming / retarget / export
# ---------------------------------------------------------------------------
class APEX_OT_apply_name_map(_ApexOp):
    bl_idname = "apex.apply_name_map"
    bl_label = "Apply Bone Naming"
    bl_description = "Rename the rig bones to a game-engine naming convention"

    style: EnumProperty(name="Style", items=properties.NAME_MAP_ITEMS,
                        default="UE5")
    keep_vertex_groups: BoolProperty(name="Update Vertex Groups", default=True)

    def execute(self, context):
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        changed = mocap.rename_to_style(rig, self.style,
                                        update_vertex_groups=self.keep_vertex_groups)
        self.report({"INFO"}, f"Renamed {changed} bone(s) to {self.style}")
        return {"FINISHED"}


class APEX_OT_retarget(_ApexOp):
    bl_idname = "apex.retarget"
    bl_label = "Retarget Motion"
    bl_description = ("Bake motion from the selected source armature onto the active "
                      "Apex rig")

    def execute(self, context):
        st = properties.settings(context)
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        sources = [ob for ob in context.selected_objects
                   if ob.type == "ARMATURE" and ob is not rig.obj]
        if not sources:
            self.report({"ERROR"}, "Select the source armature as well")
            return {"CANCELLED"}
        source = sources[0]
        try:
            action, report = mocap.retarget(source, rig, style=st.name_map,
                                            match_scale=st.retarget_scale,
                                            frame_offset=st.retarget_start,
                                            key_ik=not st.retarget_keep_ik)
        except Exception as exc:
            utils.log.exception("retarget failed")
            self.report({"ERROR"}, f"Retarget failed: {exc}")
            return {"CANCELLED"}
        for line in report.get("messages", [])[:4]:
            self.report({"INFO"}, line)
        self.report({"INFO"}, f"Retargeted {report['frames']} frames -> {action.name}")
        return {"FINISHED"}


class APEX_OT_export(_ApexOp):
    bl_idname = "apex.export"
    bl_label = "Export Character"
    bl_description = "Export the rig, meshes and animations for a game engine"

    def invoke(self, context, event):
        st = properties.settings(context)
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        st = properties.settings(context)
        rig = _rig_from_context(context)
        if rig is None:
            return {"CANCELLED"}
        path = bpy.path.abspath(st.export_path)
        if not path:
            self.report({"ERROR"}, "Choose an export path")
            return {"CANCELLED"}
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        try:
            result = export.export_rig(
                context, rig.obj, path,
                preset=st.export_preset,
                selection_only=st.export_selection,
                bake_actions=st.export_bake_actions,
                deform_only=st.export_def_only,
                apply_modifiers=st.export_apply,
            )
        except Exception as exc:
            utils.log.exception("export failed")
            self.report({"ERROR"}, f"Export failed: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Exported to {result}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Live mocap (phone camera over WiFi)
# ---------------------------------------------------------------------------
class APEX_OT_live_start(Operator):
    bl_idname = "apex.live_start"
    bl_label = "Start Live Mocap"
    bl_description = ("Start the WiFi mocap server. Open the printed address on "
                      "your phone camera and the rig follows you")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.apex_settings
        arm = utils.active_rig() or utils.first_rig()
        if arm is None:
            self.report({"ERROR"}, "No Apex rig in the scene")
            return {"CANCELLED"}
        url = live.start(settings.live_port)
        settings.live_url = url
        self.report({"INFO"}, f"Live mocap on {url}")
        return {"FINISHED"}


class APEX_OT_live_stop(Operator):
    bl_idname = "apex.live_stop"
    bl_label = "Stop Live Mocap"
    bl_description = "Stop the WiFi mocap server"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        live.stop()
        context.scene.apex_settings.live_fps = 0.0
        self.report({"INFO"}, "Live mocap stopped")
        return {"FINISHED"}


class APEX_OT_live_copy(Operator):
    bl_idname = "apex.live_copy"
    bl_label = "Copy Address"
    bl_description = "Copy the phone address to the clipboard"

    def execute(self, context):
        settings = context.scene.apex_settings
        url = settings.live_url or "start the server first"
        try:
            context.window_manager.clipboard = url
            self.report({"INFO"}, f"Copied {url}")
        except Exception:
            self.report({"WARNING"}, url)
        return {"FINISHED"}


class APEX_OT_live_record(Operator):
    bl_idname = "apex.live_record"
    bl_label = "Record Take"
    bl_description = "Start or stop recording the live tracking into a take"
    bl_options = {"REGISTER"}

    def execute(self, context):
        if live.STATE["recording"]:
            count = live.stop_recording()
            self.report({"INFO"}, f"Take stopped: {count} frames")
        else:
            live.start_recording()
            self.report({"INFO"}, "Recording... press again to stop")
        return {"FINISHED"}


class APEX_OT_live_bake(Operator):
    bl_idname = "apex.live_bake"
    bl_label = "Bake Take"
    bl_description = "Turn the recorded take into keyframes on the rig"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        arm = utils.active_rig() or utils.first_rig()
        if arm is None or not live.STATE["take"]:
            self.report({"ERROR"}, "Nothing recorded")
            return {"CANCELLED"}
        action = live.bake_take(arm, fps=live.STATE.get("fps") or 30.0)
        if action is None:
            self.report({"ERROR"}, "Bake failed")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Baked {len(live.STATE['take'])} frames into {action.name}")
        return {"FINISHED"}


class APEX_OT_live_expression(Operator):
    bl_idname = "apex.live_expression"
    bl_label = "Face Expression"
    bl_description = "Apply an expression to the face rig"
    bl_options = {"REGISTER", "UNDO"}

    expression: bpy.props.StringProperty(default="SMILE")

    def execute(self, context):
        arm = utils.active_rig() or utils.first_rig()
        if arm is None:
            return {"CANCELLED"}
        face.apply_expression(arm, self.expression)
        return {"FINISHED"}


class APEX_OT_add_eyes(Operator):
    bl_idname = "apex.add_eyes"
    bl_label = "Add Eyes"
    bl_description = "Create eyeballs bound to the face rig"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        arm = utils.active_rig() or utils.first_rig()
        if arm is None:
            self.report({"ERROR"}, "No Apex rig")
            return {"CANCELLED"}
        if not face.has_face(arm):
            face.add_face_bones(arm, context)
        eyes = face.add_eyes(context, arm)
        face.add_mouth_interior(context, arm)
        self.report({"INFO"}, f"Added {len(eyes)} eyes")
        return {"FINISHED"}



CLASSES = (
    APEX_OT_build_realistic,
    APEX_OT_preview_motion,
    APEX_OT_apply_preset,
    APEX_OT_build_rig,
    APEX_OT_delete_rig,
    APEX_OT_apply_pose,
    APEX_OT_key_pose,
    APEX_OT_clear_pose_op,
    APEX_OT_add_motion_pick,
    APEX_OT_preserve_volume,
    APEX_OT_corrective_smooth,
    APEX_OT_remove_corrective,
    APEX_OT_weight_op,
    APEX_OT_deform_check,
    APEX_OT_analyze_character,
    APEX_OT_rig_character,
    APEX_OT_fit_rig,
    APEX_OT_check_fit,
    APEX_OT_pick_skin_method,
    APEX_OT_skin_selected,
    APEX_OT_unbind_meshes,
    APEX_OT_weight_report,
    APEX_OT_snap,
    APEX_OT_toggle_ik,
    APEX_OT_mirror_pose,
    APEX_OT_reset_pose,
    APEX_OT_key_controls,
    APEX_OT_select_controls,
    APEX_OT_collection_visibility,
    APEX_OT_pole_step,
    APEX_OT_add_motion,
    APEX_OT_clear_animation,
    APEX_OT_push_action_nla,
    APEX_OT_bake_controls,
    APEX_OT_bake_animation,
    APEX_OT_apply_name_map,
    APEX_OT_retarget,
    APEX_OT_export,
    APEX_OT_live_start,
    APEX_OT_live_stop,
    APEX_OT_live_copy,
    APEX_OT_live_record,
    APEX_OT_live_bake,
    APEX_OT_live_expression,
    APEX_OT_add_eyes,
)


def register():
    for cls in CLASSES:
        try:
            bpy.utils.register_class(cls)
        except RuntimeError:
            pass  # already registered (extension reload)


def unregister():
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
