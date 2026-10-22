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
                     start_offset=0.0, top_limit=None):
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
        if top_limit is not None and center.z > top_limit:
            continue          # keep the neck volume inside the sculpted jaw
        radius = radius_head + (radius_tail - radius_head) * t
        builder.add_ellipsoid(center, axis, radius, squash, 1.0)
    return steps + 1



def _sculpted_head(context, arm, face_mod):
    """A dense head shell sculpted with a facial heightfield.

    The body is voxel-remeshed at ~1 cm, far too coarse for a face, so the head
    is built separately: a dense sphere displaced by smooth gaussian forms
    (brow ridge, eye sockets, nose, lips, chin, cheeks, jaw taper).  Eye sockets
    are cut into it before it is joined to the body, so the eyeballs sit in real
    holes instead of floating in front of a smooth oval.
    """
    import math

    import bmesh as _bmesh
    import numpy as np

    origin, scale, front = face_mod._head_frame(arm)

    bm = _bmesh.new()
    _bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=48, radius=1.0)
    bm.verts.ensure_lookup_table()

    rx, ry, rz = 0.068 * scale, 0.074 * scale, 0.081 * scale
    centre = Vector((0.0, 0.0, 0.099 * scale))      # relative to the head bone

    def gauss(x, z, cx, cz, sx, sz, amp):
        return amp * math.exp(-(((x - cx) / sx) ** 2 + ((z - cz) / sz) ** 2) * 0.5)

    def relief(x, z):
        """Outward (towards -Y) displacement in metres at (x, z) head units."""
        if not (-0.062 < x < 0.062 and 0.008 < z < 0.120):
            return 0.0
        d = 0.0
        # brow ridge
        for sgn in (1.0, -1.0):
            d += gauss(x, z, sgn * 0.030, 0.1045, 0.020, 0.0072, 0.0058)
            # eye sockets (carved in)
            d += gauss(x, z, sgn * 0.0295, 0.0865, 0.0150, 0.0105, -0.0068)
            # upper lid fold
            d += gauss(x, z, sgn * 0.0295, 0.0955, 0.0140, 0.0035, 0.0022)
            # cheekbone
            d += gauss(x, z, sgn * 0.0420, 0.0700, 0.0160, 0.0160, 0.0035)
            # nostril wing
            d += gauss(x, z, sgn * 0.0128, 0.0748, 0.0058, 0.0048, 0.0085)
            # philtrum columns
            d += gauss(x, z, sgn * 0.0075, 0.0765, 0.0022, 0.0055, 0.0015)
        # nose bridge + tip
        d += gauss(x, z, 0.0, 0.0990, 0.0056, 0.0072, 0.0075)
        d += gauss(x, z, 0.0, 0.0885, 0.0062, 0.0078, 0.0125)
        d += gauss(x, z, 0.0, 0.0790, 0.0078, 0.0052, 0.0180)
        d += gauss(x, z, 0.0, 0.0735, 0.0070, 0.0035, 0.0040)
        # upper / lower lip
        d += gauss(x, z, 0.0, 0.0692, 0.0205, 0.0044, 0.0088)
        d += gauss(x, z, 0.0, 0.0575, 0.0190, 0.0048, 0.0094)
        # mouth line
        d += gauss(x, z, 0.0, 0.0634, 0.0235, 0.0016, -0.0062)
        # chin
        d += gauss(x, z, 0.0, 0.0300, 0.0135, 0.0135, 0.0060)
        d += gauss(x, z, 0.0, 0.0175, 0.0110, 0.0060, 0.0025)
        # soft limit at the edges of the face region
        edge_x = min(1.0, max(0.0, (0.062 - abs(x)) / 0.018))
        edge_z = min(1.0, max(0.0, (z - 0.008) / 0.014)) * \
            min(1.0, max(0.0, (0.120 - z) / 0.014))
        return d * edge_x * edge_z * scale

    for vert in bm.verts:
        ux, uy, uz = vert.co.x, vert.co.y, vert.co.z
        x = ux * rx
        z = uz * rz + centre.z
        y = uy * ry + centre.y
        # jaw taper: narrow the lower third towards the chin
        if z < 0.070 * scale:
            t = min(1.0, (0.070 * scale - z) / (0.070 * scale))
            taper = 1.0 - 0.30 * (t ** 1.4)
            x *= taper
            y *= (1.0 - 0.30 * (t ** 1.4))
        # flatten the back of the skull slightly and add the face relief
        if uy < 0:                                   # front half
            strength = min(1.0, (-uy) ** 1.6)
            y -= relief(x, z) * strength
        # back into armature space: the sculpted head sits on the head bone
        # widen the bottom of the shell into a jaw plane: a sphere tapers to a
        # point, which reads as a floating egg once the neck is attached
        if z < 0.062 * scale:
            t = min(1.0, max(0.0, (0.062 * scale - z) / (0.042 * scale)))
            h_now = math.hypot(x, y)
            target = 0.050 * scale
            if h_now > 1e-4:
                factor = 1.0 + t * (target / h_now - 1.0)
                factor = max(1.0, min(2.6, factor))
                x *= factor
                y *= factor

        # flatten the crown a little so the skull is not egg-shaped
        zz = z
        if zz > 0.140 * scale:
            zz = 0.140 * scale + (zz - 0.140 * scale) * 0.82
        vert.co = Vector((origin.x + x, origin.y + y, origin.z + zz))

    # trim the shell at the jawline: everything below belongs to the neck,
    # which the body already builds.  This is what stops the jaw tear.
    for vert in bm.verts:
        if vert.co.z < 0.014 * scale:
            vert.co.z = 0.014 * scale

    # neck stub: a slim column that lives *inside* the body's collar, so an
    # open jaw never reveals a gap between the head shell and the neck
    neck = _bmesh.new()
    _bmesh.ops.create_cone(neck, cap_ends=True, cap_tris=False, segments=40,
                           radius1=0.0490 * scale, radius2=0.0470 * scale,
                           depth=0.150 * scale)
    for vert in neck.verts:
        vert.co = Vector((vert.co.x, vert.co.y + 0.002 * scale,
                          vert.co.z - 0.030 * scale))
    neck_mesh = bpy.data.meshes.new("ApexNeckTemp")
    neck.to_mesh(neck_mesh)
    neck.free()
    bm.from_mesh(neck_mesh)
    bpy.data.meshes.remove(neck_mesh)
    _bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0006)

    mesh = bpy.data.meshes.new("ApexHead")
    bm.to_mesh(mesh)
    bm.free()
    head_obj = bpy.data.objects.new("ApexHead", mesh)
    body_coll = arm.users_collection[0] if arm.users_collection else context.collection
    body_coll.objects.link(head_obj)

    utils.select_only([head_obj])
    context.view_layer.objects.active = head_obj
    # fuse cranium + neck into one watertight shell (fine voxels keep the face)
    fuse = head_obj.modifiers.new("Apex Head Unify", "REMESH")
    fuse.mode = "VOXEL"
    fuse.voxel_size = 0.0032
    fuse.use_smooth_shade = True
    bpy.ops.object.modifier_apply(modifier=fuse.name)
    sub = head_obj.modifiers.new("Apex Head Smooth", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 1
    bpy.ops.object.modifier_apply(modifier=sub.name)
    for poly in head_obj.data.polygons:
        poly.use_smooth = True

    _cut_eye_sockets(context, head_obj, arm)
    _cut_mouth(context, head_obj, arm)
    utils.set_active(arm)
    return head_obj


def _cut_mouth(context, body, arm) -> bool:
    """Cut a thin mouth slit so the dark interior shows when the jaw opens."""
    from . import face as face_mod

    origin, scale, front = face_mod._head_frame(arm)
    centre = origin + Vector((0.0, front * 0.0620 * scale, 0.0634 * scale))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0,
                                         location=centre)
    cutter = context.view_layer.objects.active
    cutter.name = "ApexMouthCut"
    cutter.scale = (0.0210 * scale, 0.030 * scale, 0.0012 * scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    utils.select_only([body])
    context.view_layer.objects.active = body
    mod = body.modifiers.new("Apex Mouth Cut", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cutter
    ok = True
    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
    except Exception as exc:
        utils.log.warning("mouth cut failed: %s", exc)
        ok = False
    bpy.data.objects.remove(cutter, do_unlink=True)
    return ok


def _cut_eye_sockets(context, body, arm) -> int:
    """Subtract two spheres so the eyeballs sit in real sockets."""
    from . import face as face_mod

    origin, scale, front = face_mod._head_frame(arm)
    cutters = []
    for side in (1.0, -1.0):
        centre = origin + Vector((side * 0.0295 * scale, front * 0.0625 * scale,
                                  0.0865 * scale))
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16,
                                             radius=0.0175 * scale, location=centre)
        cutter = context.view_layer.objects.active
        cutter.name = "ApexEyeSocketCut"
        cutters.append(cutter)
    utils.select_only(cutters)
    context.view_layer.objects.active = cutters[0]
    if len(cutters) > 1:
        bpy.ops.object.join()
    cutter = context.view_layer.objects.active
    cutter.hide_render = True
    utils.select_only([body])
    context.view_layer.objects.active = body
    mod = body.modifiers.new("Apex Eye Sockets", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cutter
    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
    except Exception as exc:
        utils.log.warning("eye socket boolean failed: %s", exc)
    bpy.data.objects.remove(cutter, do_unlink=True)
    return 2


def build_mannequin_mesh(context, arm, name="ApexBody", voxel_size=0.011,
                         smooth=True):
    """Create the mannequin mesh object (unskinned)."""
    # facial features: only when the armature carries the Apex face bones
    try:
        from . import face as face_mod
        has_face = face_mod.has_face(arm)
    except Exception:
        face_mod, has_face = None, False

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
            if has_face:
                continue          # a sculpted head replaces the plain oval
            head, tail = bone.head_local.copy(), bone.tail_local.copy()
            axis = (tail - head).normalized()
            # cranium, mid-face and jaw blocks read better than one long oval
            builder.add_ellipsoid(head.lerp(tail, 0.62), axis, 0.079, squash=0.94,
                                  stretch=1.02)
            builder.add_ellipsoid(head.lerp(tail, 0.42), axis, 0.073, squash=0.92,
                                  stretch=0.92)
            builder.add_ellipsoid(head.lerp(tail, 0.24), axis, 0.059, squash=0.86,
                                  stretch=0.95)
            continue
        start_offset = {"upper_arm": 0.16, "thigh": 0.12}.get(key, 0.0)
        top_limit = None
        if has_face and key == "neck":
            origin, scale, _front = face_mod._head_frame(arm)
            top_limit = origin.z + 0.042 * scale      # inside the jaw plane
        _add_bone_volume(builder, bone, r_head, r_tail, squash, extra,
                         start_offset=start_offset, top_limit=top_limit)

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

    if has_face:
        head_obj = _sculpted_head(context, arm, face_mod)
        if head_obj is not None:
            utils.select_only([body, head_obj])
            context.view_layer.objects.active = body
            bpy.ops.object.join()
            utils.set_active(arm)

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
    try:
        from . import face as face_mod
        if face_mod.has_face(arm):
            face_mod.add_eyes(context, arm)
            face_mod.add_mouth_interior(context, arm)
            face_mod.apply_face_weights(body, arm)
    except Exception as exc:
        utils.log.warning("face setup skipped: %s", exc)
    body["apex_mannequin"] = True
    utils.set_active(arm)
    return body
