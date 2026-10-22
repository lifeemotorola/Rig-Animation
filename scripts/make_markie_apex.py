# SPDX-License-Identifier: GPL-3.0-or-later
"""Convert the Markie reference character from its Mixamo-style rig to Apex.

Run head-less (Blender 5.2 LTS):

    blender -b --factory-startup --python scripts/make_markie_apex.py -- \
        --source "References/Markie .fbx" \
        --mesh-out "References/Markie_mesh.fbx" \
        --apex-out "References/Markie_Apex.fbx"

Steps
  1. import the source FBX,
  2. strip the existing armature (bones, armature modifiers, vertex groups)
     and export the bare mesh to ``--mesh-out``,
  3. fit an Apex rig to the mesh measurements (``prefer_skeleton=False`` so
     the old Mixamo joints are not used) and skin the mesh with Apex weights,
  4. add a procedural motion (``--motion``, default WALK) and export the
     rigged character to ``--apex-out`` as a Unity-style FBX.

The original source file is never modified.
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

import apex_rig  # noqa: E402
from apex_rig import animation, export, fit, properties, utils  # noqa: E402


def parse_args(argv):
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source", default=os.path.join(ROOT, "References", "Markie .fbx"))
    p.add_argument("--mesh-out", default=os.path.join(ROOT, "References", "Markie_mesh.fbx"))
    p.add_argument("--apex-out", default=os.path.join(ROOT, "References", "Markie_Apex.fbx"))
    p.add_argument("--motion", default="WALK",
                   help="procedural motion to add to the Apex export ('' for none)")
    return p.parse_args(argv)


def import_source(path: str):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False)
    return [ob for ob in bpy.context.scene.objects if ob.type == "MESH"]


def strip_rig(meshes):
    """Remove every armature binding; the meshes keep their geometry and transform."""
    for ob in meshes:
        for mod in list(ob.modifiers):
            if mod.type == "ARMATURE":
                ob.modifiers.remove(mod)
        if ob.parent is not None and ob.parent.type == "ARMATURE":
            world = ob.matrix_world.copy()
            ob.parent = None
            ob.matrix_world = world
        ob.vertex_groups.clear()
    for ob in list(bpy.context.scene.objects):
        if ob.type == "ARMATURE":
            bpy.data.objects.remove(ob, do_unlink=True)
    for arm in list(bpy.data.armatures):
        if arm.users == 0:
            bpy.data.armatures.remove(arm)


def export_mesh_only(meshes, path: str):
    bpy.ops.object.select_all(action="DESELECT")
    for ob in meshes:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"MESH"},
        apply_scale_options="FBX_SCALE_NONE", global_scale=1.0,
        axis_forward="-Z", axis_up="Y", add_leaf_bones=False,
        bake_space_transform=False, path_mode="AUTO", embed_textures=False,
    )


def build_apex(context, meshes):
    st = properties.settings(context)
    opts = properties.rig_options(st)
    built, info, stats = fit.rig_character(
        context, meshes, opts,
        facing_pref=st.fit_facing,
        refine=st.fit_refine,
        skin_method=st.skin_method,
        smooth_iterations=st.smooth_iterations,
        max_influences=st.max_influences,
        prefer_skeleton=False,      # ignore the old Mixamo joints
        bind=True,
    )
    report = fit.joint_report(built.arm, meshes)
    return built.arm, info, stats, report


def main():
    args = parse_args(sys.argv)
    apex_rig.register()
    try:
        meshes = import_source(args.source)
        if not meshes:
            raise SystemExit(f"No mesh found in {args.source}")

        strip_rig(meshes)
        export_mesh_only(meshes, args.mesh_out)
        print("MESH-ONLY", args.mesh_out, flush=True)

        context = bpy.context
        arm, info, stats, report = build_apex(context, meshes)
        print("ANALYSIS", info.summary(), flush=True)
        print("JOINTS", report, flush=True)
        print("SKIN", stats, flush=True)

        if args.motion:
            action = animation.create_motion(arm, args.motion, start=1.0)
            animation.push_action_to_nla(arm, action, start=1.0)
            scene = context.scene
            scene.frame_start = 1
            scene.frame_end = int(round(action.frame_range[1]))
            print("MOTION", action.name, scene.frame_end, "frames", flush=True)

        export.export_rig(context, arm, args.apex_out, preset="FBX_UNITY",
                          selection_only=False, bake_actions=True,
                          deform_only=True)
        print("APEX", args.apex_out, flush=True)
    finally:
        apex_rig.unregister()


if __name__ == "__main__":
    main()
