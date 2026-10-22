# SPDX-License-Identifier: GPL-3.0-or-later
"""Apex Rig & Motion - procedural mannequin body.

A smooth, single-shell mannequin is built from ellipsoids placed on the
skeleton, unioned with a voxel remesh and skinned with Apex capsule weights.
It gives every fresh rig an immediately animatable body (look-dev, retarget
checks, silhouette tests) and can be swapped for a real character at any time.
"""
from __future__ import annotations

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import utils

# bone: (radius at head, radius at tail, squash across, extra length)
BODY_BONES = {
    "pelvis": (0.100, 0.098, 1.10, 0.01),
    "spine_01": (0.093, 0.100, 1.05, 0.015),
    "spine_02": (0.101, 0.112, 1.0, 0.015),
    "chest": (0.118, 0.096, 0.95, 0.02),
    "neck": (0.043, 0.046, 1.0, 0.01),
    "head": (0.070, 0.078, 0.92, 0.012),
    "clavicle": (0.052, 0.050, 1.0, 0.0),
    "upper_arm": (0.050, 0.040, 1.0, 0.0),
    "forearm": (0.041, 0.031, 1.0, 0.0),
    "hand": (0.030, 0.026, 0.55, 0.0),
    "thigh": (0.078, 0.054, 1.0, 0.0),
    "shin": (0.066, 0.042, 1.0, 0.0),
    "foot": (0.034, 0.030, 1.15, 0.0),
    "toe": (0.028, 0.023, 1.25, 0.0),
}

STEPS = 5


_TEMPLATE_CACHE: dict = {}


def _sphere_template(u: int = 12, v: int = 8):
    """Unit UV sphere as (vertices, faces) - built once, instanced in Python."""
    key = (u, v)
    if key in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[key]
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=1.0)
    bm.verts.ensure_lookup_table()
    verts = [vert.co.copy() for vert in bm.verts]
    faces = [tuple(vert.index for vert in face.verts) for face in bm.faces]
    bm.free()
    _TEMPLATE_CACHE[key] = (verts, faces)
    return verts, faces


class _GeoBuilder:
    """Accumulates instanced primitives and emits one mesh in a single call."""

    def __init__(self):
        self.verts: list[Vector] = []
        self.faces: list[tuple] = []

    def add_primitive(self, template, matrix):
        verts, faces = template
        offset = len(self.verts)
        self.verts.extend(matrix @ vert for vert in verts)
        self.faces.extend(tuple(offset + i for i in face) for face in faces)

    def add_ellipsoid(self, center, direction, radius, squash=1.0, stretch=1.0):
        if direction.length < 1e-6:
            rotation = Matrix.Identity(4)
        else:
            rotation = direction.normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()
        mat = (Matrix.Translation(center) @ rotation
               @ Matrix.Diagonal((radius * squash, radius, radius * stretch, 1.0)))
        self.add_primitive(_sphere_template(), mat)

    def add_box(self, center, sizes):
        template = _TEMPLATE_CACHE.get("box")
        if template is None:
            bm = bmesh.new()
            bmesh.ops.create_cube(bm, size=1.0)
            verts = [v.co.copy() for v in bm.verts]
            faces = [tuple(v.index for v in f.verts) for f in bm.faces]
            bm.free()
            template = (verts, faces)
            _TEMPLATE_CACHE["box"] = template
        mat = Matrix.Translation(center) @ Matrix.Diagonal((sizes[0], sizes[1],
                                                            sizes[2], 1.0))
        self.add_primitive(template, mat)

    def to_mesh(self, name: str):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([tuple(v) for v in self.verts], [], self.faces)
        mesh.validate(verbose=False)
        mesh.update()
        return mesh


def _add_bone_volume(builder, bone, radius_head, radius_tail, squash, extra,
                     start_offset=0.0):
    head, tail = bone.head_local.copy(), bone.tail_local.copy()
    direction = tail - head
    length = direction.length
    if length < 1e-6:
        return 0
    axis = direction.normalized()
    # extend joints slightly so limbs and torso fuse during the voxel remesh
    start = head + axis * (length * start_offset) - axis * radius_head * 0.25
    end = tail + axis * (radius_tail * 0.25 + extra)
    span = (end - start).length
    smallest = max(min(radius_head, radius_tail), 1e-4)
    steps = int(max(3, min(40, round(span / (smallest * 0.34)))))
    for i in range(steps + 1):
        t = i / steps
        center = start.lerp(end, t)
        radius = radius_head + (radius_tail - radius_head) * t
        builder.add_ellipsoid(center, axis, radius, squash, 1.0)
    return steps + 1


def build_mannequin_mesh(context, arm, name="ApexBody", voxel_size=0.011,
                         smooth=True):
    """Create the mannequin mesh object (unskinned)."""
    builder = _GeoBuilder()
    FINGER_PREFIX = ("f_index", "f_middle", "f_ring", "f_pinky", "thumb")
    for bone in arm.data.bones:
        if bone.name.startswith(FINGER_PREFIX):
            # individual phalanges so the hands actually have fingers
            head, tail = bone.head_local.copy(), bone.tail_local.copy()
            axis = tail - head
            if axis.length < 1e-6:
                continue
            radius = 0.0105 if bone.name.startswith("thumb") else 0.0088
            builder.add_ellipsoid(head.lerp(tail, 0.15), axis, radius * 1.05)
            builder.add_ellipsoid(head.lerp(tail, 0.55), axis, radius)
            builder.add_ellipsoid(head.lerp(tail, 0.92), axis, radius * 0.88)
            continue
        base = bone.name
        key = None
        for cand in (base, base.split(".")[0]):
            if cand in BODY_BONES:
                key = cand
                break
        if key is None:
            continue
        if key == "hand":
            # a palm slab plus a mitten block, wider than deep
            head, tail = bone.head_local.copy(), bone.tail_local.copy()
            axis = (tail - head).normalized()
            side = (axis.cross(Vector((0, 0, 1))).normalized()
                    if abs(axis.dot(Vector((0, 0, 1)))) < 0.99 else Vector((1, 0, 0)))
            palm = head.lerp(tail, 0.45)
            builder.add_ellipsoid(palm, axis, 0.042, squash=1.0)
            builder.add_ellipsoid(head.lerp(tail, 0.92), axis, 0.038, squash=0.85)
            builder.add_ellipsoid(head.lerp(tail, 0.35) + side * 0.012, axis,
                                  0.026, squash=0.8)
            continue
        r_head, r_tail, squash, extra = BODY_BONES[key]
        if key in ("pelvis", "spine_01", "spine_02", "chest"):
            # torso: a stack of rings, widest across the shoulders/hips
            head, tail = bone.head_local.copy(), bone.tail_local.copy()
            axis = (tail - head).normalized()
            steps = 5
            for i in range(steps + 1):
                t = i / steps
                r = r_head + (r_tail - r_head) * t
                builder.add_ellipsoid(head.lerp(tail, t), axis, r, squash=squash,
                                      stretch=1.35)
            continue
        if key == "head":
            head, tail = bone.head_local.copy(), bone.tail_local.copy()
            axis = (tail - head).normalized()
            centre = head.lerp(tail, 0.56)
            builder.add_ellipsoid(centre, axis, 0.081, squash=0.94, stretch=1.16)
            # jaw / chin
            builder.add_ellipsoid(head.lerp(tail, 0.26), axis, 0.064, squash=0.99)
            continue
        start_offset = {"upper_arm": 0.16, "thigh": 0.12}.get(key, 0.0)
        _add_bone_volume(builder, bone, r_head, r_tail, squash, extra,
                         start_offset=start_offset)

    # hip bridge: two tapering volumes carry the pelvis out into each thigh so
    # there is no shelf where the torso meets the legs
    hips = [arm.data.bones.get(f"thigh.{s}") for s in ("L", "R")]
    hips = [h for h in hips if h is not None]
    if len(hips) == 2:
        pelvis = arm.data.bones.get("pelvis")
        centre = (hips[0].head_local + hips[1].head_local) * 0.5
        if pelvis is not None:
            centre.z = min(centre.z, pelvis.head_local.z)
        for hip in hips:
            direction = (hip.head_local - centre)
            if direction.length < 1e-5:
                continue
            axis = direction.normalized()
            for t, radius in ((0.30, 0.085), (0.62, 0.080), (0.92, 0.072)):
                builder.add_ellipsoid(centre.lerp(hip.head_local, t), axis,
                                      radius, squash=1.05, stretch=1.0)

    # soles: flat slabs from heel to toe tip, resting on the floor
    for side in ("L", "R"):
        foot = arm.data.bones.get(f"foot.{side}")
        toe = arm.data.bones.get(f"toe.{side}")
        if foot is None:
            continue
        ankle = foot.head_local.copy()
        tip = toe.tail_local.copy() if toe else foot.tail_local.copy()
        heel = ankle + Vector((0.0, 0.035, 0.0))
        centre = Vector((ankle.x, (heel.y + tip.y) * 0.5, 0.019))
        length = abs(heel.y - tip.y)
        builder.add_box(centre, (0.062, length, 0.038))
        builder.add_ellipsoid(Vector((ankle.x, tip.y + 0.012, 0.026)),
                              Vector((0, -1, 0)), 0.026, squash=1.15)

    mesh = builder.to_mesh(name)
    body = bpy.data.objects.new(name, mesh)
    coll = arm.users_collection[0] if arm.users_collection else context.collection
    coll.objects.link(body)

    # unify everything into one watertight shell
    remesh = body.modifiers.new("Apex Unify", "REMESH")
    remesh.mode = "VOXEL"
    remesh.voxel_size = voxel_size
    remesh.adaptivity = 0.012
    remesh.use_smooth_shade = True
    bpy.context.view_layer.objects.active = body
    utils.select_only([body])
    bpy.ops.object.modifier_apply(modifier=remesh.name)

    if smooth:
        smooth_mod = body.modifiers.new("Apex Smooth", "SMOOTH")
        smooth_mod.factor = 0.75
        smooth_mod.iterations = 6
        bpy.ops.object.modifier_apply(modifier=smooth_mod.name)
        if len(body.data.vertices) < 14000:
            sub = body.modifiers.new("Apex Subdiv", "SUBSURF")
            sub.levels = 1
            sub.render_levels = 1
            bpy.ops.object.modifier_apply(modifier=sub.name)
        for poly in body.data.polygons:
            poly.use_smooth = True

    mat = bpy.data.materials.get("Apex Skin")
    if mat is None:
        mat = bpy.data.materials.new("Apex Skin")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.node_tree else None
        if bsdf is not None:
            def _set(input_name, value):
                if input_name in bsdf.inputs:
                    bsdf.inputs[input_name].default_value = value
            _set("Base Color", (0.62, 0.44, 0.36, 1.0))
            _set("Roughness", 0.52)
            _set("Specular IOR Level", 0.35)
            _set("Subsurface Weight", 0.06)
    body.data.materials.append(mat)
    return body


def add_mannequin(context, arm, name="ApexBody", resolution=0.012,
                  smooth=True) -> bpy.types.Object:
    """Create, skin and bind a mannequin body for *arm*."""
    from . import skin

    utils.ensure_object_mode()
    voxel = float(resolution) * 1.6
    body = build_mannequin_mesh(context, arm, name=name, voxel_size=voxel,
                                smooth=smooth)
    skin.skin_mesh(arm, body, method="APEX", smooth_iterations=4,
                   max_influences=4)
    body["apex_mannequin"] = True
    utils.set_active(arm)
    return body
