# SPDX-License-Identifier: GPL-3.0-or-later
"""Apex Rig & Motion - N-panel UI (picture driven)."""
from __future__ import annotations

import bpy
from bpy.types import Panel

from . import face_icons, properties, rig as rigmod, ui_icons, utils
from .const import (ADDON_NAME, MOTIONS, PROPS, SKIN_METHODS,
                    VERSION_STRING, WALK_PRESETS)

POSE_ORDER = ("A_POSE", "T_POSE", "RELAXED", "COMBAT", "CROUCH", "JUMP",
              "WAVE", "HERO", "SIT", "LOOK_BACK")


def _layout_header(layout, rig):
    row = layout.row(align=True)
    row.label(text="APEX", icon="ARMATURE_DATA")
    row.label(text=f"v{VERSION_STRING}")
    if rig is not None:
        row.label(text=f"{len(rig.obj.data.bones)} bones")


class APEX_PT_base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Apex"
    bl_options = set()


class APEX_PT_general(APEX_PT_base, Panel):
    """Root panel (BlenRig-style): every other Apex panel nests under it."""
    bl_label = "Apex Rig & Motion"
    bl_idname = "APEX_PT_general"

    def draw(self, context):
        layout = self.layout
        rig = rigmod.get_rig()
        _layout_header(layout, rig)
        if rig is None:
            layout.label(text="Start with My Character or a Realistic Body", icon="INFO")
        else:
            layout.label(text=f"Rig: {rig.obj.name}", icon="OUTLINER_OB_ARMATURE")


def _child(cls, order, parent="APEX_PT_general", closed=False):
    """Attach a section panel under the root with a fixed order."""
    cls.bl_parent_id = parent
    cls.bl_order = order
    cls.bl_options = {"DEFAULT_CLOSED"} if closed else set()
    return cls


# ---------------------------------------------------------------------------
# 1. Character (fit to an existing mesh)
# ---------------------------------------------------------------------------
class APEX_PT_character(APEX_PT_base, Panel):
    bl_label = "My Character"
    bl_idname = "APEX_PT_character"

    def draw(self, context):
        layout = self.layout
        st = properties.settings(context)
        rig = rigmod.get_rig()

        box = layout.box()
        col = box.column(align=True)
        col.label(text="Rig a character you already have", icon="MESH_DATA")
        col.label(text="1. Select your character mesh", icon="RESTRICT_SELECT_OFF")
        col.label(text="2. Analyze, then Rig My Character", icon="RESTRICT_SELECT_OFF")

        row = box.row(align=True)
        row.operator("apex.analyze_character", icon="VIEWZOOM")
        row.operator("apex.check_fit", text="Check", icon="CHECKMARK")

        if st.detected_summary:
            info = box.column(align=True)
            info.scale_y = 0.95
            for label, value in (("Height", f"{st.detected_height:.3f} m"),
                                 ("A-pose", f"{st.detected_arm_angle:.1f}°"),
                                 ("Facing", st.detected_facing.replace("FRONT_", "")),
                                 ("Leg length", f"{st.detected_leg_len:.3f}"),
                                 ("Measured from", st.detected_source)):
                row = info.row(align=True)
                row.label(text=label)
                row.label(text=value)
            if st.detected_fit:
                box.label(text=st.detected_fit, icon="INFO")

        col = box.column(heading="Fit")
        col.prop(st, "fit_facing", text="Facing")
        col.prop(st, "fit_prefer_skeleton", text="Use Existing Skeleton")
        col.prop(st, "fit_refine", text="Fit Proportions")
        col.prop(st, "fit_replace_rig", text="Replace Existing Rig")
        col.prop(st, "fit_skin", text="Skin Afterwards")

        big = box.column(align=True)
        big.scale_y = 1.5
        big.operator("apex.rig_character", text="Rig My Character", icon="ARMATURE_DATA")

        if rig is not None:
            row = box.row(align=True)
            row.operator("apex.fit_rig", text="Refit Existing Rig", icon="SNAP_ON")
            row.operator("apex.unbind_meshes", text="Unbind", icon="X")


# ---------------------------------------------------------------------------
# 2. Body presets (picture buttons)
# ---------------------------------------------------------------------------
class APEX_PT_body(APEX_PT_base, Panel):
    bl_label = "Body Presets"
    bl_idname = "APEX_PT_body"

    def draw(self, context):
        layout = self.layout
        st = properties.settings(context)

        # ---- realistic adult body (MakeHuman CC0 data) ----------------
        # The realistic character is the only body. Poses, motions and
        # skinning all act on it; the old mannequin presets are no longer offered.
        rbox = layout.box()
        rbox.label(text="Realistic Body (MakeHuman)", icon="USER")
        from .makehuman import PRESETS as REAL
        real_items = [(k, v[0]) for k, v in REAL.items() if k != "REAL_CUSTOM"]
        if ui_icons.icon_id("body", "REAL_MALE") != 0:
            ui_icons.picture_grid(
                rbox, "apex.build_realistic", real_items, "body", columns=4,
                props_for=lambda key: {"preset": key})
        else:
            grid = rbox.grid_flow(columns=2, align=True)
            for key, label in real_items:
                op = grid.operator("apex.build_realistic", text=label)
                op.preset = key
        sub = rbox.column(align=True)
        sub.prop(st, "rb_gender", slider=True)
        sub.prop(st, "rb_muscle", slider=True)
        sub.prop(st, "rb_weight", slider=True)
        op = sub.operator("apex.build_realistic", text="Build Custom Body", icon="ARMATURE_DATA")
        op.preset = "REAL_CUSTOM"
        if st.detected_fit:
            rbox.label(text=f"Fit: {st.detected_fit}", icon="CHECKMARK")

        col = layout.column(align=True)
        col.label(text="Proportions", icon="TOOL_SETTINGS")
        col.prop(st, "height")
        col.prop(st, "build", slider=True)
        grid = col.grid_flow(row_major=True, columns=2, align=True)
        for name in ("head_scale", "shoulder", "chest", "waist", "hip",
                     "arm_len", "leg_len", "arm_angle", "fingers"):
            grid.prop(st, name)
        col.prop(st, "twist_bones")
        col.prop(st, "bbone")

        big = layout.column(align=True)
        big.scale_y = 1.4
        big.operator("apex.build_rig", text="Build Rig", icon="ARMATURE_DATA")
        rig = rigmod.get_rig()
        if rig is not None:
            layout.operator("apex.delete_rig", text="Delete Rig", icon="TRASH")


# ---------------------------------------------------------------------------
# 3. Poses (picture buttons)
# ---------------------------------------------------------------------------
class APEX_PT_poses(APEX_PT_base, Panel):
    bl_label = "Poses"
    bl_idname = "APEX_PT_poses"

    @classmethod
    def poll(cls, context):
        return rigmod.get_rig() is not None

    def draw(self, context):
        layout = self.layout
        st = properties.settings(context)
        box = layout.box()
        box.label(text="Click a pose to apply it", icon="POSE_HLT")
        from .poses import POSE_LIBRARY

        items = [(key, POSE_LIBRARY[key][0]) for key in POSE_ORDER
                 if key in POSE_LIBRARY]
        if ui_icons.icon_id("pose", "RELAXED") != 0:
            ui_icons.picture_grid(
                box, "apex.apply_pose", items, "pose", columns=5,
                props_for=lambda key: {"pose": key})
        else:
            grid = box.grid_flow(columns=2, align=True)
            for key, label in items:
                op = grid.operator("apex.apply_pose", text=label)
                op.pose = key

        row = layout.row(align=True)
        row.operator("apex.key_pose", text="Key Pose", icon="KEY_HLT")
        row.operator("apex.clear_pose_op", text="Clear", icon="LOOP_BACK")
        row = layout.row(align=True)
        row.operator("apex.mirror_pose", text="Mirror", icon="ARROW_LEFTRIGHT")
        row.operator("apex.reset_pose", text="Rest", icon="FILE_REFRESH")
        layout.label(text="Tip: thumbnails need a GPU session", icon="INFO")


# ---------------------------------------------------------------------------
# 4. Controls (IK / FK, fingers, poles)
# ---------------------------------------------------------------------------
class APEX_PT_controls(APEX_PT_base, Panel):
    bl_label = "Controls"
    bl_idname = "APEX_PT_controls"

    @classmethod
    def poll(cls, context):
        return rigmod.get_rig() is not None

    def draw(self, context):
        layout = self.layout
        rig = rigmod.get_rig()
        pb = rig.props_bone if rig else None
        if pb is None:
            layout.label(text="No control properties found", icon="ERROR")
            return

        for limb, icon in (("arm", "VIEW_PAN"), ("leg", "MOD_ARMATURE")):
            box = layout.box()
            box.label(text=limb.title() + " IK / FK", icon=icon)
            for side in ("L", "R"):
                row = box.row(align=True)
                prop = f"ik_{limb}.{side}"
                if prop in pb.keys():
                    row.prop(pb, f'["{prop}"]', text=side, slider=True)
                mprop = f"mocap_{limb}.{side}"
                if mprop in pb.keys():
                    row.prop(pb, f'["{mprop}"]', text="MOCAP", slider=True)
                op = row.operator("apex.toggle_ik", text="", icon="FILE_REFRESH")
                op.limb = limb
                op.side = side
            row = box.row(align=True)
            op = row.operator("apex.snap", text="Snap IK > FK")
            op.mode = "IK_TO_FK"
            op.limb = limb
            op.side = "BOTH"
            op = row.operator("apex.snap", text="Snap FK > IK")
            op.mode = "FK_TO_IK"
            op.limb = limb
            op.side = "BOTH"

        box = layout.box()
        box.label(text="Fingers", icon="HAND")
        for side in ("L", "R"):
            row = box.row(align=True)
            row.label(text=side)
            for prop in (f"finger_curl.{side}", f"finger_spread.{side}",
                         f"thumb_curl.{side}"):
                if prop in pb.keys():
                    row.prop(pb, f'["{prop}"]', text="", slider=True)

        box = layout.box()
        box.label(text="Pole Targets", icon="PIVOT_CURSOR")
        for limb in ("arm", "leg"):
            for side in ("L", "R"):
                prop = f"pole_angle_{limb}.{side}"
                if prop not in pb.keys():
                    continue
                row = box.row(align=True)
                row.prop(pb, f'["{prop}"]', text=f"{limb.title()} {side}")
                for step, icon_sign in ((-5.0, "REMOVE"), (5.0, "ADD")):
                    op = row.operator("apex.pole_step", text="", icon=icon_sign)
                    op.step = step
                    op.limb = limb
                    op.side = side

        box = layout.box()
        box.label(text="Bone Collections", icon="GROUP_BONE")
        for coll in rig.obj.data.collections:
            row = box.row(align=True)
            row.prop(coll, "is_visible", text=coll.name, emboss=False,
                     icon="HIDE_OFF" if coll.is_visible else "HIDE_ON")


# ---------------------------------------------------------------------------
# 5. Skinning
# ---------------------------------------------------------------------------
class APEX_PT_skin(APEX_PT_base, Panel):
    bl_label = "Skinning"
    bl_idname = "APEX_PT_skin"

    def draw(self, context):
        layout = self.layout
        st = properties.settings(context)
        rig = rigmod.get_rig()

        box = layout.box()
        box.label(text="Weight Method", icon="MOD_VERTEX_WEIGHT")
        items = [(key, label) for key, label, _desc in SKIN_METHODS]
        if ui_icons.icon_id("skin", "APEX") != 0:
            ui_icons.picture_grid(box, "apex.pick_skin_method", items, "skin",
                                  columns=4,
                                  props_for=lambda key: {"method": key})
        col = box.column(align=True)
        col.prop(st, "skin_method", text="")
        col.prop(st, "smooth_iterations")
        col.prop(st, "max_influences")
        col.operator("apex.skin_selected", text="Skin Selected Meshes",
                     icon="MOD_VERTEX_WEIGHT")
        col.operator("apex.weight_report", text="Validate Weights", icon="CHECKMARK")
        col.operator("apex.detect_parts", text="Detect Body Parts", icon="OUTLINER_OB_GROUP_INSTANCE")
        col.operator("apex.unbind_meshes", icon="X")

        box = layout.box()
        box.label(text="Weight Tools", icon="BRUSH_DATA")
        row = box.row(align=True)
        for tool, label in (("SMOOTH", "Smooth"), ("SYMMETRIZE", "Symmetrize")):
            op = row.operator("apex.weight_op", text=label)
            op.tool = tool
        row = box.row(align=True)
        for tool, label in (("CLEAN", "Clean 4"), ("RESTORE", "Restore")):
            op = row.operator("apex.weight_op", text=label)
            op.tool = tool
        box.operator("apex.weight_op", text="Weight Heatmap",
                     icon="COLOR").tool = "HEATMAP"

        if rig is not None:
            box = layout.box()
            box.label(text="Deformation", icon="MOD_ARMATURE")
            box.prop(st, "preserve_volume")
            op = box.operator("apex.preserve_volume",
                              text="Apply Preserve Volume", icon="CHECKMARK")
            op.enabled = st.preserve_volume
            row = box.row(align=True)
            row.operator("apex.corrective_smooth", text="Corrective Smooth",
                         icon="SMOOTH")
            row.operator("apex.remove_corrective", text="", icon="X")
            big = box.column(align=True)
            big.scale_y = 1.3
            big.operator("apex.deform_check", text="Check Deformation",
                         icon="PLAY")
            if st.deform_report:
                box.label(text=st.deform_report, icon="INFO")
            if st.deform_details:
                col = box.column(align=True)
                col.scale_y = 0.9
                for line in st.deform_details.split("; "):
                    col.label(text=line)


# ---------------------------------------------------------------------------
# 6. Animation (picture buttons)
# ---------------------------------------------------------------------------
class APEX_PT_animation(APEX_PT_base, Panel):
    bl_label = "Animation"
    bl_idname = "APEX_PT_animation"

    @classmethod
    def poll(cls, context):
        return rigmod.get_rig() is not None

    def draw(self, context):
        layout = self.layout
        st = properties.settings(context)
        rig = rigmod.get_rig()

        box = layout.box()
        box.label(text="Click a motion to add it", icon="PLAY")
        items = []
        for key, data in MOTIONS.items():
            items.append((key, data[0]))
        for key, data in WALK_PRESETS.items():
            items.append((key, data[0]))
        if ui_icons.icon_id("motion", "WALK") != 0:
            ui_icons.picture_grid(
                box, "apex.add_motion_pick", items, "motion", columns=5,
                props_for=lambda key: {"motion": key})
        else:
            grid = box.grid_flow(columns=3, align=True)
            for key, label in items:
                op = grid.operator("apex.add_motion_pick", text=label)
                op.motion = key

        pv = layout.row()
        pv.scale_y = 1.2
        pv.operator("apex.preview_motion", text="Preview Motion", icon="PLAY")

        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(st, "motion_start")
        row.prop(st, "motion_use_default_loop", text="Auto Loop")
        row = col.row(align=True)
        row.prop(st, "motion_push_nla")
        row.prop(st, "motion_mute")

        box = layout.box()
        box.label(text="Actions", icon="ACTION")
        ad = rig.obj.animation_data if rig else None
        if ad and ad.action:
            box.label(text=ad.action.name, icon="FILE")
            row = box.row(align=True)
            row.operator("apex.push_action_nla", text="Push to NLA", icon="NLA_PUSHED")
            row.operator("apex.bake_animation", text="Bake", icon="REC")
        else:
            box.label(text="No active action", icon="INFO")
        row = box.row(align=True)
        row.operator("apex.bake_controls", text="Bake Controls", icon="DUPLICATE")
        row.operator("apex.clear_animation", text="Clear", icon="TRASH")


# ---------------------------------------------------------------------------
# 7. Mocap / retarget
# ---------------------------------------------------------------------------
class APEX_PT_retarget(APEX_PT_base, Panel):
    bl_label = "Mocap / Retarget"
    bl_idname = "APEX_PT_retarget"

    @classmethod
    def poll(cls, context):
        return rigmod.get_rig() is not None

    def draw(self, context):
        layout = self.layout
        st = properties.settings(context)
        col = layout.column(align=True)
        col.label(text="Source must be selected too", icon="INFO")
        col.prop(st, "name_map", text="Source Style")
        col.prop(st, "retarget_scale")
        col.prop(st, "retarget_start")
        col.prop(st, "retarget_keep_ik")
        col.scale_y = 1.3
        col.operator("apex.retarget", text="Retarget Selected", icon="ARMATURE_DATA")
        layout.operator("apex.apply_name_map", text="Rename Rig Bones", icon="SORTALPHA")


# ---------------------------------------------------------------------------
# 8. Export
# ---------------------------------------------------------------------------
class APEX_PT_export(APEX_PT_base, Panel):
    bl_label = "Export"
    bl_idname = "APEX_PT_export"

    def draw(self, context):
        layout = self.layout
        st = properties.settings(context)
        rig = rigmod.get_rig()
        col = layout.column(align=True)
        col.prop(st, "export_preset", text="")
        col.prop(st, "export_path", text="")
        col.prop(st, "export_selection")
        col.prop(st, "export_bake_actions")
        col.prop(st, "export_def_only")
        col.prop(st, "export_apply")
        col.scale_y = 1.3
        col.operator("apex.export", text="Export", icon="EXPORT")
        if rig is not None:
            meshes = utils.meshes_of_armature(rig.obj)
            col.label(text=f"{len(meshes)} skinned mesh(es)", icon="MESH_DATA")


class APEX_PT_face(APEX_PT_base, Panel):
    bl_label = "Face"
    bl_idname = "APEX_PT_face"

    def draw(self, context):
        from . import face
        layout = self.layout
        st = properties.settings(context)
        arm = utils.active_rig() or utils.first_rig()
        if arm is None:
            layout.label(text="Build or select an Apex rig first", icon="INFO")
            return
        active = face.has_face(arm)
        row = layout.row(align=True)
        row.scale_y = 1.25
        if active:
            info = face.face_report(arm)
            row.label(text=f"{info['bones']} face bones · {info['controls']} controls",
                      icon="CHECKMARK")
        else:
            row.operator("apex.add_eyes", text="Add Facial Rig", icon="ADD")
            return

        layout.separator()
        grid = face_icons.picture_grid(layout, "expression", face.EXPRESSION_ORDER,
                                       columns=4, operator="apex.live_expression")
        layout.separator()

        col = layout.column(align=True)
        col.operator("apex.add_eyes", text="Add Eyes + Mouth", icon="HIDE_OFF")
        col.operator("apex.deform_check", text="Check Face Deformation",
                     icon="MOD_ARMATURE")

        box = layout.box()
        box.label(text="Live controls", icon="POSE_HLT")
        props_bone = arm.pose.bones.get(arm.get("root_bone", "root"))
        if props_bone is None:
            return
        groups = (
            ("Jaw", ("jaw_open", "jaw_side", "jaw_thrust", "chin_raise")),
            ("Lips", ("lip_up_raise", "lip_low_drop", "mouth_pucker",
                      "mouth_smile.L", "mouth_smile.R", "mouth_frown.L")),
            ("Brows & eyes", ("brow_raise.L", "brow_inner_up", "brow_furrow",
                              "blink.L", "blink.R", "squint.L")),
        )
        for title, names in groups:
            sub = box.column(align=True)
            sub.label(text=title)
            for name in names:
                if name in props_bone.keys():
                    sub.prop(props_bone, f'["{name}"]', text=name.replace("_", " "),
                             slider=True)


class APEX_PT_live(APEX_PT_base, Panel):
    bl_label = "Live Mocap (WiFi camera)"
    bl_idname = "APEX_PT_live"

    def draw(self, context):
        from . import live
        layout = self.layout
        st = properties.settings(context)
        running = live.is_running()

        box = layout.box()
        row = box.row(align=True)
        row.scale_y = 1.3
        if running:
            row.operator("apex.live_stop", text="Stop", icon="PAUSE")
        else:
            row.operator("apex.live_start", text="Start Server", icon="PLAY")
        box.operator("apex.live_copy", text=st.live_url or "Copy Address", icon="COPY_ID")

        info = box.column(align=True)
        info.label(text=("Server running" if running else "Server stopped"),
                   icon="CHECKMARK" if running else "X")
        info.label(text=f"Frames {st.live_frames}   {st.live_fps:.1f} fps   "
                        f"clients {st.live_clients}")

        col = layout.column(align=True)
        col.prop(st, "live_port")
        col.prop(st, "live_head")
        col.prop(st, "live_smooth")

        layout.separator()
        row = layout.row(align=True)
        row.scale_y = 1.25
        row.operator("apex.live_record", text="Record Take",
                     icon="REC" if not live.STATE["recording"] else "PAUSE")
        row.operator("apex.live_bake", text="Bake", icon="KEY_HLT")

        help_box = layout.box()
        help_box.label(text="How to connect", icon="QUESTION")
        for line in ("1. Start the server (this panel).",
                     "2. Phone: same WiFi as this computer.",
                     "3. Open the copied address in the phone browser.",
                     "4. Allow the camera, press Start camera.",
                     "5. Move your face - the rig follows live."):
            help_box.label(text=line)



# (class, order, start collapsed) - BlenRig-style: setup and motion open,
# secondary tools collapsed under the root panel.
_CHILDREN = (
    (APEX_PT_character, 1, False),
    (APEX_PT_body, 2, False),
    (APEX_PT_poses, 3, False),
    (APEX_PT_controls, 4, True),
    (APEX_PT_skin, 5, True),
    (APEX_PT_face, 6, True),
    (APEX_PT_animation, 7, False),
    (APEX_PT_retarget, 8, True),
    (APEX_PT_live, 9, True),
    (APEX_PT_export, 10, True),
)
for _cls, _order, _closed in _CHILDREN:
    _child(_cls, _order, closed=_closed)

CLASSES = (APEX_PT_general,) + tuple(c for c, _o, _c in _CHILDREN)


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
