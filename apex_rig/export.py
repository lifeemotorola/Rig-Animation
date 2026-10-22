# SPDX-License-Identifier: GPL-3.0-or-later
"""Apex Rig & Motion - game-engine export.

Thin, future-proof wrappers around the glTF and FBX exporters.  Keyword
arguments are filtered against the operator's RNA so the add-on keeps working
when Blender renames an export option (which happens regularly).
"""
from __future__ import annotations

import os

import bpy

from . import utils


def _filter_kwargs(op, kwargs: dict) -> dict:
    try:
        rna = op.get_rna_type()
        known = set(rna.properties.keys())
        return {k: v for k, v in kwargs.items() if k in known}
    except Exception:
        return dict(kwargs)


def _select_for_export(arm, selection_only: bool):
    meshes = utils.meshes_of_armature(arm)
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    if selection_only:
        for ob in meshes:
            ob.select_set(True)
    bpy.context.view_layer.objects.active = arm
    return [arm] + meshes


def _merge_actions_into_nla(arm) -> int:
    """Make sure every action is reachable by the exporters."""
    count = 0
    ad = arm.animation_data or arm.animation_data_create()
    for action in bpy.data.actions:
        action.use_fake_user = True
        if not action.slots:
            continue
        if any(strip.action is action for tr in ad.nla_tracks for strip in tr.strips):
            continue
        if ad.action is action:
            continue
        try:
            utils.add_nla_strip(arm, action, action.slots[0], name=action.name,
                                blend="REPLACE", start=utils.action_range(action)[0],
                                track_name=action.name, mute=True)
            count += 1
        except Exception as exc:
            utils.log.debug("could not stash %s: %s", action.name, exc)
    return count


def _gltf(context, arm, path, glb: bool, selection_only: bool,
          deform_only: bool, apply_modifiers: bool) -> str:
    _select_for_export(arm, selection_only)
    kwargs = dict(
        filepath=path,
        export_format="GLB" if glb else "GLTF_SEPARATE",
        use_selection=selection_only,
        use_visible=False,
        use_active_collection=False,
        export_apply=apply_modifiers,
        export_yup=True,
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
        export_skins=True,
        export_influence_nb=4,
        export_all_influences=False,
        export_def_bones=deform_only,
        export_rest_position_armature=True,
        export_anim_single_armature=True,
        export_animations=True,
        export_animation_mode="ACTIONS",
        export_nla_strips=True,
        export_bake_animation=True,
        export_frame_range=False,
        export_force_sampling=True,
        export_optimize_animation_size=True,
        export_optimize_animation_keep_anim_armature=True,
        export_reset_pose_bones=True,
        export_anim_slide_to_zero=True,
        export_current_frame=False,
        export_morph=False,
        export_extras=True,
        export_cameras=False,
        export_lights=False,
    )
    kwargs = _filter_kwargs(bpy.ops.export_scene.gltf, kwargs)
    bpy.ops.export_scene.gltf(**kwargs)
    return path


def _fbx(context, arm, path, preset: str, selection_only: bool,
         deform_only: bool) -> str:
    _select_for_export(arm, selection_only)
    common = dict(
        filepath=path,
        use_selection=selection_only,
        use_visible=False,
        object_types={"ARMATURE", "MESH"},
        apply_scale_options="FBX_SCALE_NONE",
        use_mesh_modifiers=False,
        bake_anim=True,
        bake_anim_use_all_actions=True,
        bake_anim_use_nla_strips=True,
        bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0,
        bake_anim_force_startend_keying=True,
        add_leaf_bones=False,
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        armature_nodetype="NULL",
        use_armature_deform_only=deform_only,
        path_mode="AUTO",
        embed_textures=False,
    )
    if preset == "FBX_UNITY":
        common.update(dict(global_scale=1.0, axis_forward="-Z", axis_up="Y"))
    elif preset == "FBX_UE":
        common.update(dict(global_scale=1.0, axis_forward="-Z", axis_up="Y",
                           apply_unit_scale=True))
    else:
        common.update(dict(global_scale=1.0, axis_forward="-Z", axis_up="Y"))
    kwargs = _filter_kwargs(bpy.ops.export_scene.fbx, common)
    bpy.ops.export_scene.fbx(**kwargs)
    return path


def export_rig(context, arm, path: str, preset: str = "GLTF_GLB",
               selection_only: bool = True, bake_actions: bool = True,
               deform_only: bool = True, apply_modifiers: bool = False) -> str:
    """Export *arm* (and its meshes) to *path* using *preset*."""
    utils.ensure_object_mode()
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    if bake_actions:
        stashed = _merge_actions_into_nla(arm)
        if stashed:
            utils.log.info("stashed %d action(s) on NLA tracks", stashed)
    if preset.startswith("GLTF"):
        result = _gltf(context, arm, path, glb=(preset == "GLTF_GLB"),
                       selection_only=selection_only, deform_only=deform_only,
                       apply_modifiers=apply_modifiers)
    else:
        result = _fbx(context, arm, path, preset, selection_only, deform_only)
    if not os.path.exists(result):
        raise RuntimeError(f"Exporter did not write {result}")
    return result
