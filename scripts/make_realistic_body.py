# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a realistic MakeHuman body and rig it with Apex.

Source data: the MakeHuman base mesh and macro targets (CC0 1.0, released
September 2020). Fetch them once, outside the repository:

    curl -sL -o mh.tar.gz https://codeload.github.com/makehumancommunity/makehuman/tar.gz/refs/heads/master
    tar -xzf mh.tar.gz --wildcards 'makehuman-master/makehuman/data/3dobjs/*' \
        'makehuman-master/makehuman/data/targets/macrodetails/*'

Run head-less (Blender 5.2 LTS):

    blender -b --factory-startup --python scripts/make_realistic_body.py -- \
        --mh-data mh/makehuman-master/makehuman/data \
        --gender 1.0 --out-dir References

Steps
  1. blend the macro targets for the requested gender / age / muscle / weight
     (MakeHuman's own combination rule: race x gender x age lattice plus the
     universal gender x age x muscle x weight lattice, all summed),
  2. convert units (MakeHuman uses decimetres, Y up) to metres, Z up,
  3. write ``<out-dir>/MakeHuman_mesh.fbx`` (bare body),
  4. fit an Apex rig to the body, skin it with Apex weights, add a walk
     motion and write ``<out-dir>/MakeHuman_Apex.fbx``.
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import surigandanim  # noqa: E402
from surigandanim import animation, export  # noqa: E402

from make_markie_apex import build_apex, export_mesh_only  # noqa: E402

UNIT_TO_M = 0.1  # MakeHuman decimetres -> metres


def parse_args(argv):
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--mh-data", required=True, help="MakeHuman 'data' folder")
    p.add_argument("--gender", type=float, default=0.5, help="0 = female, 1 = male")
    p.add_argument("--age", type=float, default=0.5, help="0.5 = 25 years")
    p.add_argument("--muscle", type=float, default=0.5)
    p.add_argument("--weight", type=float, default=0.5)
    p.add_argument("--out-dir", default=os.path.join(ROOT, "References"))
    p.add_argument("--name", default="MakeHuman", help="output file prefix")
    p.add_argument("--motion", default="WALK", help="motion for the Apex export ('' for none)")
    return p.parse_args(argv)


def read_base(data: str):
    """Return (all vertices, body faces only).

    base.obj also holds helper groups (tights, joints, ...) that must not be
    part of the bare body, so only faces from the ``body`` group are kept.
    """
    verts, faces = [], []
    group = None
    with open(os.path.join(data, "3dobjs", "base.obj")) as fh:
        for line in fh:
            if line.startswith("v "):
                verts.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("g "):
                group = line.split()[1] if len(line.split()) > 1 else None
            elif line.startswith("f ") and group == "body":
                faces.append([int(tok.split("/")[0]) - 1 for tok in line.split()[1:]])
    verts = np.array(verts, dtype=float)
    used = sorted({i for f in faces for i in f})
    remap = {old: new for new, old in enumerate(used)}
    faces = [[remap[i] for i in f] for f in faces]
    return verts, used, faces


def read_target(path: str):
    idx, off = [], []
    with open(path) as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            p = line.split()
            idx.append(int(p[0]))
            off.append([float(x) for x in p[1:4]])
    return np.array(idx, dtype=int), np.array(off, dtype=float).reshape(-1, 3)


def macro_weights(gender: float, age: float, muscle: float, weight: float):
    """MakeHuman macro factors. Each family of factors sums to 1.

    age: baby (0) -> child (0.1875) -> young (0.5) -> old (1).
    """
    g = {"male": gender, "female": 1.0 - gender}
    if age < 0.1875:
        t = age / 0.1875
        a = {"baby": 1.0 - t, "child": t, "young": 0.0, "old": 0.0}
    elif age < 0.5:
        t = (age - 0.1875) / 0.3125
        a = {"baby": 0.0, "child": 1.0 - t, "young": t, "old": 0.0}
    else:
        t = (age - 0.5) * 2
        a = {"baby": 0.0, "child": 0.0, "young": 1.0 - t, "old": t}
    mus = _tri(muscle, "minmuscle", "averagemuscle", "maxmuscle")
    wgt = _tri(weight, "minweight", "averageweight", "maxweight")
    return g, a, mus, wgt


def _tri(v, lo, mid, hi):
    mx = max(0.0, v * 2 - 1)
    mn = max(0.0, 1 - v * 2)
    return {lo: mn, mid: 1 - (mx + mn), hi: mx}


def blended_offsets(data: str, base_count: int, gender, age, muscle, weight):
    g, a, mus, wgt = macro_weights(gender, age, muscle, weight)
    race = {"caucasian": 1 / 3, "asian": 1 / 3, "african": 1 / 3}
    macro_dir = os.path.join(data, "targets", "macrodetails")
    jobs = []
    for r, rw in race.items():
        for gn, gw in g.items():
            for an, aw in a.items():
                w = rw * gw * aw
                f = f"{r}-{gn}-{an}.target"
                if w > 1e-9 and os.path.exists(os.path.join(macro_dir, f)):
                    jobs.append((f, w))
    for gn, gw in g.items():
        for an, aw in a.items():
            for mn, mw in mus.items():
                for wn, ww in wgt.items():
                    w = gw * aw * mw * ww
                    f = f"universal-{gn}-{an}-{mn}-{wn}.target"
                    if w > 1e-9 and os.path.exists(os.path.join(macro_dir, f)):
                        jobs.append((f, w))
    V = np.zeros((base_count, 3))
    for f, w in jobs:
        idx, off = read_target(os.path.join(macro_dir, f))
        np.add.at(V, idx, w * off)
    return V, jobs


def make_body(data: str, args):
    all_verts, used, faces = read_base(data)
    offs, jobs = blended_offsets(data, len(all_verts), args.gender, args.age,
                                 args.muscle, args.weight)
    V = (all_verts + offs)[used] * UNIT_TO_M
    # MakeHuman: x = width, y = height, z = depth (front towards -z).
    # Blender: Z up, front towards -Y.
    V_bl = np.stack([V[:, 0], -V[:, 2], V[:, 1]], axis=1)
    V_bl[:, 2] -= V_bl[:, 2].min()          # feet on the floor
    mesh = bpy.data.meshes.new(f"{args.name}_body")
    mesh.from_pydata(V_bl.tolist(), [], faces)
    mesh.update()
    ob = bpy.data.objects.new(f"{args.name}_body", mesh)
    bpy.context.scene.collection.objects.link(ob)
    mat = bpy.data.materials.new(f"{args.name}_skin")
    mat.diffuse_color = (0.62, 0.46, 0.38, 1.0)
    mesh.materials.append(mat)
    for poly in mesh.polygons:
        poly.use_smooth = True
    print("BODY", len(V_bl), "verts", len(faces), "faces", "macro targets", len(jobs),
          "height_m", round(float(V_bl[:, 2].max()), 3), flush=True)
    return ob


def main():
    args = parse_args(sys.argv)
    surigandanim.register()
    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        ob = make_body(args.mh_data, args)
        os.makedirs(args.out_dir, exist_ok=True)

        mesh_path = os.path.join(args.out_dir, f"{args.name}_mesh.fbx")
        export_mesh_only([ob], mesh_path)
        print("MESH-ONLY", mesh_path, flush=True)

        context = bpy.context
        arm, info, stats, report = build_apex(context, [ob])
        print("ANALYSIS", info.summary(), flush=True)
        print("JOINTS", report, flush=True)

        if args.motion:
            action = animation.create_motion(arm, args.motion, start=1.0)
            animation.push_action_to_nla(arm, action, start=1.0)
            context.scene.frame_start = 1
            context.scene.frame_end = int(round(action.frame_range[1]))

        apex_path = os.path.join(args.out_dir, f"{args.name}_Apex.fbx")
        export.export_rig(context, arm, apex_path, preset="FBX_UNITY",
                          selection_only=False, bake_actions=True, deform_only=True)
        print("APEX", apex_path, flush=True)
    finally:
        surigandanim.unregister()


if __name__ == "__main__":
    main()
