# SPDX-License-Identifier: GPL-3.0-or-later
"""Realistic adult body from the bundled MakeHuman data (CC0 1.0).

The body is the MakeHuman base mesh with its macro targets blended for the
requested gender, muscle and weight. Only young-adult targets are bundled
(``data/makehuman_adult.npz``, built by ``scripts/build_makehuman_data.py``).
"""
from __future__ import annotations

import os
from functools import lru_cache

import numpy as np

UNIT_TO_M = 0.1          # MakeHuman decimetres -> metres
DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "makehuman_adult.npz")
RACES = ("caucasian", "asian", "african")


@lru_cache(maxsize=1)
def load_data() -> dict:
    """Read the packed MakeHuman data once."""
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"MakeHuman data missing: {DATA_FILE}")
    raw = np.load(DATA_FILE, allow_pickle=False)
    names = [str(n) for n in raw["t_names"]]
    targets = {}
    for i, name in enumerate(names):
        targets[name] = (raw[f"t_idx_{i}"], raw[f"t_off_{i}"])
    return {
        "base": raw["base"].astype(np.float64),
        "body_idx": raw["body_idx"],
        "faces": raw["body_faces"],
        "targets": targets,
    }


def macro_weights(gender: float, muscle: float, weight: float) -> dict:
    """Weights of every bundled target for a young adult.

    gender: 0 = female, 1 = male. muscle / weight: 0..1, 0.5 = average.
    Each family of factors sums to 1, as in MakeHuman.
    """
    gender = min(max(gender, 0.0), 1.0)
    g = {"male": gender, "female": 1.0 - gender}
    mus = _tri(min(max(muscle, 0.0), 1.0), "minmuscle", "averagemuscle", "maxmuscle")
    wgt = _tri(min(max(weight, 0.0), 1.0), "minweight", "averageweight", "maxweight")
    out = {}
    race = 1.0 / len(RACES)
    for r in RACES:
        for gn, gw in g.items():
            out[f"{r}-{gn}-young.target"] = race * gw
    for gn, gw in g.items():
        for mn, mw in mus.items():
            for wn, ww in wgt.items():
                out[f"universal-{gn}-young-{mn}-{wn}.target"] = gw * mw * ww
    return out


def _tri(v: float, lo: str, mid: str, hi: str) -> dict:
    mx = max(0.0, v * 2 - 1)
    mn = max(0.0, 1 - v * 2)
    return {lo: mn, mid: 1 - (mx + mn), hi: mx}


def blended_vertices(gender: float, muscle: float = 0.5, weight: float = 0.5) -> np.ndarray:
    """Body vertices in MakeHuman units (decimetres, Y up), body group only."""
    data = load_data()
    verts = data["base"].copy()
    for name, w in macro_weights(gender, muscle, weight).items():
        if w <= 1e-9 or name not in data["targets"]:
            continue
        idx, off = data["targets"][name]
        np.add.at(verts, idx, w * off)
    return verts[data["body_idx"]]


def blender_coords(verts_mh: np.ndarray) -> np.ndarray:
    """MakeHuman (x width, y height, z depth, front -z) -> Blender (Z up, front -Y), metres."""
    v = verts_mh * UNIT_TO_M
    out = np.stack([v[:, 0], -v[:, 2], v[:, 1]], axis=1)
    out[:, 2] -= out[:, 2].min()          # feet on the floor
    return out


def build_object(context, name: str, gender: float, muscle: float = 0.5,
                 weight: float = 0.5):
    """Create the body mesh object in the scene and return it."""
    import bpy

    data = load_data()
    coords = blender_coords(blended_vertices(gender, muscle, weight))
    faces = [[int(i) for i in f if i >= 0] for f in data["faces"]]
    mesh = bpy.data.meshes.new(f"{name}_body")
    mesh.from_pydata(coords.tolist(), [], faces)
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new(f"{name}_body", mesh)
    context.collection.objects.link(ob)
    mat = bpy.data.materials.get("Apex Skin") or bpy.data.materials.new("Apex Skin")
    mat.diffuse_color = (0.62, 0.46, 0.38, 1.0)
    if not mesh.materials:
        mesh.materials.append(mat)
    return ob


# (key, label, gender, muscle, weight) for the picture presets
PRESETS = {
    "REAL_MALE": ("Male", 1.0, 0.5, 0.5),
    "REAL_FEMALE": ("Female", 0.0, 0.5, 0.5),
    "REAL_ATHLETIC": ("Athletic male", 1.0, 0.85, 0.35),
    "REAL_HEAVY": ("Heavier male", 1.0, 0.5, 0.85),
    "REAL_CUSTOM": ("Custom", 0.5, 0.5, 0.5),   # values come from the panel sliders
}
