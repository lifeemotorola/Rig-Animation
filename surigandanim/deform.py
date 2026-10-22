# SPDX-License-Identifier: GPL-3.0-or-later
"""SuRigandAnim - deformation quality toolkit.

Tools that make a bound character actually deform well:

* **Preserve volume** - dual-quaternion skinning on every armature modifier.
* **Corrective smooth** - a deformation-aware smoothing modifier after the skin.
* **Weight smoothing / symmetrising / heatmap** - direct numpy editing of groups.
* **Deformation check** - poses the rig and *measures* which bones fail to move
  their geometry, so silent skinning problems are found in one click.
"""
from __future__ import annotations

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

from . import utils


# ---------------------------------------------------------------------------
# Modifier level tools
# ---------------------------------------------------------------------------
def armature_modifiers(arm, meshes=None):
    result = []
    for ob in (meshes if meshes is not None else utils.meshes_of_armature(arm)):
        for mod in ob.modifiers:
            if mod.type == "ARMATURE" and mod.object is arm:
                result.append((ob, mod))
    return result


def set_preserve_volume(arm, enabled=True, meshes=None) -> int:
    """Dual quaternion skinning - keeps volume at shoulders, elbows and knees."""
    count = 0
    for _ob, mod in armature_modifiers(arm, meshes):
        mod.use_deform_preserve_volume = bool(enabled)
        count += 1
    return count


def add_corrective_smooth(mesh_obj, factor=0.5, iterations=10,
                          smooth_type="LENGTH_WEIGHTED", use_only_smooth=False):
    """Insert a Corrective Smooth modifier right after the armature."""
    for mod in mesh_obj.modifiers:
        if mod.type == "CORRECTIVE_SMOOTH":
            _configure_corrective(mod, factor, iterations, smooth_type,
                                  use_only_smooth)
            return mod
    mod = mesh_obj.modifiers.new("Apex Corrective Smooth", "CORRECTIVE_SMOOTH")
    _configure_corrective(mod, factor, iterations, smooth_type, use_only_smooth)
    # keep it directly after the armature modifier
    try:
        index = next(i for i, m in enumerate(mesh_obj.modifiers)
                     if m.type == "ARMATURE")
        while mesh_obj.modifiers.find(mod.name) > index + 1:
            bpy.context.view_layer.objects.active = mesh_obj
            with bpy.context.temp_override(object=mesh_obj):
                bpy.ops.object.modifier_move_up(modifier=mod.name)
    except Exception:
        pass
    return mod


def _configure_corrective(mod, factor, iterations, smooth_type, use_only_smooth):
    mod.factor = float(factor)
    mod.iterations = int(iterations)
    try:
        mod.smooth_type = smooth_type
    except Exception:
        pass
    mod.use_only_smooth = bool(use_only_smooth)
    try:
        mod.rest_source = "ORCO"
    except Exception:
        pass


def remove_corrective_smooth(mesh_obj) -> int:
    removed = 0
    for mod in list(mesh_obj.modifiers):
        if mod.type == "CORRECTIVE_SMOOTH" and mod.name.startswith("Apex"):
            mesh_obj.modifiers.remove(mod)
            removed += 1
    return removed


# ---------------------------------------------------------------------------
# Weight editing
# ---------------------------------------------------------------------------
def _arm_of(mesh_obj):
    for mod in mesh_obj.modifiers:
        if mod.type == "ARMATURE" and mod.object is not None:
            return mod.object
    if mesh_obj.parent is not None and mesh_obj.parent.type == "ARMATURE":
        return mesh_obj.parent
    return None


def _read_weights(mesh_obj, bone_names):
    """Dense (verts x bones) weight matrix plus the group indices."""
    groups = {}
    for name in bone_names:
        group = mesh_obj.vertex_groups.get(name)
        if group is not None:
            groups[group.index] = name
    matrix = np.zeros((len(mesh_obj.data.vertices), len(bone_names)))
    lookup = {name: i for i, name in enumerate(bone_names)}
    for vertex in mesh_obj.data.vertices:
        for element in vertex.groups:
            name = groups.get(element.group)
            if name is not None:
                matrix[vertex.index, lookup[name]] = element.weight
    return matrix


def _edges_array(mesh_obj):
    edges = np.empty(len(mesh_obj.data.edges) * 2, dtype=np.int32)
    mesh_obj.data.edges.foreach_get("vertices", edges)
    return edges.reshape(-1, 2)


def smooth_weights(mesh_obj, iterations=3, factor=0.5, expand=0.0,
                   normalize=True) -> dict:
    """Laplacian smoothing of every vertex group (no weight-paint mode needed)."""
    from .skin import _prune_and_normalise, _assign_weights, _smooth_weights

    names = [g.name for g in mesh_obj.vertex_groups]
    if not names:
        return {"groups": 0}
    weights = _read_weights(mesh_obj, names)
    if expand > 0.0:
        # "expand" pushes weights towards 1 before smoothing (fills gaps)
        weights = np.clip(weights + expand * (weights > 0.0) * 0.5, 0.0, 1.0)
    weights = _smooth_weights(weights, _edges_array(mesh_obj),
                              iterations=int(iterations), factor=float(factor))
    if normalize:
        weights = _prune_and_normalise(weights, max_influences=8, threshold=1e-4)
    _assign_weights(mesh_obj, names, weights)
    ensure_bone_coverage(mesh_obj, _arm_of(mesh_obj))
    return {"groups": len(names), "verts": len(mesh_obj.data.vertices)}


def symmetrize_weights(mesh_obj, direction="L_TO_R", tolerance=0.0025) -> dict:
    """Copy weights from one side to the other using mirrored vertex positions."""
    names = [g.name for g in mesh_obj.vertex_groups]
    pairs = {}
    for name in names:
        if name.endswith(".L"):
            mirror = name[:-2] + ".R"
            if mirror in names:
                pairs[name] = mirror
        elif name.endswith(".R"):
            mirror = name[:-2] + ".L"
            if mirror in names:
                pairs[name] = mirror
    if not pairs:
        return {"pairs": 0}

    verts = mesh_obj.data.vertices
    kd = KDTree(len(verts))
    for vertex in verts:
        kd.insert(vertex.co, vertex.index)
    kd.balance()

    matrix = _read_weights(mesh_obj, names)
    lookup = {name: i for i, name in enumerate(names)}
    source_side, target_side = ("L", "R") if direction == "L_TO_R" else ("R", "L")

    for vertex in verts:
        mirrored = Vector((-vertex.co.x, vertex.co.y, vertex.co.z))
        co, index, distance = kd.find(mirrored)
        if distance is None or distance > tolerance:
            continue
        source = verts[index]
        # only copy when we are on the target side
        side = "L" if vertex.co.x > 0 else "R"
        if side != target_side:
            continue
        for source_name, target_name in pairs.items():
            if not source_name.endswith("." + source_side):
                continue
            src = matrix[source.index, lookup[source_name]]
            dst = matrix[vertex.index, lookup[target_name]]
            matrix[vertex.index, lookup[target_name]] = src
    totals = matrix.sum(axis=1, keepdims=True)
    totals[totals <= 1e-6] = 1.0
    from .skin import _assign_weights

    _assign_weights(mesh_obj, names, matrix / totals)
    ensure_bone_coverage(mesh_obj, _arm_of(mesh_obj))
    return {"pairs": len(pairs), "verts": len(verts)}


def ensure_bone_coverage(mesh_obj, arm, share=0.3, per_bone=6) -> dict:
    """Never let an editing pass leave a deform bone without geometry."""
    from .skin import _dist_to_segment

    names = [b.name for b in arm.data.bones if b.use_deform]
    matrix = _read_weights(mesh_obj, names)
    lookup = {name: i for i, name in enumerate(names)}
    co = np.empty(len(mesh_obj.data.vertices) * 3)
    mesh_obj.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    affected = []
    for bone in arm.data.bones:
        if not bone.use_deform:
            continue
        column = matrix[:, lookup[bone.name]]
        if column.sum() > 1e-4 and column.max() >= 0.05:
            continue
        head = np.array(bone.head_local[:])
        tail = np.array(bone.tail_local[:])
        distance, _t = _dist_to_segment(co, head, tail)
        for vertex in np.argsort(distance)[:per_bone]:
            if distance[vertex] > 0.08:
                continue
            row = matrix[vertex]
            row *= (1.0 - share)
            row[lookup[bone.name]] += share
            total = row.sum()
            if total > 0:
                matrix[vertex] = row / total
        affected.append(bone.name)
    if affected:
        from .skin import _assign_weights

        _assign_weights(mesh_obj, names, matrix)
    return {"restored": affected}


def clean_weights(mesh_obj, threshold=1e-4, max_influences=4) -> dict:
    from .skin import _assign_weights

    names = [g.name for g in mesh_obj.vertex_groups]
    if not names:
        return {"groups": 0}
    matrix = _read_weights(mesh_obj, names)
    if max_influences and matrix.shape[1] > max_influences:
        keep = np.argpartition(-matrix, max_influences - 1, axis=1)[:, :max_influences]
        mask = np.zeros_like(matrix, dtype=bool)
        rows = np.arange(matrix.shape[0])[:, None]
        mask[rows, keep] = True
        matrix = np.where(mask, matrix, 0.0)
    matrix[matrix < threshold] = 0.0
    totals = matrix.sum(axis=1, keepdims=True)
    totals[totals <= 1e-6] = 1.0
    _assign_weights(mesh_obj, names, matrix / totals)
    ensure_bone_coverage(mesh_obj, _arm_of(mesh_obj))
    return {"verts": len(mesh_obj.data.vertices)}


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------
PALETTE = np.array([
    [0.90, 0.22, 0.20], [0.20, 0.55, 0.90], [0.25, 0.75, 0.35],
    [0.95, 0.72, 0.15], [0.72, 0.35, 0.85], [0.20, 0.80, 0.80],
    [0.95, 0.50, 0.20], [0.60, 0.85, 0.30], [0.85, 0.40, 0.60],
    [0.45, 0.50, 0.95],
])


def weight_heatmap(mesh_obj, arm, layer_name="ApexWeights") -> dict:
    """Paint each vertex with the colour of its dominant bone."""
    names = [b.name for b in arm.data.bones if b.use_deform]
    matrix = _read_weights(mesh_obj, names)
    if matrix.size == 0:
        return {"verts": 0}
    dominant = np.argmax(matrix, axis=1)
    colors = PALETTE[dominant % len(PALETTE)]
    mesh = mesh_obj.data
    attribute = mesh.color_attributes.get(layer_name)
    if attribute is None:
        attribute = mesh.color_attributes.new(name=layer_name, type="FLOAT_COLOR",
                                              domain="POINT")
    data = np.concatenate([colors, np.ones((len(colors), 1))], axis=1).astype(np.float32)
    attribute.data.foreach_set("color", data.ravel())
    mesh.update()
    # show it
    try:
        mesh.color_attributes.active_color = attribute
        mesh.color_attributes.render_color_index = mesh.color_attributes.find(layer_name)
    except Exception:
        pass
    return {"verts": int(len(colors)), "colors": int(len(np.unique(dominant)))}


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------
def bone_coverage(mesh_obj, arm) -> dict:
    names = [b.name for b in arm.data.bones if b.use_deform]
    matrix = _read_weights(mesh_obj, names)
    counts = (matrix > 0.01).sum(axis=0)
    empty = [name for name, count in zip(names, counts) if count == 0]
    return {"per_bone": dict(zip(names, counts.tolist())), "empty": empty,
            "verts": len(mesh_obj.data.vertices)}


def _evaluated_positions(mesh_obj) -> np.ndarray:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    ev = mesh_obj.evaluated_get(depsgraph)
    me = ev.data
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    return co.reshape(n, 3)


def deform_check(arm, mesh_obj, stress=True, threshold=0.002) -> dict:
    """Pose the rig and measure whether every bone actually moves its vertices.

    Returns a per-bone report of vertices weighted to the bone and how far they
    travel; bones that own vertices but do not move them are flagged.
    """
    from .animation import clear_pose_channels

    names = [b.name for b in arm.data.bones if b.use_deform]
    matrix = _read_weights(mesh_obj, names)
    scene = bpy.context.scene

    clear_pose_channels(arm)
    utils.refresh(arm)
    base = _evaluated_positions(mesh_obj)

    if stress:
        _apply_stress_pose(arm)
        utils.refresh(arm)
    moved = _evaluated_positions(mesh_obj)
    displacement = np.linalg.norm(moved - base, axis=1)

    report = {}
    stalled = []
    for idx, name in enumerate(names):
        column = matrix[:, idx]
        owned = column > 0.05
        count = int(owned.sum())
        if count == 0:
            report[name] = {"verts": 0, "max_move": 0.0, "mean_move": 0.0}
            stalled.append(name)
            continue
        movement = displacement[owned]
        entry = {"verts": count, "max_move": round(float(movement.max()), 4),
                 "mean_move": round(float(movement.mean()), 4)}
        report[name] = entry
        # the bone moved (stress pose) but its vertices stayed put
        bone = arm.data.bones[name]
        bone_moved = (arm.matrix_world @ bone.tail_local -
                      arm.matrix_world @ bone.head_local).length
        if entry["max_move"] < threshold and bone_moved > 0.01:
            stalled.append(name)

    if stress:
        clear_pose_channels(arm)
        utils.refresh(arm)
    total_stalled = len(stalled)
    worst = sorted(((n, d["max_move"]) for n, d in report.items() if d["verts"]),
                   key=lambda kv: kv[1])[:6]
    return {
        "bones": len(names),
        "empty_bones": [n for n, d in report.items() if d["verts"] == 0],
        "stalled_bones": stalled,
        "stalled": total_stalled,
        "weakest": worst,
        "max_displacement": round(float(displacement.max()), 4),
        "per_bone": report,
    }


def animation_coverage(arm, mesh_obj, action=None, step=2, threshold=0.0015) -> dict:
    """Sample a whole action and report bones whose vertices never move.

    This catches the classic "part of the body does not follow the animation"
    problem, including bones that are weighted but overridden by constraints.
    """
    from . import utils

    ad = getattr(arm, "animation_data", None)
    action = action or (ad.action if ad else None)
    if action is None:
        return {"frames": 0, "static_bones": [], "notes": ["no active action"]}
    start, end = utils.action_range(action)
    frames = list(range(int(start), int(end) + 1, max(1, int(step))))
    if len(frames) < 2:
        frames = [int(start), int(start) + 1]

    previous_action = ad.action
    ad.action = action
    try:
        if action.slots:
            ad.action_slot = action.slots[0]
    except Exception:
        pass

    names = [b.name for b in arm.data.bones if b.use_deform]
    matrix = _read_weights(mesh_obj, names)
    scene = bpy.context.scene
    positions = []
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        positions.append(_evaluated_positions(mesh_obj))
    stack = np.stack(positions)                 # (frames, verts, 3)
    displacement = np.linalg.norm(stack - stack[0], axis=2).max(axis=0)

    static = []
    per_bone = {}
    for idx, name in enumerate(names):
        owned = matrix[:, idx] > 0.05
        if not owned.any():
            static.append(name)
            per_bone[name] = 0.0
            continue
        movement = float(displacement[owned].max())
        per_bone[name] = round(movement, 4)
        if movement < threshold:
            static.append(name)

    ad.action = previous_action
    utils.refresh(arm)
    return {
        "frames": len(frames),
        "action": action.name,
        "static_bones": static,
        "per_bone": per_bone,
        "total": len(names),
        "moving": len(names) - len(static),
    }


def _apply_stress_pose(arm):
    """A pose that exercises every joint: arms up, knees bent, head turned."""
    from mathutils import Euler

    rotations = {
        "cog": (0.0, 0.0, 6.0),
        "spine_01": (-4.0, 0.0, 4.0),
        "spine_02": (-4.0, 0.0, 4.0),
        "chest": (-5.0, 0.0, 4.0),
        "neck": (6.0, 0.0, -6.0),
        "head": (8.0, 0.0, -10.0),
        "clavicle.L": (0.0, -8.0, 0.0),
        "clavicle.R": (0.0, 8.0, 0.0),
        "upper_arm.L": (-55.0, 0.0, 0.0),
        "upper_arm.R": (-55.0, 0.0, 0.0),
        "forearm.L": (70.0, 0.0, 0.0),
        "forearm.R": (70.0, 0.0, 0.0),
        "hand.L": (12.0, 0.0, 10.0),
        "hand.R": (12.0, 0.0, -10.0),
        "thigh.L": (-30.0, 0.0, 0.0),
        "thigh.R": (-30.0, 0.0, 0.0),
        "shin.L": (55.0, 0.0, 0.0),
        "shin.R": (55.0, 0.0, 0.0),
        "foot.L": (-20.0, 0.0, 0.0),
        "foot.R": (-20.0, 0.0, 0.0),
        "toe.L": (25.0, 0.0, 0.0),
        "toe.R": (25.0, 0.0, 0.0),
    }
    for finger in ("f_index", "f_middle", "f_ring", "f_pinky", "thumb"):
        for i in range(1, 4):
            for side in ("L", "R"):
                name = f"{finger}_{i:02d}.{side}"
                if name in arm.pose.bones:
                    rotations[name] = (35.0 if finger != "thumb" else 25.0, 0.0, 0.0)

    # IK off so the deform chain drives the pose
    props = arm.pose.bones.get("root")
    if props is not None:
        for key in ("ik_arm.L", "ik_arm.R", "ik_leg.L", "ik_leg.R"):
            if key in props.keys():
                props[key] = 0.0
    for bone_name, angles in rotations.items():
        pb = arm.pose.bones.get(bone_name)
        if pb is None:
            continue
        if pb.rotation_mode == "QUATERNION":
            pb.rotation_quaternion = Euler(
                tuple(a * 3.14159265358979 / 180.0 for a in angles), "XYZ"
            ).to_quaternion()
        else:
            pb.rotation_euler = tuple(a * 3.14159265358979 / 180.0 for a in angles)
