# SPDX-License-Identifier: GPL-3.0-or-later
"""Apex Rig & Motion - automatic body-part detection.

Every skinned vertex is labelled with the body part of its dominant deform
bone (the bone with the largest weight).  The labels become vertex groups
``APEX_part_<part>`` (weight 1.0), so the parts can be used as masks for
painting, hiding, material or export work, and the report tells the artist
how many vertices each part owns.  Parts are derived from the rig's own
weights, so they follow the actual fit on any character.
"""
from __future__ import annotations

import json
import re

import numpy as np

PARTS = ("head", "torso", "arm_L", "arm_R", "hand_L", "hand_R",
         "leg_L", "leg_R", "foot_L", "foot_R")

GROUP_PREFIX = "APEX_part_"
PROPERTY = "apex_parts"


def _side(name: str) -> str:
    base = name.split(":")[-1]
    if base.endswith(".L") or base.endswith("_L"):
        return "L"
    if base.endswith(".R") or base.endswith("_R"):
        return "R"
    return ""


def part_for_bone(name: str) -> str | None:
    """Body part that a deform bone belongs to, or None if unknown.

    Matching uses whole name tokens (split on . _ - :) so that e.g. "forearm"
    is not mistaken for "ear".
    """
    base = name.split(":")[-1].lower()
    side = _side(name)
    tokens = {t for t in re.split(r"[._\-]", base) if t and t not in ("l", "r")}

    def has(*words):
        return any(w in tokens for w in words)

    if has("toe", "toes", "foot", "ankle", "toebase"):
        return f"foot_{side}" if side else None
    if has("thigh", "shin", "calf", "leg", "knee", "upleg", "uplegs"):
        return f"leg_{side}" if side else None
    if has("hand", "wrist", "finger", "thumb", "index", "middle", "ring",
           "pinky", "little", "pinkie"):
        return f"hand_{side}" if side else None
    if has("forearm", "arm", "elbow", "upperarm", "shoulderarm"):
        return f"arm_{side}" if side else None
    if has("head", "neck", "eye", "eyes", "jaw", "lip", "lips", "tongue",
           "chin", "brow", "cheek", "nose", "ear", "ears"):
        return "head"
    if has("pelvis", "spine", "chest", "clavicle", "shoulder", "hips", "torso",
           "root"):
        return "torso"
    return None


def classify(mesh_obj, arm) -> tuple[np.ndarray, list[str | None]]:
    """Return (per-vertex part index, parts list) for a bound mesh.

    Vertices whose dominant group is not a deform bone get part index -1.
    """
    bone_names = {b.name for b in arm.data.bones if b.use_deform}
    group_names = {g.index: g.name for g in mesh_obj.vertex_groups}
    me = mesh_obj.data
    labels = np.full(len(me.vertices), -1, dtype=np.int32)
    index_of = {p: i for i, p in enumerate(PARTS)}
    part_of_group = {}
    for gi, gname in group_names.items():
        if gname in bone_names:
            part_of_group[gi] = part_for_bone(gname)
    for vi, v in enumerate(me.vertices):
        best, best_w = None, 0.0
        for ge in v.groups:
            if ge.weight > best_w and ge.group in part_of_group:
                best, best_w = ge.group, ge.weight
        if best is None:
            continue
        part = part_of_group[best]
        if part in index_of:
            labels[vi] = index_of[part]
    return labels, list(PARTS)


def apply(mesh_obj, arm) -> dict:
    """Write APEX_part_* vertex groups and return a per-part vertex count."""
    labels, parts = classify(mesh_obj, arm)
    counts = {}
    for name in [g.name for g in mesh_obj.vertex_groups
                 if g.name.startswith(GROUP_PREFIX)]:
        mesh_obj.vertex_groups.remove(mesh_obj.vertex_groups[name])
    for i, part in enumerate(parts):
        idx = np.nonzero(labels == i)[0].tolist()
        counts[part] = len(idx)
        if not idx:
            continue
        group = mesh_obj.vertex_groups.new(name=GROUP_PREFIX + part)
        group.add(idx, 1.0, "REPLACE")
    counts["unassigned"] = int(np.count_nonzero(labels < 0))
    mesh_obj[PROPERTY] = json.dumps(counts)
    return counts


def report_lines(counts: dict) -> list[str]:
    total = sum(v for k, v in counts.items() if k != "unassigned") or 1
    lines = []
    for part in PARTS:
        n = counts.get(part, 0)
        lines.append(f"{part:<8} {n:>6} verts  ({100.0 * n / total:4.1f}%)")
    lines.append(f"unassigned {counts.get('unassigned', 0)} verts")
    return lines
