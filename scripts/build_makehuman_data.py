# SPDX-License-Identifier: GPL-3.0-or-later
"""Pack the adult MakeHuman body data used by the add-on into one .npz file.

Source: MakeHuman base mesh and macro targets, CC0 1.0 (released 2020).
Fetch the data once (outside the repository):

    curl -sL -o mh.tar.gz https://codeload.github.com/makehumancommunity/makehuman/tar.gz/refs/heads/master
    tar -xzf mh.tar.gz --wildcards 'makehuman-master/makehuman/data/3dobjs/*' \
        'makehuman-master/makehuman/data/targets/macrodetails/*'

Run with any Python that has numpy:

    python3 scripts/build_makehuman_data.py --mh-data mh/makehuman-master/makehuman/data

Output: apex_rig/data/makehuman_adult.npz containing
  base        float32 (N, 3)   all base vertices (MakeHuman units, decimetres)
  body_idx    int32            vertex indices of the ``body`` group
  body_faces  int32 (F, 4)     body faces (remapped to body_idx positions; -1 pads)
  t_names     str              macro target names
  t_idx_<i>   int32            sparse target vertex indices
  t_off_<i>   float32 (k, 3)   sparse target offsets
Only the 24 young-adult targets are packed (races x genders, universal
gender x muscle x weight). Baby, child and old targets are not included.
"""
from __future__ import annotations

import argparse
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def wanted(name: str) -> bool:
    if name.endswith("-young.target") and name.split("-")[0] in ("caucasian", "asian", "african"):
        return True
    return name.startswith("universal-") and "-young-" in name


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mh-data", required=True)
    ap.add_argument("--out", default=os.path.join(ROOT, "apex_rig", "data", "makehuman_adult.npz"))
    args = ap.parse_args()

    base, group_faces = [], []
    group = None
    with open(os.path.join(args.mh_data, "3dobjs", "base.obj")) as fh:
        for line in fh:
            if line.startswith("v "):
                base.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("g "):
                group = line.split()[1] if len(line.split()) > 1 else None
            elif line.startswith("f ") and group == "body":
                group_faces.append([int(t.split("/")[0]) - 1 for t in line.split()[1:]])
    base = np.asarray(base, dtype=np.float32)
    body_idx = np.array(sorted({i for f in group_faces for i in f}), dtype=np.int32)
    remap = {int(v): k for k, v in enumerate(body_idx)}
    faces = np.full((len(group_faces), 4), -1, dtype=np.int32)
    for r, f in enumerate(group_faces):
        if len(f) > 4:
            raise SystemExit("body faces with more than 4 corners are not supported")
        faces[r, :len(f)] = [remap[i] for i in f]

    macro_dir = os.path.join(args.mh_data, "targets", "macrodetails")
    names = sorted(n for n in os.listdir(macro_dir) if n.endswith(".target") and wanted(n))
    arrays = {"base": base, "body_idx": body_idx, "body_faces": faces,
              "t_names": np.array(names)}
    for i, name in enumerate(names):
        idx, off = [], []
        with open(os.path.join(macro_dir, name)) as fh:
            for line in fh:
                if not line.strip() or line.startswith("#"):
                    continue
                p = line.split()
                idx.append(int(p[0]))
                off.append([float(x) for x in p[1:4]])
        arrays[f"t_idx_{i}"] = np.array(idx, dtype=np.int32)
        arrays[f"t_off_{i}"] = np.asarray(off, dtype=np.float32).reshape(-1, 3)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    np.savez_compressed(args.out, **arrays)
    print("WROTE", args.out, len(names), "targets,", os.path.getsize(args.out), "bytes")


if __name__ == "__main__":
    main()
