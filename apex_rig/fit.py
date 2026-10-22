# SPDX-License-Identifier: GPL-3.0-or-later
"""Apex Rig & Motion - fit the rig to a character that already exists in the scene.

Two measurement paths are supported:

* **skeleton** - if the character is already rigged, the source armature is read
  (hips / feet / head / shoulders / elbows), which gives exact joints.
* **mesh** - a pure mesh is measured from its evaluated geometry: overall height,
  floor, body axis, facing direction (heel -> toe), arm angle, crotch height.

The measurement drives the parametric rig builder (height, A-pose angle, leg
length) and the final placement (location + facing rotation), so the Apex rig
lands inside the character instead of at the world origin.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import bpy
import numpy as np
from mathutils import Vector

from . import utils

# crotch height of the reference body, as a fraction of total height
DEFAULT_CROTCH_FRAC = 0.46
MAX_POINTS = 120_000

FACING = {
    "AUTO": None,
    "FRONT_NEG_Y": Vector((0.0, -1.0, 0.0)),
    "FRONT_POS_Y": Vector((0.0, 1.0, 0.0)),
    "FRONT_POS_X": Vector((1.0, 0.0, 0.0)),
    "FRONT_NEG_X": Vector((-1.0, 0.0, 0.0)),
}


@dataclass
class CharacterInfo:
    height: float
    floor: float
    center: tuple                 # (x, y) of the body axis at the floor
    facing_vec: Vector
    facing_key: str = "FRONT_NEG_Y"
    arm_angle: float = 44.0
    crotch_frac: float | None = None
    leg_len: float = 1.0
    hip_width: float | None = None
    source: str = "mesh"
    bones_matched: int = 0
    profile: dict = field(default_factory=dict)   # RigOptions overrides
    transform: tuple | None = None                # (rotation, translation) local -> world
    fit_error: float | None = None
    warnings: list = field(default_factory=list)

    def summary(self) -> str:
        parts = [f"H {self.height:.2f} m", f"facing {self.facing_key.replace('FRONT_', '')}",
                 f"arm {self.arm_angle:.0f}°"]
        if self.crotch_frac is not None:
            parts.append(f"crotch {self.crotch_frac:.2f} H")
        parts.append(f"via {self.source}")
        if self.fit_error is not None:
            parts.append(f"RMS {self.fit_error * 100:.1f} cm")
        return " · ".join(parts)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def _evaluated_points(objects, limit: int = MAX_POINTS) -> np.ndarray:
    """World-space vertex positions of the evaluated objects."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    chunks = []
    total = 0
    for ob in objects:
        if ob.type != "MESH":
            continue
        ev = ob.evaluated_get(depsgraph)
        me = ev.to_mesh()
        try:
            n = len(me.vertices)
            if n == 0:
                continue
            co = np.empty(n * 3, dtype=np.float64)
            me.vertices.foreach_get("co", co)
            co = co.reshape(n, 3)
            matrix = np.array(ob.matrix_world)
            co = co @ matrix[:3, :3].T + matrix[:3, 3]
            chunks.append(co)
            total += n
        finally:
            ev.to_mesh_clear()
    if not chunks:
        raise ValueError("No mesh geometry selected")
    points = np.concatenate(chunks, axis=0)
    if len(points) > limit:
        step = int(math.ceil(len(points) / limit))
        points = points[::step]
    return points


def _refine_facing(vec: Vector, tolerance_deg: float = 12.0) -> tuple[Vector, str]:
    """Snap to a world axis only when the character is (almost) axis aligned."""
    snapped, key = _snap_direction(vec)
    if vec.length < 1e-6:
        return snapped, key
    flat = Vector((vec.x, vec.y, 0.0)).normalized()
    angle = math.degrees(math.acos(max(-1.0, min(1.0, flat.dot(snapped)))))
    if angle <= tolerance_deg:
        return snapped, key
    return flat, "CUSTOM"


def _snap_direction(vec: Vector) -> tuple[Vector, str]:
    if vec.length < 1e-6:
        return FACING["FRONT_NEG_Y"].copy(), "FRONT_NEG_Y"
    axes = {"FRONT_NEG_Y": (0.0, -1.0), "FRONT_POS_Y": (0.0, 1.0),
            "FRONT_POS_X": (1.0, 0.0), "FRONT_NEG_X": (-1.0, 0.0)}
    flat = Vector((vec.x, vec.y, 0.0)).normalized()
    best_key, best_dot = "FRONT_NEG_Y", -9.0
    for key, (ax, ay) in axes.items():
        dot = flat.x * ax + flat.y * ay
        if dot > best_dot:
            best_key, best_dot = key, dot
    return Vector((axes[best_key][0], axes[best_key][1], 0.0)), best_key


# ---------------------------------------------------------------------------
# Mesh measurement
# ---------------------------------------------------------------------------
def _kmeans2(flat: np.ndarray, iterations: int = 25):
    """Tiny 2-means on 2D points; returns label array (0/1)."""
    spread = flat.max(axis=0) - flat.min(axis=0)
    axis = int(np.argmax(spread))
    order = np.argsort(flat[:, axis])
    centres = np.stack([flat[order[len(order) // 8]], flat[order[-len(order) // 8]]])
    labels = np.zeros(len(flat), dtype=np.int32)
    for _ in range(iterations):
        d = ((flat[:, None, :] - centres[None, :, :]) ** 2).sum(axis=2)
        labels = np.argmin(d, axis=1)
        for k in (0, 1):
            sel = flat[labels == k]
            if len(sel):
                centres[k] = sel.mean(axis=0)
    return labels


def _foot_axis(foot: np.ndarray) -> Vector | None:
    """Long axis of a single foot (fore-aft), pointing from heel to toe."""
    if len(foot) < 25:
        return None
    flat = foot[:, :2] - foot[:, :2].mean(axis=0)
    cov = np.cov(flat.T)
    if not np.all(np.isfinite(cov)):
        return None
    values, vectors = np.linalg.eigh(cov)
    if values.max() <= 1e-12:
        return None
    axis = vectors[:, int(np.argmax(values))]
    axis = axis / (np.linalg.norm(axis) + 1e-12)
    # heel -> toe: ankles sit in the upper part, toes are further away
    cut = np.quantile(foot[:, 2], 0.80)
    ankle = foot[foot[:, 2] >= cut][:, :2].mean(axis=0) - foot[:, :2].mean(axis=0)
    projection = flat @ axis
    ankle_t = float(ankle @ axis)
    if (ankle_t - float(projection.min())) > (float(projection.max()) - ankle_t):
        axis = -axis
    return Vector((float(axis[0]), float(axis[1]), 0.0))


def _facing_from_feet(feet: np.ndarray) -> Vector:
    """Facing direction from the feet: per-foot fore-aft axis, averaged."""
    if len(feet) < 40:
        return Vector((0.0, -1.0, 0.0))
    flat = feet[:, :2]
    axes = []
    if len(flat) >= 80:
        labels = _kmeans2(flat)
        for k in (0, 1):
            axis = _foot_axis(feet[labels == k])
            if axis is not None:
                axes.append(axis)
    else:
        axis = _foot_axis(feet)
        if axis is not None:
            axes.append(axis)
    if not axes:
        return Vector((0.0, -1.0, 0.0))
    reference = axes[0]
    total = Vector((0.0, 0.0, 0.0))
    for axis in axes:
        total += axis if axis.dot(reference) >= 0 else -axis
    if total.length < 1e-9:
        return Vector((0.0, -1.0, 0.0))
    return total.normalized()


def _character_space(points: np.ndarray, facing: Vector):
    """Rotate the cloud so the character faces -Y; returns (points, rotation)."""
    from mathutils import Matrix

    angle = -math.pi / 2.0 - math.atan2(facing.y, facing.x)
    rot = Matrix.Rotation(angle, 3, "Z")
    rotated = points @ np.array(rot).T
    return rotated, rot


def measure_mesh(meshes, facing_pref: str = "AUTO") -> CharacterInfo:
    points = _evaluated_points(meshes)
    z_min, z_max = float(points[:, 2].min()), float(points[:, 2].max())
    height = z_max - z_min
    if height < 0.2:
        raise ValueError("The selected mesh is too small to be a character")
    floor = z_min

    # --- facing (rotation independent) ---------------------------------
    feet = points[points[:, 2] <= z_min + 0.10 * height]
    facing = _facing_from_feet(feet)
    if facing_pref != "AUTO" and FACING.get(facing_pref) is not None:
        facing = FACING[facing_pref].copy()
        facing_key = facing_pref
    else:
        facing, facing_key = _refine_facing(facing)

    # --- everything else is measured with the character facing -Y ------
    local, rot = _character_space(points, facing)
    local_feet = local[local[:, 2] <= z_min + 0.10 * height]

    hip_band = local[(local[:, 2] >= z_min + 0.42 * height) &
                     (local[:, 2] <= z_min + 0.52 * height)]
    if len(hip_band) > 50:
        cx = float(hip_band[:, 0].mean())
        cy = float(hip_band[:, 1].mean())
    else:
        torso = local[(local[:, 2] >= z_min + 0.55 * height) &
                      (local[:, 2] <= z_min + 0.72 * height)]
        centre = torso.mean(axis=0) if len(torso) else local.mean(axis=0)
        cx, cy = float(centre[0]), float(centre[1])
    # world-space body axis (used for placement)
    centre_world = rot.transposed() @ Vector((cx, cy, 0.0))

    # --- arm angle ------------------------------------------------------
    arm_angle = 44.0
    mask = ((np.abs(local[:, 0] - cx) > 0.19 * height) &
            (local[:, 2] > z_min + 0.50 * height) &
            (local[:, 2] < z_min + 0.88 * height))
    arm_pts = local[mask]
    if len(arm_pts) > 200:
        radius = np.abs(arm_pts[:, 0] - cx)
        edges = np.linspace(radius.min(), radius.max(), 9)
        idx = np.clip(np.digitize(radius, edges) - 1, 0, len(edges) - 2)
        xs, zs = [], []
        for b in range(len(edges) - 1):
            sel = arm_pts[idx == b]
            if len(sel) < 30:
                continue
            xs.append(float(np.abs(sel[:, 0] - cx).mean()))
            zs.append(float(sel[:, 2].mean()))
        if len(xs) >= 4:
            slope = float(np.polyfit(xs, zs, 1)[0])
            arm_angle = math.degrees(math.atan2(-slope, 1.0))
    arm_angle = float(min(max(arm_angle, 5.0), 70.0))

    # --- crotch ---------------------------------------------------------
    crotch_frac = None
    bins = np.arange(z_min + 0.20 * height, z_min + 0.55 * height, 0.01 * height)
    offsets = (0.0, 0.02, 0.04)
    for z in bins:
        mins = []
        for off in offsets:
            band = local[(local[:, 2] >= z + off * height - 0.004 * height) &
                         (local[:, 2] <= z + off * height + 0.004 * height)]
            if len(band) < 20:
                mins = []
                break
            mins.append(float(np.abs(band[:, 0] - cx).min()))
        if len(mins) == 3 and mins[0] < 0.030 * height and \
                mins[1] < 0.050 * height and mins[2] < 0.060 * height:
            crotch_frac = (float(z) - z_min) / height
            break

    info = CharacterInfo(
        height=height, floor=floor, center=(float(centre_world.x), float(centre_world.y)),
        facing_vec=facing, facing_key=facing_key, arm_angle=arm_angle,
        crotch_frac=crotch_frac, source="mesh",
    )
    if crotch_frac is not None:
        info.leg_len = float(min(max(crotch_frac / DEFAULT_CROTCH_FRAC, 0.85), 1.15))
    else:
        info.warnings.append("Could not locate the crotch - leg length left at 1.0")

    # --- arm length from the wingspan -----------------------------------
    # The hands are the lateral extremes of the body. Solve arm_len so the
    # wrists (rig hand joints) end one hand length short of the fingertips.
    arms = local[local[:, 2] > z_min + 0.45 * height]
    if len(arms) > 200:
        reach = float(np.percentile(np.abs(arms[:, 0] - cx), 99.5))
        arm_len = _solve_arm_len(height, arm_angle, reach - 0.07 * height)
        if arm_len is not None:
            info.profile["arm_len"] = arm_len
    return info


def _solve_arm_len(height: float, arm_angle: float, wrist_reach: float):
    """arm_len that puts the rig's wrist this far from the body axis."""
    from .proportions import HumanProportions, RigOptions

    def hand_x(arm_len: float) -> float:
        opts = RigOptions.from_preset("CUSTOM", height=height, arm_angle=arm_angle,
                                      arm_len=arm_len)
        props = HumanProportions(opts)
        heads = {spec.name: spec.head for spec in props.specs}
        return abs(float(heads["hand.L"][0]))

    x1, x2 = hand_x(0.5), hand_x(1.5)
    if abs(x2 - x1) < 1e-6:
        return None
    slope = (x2 - x1) / 1.0
    arm_len = 0.5 + (wrist_reach - x1) / slope
    return float(min(max(arm_len, 0.7), 1.4))


# ---------------------------------------------------------------------------
# Skeleton measurement
# ---------------------------------------------------------------------------
def _find_source_armature(meshes, explicit=None):
    candidates = []
    if explicit is not None and explicit.type == "ARMATURE":
        candidates.append(explicit)
    for ob in meshes:
        for parent in (ob.parent,):
            if parent is not None and parent.type == "ARMATURE":
                candidates.append(parent)
        for mod in ob.modifiers:
            if mod.type == "ARMATURE" and mod.object is not None:
                candidates.append(mod.object)
    for ob in (bpy.context.selected_objects or ()):
        if ob.type == "ARMATURE":
            candidates.append(ob)
    for cand in candidates:
        if cand is not None and cand.type == "ARMATURE" and len(cand.data.bones) >= 6:
            return cand
    return None


def _match_landmarks(source) -> dict:
    """canonical landmark -> source bone (deform bones, best effort)."""
    from .mocap import canonical_candidates

    wanted = {"pelvis", "chest", "neck", "head",
              "upper_arm.L", "upper_arm.R", "forearm.L", "forearm.R",
              "hand.L", "hand.R", "thigh.L", "thigh.R",
              "f_middle_01.L", "f_middle_01.R", "f_index_01.L", "f_index_01.R",
              "thumb_01.L", "thumb_01.R",
              "foot.L", "foot.R", "toe.L", "toe.R"}
    found = {}
    for bone in source.data.bones:
        for candidate in canonical_candidates(bone.name):
            if candidate in wanted and candidate not in found:
                found[candidate] = bone
                break
    return found


def measure_armature(source, facing_pref: str = "AUTO") -> CharacterInfo:
    lm = _match_landmarks(source)
    if "pelvis" not in lm or not ({"foot.L", "foot.R"} & lm.keys()):
        raise ValueError("The source armature has no recognisable hips/feet bones")

    world = source.matrix_world
    def wpos(bone, tail=False):
        return world @ (bone.tail_local if tail else bone.head_local)

    feet = [wpos(lm[k]) for k in ("foot.L", "foot.R") if k in lm]
    toes = [wpos(lm[k], tail=True) for k in ("toe.L", "toe.R") if k in lm]
    floor = min(v.z for v in feet)
    hips = wpos(lm["pelvis"])
    top_bone = lm.get("head")
    top = wpos(top_bone, tail=True).z if top_bone else hips.z + 0.8 * (hips.z - floor)
    height = top - floor
    if height < 0.2:
        raise ValueError("The source skeleton is too small")

    facing = Vector((0.0, -1.0, 0.0))
    if feet and toes:
        toe_mid = sum(toes, Vector()) / len(toes)
        foot_mid = sum(feet, Vector()) / len(feet)
        facing = Vector((toe_mid.x - foot_mid.x, toe_mid.y - foot_mid.y, 0.0))
    if facing_pref != "AUTO" and FACING.get(facing_pref) is not None:
        facing = FACING[facing_pref].copy()
        facing_key = facing_pref
    else:
        facing, facing_key = _refine_facing(facing)

    arm_angle = 44.0
    angles = []
    for side in ("L", "R"):
        up = lm.get(f"upper_arm.{side}")
        fore = lm.get(f"forearm.{side}")
        if up is None or fore is None:
            continue
        v = wpos(fore) - wpos(up)
        if abs(v.x) > 1e-5:
            angles.append(math.degrees(math.atan2(-v.z, abs(v.x))))
    if angles:
        arm_angle = sum(angles) / len(angles)
    arm_angle = float(min(max(arm_angle, 5.0), 70.0))

    crotch_frac = float((hips.z - floor) / height)
    info = CharacterInfo(
        height=height, floor=floor, center=(float(hips.x), float(hips.y)),
        facing_vec=facing, facing_key=facing_key, arm_angle=arm_angle,
        crotch_frac=crotch_frac,
        leg_len=float(min(max(crotch_frac / 0.539, 0.85), 1.15)),
        source="skeleton", bones_matched=len(lm),
    )
    return info


# ---------------------------------------------------------------------------
# Proportion solving against a source skeleton
# ---------------------------------------------------------------------------
SOLVE_BONES = ("pelvis", "chest", "neck", "head",
               "upper_arm.L", "forearm.L", "hand.L",
               "f_middle_01.L", "f_index_01.L", "thumb_01.L",
               "upper_arm.R", "forearm.R", "hand.R",
               "f_middle_01.R", "f_index_01.R", "thumb_01.R",
               "thigh.L", "foot.L", "toe.L",
               "thigh.R", "foot.R", "toe.R")


def _kabsch(source: np.ndarray, target: np.ndarray):
    """Rigid transform (rotation + translation) mapping source onto target."""
    src_centre = source.mean(axis=0)
    dst_centre = target.mean(axis=0)
    src = source - src_centre
    dst = target - dst_centre
    cov = src.T @ dst
    u, _singular, vt = np.linalg.svd(cov)
    d = np.sign(np.linalg.det(vt.T @ u.T))
    correction = np.diag([1.0, 1.0, d if d != 0 else 1.0])
    rotation = vt.T @ correction @ u.T
    return rotation, dst_centre - rotation @ src_centre


def _upright(rotation: np.ndarray, translation: np.ndarray,
             source: np.ndarray, target: np.ndarray):
    """Keep only the yaw part of the fitted rotation (rigs stay vertical)."""
    yaw = math.atan2(rotation[1, 0], rotation[0, 0])
    c, s = math.cos(yaw), math.sin(yaw)
    rot = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
    offset = (target - source @ rot.T).mean(axis=0)
    return rot, offset


def _rig_landmarks(options):
    from .proportions import HumanProportions

    props = HumanProportions(options)
    heads = {spec.name: np.array(spec.head[:]) for spec in props.specs}
    available = [name for name in SOLVE_BONES if name in heads]
    return np.array([heads[name] for name in available]), available


def _residual(options, target: np.ndarray, names) -> tuple[float, np.ndarray, np.ndarray]:
    points, available = _rig_landmarks(options)
    if available != list(names):
        index = [available.index(n) for n in names]
        points = points[index]
    rotation, translation = _kabsch(points, target)
    rotation, translation = _upright(rotation, translation, points, target)
    predicted = points @ rotation.T + translation
    error = float(np.sqrt(((predicted - target) ** 2).sum(axis=1).mean()))
    return error, rotation, translation


def solve_profile(target_world: dict, base) -> tuple[dict, tuple, float]:
    """Fit the rig's proportions to landmark positions from a real skeleton.

    Coordinate descent (best-of-candidates per parameter, repeated passes) over
    height / leg / arm / shoulder / hip / head scale / A-pose angle, minimising
    the RMS landmark error after an upright rigid alignment.
    """
    names = [n for n in SOLVE_BONES if n in target_world]
    if len(names) < 6:
        raise ValueError("Not enough landmarks to fit the rig")
    target = np.array([target_world[n] for n in names], dtype=np.float64)

    from .proportions import RigOptions

    def make(**kw):
        data = dict(height=base.height, build=base.build, head_scale=base.head_scale,
                    shoulder=base.shoulder, chest=base.chest, waist=base.waist,
                    hip=base.hip, arm_len=base.arm_len, leg_len=base.leg_len,
                    arm_angle=base.arm_angle, fingers=base.fingers,
                    twist_bones=False, bbone=False,
                    ik_arms=False, ik_legs=False, pole_targets=False)
        data.update(kw)
        return RigOptions(preset="CUSTOM", **data)

    bounds = {
        "height": (0.6, 2.6), "leg_len": (0.80, 1.2), "arm_len": (0.80, 1.25),
        "shoulder": (0.70, 1.4), "hip": (0.70, 1.4), "head_scale": (0.7, 1.8),
        "arm_angle": (5.0, 70.0),
    }
    best = dict(height=base.height, leg_len=base.leg_len, arm_len=base.arm_len,
                shoulder=base.shoulder, hip=base.hip, head_scale=base.head_scale,
                arm_angle=base.arm_angle)
    order = ("height", "leg_len", "arm_len", "shoulder", "hip", "head_scale",
             "arm_angle")
    best_error, rotation, translation = _residual(make(**best), target, names)
    factors = (0.85, 0.90, 0.95, 1.0, 1.05, 1.10, 1.15)

    for _pass in range(5):
        improved = False
        for key in order:
            current = best[key]
            candidate_best = None
            low, high = bounds[key]
            for factor in factors:
                trial = dict(best)
                value = min(max(current * factor, low), high)
                if abs(value - current) < 1e-6:
                    continue
                trial[key] = value
                error, rot, trans = _residual(make(**trial), target, names)
                if candidate_best is None or error < candidate_best[0]:
                    candidate_best = (error, trial, rot, trans)
            if candidate_best is not None and candidate_best[0] < best_error - 1e-6:
                best_error, best, rotation, translation = candidate_best
                improved = True
        if not improved:
            break
    return best, (rotation, translation), best_error


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def analyze(meshes, source_armature=None, facing_pref="AUTO",
            prefer_skeleton=True) -> CharacterInfo:
    meshes = [ob for ob in meshes if ob.type == "MESH"]
    if not meshes:
        raise ValueError("Select the character mesh first")
    source = _find_source_armature(meshes, source_armature) if prefer_skeleton else None
    if source is not None:
        try:
            info = measure_armature(source, facing_pref)
            info.warnings.append(f"Joint positions read from '{source.name}'")
            try:
                from .proportions import RigOptions

                landmarks = _match_landmarks(source)
                targets = {name: (source.matrix_world @ bone.head_local)
                           for name, bone in landmarks.items()}
                base = RigOptions.from_preset("CUSTOM")
                # seed with the measured size (head-tail span is ~93 % of height)
                base.height = max(info.height / 0.9358, 0.4)
                base.leg_len = info.leg_len
                base.arm_angle = info.arm_angle
                profile, transform, error = solve_profile(targets, base)
                info.profile = profile
                info.transform = transform
                info.fit_error = error
                info.height = profile.get("height", info.height)
                info.leg_len = profile.get("leg_len", info.leg_len)
                info.arm_angle = profile.get("arm_angle", info.arm_angle)
                info.bones_matched = len(landmarks)
                info.warnings.append(
                    f"Proportions solved from {len(landmarks)} joints "
                    f"(RMS {error * 100:.1f} cm)")
            except Exception as exc:
                utils.log.info("proportion solve skipped: %s", exc)
            # cross-check the height against the mesh
            try:
                pts = _evaluated_points(meshes)
                mesh_h = float(pts[:, 2].max() - pts[:, 2].min())
                if abs(mesh_h - info.height) > 0.08 * info.height:
                    info.warnings.append(
                        f"Mesh height {mesh_h:.2f} m differs from skeleton "
                        f"{info.height:.2f} m - check the bind pose")
            except Exception:
                pass
            return info
        except Exception as exc:
            utils.log.info("skeleton measurement failed (%s), using the mesh", exc)
    return measure_mesh(meshes, facing_pref)


def apply_to_options(info: CharacterInfo, options, refine=True):
    """Write the measured values into a RigOptions instance."""
    options.preset = "CUSTOM"
    options.height = round(float(info.height), 4)
    options.arm_angle = round(float(info.arm_angle), 2)
    if refine:
        options.leg_len = round(float(info.leg_len), 4)
    if refine:
        for key in ("arm_len", "shoulder", "hip", "head_scale", "chest",
                    "waist", "build"):
            if key in info.profile:
                setattr(options, key, round(float(info.profile[key]), 4))
    return options


def place_armature(arm, info: CharacterInfo) -> None:
    """Move / rotate the armature so it sits inside the character."""
    if info.transform is not None:
        from mathutils import Matrix as _M

        rotation, translation = info.transform
        rows = [[float(rotation[r][c]) for c in range(3)] for r in range(3)]
        arm.rotation_mode = "QUATERNION"
        arm.rotation_quaternion = _M(rows).to_quaternion()
        arm.location = Vector((float(translation[0]), float(translation[1]),
                               float(translation[2])))
        arm.scale = (1.0, 1.0, 1.0)
        bpy.context.view_layer.update()
        return
    forward = Vector((info.facing_vec.x, info.facing_vec.y, 0.0))
    if forward.length < 1e-6:
        forward = Vector((0.0, -1.0, 0.0))
    forward.normalize()
    quat = Vector((0.0, -1.0, 0.0)).rotation_difference(forward)

    arm.rotation_mode = "QUATERNION"
    arm.rotation_quaternion = quat
    arm.location = Vector((info.center[0], info.center[1], info.floor))
    arm.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()


def fit_armature(arm, info: CharacterInfo, scale: bool = True) -> dict:
    """Fit an existing Apex rig to a measured character."""
    current = max((b.tail_local.z for b in arm.data.bones), default=1.0) * \
        max(arm.scale[2], 1e-6)
    factor = (info.height / current) if (scale and current > 1e-5) else 1.0
    place_armature(arm, info)
    arm.scale = (factor, factor, factor)
    bpy.context.view_layer.update()
    return {"scale": round(factor, 4), "height": round(info.height, 4)}


def prepare_meshes(meshes, keep_existing_armature=False) -> None:
    """Remove previous armature bindings so the Apex rig owns the character."""
    if keep_existing_armature:
        return
    for ob in meshes:
        for mod in list(ob.modifiers):
            if mod.type == "ARMATURE":
                ob.modifiers.remove(mod)
        if ob.parent is not None and ob.parent.type == "ARMATURE":
            world = ob.matrix_world.copy()
            ob.parent = None
            ob.matrix_world = world
        ob.vertex_groups.clear()
        # vertex groups must go: stale groups from another skeleton would leak
    utils.refresh(bpy.context.view_layer.objects.active) if \
        bpy.context.view_layer.objects.active else None


def rig_character(context, meshes, options, facing_pref="AUTO",
                  refine=True, skin_method="APEX", smooth_iterations=4,
                  max_influences=4, source_armature=None,
                  prefer_skeleton=True, bind=True, replace_existing=True):
    """Analyze the character, build a fitted rig, bind the meshes."""
    from . import rig as rigmod
    from . import skin as skin_module

    meshes = [ob for ob in meshes if ob.type == "MESH"]
    if not meshes:
        raise ValueError("Select the character mesh first")
    info = analyze(meshes, source_armature=source_armature,
                   facing_pref=facing_pref, prefer_skeleton=prefer_skeleton)
    apply_to_options(info, options, refine=refine)

    built = rigmod.build_rig(context, options)
    arm = built.arm
    place_armature(arm, info)

    stats = []
    if bind:
        prepare_meshes(meshes)
        for ob in meshes:
            stats.append(skin_module.skin_mesh(arm, ob, method=skin_method,
                                        smooth_iterations=smooth_iterations,
                                        max_influences=max_influences))
    utils.set_active(arm)
    return built, info, stats


def joint_report(arm, meshes) -> dict:
    """Check that the rig's joints sit inside the character.

    Returns the count of bones whose head is inside the mesh, the largest
    bone-to-surface distance and the worst offenders.
    """
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    depsgraph = bpy.context.evaluated_depsgraph_get()
    trees = []
    for ob in meshes:
        if ob.type != "MESH":
            continue
        ev = ob.evaluated_get(depsgraph)
        trees.append((BVHTree.FromObject(ev, depsgraph), ob.matrix_world.copy()))
    if not trees:
        return {}

    def inside(point, tolerance: float = 0.002) -> bool:
        """Signed distance to the closest surface (normal based, shell safe)."""
        best = None
        for tree, matrix in trees:
            local = matrix.inverted() @ point
            location, normal, _index, distance = tree.find_nearest(local)
            if location is None:
                continue
            signed = (local - location).dot(normal)
            if best is None or abs(signed) < abs(best):
                best = signed
        if best is None:
            return False
        return best <= tolerance

    finger_prefixes = ("f_index", "f_middle", "f_ring", "f_pinky", "thumb")
    to_world = arm.matrix_world
    distances, outside, finger_outside = {}, [], []
    for bone in arm.data.bones:
        if not bone.use_deform:
            continue
        head = to_world @ bone.head_local
        best = 1e9
        for tree, matrix in trees:
            local = matrix.inverted() @ head
            hit = tree.find_nearest(local)
            if hit[3] is not None:
                best = min(best, (hit[0] - local).length)
        is_in = inside(head)
        distances[bone.name] = round(best, 4)
        if not is_in:
            entry = (bone.name, round(best, 4))
            if bone.name.startswith(finger_prefixes):
                finger_outside.append(entry)
            else:
                outside.append(entry)
    major = {k: v for k, v in distances.items() if not k.startswith(finger_prefixes)}
    values = list(major.values())
    return {
        "bones": len(values),
        "inside": len(values) - len(outside),
        "outside": outside[:8],
        "finger_outside": len(finger_outside),
        "max_distance": round(max(values), 4) if values else None,
        "mean_distance": round(sum(values) / len(values), 4) if values else None,
    }
