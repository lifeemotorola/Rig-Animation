# SPDX-License-Identifier: GPL-3.0-or-later
"""Render the thumbnails for the realistic body presets.

Run head-less (Blender 5.2 LTS, Cycles CPU):

    blender -b --factory-startup --python scripts/make_body_previews.py

Writes ``apex_rig/previews/body_<KEY>.png`` (160 x 220) for every entry of
``apex_rig.makehuman.PRESETS``. Re-run after changing the body data.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import apex_rig  # noqa: E402
from apex_rig import makehuman  # noqa: E402

OUT_DIR = os.path.join(ROOT, "apex_rig", "previews")
RES_X, RES_Y = 160, 220


def _frame_camera(ob):
    corners = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    lo = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    hi = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    centre = (lo + hi) / 2
    size = max(hi - lo)
    cam = bpy.data.objects.new("ThumbCam", bpy.data.cameras.new("ThumbCam"))
    bpy.context.scene.collection.objects.link(cam)
    cam.data.lens = 50
    cam.location = centre + Vector((size * 1.5, -size * 2.0, size * 0.05))
    direction = centre - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam


def main():
    apex_rig.register()
    try:
        for key in makehuman.PRESETS:
            if key == "REAL_CUSTOM":
                continue
            bpy.ops.wm.read_factory_settings(use_empty=True)
            scene = bpy.context.scene
            scene.render.engine = "CYCLES"
            scene.cycles.device = "CPU"
            scene.cycles.samples = 24
            scene.render.resolution_x, scene.render.resolution_y = RES_X, RES_Y
            scene.render.image_settings.file_format = "PNG"
            scene.render.film_transparent = True
            _, gender, muscle, weight = makehuman.PRESETS[key]
            body = makehuman.build_object(bpy.context, key.lower(), gender, muscle, weight)
            _frame_camera(body)
            light = bpy.data.lights.new("ThumbSun", "SUN")
            light.energy = 4.0
            sun = bpy.data.objects.new("ThumbSun", light)
            scene.collection.objects.link(sun)
            sun.rotation_euler = (0.9, 0.0, 0.6)
            scene.render.filepath = os.path.join(OUT_DIR, f"body_{key}.png")
            bpy.ops.render.render(write_still=True)
            print("PREVIEW", scene.render.filepath, flush=True)
    finally:
        apex_rig.unregister()


if __name__ == "__main__":
    main()
