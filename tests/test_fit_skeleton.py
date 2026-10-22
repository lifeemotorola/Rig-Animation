import sys, math
sys.path.insert(0,'/home/user')
import bpy, mathutils
from mathutils import Euler, Vector
import apex_rig
from apex_rig import rig as rigmod, skin_body, utils, properties, fit, mocap
apex_rig.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
st = properties.settings(bpy.context)

# character already rigged with a Mixamo-named skeleton
src_res = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("HEROIC"), replace=True)
src = src_res.arm
body = skin_body.add_mannequin(bpy.context, src, resolution=0.016)
srcR = rigmod.Rig(src)
n = mocap.rename_to_style(srcR, "MIXAMO")
print("renamed bones:", n, "sample:", [b.name for b in src.data.bones if "UpLeg" in b.name][:2], flush=True)

X = (mathutils.Matrix.Translation(Vector((-2.5, 4.0, 0.2)))
     @ Euler((0,0,math.radians(-25))).to_matrix().to_4x4()
     @ mathutils.Matrix.Diagonal((1.15,1.15,1.15,1.0)))
GT = {}
for b in src.data.bones:
    pass
lm = fit._match_landmarks(src)
GT = {k: X @ v.head_local for k, v in lm.items()}
# move rig + mesh together
src.parent = None
body.parent = src
body.matrix_parent_inverse = src.matrix_world.inverted()
src.matrix_world = X
bpy.context.view_layer.update()
print("source matched landmarks:", len(lm), sorted(lm)[:6], flush=True)

utils.select_only([body]); bpy.context.view_layer.objects.active = body
info = fit.analyze([body])
print("ANALYZE:", info.summary(), "| bones matched", info.bones_matched, flush=True)
assert info.source == "skeleton", "should have used the skeleton"

built, info2, stats = fit.rig_character(bpy.context, [body], properties.rig_options(st))
arm = built.arm
print("RIG:", len(arm.data.bones), "bones, height", round(arm.data.bones["head"].tail_local.z,3), flush=True)
errs=[]
for k, gt in GT.items():
    if k not in arm.data.bones: 
        print("  missing", k); continue
    pos = arm.matrix_world @ arm.data.bones[k].head_local
    errs.append((pos-gt).length)
    print(f"  {k:12s} err {errs[-1]:.4f} m", flush=True)
print("MAX joint error:", round(max(errs),4), "MEAN:", round(sum(errs)/len(errs),4), flush=True)
print("skin:", stats, flush=True)
rep = fit.joint_report(arm, [body])
print("fit:", rep["inside"], "/", rep["bones"], "outside", rep["outside"], flush=True)
# rig only (no skin) path
import importlib
bpy.ops.apex.clear_animation()
print("OK", flush=True)
