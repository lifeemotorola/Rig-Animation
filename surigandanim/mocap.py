# SPDX-License-Identifier: GPL-3.0-or-later
"""SuRigandAnim - motion capture import and retargeting.

The retargeter is name-first, position-fallback:

1. every source bone is matched to a canonical Apex bone through a large alias
   table (Mixamo, UE5, Unity, VRM, Rigify, BVH conventions),
2. unmatched bones fall back to a rest-pose position match,
3. rotation deltas are copied in world space and reapplied to the Apex rest
   skeleton, so different bone rolls and bone lengths are handled correctly,
4. the hip translation is scaled to the Apex height and the result is written
   as a plain, editable action on the controls (IK props keyed to FK).
"""
from __future__ import annotations

import math
import os
import re

import bpy
from mathutils import Matrix, Quaternion, Vector

from . import utils

# ---------------------------------------------------------------------------
# Naming tables
# ---------------------------------------------------------------------------
UE5 = {
    "pelvis": "pelvis", "spine_01": "spine_01", "spine_02": "spine_02",
    "chest": "spine_03", "neck": "neck_01", "head": "head",
    "clavicle": "clavicle_{s}", "upper_arm": "upperarm_{s}",
    "forearm": "lowerarm_{s}", "hand": "hand_{s}",
    "thigh": "thigh_{s}", "shin": "calf_{s}", "foot": "foot_{s}", "toe": "ball_{s}",
    "f_index_01": "index_01_{s}", "f_index_02": "index_02_{s}",
    "f_index_03": "index_03_{s}",
    "f_middle_01": "middle_01_{s}", "f_middle_02": "middle_02_{s}",
    "f_middle_03": "middle_03_{s}",
    "f_ring_01": "ring_01_{s}", "f_ring_02": "ring_02_{s}",
    "f_ring_03": "ring_03_{s}",
    "f_pinky_01": "pinky_01_{s}", "f_pinky_02": "pinky_02_{s}",
    "f_pinky_03": "pinky_03_{s}",
    "thumb_01": "thumb_01_{s}", "thumb_02": "thumb_02_{s}", "thumb_03": "thumb_03_{s}",
}

MIXAMO = {
    "pelvis": "mixamorig:Hips", "spine_01": "mixamorig:Spine",
    "spine_02": "mixamorig:Spine1", "chest": "mixamorig:Spine2",
    "neck": "mixamorig:Neck", "head": "mixamorig:Head",
    "clavicle": "mixamorig:{S}Shoulder", "upper_arm": "mixamorig:{S}Arm",
    "forearm": "mixamorig:{S}ForeArm", "hand": "mixamorig:{S}Hand",
    "thigh": "mixamorig:{S}UpLeg", "shin": "mixamorig:{S}Leg",
    "foot": "mixamorig:{S}Foot", "toe": "mixamorig:{S}ToeBase",
    "f_index_01": "mixamorig:{S}HandIndex1", "f_index_02": "mixamorig:{S}HandIndex2",
    "f_index_03": "mixamorig:{S}HandIndex3",
    "f_middle_01": "mixamorig:{S}HandMiddle1",
    "f_middle_02": "mixamorig:{S}HandMiddle2",
    "f_middle_03": "mixamorig:{S}HandMiddle3",
    "f_ring_01": "mixamorig:{S}HandRing1", "f_ring_02": "mixamorig:{S}HandRing2",
    "f_ring_03": "mixamorig:{S}HandRing3",
    "f_pinky_01": "mixamorig:{S}HandPinky1",
    "f_pinky_02": "mixamorig:{S}HandPinky2",
    "f_pinky_03": "mixamorig:{S}HandPinky3",
    "thumb_01": "mixamorig:{S}HandThumb1", "thumb_02": "mixamorig:{S}HandThumb2",
    "thumb_03": "mixamorig:{S}HandThumb3",
}

UNITY = {
    "pelvis": "Hips", "spine_01": "Spine", "spine_02": "Chest", "chest": "UpperChest",
    "neck": "Neck", "head": "Head",
    "clavicle": "{S}Shoulder", "upper_arm": "{S}UpperArm",
    "forearm": "{S}LowerArm", "hand": "{S}Hand",
    "thigh": "{S}UpperLeg", "shin": "{S}LowerLeg", "foot": "{S}Foot",
    "toe": "{S}Toes",
    "f_index_01": "{S}IndexProximal", "f_index_02": "{S}IndexIntermediate",
    "f_index_03": "{S}IndexDistal",
    "f_middle_01": "{S}MiddleProximal", "f_middle_02": "{S}MiddleIntermediate",
    "f_middle_03": "{S}MiddleDistal",
    "f_ring_01": "{S}RingProximal", "f_ring_02": "{S}RingIntermediate",
    "f_ring_03": "{S}RingDistal",
    "f_pinky_01": "{S}LittleProximal", "f_pinky_02": "{S}LittleIntermediate",
    "f_pinky_03": "{S}LittleDistal",
    "thumb_01": "{S}ThumbProximal", "thumb_02": "{S}ThumbIntermediate",
    "thumb_03": "{S}ThumbDistal",
}

VRM = {
    "pelvis": "hips", "spine_01": "spine", "spine_02": "chest", "chest": "upperChest",
    "neck": "neck", "head": "head",
    "clavicle": "{l}Shoulder", "upper_arm": "{l}UpperArm",
    "forearm": "{l}LowerArm", "hand": "{l}Hand",
    "thigh": "{l}UpperLeg", "shin": "{l}LowerLeg", "foot": "{l}Foot",
    "toe": "{l}Toes",
    "f_index_01": "{l}IndexProximal", "f_index_02": "{l}IndexIntermediate",
    "f_index_03": "{l}IndexDistal",
    "f_middle_01": "{l}MiddleProximal", "f_middle_02": "{l}MiddleIntermediate",
    "f_middle_03": "{l}MiddleDistal",
    "f_ring_01": "{l}RingProximal", "f_ring_02": "{l}RingIntermediate",
    "f_ring_03": "{l}RingDistal",
    "f_pinky_01": "{l}LittleProximal", "f_pinky_02": "{l}LittleIntermediate",
    "f_pinky_03": "{l}LittleDistal",
    "thumb_01": "{l}ThumbProximal", "thumb_02": "{l}ThumbIntermediate",
    "thumb_03": "{l}ThumbDistal",
}

STYLE_MAPS = {"UE5": UE5, "MIXAMO": MIXAMO, "UNITY": UNITY, "VRM": VRM}

# generic aliases used when detecting the source skeleton
GENERIC_ALIASES = {
    "pelvis": ("hips", "hip", "pelvis", "root_m", "bip01pelvis", "bip01",
               "hipjoint", "pelvisroot"),
    "spine_01": ("spine", "spine1", "spine01", "abdomen", "waist",
                 "spinelower", "bip01spine", "bip01spine1"),
    "spine_02": ("spine2", "spine02", "spine1", "spinemid", "spineuppermid",
                 "bip01spine2"),
    "chest": ("chest", "spine3", "spine03", "upperchest", "spineupper",
              "bip01spine3", "bip01neck"),
    "neck": ("neck", "neck1", "neck01", "bip01neck1"),
    "head": ("head", "skull", "bip01head"),
    "clavicle": ("shoulder", "clavicle", "collarbone", "shoulderjoint"),
    "upper_arm": ("arm", "upperarm", "shoulderarm", "uparm", "armupper"),
    "forearm": ("forearm", "lowerarm", "elbow", "armlower", "loarm"),
    "hand": ("hand", "wrist", "handjoint"),
    "thigh": ("upleg", "thigh", "upperleg", "legupper", "hipjointl"),
    "shin": ("leg", "shin", "calf", "lowerleg", "leglower", "shinbone"),
    "foot": ("foot", "ankle", "footjoint"),
    "toe": ("toe", "toebase", "toes", "ball", "toetip"),
}

FINGER_ALIASES = {
    "thumb": ("thumb", "pollex"),
    "f_index": ("index", "pointer"),
    "f_middle": ("middle", "mid"),
    "f_ring": ("ring", "third"),
    "f_pinky": ("pinky", "little", "pinkie"),
}

SIDE_TOKENS = {
    "left": "L", "l": "L", "_l": "L", "lf": "L",
    "right": "R", "r": "R", "_r": "R", "rt": "R",
}


def _norm(name: str) -> str:
    original = name.split(":")[-1].split("|")[-1]
    stripped = re.sub(r"^(mixamorig|bip01|bip|character|armature|def|org)[_\-.]*",
                      "", original, flags=re.I)
    if not stripped:
        stripped = original
    return re.sub(r"[^a-z0-9]", "", stripped.lower())


def _side_of(name: str) -> str:
    n = name.lower().replace("_", ".").replace("-", ".")
    if "left" in n or n.endswith(".l") or n.startswith("l.") or n.endswith("_l"):
        return "L"
    if "right" in n or n.endswith(".r") or n.startswith("r.") or n.endswith("_r"):
        return "R"
    return ""


def _style_name(style: str, canonical: str, side: str = "") -> str | None:
    table = STYLE_MAPS.get(style)
    if not table or canonical not in table:
        return None
    pattern = table[canonical]
    return (pattern.replace("{s}", side.lower()).replace("{S}", "Left" if side == "L" else "Right")
            .replace("{l}", "left" if side == "L" else "right"))


def canonical_candidates(name: str) -> list[str]:
    """Return canonical Apex bone names a source bone might map to."""
    base = name.split(":")[-1]
    side = _side_of(base)
    norm = _norm(base)
    result: list[str] = []
    # exact table names (all styles)
    for style in STYLE_MAPS.values():
        for canonical, pattern in style.items():
            for s in ("L", "R"):
                candidate = (pattern.replace("{s}", s.lower())
                             .replace("{S}", "Left" if s == "L" else "Right")
                             .replace("{l}", "left" if s == "L" else "right"))
                if _norm(candidate) == norm:
                    result.append(canonical + (f".{side or s}" if canonical not in
                                               ("pelvis", "spine_01", "spine_02",
                                                "chest", "neck", "head") else ""))
    # generic aliases
    for canonical, aliases in GENERIC_ALIASES.items():
        if any(norm and (norm == _norm(a) or
                         (len(_norm(a)) >= 4 and norm.endswith(_norm(a))))
               for a in aliases):
            if canonical in ("pelvis", "spine_01", "spine_02", "chest", "neck", "head"):
                result.append(canonical)
            else:
                result.append(f"{canonical}.{side}" if side else f"{canonical}.L")
    # fingers
    for fname, aliases in FINGER_ALIASES.items():
        for alias in aliases:
            if alias in norm:
                digits = re.findall(r"[1-4]", norm)
                idx = int(digits[0]) if digits else 1
                idx = min(max(idx, 1), 3)
                result.append(f"{fname}_{idx:02d}.{side}" if side else f"{fname}_{idx:02d}.L")
    # direct bone name match
    result.append(base)
    seen = []
    for item in result:
        if item not in seen:
            seen.append(item)
    return seen


# ---------------------------------------------------------------------------
# Renaming
# ---------------------------------------------------------------------------
def rename_to_style(rig, style: str, update_vertex_groups: bool = True) -> int:
    """Rename the rig's bones to *style* (UE5 / MIXAMO / UNITY / VRM)."""
    if style == "NONE":
        return 0
    arm = rig.obj
    mapping = {}
    for canonical in list(rig._map.keys()):
        current = rig.n(canonical)
        if "." in canonical:
            side = canonical[-1]
            base = canonical[:-2]
        else:
            side, base = "", canonical
        if base in ("root", "cog") or base.startswith(("hand_ik", "foot_ik", "toe_ik",
                                                        "elbow_pole", "knee_pole")):
            continue
        target = _style_name(style, base, side)
        if not target or target == current or target in arm.data.bones:
            continue
        mapping[current] = target

    # deferred rename so we never collide with a not-yet-renamed bone
    done = {}
    for old, new in mapping.items():
        if old not in arm.data.bones:
            continue
        temp = f"__apex_tmp_{len(done)}"
        arm.data.bones[old].name = temp
        done[temp] = new
    for temp, new in done.items():
        if new not in arm.data.bones:
            arm.data.bones[temp].name = new
        else:
            arm.data.bones[temp].name = new + "_apex"

    # update the canonical -> current name map through the rename table
    new_map = {}
    for canonical, current in rig._map.items():
        new_map[canonical] = mapping.get(current, current)
    rig.update_name_map(new_map)

    if update_vertex_groups:
        for ob in utils.meshes_of_armature(arm):
            for old, new in mapping.items():
                vg = ob.vertex_groups.get(old)
                if vg is not None and new not in ob.vertex_groups:
                    vg.name = new
    return len(mapping)


# ---------------------------------------------------------------------------
# Retarget
# ---------------------------------------------------------------------------
def _height(arm) -> float:
    return max((b.tail_local.z for b in arm.data.bones), default=1.7)


def build_bone_map(source, rig, style: str = "MIXAMO") -> dict:
    """Map canonical Apex deform bones to source bones."""
    source_bones = [b for b in source.data.bones]
    allowed = {b.name for b in rig.obj.data.bones if b.use_deform} | {"cog"}
    used = set()
    result = {}
    # pass 1: style table + aliases
    for sb in source_bones:
        for candidate in canonical_candidates(sb.name):
            if candidate in rig._map and candidate not in result and \
                    candidate in rig.obj.data.bones and candidate in allowed:
                result[candidate] = sb.name
                used.add(sb.name)
                break
    # pass 2: positional fallback
    h_src = _height(source)
    h_tgt = _height(rig.obj)
    scale = (h_tgt / h_src) if h_src else 1.0
    src_rest = {b.name: (b.head_local.copy(), b.tail_local.copy()) for b in source_bones}
    for canonical in rig._map:
        if canonical in result or canonical not in rig.obj.data.bones:
            continue
        if canonical not in allowed:
            continue
        tb = rig.obj.data.bones[canonical]
        best, best_d = None, 1e9
        for sb in source_bones:
            if sb.name in used:
                continue
            head, tail = src_rest[sb.name]
            d = ((head * scale) - tb.head_local).length + ((tail * scale) - tb.tail_local).length
            if d < best_d:
                best, best_d = sb.name, d
        if best is not None and best_d < 0.12 * h_tgt:
            result[canonical] = best
            used.add(best)
    return result


def _frame_range(source, fallback=(1, 60)):
    ad = getattr(source, "animation_data", None)
    if ad and ad.action:
        rng = utils.action_range(ad.action)
        if rng[1] > rng[0]:
            return int(rng[0]), int(rng[1])
    return fallback


def retarget(source, rig, style: str = "MIXAMO", match_scale: bool = True,
             frame_offset: int = 0, key_ik: bool = True, step: int = 1):
    """Retarget *source* armature animation onto *rig*; returns (action, report)."""
    utils.ensure_object_mode()
    bone_map = build_bone_map(source, rig, style)
    if not bone_map:
        raise RuntimeError("No bones matched - check the source skeleton naming")
    start, end = _frame_range(source)
    if end <= start:
        raise RuntimeError("Source armature has no animation range")

    h_src, h_tgt = _height(source), _height(rig.obj)
    scale = (h_tgt / h_src) if (match_scale and h_src > 1e-5) else 1.0

    frames = list(range(start, end + 1, max(1, step)))
    action, slot = utils.new_action_for(rig.obj, f"Apex_Retarget_{source.name}")

    # rest data
    tgt_rest = {name: rig.obj.data.bones[name].matrix_local.copy() for name in rig.obj.data.bones.keys()}
    tgt_parent = {name: (rig.obj.data.bones[name].parent.name
                         if rig.obj.data.bones[name].parent else None)
                  for name in rig.obj.data.bones.keys()}
    src_rest_mat = {b.name: b.matrix_local.copy() for b in source.data.bones}
    src_rest_rot = {name: m.to_3x3() for name, m in src_rest_mat.items()}

    depth = {}
    for name in tgt_rest:
        d, p = 0, tgt_parent[name]
        while p is not None:
            d += 1
            p = tgt_parent[p]
        depth[name] = d
    ordered = sorted(bone_map.keys(), key=lambda n: depth.get(n, 0))

    locs = {n: [] for n in ordered}
    quats = {n: [] for n in ordered}
    scene = bpy.context.scene
    hips_key = "pelvis" if "pelvis" in bone_map else next(iter(bone_map))

    for frame in frames:
        scene.frame_set(int(frame))
        depsgraph = bpy.context.evaluated_depsgraph_get()
        src_eval = source.evaluated_get(depsgraph)
        pose_world = {}
        for canonical, src_name in bone_map.items():
            src_pb = src_eval.pose.bones.get(src_name)
            if src_pb is None:
                continue
            pose_world[canonical] = src_pb.matrix.copy()

        computed = {}
        for canonical in ordered:
            if canonical not in pose_world:
                continue
            src_name = bone_map[canonical]
            src_rot = pose_world[canonical].to_3x3()
            delta = src_rot @ src_rest_rot[src_name].inverted()
            target_rot = delta @ tgt_rest[canonical].to_3x3()
            parent = tgt_parent[canonical]
            if parent is not None and parent in computed:
                parent_pose = computed[parent]
                head = parent_pose @ (tgt_rest[parent].inverted() @ tgt_rest[canonical].translation)
            else:
                head = tgt_rest[canonical].translation.copy()
            if canonical == hips_key:
                src_delta = pose_world[canonical].translation - src_rest_mat[src_name].translation
                head = tgt_rest[canonical].translation + src_delta * scale
            pose_matrix = Matrix.Translation(head) @ target_rot.to_4x4()
            computed[canonical] = pose_matrix
            if parent is not None and parent in computed:
                rest_local = tgt_rest[parent].inverted() @ tgt_rest[canonical]
                basis = (computed[parent] @ rest_local).inverted() @ pose_matrix
            else:
                basis = tgt_rest[canonical].inverted() @ pose_matrix
            locs[canonical].append(tuple(basis.translation))
            quats[canonical].append(tuple(basis.to_quaternion()))

    out_frames = [f + frame_offset for f in frames]
    for canonical in ordered:
        if not locs[canonical]:
            continue
        bone_name = canonical
        path = f'pose.bones["{bone_name}"].'
        for i in range(3):
            utils.write_curve(action, slot, path + "location", i, out_frames,
                              [v[i] for v in locs[canonical]], interpolation="LINEAR")
        q = quats[canonical]
        fixed, prev = [], None
        for item in q:
            if prev is not None and sum(a * b for a, b in zip(prev, item)) < 0:
                item = tuple(-c for c in item)
            fixed.append(item)
            prev = item
        for i in range(4):
            utils.write_curve(action, slot, path + "rotation_quaternion", i,
                              out_frames, [v[i] for v in fixed], interpolation="LINEAR")

    if key_ik:
        for prop in ("ik_arm.L", "ik_arm.R", "ik_leg.L", "ik_leg.R"):
            if prop in rig.obj.pose.bones["root"].keys():
                utils.write_curve(action, slot, f'pose.bones["root"]["{prop}"]', 0,
                                  [out_frames[0], out_frames[-1]], [0.0, 0.0],
                                  interpolation="CONSTANT")

    try:
        action["apex_motion"] = "RETARGET"
        action["apex_source"] = source.name
    except Exception:
        pass
    ad = rig.obj.animation_data or rig.obj.animation_data_create()
    ad.action = action
    try:
        ad.action_slot = slot
    except Exception:
        pass
    report = {
        "frames": len(frames),
        "mapped": len(bone_map),
        "unmapped": [b.name for b in source.data.bones if b.name not in set(bone_map.values())][:24],
        "scale": round(scale, 4),
        "messages": [
            f"Mapped {len(bone_map)} bones from {source.name}",
            f"Scale {scale:.3f} ({h_src:.2f} m -> {h_tgt:.2f} m)",
        ],
    }
    utils.refresh(rig.obj)
    return action, report


# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------
def import_motion_file(context, path: str):
    """Import an FBX / BVH / glTF file and return its armature object."""
    ext = os.path.splitext(path)[1].lower()
    before = set(bpy.data.objects)
    if ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext in (".bvh",):
        bpy.ops.import_anim.bvh(filepath=path)
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        raise RuntimeError(f"Unsupported motion file: {ext}")
    new_objects = [ob for ob in bpy.data.objects if ob not in before]
    armatures = [ob for ob in new_objects if ob.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("No armature found in the imported file")
    return armatures[0]
