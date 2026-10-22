# SPDX-License-Identifier: GPL-3.0-or-later
"""Apex Rig & Motion - procedural custom-shape (widget) library.

Widgets are generated as edge-only meshes so they behave like classic control
curves in the viewport.  Geometry is authored in bone space (Y = along bone)
and normalised around the bone head; per-bone sizing is done with
``custom_shape_scale_xyz``.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

from .const import WIDGET_COLLECTION, WIDGET_PREFIX
from . import utils


# ---------------------------------------------------------------------------
# Geometry builders - all return (verts, edges)
# ---------------------------------------------------------------------------
def _ring(radius: float, segments: int, plane: str = "XZ", z: float = 0.0):
    verts, edges = [], []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        c, s = math.cos(a) * radius, math.sin(a) * radius
        if plane == "XZ":
            verts.append((c, z, s))
        elif plane == "XY":
            verts.append((c, s, z))
        else:  # YZ
            verts.append((z, c, s))
    for i in range(segments):
        edges.append((i, (i + 1) % segments))
    return verts, edges


def _polyline(points, closed: bool = False):
    verts = [tuple(p) for p in points]
    edges = [(i, i + 1) for i in range(len(verts) - 1)]
    if closed and len(verts) > 2:
        edges.append((len(verts) - 1, 0))
    return verts, edges


def _merge(*parts):
    verts, edges = [], []
    for v, e in parts:
        offset = len(verts)
        verts.extend(v)
        edges.extend([(a + offset, b + offset) for a, b in e])
    return verts, edges


def build_ring():
    return _ring(1.0, 24, "XZ")


def build_ring_flat():
    return _ring(1.0, 24, "XY")


def build_box():
    v = [(-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1)]
    return v, [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3)]


def build_diamond():
    v = [(0, 0, -1.2), (0.55, 0, 0), (0, 0, 1.2), (-0.55, 0, 0)]
    e = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3)]
    return v, e


def build_cog():
    """Ring with an inner diamond - the COG / hips control."""
    return _merge(_ring(1.0, 24, "XZ"), _polyline(
        [(0, 0, -0.55), (0.55, 0, 0), (0, 0, 0.55), (-0.55, 0, 0)], closed=True))


def build_root():
    """Floor disc with a forward arrow and X axis ticks."""
    ring = _ring(1.0, 32, "XY")
    cross1 = _polyline([(-1, 0, 0), (1, 0, 0)])
    cross2 = _polyline([(0, -1, 0), (0, 1, 0)])
    arrow = _polyline([(-0.25, 0.6, 0), (0, 1.45, 0), (0.25, 0.6, 0)])
    inner = _ring(0.35, 16, "XY")
    ticks = []
    for i in range(4):
        a = math.pi / 2 * i
        p = (math.cos(a), math.sin(a), 0)
        ticks.append(_polyline([(p[0] * 1.0, p[1] * 1.0, 0),
                                (p[0] * 1.15, p[1] * 1.15, 0)]))
    return _merge(ring, cross1, cross2, arrow, inner, *ticks)


def build_paddle():
    """Hand IK control: ring with a flat 'paddle' blade along the bone."""
    ring = _ring(0.9, 20, "XZ")
    stem = _polyline([(0, -0.8, 0), (0, 1.6, 0)])
    blade = _merge(
        _polyline([(-0.5, 1.6, 0), (0.5, 1.6, 0), (0.5, 2.6, 0), (-0.5, 2.6, 0)], closed=True),
        _polyline([(0, 2.6, 0), (0, 3.1, 0)]),
    )
    return _merge(ring, stem, blade)


def build_foot():
    """Foot control: flat outline (origin at ankle, -Y forward)."""
    outline = _polyline([
        (-0.55, 0.45, 0), (0.55, 0.45, 0),
        (0.55, -0.9, 0), (0.85, -1.05, 0),
        (0.85, -1.7, 0), (0.0, -1.85, 0),
        (-0.85, -1.7, 0), (-0.85, -1.05, 0),
        (-0.55, -0.9, 0),
    ], closed=True)
    centre = _polyline([(-0.55, 0.45, 0), (0.55, 0.45, 0)])
    heel = _polyline([(-0.55, 0.45, 0), (-0.55, 0.45, 0.35), (0.55, 0.45, 0.35), (0.55, 0.45, 0)])
    return _merge(outline, centre, heel)


def build_toe():
    outline = _polyline([
        (-0.7, 0.5, 0), (0.7, 0.5, 0), (0.7, -0.9, 0), (-0.7, -0.9, 0),
    ], closed=True)
    return _merge(outline, _polyline([(0, 0.5, 0), (0, -0.9, 0)]))


def build_sphere():
    v = [(0, 0, 1), (1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0), (0, 0, -1)]
    e = [(0, 1), (0, 2), (0, 3), (0, 4), (5, 1), (5, 2), (5, 3), (5, 4),
         (1, 2), (2, 3), (3, 4), (4, 1)]
    return v, e


def build_cross():
    return _merge(
        _polyline([(-1, 0, 0), (1, 0, 0)]),
        _polyline([(0, -1, 0), (0, 1, 0)]),
        _polyline([(0, 0, -1), (0, 0, 1)]),
        _ring(0.25, 12, "XZ"),
    )


def build_arc():
    verts, edges = [], []
    segments = 12
    for i in range(segments + 1):
        a = math.pi * i / segments
        verts.append((math.cos(a), 0.0, math.sin(a)))
    for i in range(segments):
        edges.append((i, i + 1))
    edges.append((0, segments))
    return verts, edges


BUILDERS = {
    "ring": build_ring,
    "ring_flat": build_ring_flat,
    "box": build_box,
    "diamond": build_diamond,
    "cog": build_cog,
    "root": build_root,
    "paddle": build_paddle,
    "foot": build_foot,
    "toe": build_toe,
    "sphere": build_sphere,
    "cross": build_cross,
    "arc": build_arc,
}


# ---------------------------------------------------------------------------
# Widget object management
# ---------------------------------------------------------------------------
def get_widget_collection(scene=None, create: bool = True):
    scene = scene or bpy.context.scene
    coll = bpy.data.collections.get(WIDGET_COLLECTION)
    if coll is None and create:
        coll = bpy.data.collections.new(WIDGET_COLLECTION)
        scene.collection.children.link(coll)
    return coll


def hide_widget_collection(scene=None) -> None:
    """Exclude the widget collection from the view layer (Rigify-style)."""
    scene = scene or bpy.context.scene
    coll = get_widget_collection(scene, create=False)
    if coll is None:
        return
    def _exclude(layer_coll):
        if layer_coll.collection == coll:
            layer_coll.exclude = True
            layer_coll.hide_viewport = True
            return True
        for child in layer_coll.children:
            if _exclude(child):
                return True
        return False
    _exclude(bpy.context.view_layer.layer_collection)


def widget_object(shape: str, scene=None):
    """Get (or create) a shared widget object for *shape*."""
    if shape not in BUILDERS:
        shape = "ring"
    name = f"{WIDGET_PREFIX}{shape}"
    ob = bpy.data.objects.get(name)
    if ob is not None:
        return ob
    verts, edges = BUILDERS[shape]()
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, edges, [])
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    ob.hide_render = True
    ob.lock_location = (True, True, True)
    ob.lock_rotation = (True, True, True)
    ob.lock_scale = (True, True, True)
    coll = get_widget_collection(scene)
    coll.objects.link(ob)
    return ob


def assign_shape(arm, bone_name: str, shape: str, scale: float,
                 rotation: tuple = (0.0, 0.0, 0.0), translation=(0.0, 0.0, 0.0),
                 wire_width: float = 1.2) -> None:
    pb = arm.pose.bones.get(bone_name)
    if pb is None:
        return
    pb.custom_shape = widget_object(shape)
    pb.use_custom_shape_bone_size = False
    pb.custom_shape_scale_xyz = (scale, scale, scale)
    pb.custom_shape_rotation_euler = rotation
    pb.custom_shape_translation = translation
    pb.custom_shape_wire_width = wire_width


def clear_widgets(remove_objects: bool = True) -> None:
    if not remove_objects:
        return
    coll = get_widget_collection(create=False)
    if coll is None:
        return
    for ob in list(coll.objects):
        utils.safe_remove(ob)
    try:
        bpy.data.collections.remove(coll)
    except Exception:
        pass
