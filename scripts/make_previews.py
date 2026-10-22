# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate the preview thumbnails shipped with Apex Rig & Motion.

Run head-less:

    blender -b --factory-startup --python scripts/make_previews.py

Writes ``apex_rig/previews/<kind>_<KEY>.png`` (160 x 220) for every body preset
and every motion, so the panel can offer picture buttons instead of text menus.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bpy
from mathutils import Vector

import apex_rig
from apex_rig import animation, const, rig as rigmod, skin_body, utils

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "apex_rig", "previews")
RES_X, RES_Y = 160, 220


def _setup_scene(context):
    scene = context.scene
    scene.render.engine = "CYCLES"
    scene.render.resolution_x = RES_X
    scene.render.resolution_y = RES_Y
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = False
    scene.cycles.max_bounces = 4
    scene.cycles.transparent_max_bounces = 2
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"

    world = bpy.data.worlds.new("PreviewWorld")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.0, 0.0, 0.0, 0)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.0
    scene.cycles.use_adaptive_sampling = True

    def area(name, location, energy, size, color=(1.0, 1.0, 1.0)):
        light = bpy.data.lights.new(name, type="AREA")
        light.energy = energy
        light.size = size
        light.color = color
        obj = bpy.data.objects.new(name, light)
        context.collection.objects.link(obj)
        obj.location = location
        obj.rotation_euler = (Vector((0, 0, 1.0)) - Vector(location)).to_track_quat(
            "-Z", "Y").to_euler()
        return obj

    area("Key", (2.2, -2.6, 2.6), 90, 2.4, (1.0, 0.96, 0.92))
    area("Fill", (-2.4, -1.6, 1.6), 28, 2.6, (0.72, 0.82, 1.0))
    area("Rim", (-0.6, 2.4, 2.2), 60, 1.8, (1.0, 0.95, 0.92))

    camera = bpy.data.objects.new("PreviewCam", bpy.data.cameras.new("PreviewCam"))
    context.collection.objects.link(camera)
    scene.camera = camera
    camera.data.lens = 70
    return camera


def _posed_bounds(objects):
    """World-space bounding box of the evaluated meshes."""
    import numpy as np

    depsgraph = bpy.context.evaluated_depsgraph_get()
    lows, highs = [], []
    for ob in objects:
        if ob.type != "MESH":
            continue
        ev = ob.evaluated_get(depsgraph)
        me = ev.to_mesh()
        try:
            n = len(me.vertices)
            if not n:
                continue
            co = np.empty(n * 3)
            me.vertices.foreach_get("co", co)
            co = co.reshape(n, 3)
            m = np.array(ob.matrix_world)
            co = co @ m[:3, :3].T + m[:3, 3]
            lows.append(co.min(axis=0))
            highs.append(co.max(axis=0))
        finally:
            ev.to_mesh_clear()
    if not lows:
        return None
    low = np.min(np.stack(lows), axis=0)
    high = np.max(np.stack(highs), axis=0)
    return Vector(low), Vector(high)


def _frame_camera(camera, height, center=(0.0, 0.0), yaw_deg=24.0, bounds=None):
    import math

    yaw = math.radians(yaw_deg)
    distance = height * 2.45
    if bounds is not None:
        low, high = bounds
        centre = (low + high) * 0.5
        span = max(high.z - low.z, 0.4)
        distance = span * 2.15 + 0.6
        camera.location = (math.sin(yaw) * distance + centre.x,
                           -math.cos(yaw) * distance + centre.y,
                           centre.z + span * 0.06)
        target = Vector((centre.x, centre.y, centre.z))
    else:
        camera.location = (math.sin(yaw) * distance + center[0],
                           -math.cos(yaw) * distance + center[1],
                           height * 0.56 + center[2] if len(center) > 2 else height * 0.56,
                           )
        target = Vector((center[0], center[1], height * 0.53))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def _render(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return os.path.getsize(path) if os.path.exists(path) else 0


def render_presets(context, camera):
    out = []
    for key, data in const.PRESETS.items():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        camera = _setup_scene(bpy.context)
        options = rigmod.RigOptions.from_preset(key)
        arm = rigmod.build_rig(bpy.context, options, replace=True).arm
        body = skin_body.add_mannequin(bpy.context, arm, resolution=0.016)
        height = max(b.tail_local.z for b in arm.data.bones)
        _frame_camera(camera, height)
        path = os.path.join(OUT_DIR, f"preset_{key}.png")
        size = _render(path)
        out.append((key, data["label"], size))
        print(f"preset {key}: {size} bytes", flush=True)
    return out


def render_motions(context, camera):
    out = []
    keys = list(const.MOTIONS.keys()) + list(const.WALK_PRESETS.keys())
    for key in keys:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        camera = _setup_scene(bpy.context)
        arm = rigmod.build_rig(bpy.context,
                               rigmod.RigOptions.from_preset("FEMALE"),
                               replace=True).arm
        body = skin_body.add_mannequin(bpy.context, arm, resolution=0.018)
        action = animation.create_motion(arm, key)
        arm.animation_data.action = action
        try:
            arm.animation_data.action_slot = action.slots[0]
        except Exception:
            pass
        start, end = utils.action_range(action)
        # choose the most dynamic frame: sample the cycle and keep the pose
        # whose limbs travel furthest from the first frame
        tracked = [b.name for b in arm.pose.bones
                   if b.name in ("foot.L", "foot.R", "hand.L", "hand.R", "head")]
        bpy.context.scene.frame_set(int(start))
        bpy.context.view_layer.update()
        origin = {n: arm.pose.bones[n].head.copy() for n in tracked}
        best, best_score = int(start), -1.0
        for f in range(int(start), int(end) + 1, max(1, int((end - start) / 8) or 1)):
            bpy.context.scene.frame_set(int(f))
            bpy.context.view_layer.update()
            score = sum((arm.pose.bones[n].head - origin[n]).length for n in tracked)
            if score > best_score:
                best, best_score = int(f), score
        frame = best
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        height = max(b.tail_local.z for b in arm.data.bones)
        _frame_camera(camera, height, yaw_deg=30.0, bounds=_posed_bounds([body]))
        path = os.path.join(OUT_DIR, f"motion_{key}.png")
        size = _render(path)
        label = const.MOTIONS[key][0] if key in const.MOTIONS else const.WALK_PRESETS[key][0]
        out.append((key, label, size))
        print(f"motion {key}: {size} bytes", flush=True)
    return out


def render_poses(context, camera):
    out = []
    from apex_rig import poses as pose_lib

    for key, (label, _fn) in pose_lib.POSE_LIBRARY.items():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        camera = _setup_scene(bpy.context)
        arm = rigmod.build_rig(bpy.context,
                               rigmod.RigOptions.from_preset("FEMALE"),
                               replace=True).arm
        body = skin_body.add_mannequin(bpy.context, arm, resolution=0.018)
        pose_lib.apply_pose(arm, key)
        utils.refresh(arm)
        height = max(b.tail_local.z for b in arm.data.bones)
        _frame_camera(camera, height, yaw_deg=28.0, bounds=_posed_bounds([body]))
        path = os.path.join(OUT_DIR, f"pose_{key}.png")
        size = _render(path)
        out.append((key, label, size))
        print(f"pose {key}: {size} bytes", flush=True)
    return out


def render_skin_methods(context, camera):
    from apex_rig import deform, skin

    out = []
    for method in ("APEX", "CAPSULE", "HEAT", "ENVELOPE"):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        camera = _setup_scene(bpy.context)
        arm = rigmod.build_rig(bpy.context,
                               rigmod.RigOptions.from_preset("FEMALE"),
                               replace=True).arm
        body = skin_body.add_mannequin(bpy.context, arm, resolution=0.020)
        try:
            skin.skin_mesh(arm, body, method=method)
            info = deform.weight_heatmap(body, arm)
            # emission material so the colour attribute is visible in the render
            mat = bpy.data.materials.new(f"SkinViz_{method}")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            for node in list(nodes):
                if node.type != "OUTPUT_MATERIAL":
                    nodes.remove(node)
            output = next(n for n in nodes if n.type == "OUTPUT_MATERIAL")
            attribute = nodes.new("ShaderNodeVertexColor")
            attribute.layer_name = "ApexWeights"
            emission = nodes.new("ShaderNodeEmission")
            emission.inputs["Strength"].default_value = 1.15
            links.new(attribute.outputs["Color"], emission.inputs["Color"])
            links.new(emission.outputs["Emission"], output.inputs["Surface"])
            body.data.materials.clear()
            body.data.materials.append(mat)
            print(f"skin {method}: {info}", flush=True)
        except Exception as exc:
            print(f"skin {method} failed: {exc}", flush=True)
        height = max(b.tail_local.z for b in arm.data.bones)
        _frame_camera(camera, height, yaw_deg=20.0, bounds=_posed_bounds([body]))
        path = os.path.join(OUT_DIR, f"skin_{method}.png")
        size = _render(path)
        out.append((method, method.title(), size))
        print(f"skin {method}: {size} bytes", flush=True)
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    apex_rig.register()
    camera = _setup_scene(bpy.context)
    presets = render_presets(bpy.context, camera)
    motions = render_motions(bpy.context, camera)
    poses = render_poses(bpy.context, camera)
    skins = render_skin_methods(bpy.context, camera)
    print(f"\nPRESETS {len(presets)}  MOTIONS {len(motions)}  POSES {len(poses)}  "
          f"SKIN {len(skins)}  -> {OUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
