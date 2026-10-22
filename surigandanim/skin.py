# SPDX-License-Identifier: GPL-3.0-or-later
"""SuRigandAnim - automatic skinning.

Three methods are supported:

* ``CAPSULE`` (default) - deterministic capsule-distance weights with edge
  aware Laplacian smoothing.  Works on any mesh (even non-manifold, separate
  shells or hard-surface parts) and never fails like bone-heat can.
* ``HEAT``    - Blender's bone-heat solver, cleaned up to 4 influences.
* ``ENVELOPE`` - fast envelope assignment.

All methods finish by parenting the mesh to the armature and ensuring an
Armature modifier with identical name/order.
"""
from __future__ import annotations

import time

import bpy
import numpy as np
from mathutils import Vector

from . import utils

EPS = 1e-6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _deform_bones(arm):
    return [b for b in arm.data.bones if b.use_deform]


def _bone_segments(arm):
    """(name, head, tail, radius_head, radius_tail) in armature space."""
    out = []
    for bone in _deform_bones(arm):
        head = bone.head_local.copy()
        tail = bone.tail_local.copy()
        out.append((
            bone.name,
            np.array([head.x, head.y, head.z], dtype=np.float64),
            np.array([tail.x, tail.y, tail.z], dtype=np.float64),
            float(max(bone.head_radius, 1e-4)),
            float(max(bone.tail_radius or bone.head_radius, 1e-4)),
        ))
    return out


def _mesh_arrays(mesh_obj, arm):
    """Vertex positions in armature space + unique edges."""
    me = mesh_obj.data
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(n, 3)
    # local -> armature space
    to_arm = arm.matrix_world.inverted() @ mesh_obj.matrix_world
    co4 = np.concatenate([co, np.ones((n, 1))], axis=1)
    co = (np.array(to_arm) @ co4.T).T[:, :3]
    edges = np.empty(len(me.edges) * 2, dtype=np.int32)
    me.edges.foreach_get("vertices", edges)
    edges = edges.reshape(-1, 2)
    return co, edges


def _dist_to_segment(points, a, b):
    ab = b - a
    denom = float(ab.dot(ab)) + EPS
    t = ((points - a) @ ab) / denom
    t = np.clip(t, 0.0, 1.0)
    proj = a[None, :] + t[:, None] * ab[None, :]
    return np.linalg.norm(points - proj, axis=1), t


def _smooth_weights(w, edges, iterations=3, factor=0.5):
    """Laplacian smoothing over mesh edges (numpy, no scipy)."""
    if iterations <= 0 or len(edges) == 0:
        return w
    n = w.shape[0]
    i = edges[:, 0].astype(np.int64)
    j = edges[:, 1].astype(np.int64)
    counts = np.bincount(np.concatenate([i, j]), minlength=n).astype(np.float64)
    counts[counts == 0] = 1.0
    for _ in range(iterations):
        acc = np.zeros_like(w)
        np.add.at(acc, i, w[j])
        np.add.at(acc, j, w[i])
        neighbour_avg = acc / counts[:, None]
        w = (1.0 - factor) * w + factor * neighbour_avg
    return w


def _prune_and_normalise(w, max_influences=4, threshold=1e-4):
    if w.shape[1] > max_influences:
        keep = np.argpartition(-w, max_influences - 1, axis=1)[:, :max_influences]
        mask = np.zeros_like(w, dtype=bool)
        rows = np.arange(w.shape[0])[:, None]
        mask[rows, keep] = True
        w = np.where(mask, w, 0.0)
    w[w < threshold] = 0.0
    sums = w.sum(axis=1, keepdims=True)
    empty = (sums[:, 0] <= EPS)
    if np.any(empty):
        # fall back to the closest bone for orphan vertices
        pass
    sums[sums <= EPS] = 1.0
    return w / sums


def _assign_weights(mesh_obj, bone_names, w, prune=1e-4):
    me = mesh_obj.data
    # drop old groups that belong to these bones
    for name in bone_names:
        vg = mesh_obj.vertex_groups.get(name)
        if vg is not None:
            mesh_obj.vertex_groups.remove(vg)
    groups = [mesh_obj.vertex_groups.new(name=n) for n in bone_names]

    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    layer = bm.verts.layers.deform.verify()
    n_bones = len(bone_names)
    nz_rows, nz_cols = np.nonzero(w > prune)
    # group by bone for fewer python-level calls
    order = np.argsort(nz_cols, kind="stable")
    rows = nz_rows[order]
    cols = nz_cols[order]
    weights = w[rows, cols]
    split_idx = np.searchsorted(cols, np.arange(n_bones + 1))
    for b_idx in range(n_bones):
        start, end = split_idx[b_idx], split_idx[b_idx + 1]
        if start == end:
            continue
        dvert = groups[b_idx].index
        for r, value in zip(rows[start:end], weights[start:end]):
            bm.verts[int(r)][layer][dvert] = float(value)
    bm.to_mesh(me)
    bm.free()
    me.update()


def _ensure_binding(arm, mesh_obj):
    if mesh_obj.parent is not arm:
        world = mesh_obj.matrix_world.copy()
        mesh_obj.parent = arm
        mesh_obj.parent_type = "OBJECT"
        mesh_obj.matrix_parent_inverse = arm.matrix_world.inverted()
        mesh_obj.matrix_world = world
    mod = None
    for m in mesh_obj.modifiers:
        if m.type == "ARMATURE" and m.object is arm:
            mod = m
            break
    if mod is None:
        mod = mesh_obj.modifiers.new(name="Apex Armature", type="ARMATURE")
        mod.object = arm
    try:
        mod.use_deform_preserve_volume = True   # dual quaternion skinning
    except Exception:
        pass
    # armature modifier should be first
    try:
        while mesh_obj.modifiers.find(mod.name) > 0:
            bpy.context.view_layer.objects.active = mesh_obj
            with bpy.context.temp_override(object=mesh_obj):
                bpy.ops.object.modifier_move_up(modifier=mod.name)
    except Exception:
        pass
    return mod


# ---------------------------------------------------------------------------
# Apex adaptive weights  (mesh-derived, no dependence on bone display radii)
# ---------------------------------------------------------------------------
def _bone_graph(arm):
    """Adjacency (parent/child + shared-parent) and side tags for filtering."""
    bones = [b.name for b in arm.data.bones]
    index = {name: i for i, name in enumerate(bones)}
    adjacency = {name: set() for name in bones}
    for bone in arm.data.bones:
        if bone.parent is not None:
            adjacency[bone.name].add(bone.parent.name)
            adjacency[bone.parent.name].add(bone.name)
    return index, adjacency


def _side_tag(name: str) -> str:
    if name.endswith(".L"):
        return "L"
    if name.endswith(".R"):
        return "R"
    return ""


def _hops_from(adjacency, start, limit):
    """Bones within *limit* joints of *start* (BFS)."""
    seen = {start: 0}
    frontier = [start]
    for depth in range(limit):
        nxt = []
        for name in frontier:
            for neighbour in adjacency.get(name, ()):
                if neighbour not in seen:
                    seen[neighbour] = depth + 1
                    nxt.append(neighbour)
        frontier = nxt
    return seen


def _compute_adaptive_weights(co, bones, adjacency, max_influences=4,
                              falloff=5.0, hop_limit=2, distance_ratio=1.9):
    """Distance-ratio weights restricted to hierarchically close bones.

    Every vertex is weighted from its nearest bone segment plus any bone that is
    (a) close in space and (b) close in the skeleton hierarchy with the same
    side.  This adapts to any mesh size, so small bones (finger phalanges) are
    never swallowed by large neighbours.
    """
    n = len(co)
    names = [b[0] for b in bones]
    count = len(names)
    distances = np.empty((n, count), dtype=np.float32)
    for idx, (_name, head, tail, _rh, _rt) in enumerate(bones):
        d, _t = _dist_to_segment(co, head, tail)
        distances[:, idx] = d

    nearest = np.argmin(distances, axis=1)
    side_tags = [_side_tag(name) for name in names]
    weights = np.zeros((n, count), dtype=np.float64)

    # hop cache per bone (jobs are cheap: <= 52 BFS runs)
    hop_cache = {idx: _hops_from(adjacency, names[idx], hop_limit) for idx in range(count)}
    name_to_idx = {name: i for i, name in enumerate(names)}

    for v in range(n):
        b0 = int(nearest[v])
        d0 = float(distances[v, b0]) + 1e-5
        allowed = [b0]
        neighbours = hop_cache[b0]
        for other_name, _depth in neighbours.items():
            idx = name_to_idx.get(other_name)
            if idx is None or idx == b0:
                continue
            ts, os_ = side_tags[b0], side_tags[idx]
            if ts and os_ and ts != os_:
                continue                      # never bridge left <-> right
            d = float(distances[v, idx])
            if d <= distance_ratio * d0:
                allowed.append(idx)
        if len(allowed) > max_influences * 2:
            allowed.sort(key=lambda i: distances[v, i])
            allowed = allowed[:max_influences * 2]
        raw = []
        for idx in allowed:
            d = float(distances[v, idx]) + 1e-5
            raw.append((1.0 / (d / d0)) ** falloff)
        raw = np.array(raw)
        if raw.sum() <= 0:
            weights[v, b0] = 1.0
            continue
        raw /= raw.sum()
        order = np.argsort(-raw)[:max_influences]
        for slot in order:
            if raw[slot] > 1e-4:
                weights[v, allowed[int(slot)]] = raw[slot]
    return weights, names


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def skin_mesh(arm, mesh_obj, method="APEX", smooth_iterations=3,
              max_influences=4, falloff=1.35, fade=2.0) -> dict:
    """Bind *mesh_obj* to *arm* and generate weights. Returns statistics."""
    started = time.time()
    if mesh_obj.type != "MESH":
        raise ValueError("Apex skinning only supports mesh objects")
    utils.ensure_object_mode()

    if method == "HEAT":
        stats = _skin_native(arm, mesh_obj, "ARMATURE_AUTO", max_influences)
    elif method == "ENVELOPE":
        stats = _skin_native(arm, mesh_obj, "ARMATURE_ENVELOPE", max_influences)
    elif method == "CAPSULE":
        stats = _skin_capsule(arm, mesh_obj, smooth_iterations, max_influences,
                              falloff, fade)
    else:
        stats = _skin_adaptive(arm, mesh_obj, smooth_iterations, max_influences,
                               falloff)
    mod = _ensure_binding(arm, mesh_obj)
    stats["modifier"] = mod.name
    try:
        from . import face as face_mod
        if face_mod.has_face(arm):
            info = face_mod.apply_face_weights(mesh_obj, arm)
            stats["face_verts"] = info.get("face_verts", 0)
    except Exception as exc:
        utils.log.debug("face weights skipped: %s", exc)
    stats["seconds"] = round(time.time() - started, 3)
    return stats


def _skin_capsule(arm, mesh_obj, smooth_iterations, max_influences, falloff, fade):
    bones = _bone_segments(arm)
    if not bones:
        raise RuntimeError("Armature has no deform bones")
    names = [b[0] for b in bones]
    co, edges = _mesh_arrays(mesh_obj, arm)
    n = len(co)
    w = np.zeros((n, len(bones)), dtype=np.float64)
    nearest = np.full(n, np.inf)
    for idx, (_name, head, tail, r_head, r_tail) in enumerate(bones):
        d, t = _dist_to_segment(co, head, tail)
        radius = (r_head + (r_tail - r_head) * t) * falloff
        radius = np.maximum(radius, 0.004)
        influence = np.clip(1.0 - d / radius, 0.0, 1.0) ** fade
        # inverse-distance term keeps joints smooth far from capsules
        influence = influence + 0.02 / (1.0 + (d / np.maximum(radius, 1e-4)) ** 4)
        w[:, idx] = influence
        nearest = np.minimum(nearest, d)

    # orphan vertices (outside every capsule): nearest bone, weight 1
    sums = w.sum(axis=1)
    if np.any(sums <= EPS):
        d_bones = np.empty((n, len(bones)), dtype=np.float64)
        for idx, (_name, head, tail, r_head, r_tail) in enumerate(bones):
            d_bones[:, idx], _ = _dist_to_segment(co, head, tail)
        closest = np.argmin(d_bones, axis=1)
        orphan = sums <= EPS
        w[orphan, closest[orphan]] = 1.0

    w = _prune_and_normalise(w, max_influences=len(bones))
    w = _smooth_weights(w, edges, iterations=smooth_iterations, factor=0.55)
    w = _prune_and_normalise(w, max_influences=max_influences)
    _assign_weights(mesh_obj, names, w)
    used = int(np.count_nonzero(w.sum(axis=0) > 1e-3))
    return {
        "verts": n,
        "method": "CAPSULE",
        "bones_used": used,
        "unweighted": 0,
        "max_influences": max_influences,
    }


def _skin_adaptive(arm, mesh_obj, smooth_iterations, max_influences, falloff=4.0):
    bones = _bone_segments(arm)
    if not bones:
        raise RuntimeError("Armature has no deform bones")
    co, edges = _mesh_arrays(mesh_obj, arm)
    _index, adjacency = _bone_graph(arm)
    weights, names = _compute_adaptive_weights(co, bones, adjacency,
                                               max_influences=max_influences,
                                               falloff=falloff)
    weights = _smooth_weights(weights, edges, iterations=max(1, smooth_iterations - 1),
                              factor=0.45)
    weights = _prune_and_normalise(weights, max_influences=max_influences)
    _rescue_empty_bones(weights, co, bones, max_influences)
    _assign_weights(mesh_obj, names, weights)
    used, empty = bone_weight_stats(names, weights)
    return {
        "verts": len(co),
        "method": "APEX",
        "bones_used": len(used),
        "bones_without_weights": empty,
        "unweighted": 0,
        "max_influences": max_influences,
    }


def _rescue_empty_bones(weights, co, bones, max_influences, per_bone=12,
                        share=0.5):
    """Guarantee that every bone owns geometry (tips often lose out to smoothing)."""
    totals = weights.sum(axis=0)
    peaks = weights.max(axis=0) if len(weights) else totals
    for idx, empty_total in enumerate(totals):
        # a bone with a tiny peak is effectively unused by the mesh
        if empty_total > 1e-4 and peaks[idx] >= 0.05:
            continue
        _name, head, tail, _rh, _rt = bones[idx]
        distance, _t = _dist_to_segment(co, head, tail)
        nearest = np.argsort(distance)[:per_bone]
        # small bones (fingers) may sit a few centimetres inside a thick mesh
        bone_length = float(np.linalg.norm(np.asarray(tail) - np.asarray(head)))
        limit = max(0.06, bone_length * 2.5)
        for vertex in nearest:
            if distance[vertex] > limit:
                continue
            row = weights[vertex]
            occupied = int(np.count_nonzero(row > 1e-5))
            if occupied >= max_influences:
                # drop the smallest contribution to make room
                weakest = int(np.argmin(np.where(row > 1e-5, row, np.inf)))
                row[weakest] = 0.0
            row *= (1.0 - share)
            row[idx] += share
            total = row.sum()
            if total > 0:
                weights[vertex] = row / total
    return weights


def bone_weight_stats(bone_names, weights):
    """Names of bones that own at least one vertex, plus the empty ones."""
    totals = weights.sum(axis=0)
    used = [name for name, total in zip(bone_names, totals) if total > 1e-4]
    empty = [name for name, total in zip(bone_names, totals) if total <= 1e-4]
    return used, empty


def _skin_native(arm, mesh_obj, parent_type, max_influences):
    utils.select_only([arm, mesh_obj])
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type=parent_type)
    # cleanup
    utils.select_only([mesh_obj])
    bpy.context.view_layer.objects.active = mesh_obj
    try:
        with bpy.context.temp_override(object=mesh_obj):
            bpy.ops.object.vertex_group_limit_total(limit=max_influences)
            bpy.ops.object.vertex_group_clean(group_select_mode="ALL", limit=1e-4)
            bpy.ops.object.vertex_group_normalize_all(lock_active=False)
    except Exception as exc:
        utils.log.warning("Weight cleanup failed: %s", exc)
    me = mesh_obj.data
    unweighted = 0
    groups = mesh_obj.vertex_groups
    for v in me.vertices:
        if not v.groups:
            unweighted += 1
    return {
        "verts": len(me.vertices),
        "method": parent_type,
        "bones_used": len(groups),
        "unweighted": unweighted,
        "max_influences": max_influences,
    }


def unbind_meshes(arm) -> int:
    count = 0
    for ob in utils.meshes_of_armature(arm):
        for mod in list(ob.modifiers):
            if mod.type == "ARMATURE" and mod.object is arm:
                ob.modifiers.remove(mod)
                count += 1
        if ob.parent is arm:
            world = ob.matrix_world.copy()
            ob.parent = None
            ob.matrix_world = world
        for bone in arm.data.bones:
            vg = ob.vertex_groups.get(bone.name)
            if vg is not None:
                ob.vertex_groups.remove(vg)
    return count


def weight_report(mesh_obj, arm) -> dict:
    """Inspect an existing skinned mesh."""
    me = mesh_obj.data
    names = {b.name for b in arm.data.bones}
    group_names = {g.index: g.name for g in mesh_obj.vertex_groups}
    unweighted = 0
    too_many = 0
    not_normalised = 0
    for v in me.vertices:
        total = 0.0
        count = 0
        for ge in v.groups:
            if group_names.get(ge.group) in names and ge.weight > 1e-5:
                total += ge.weight
                count += 1
        if count == 0:
            unweighted += 1
        elif count > 4:
            too_many += 1
        if count and abs(total - 1.0) > 0.01:
            not_normalised += 1
    return {
        "verts": len(me.vertices),
        "unweighted": unweighted,
        "over_four_influences": too_many,
        "not_normalised": not_normalised,
        "armature_modifiers": sum(1 for m in mesh_obj.modifiers
                                  if m.type == "ARMATURE" and m.object is arm),
    }
