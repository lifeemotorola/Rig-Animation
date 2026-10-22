import sys, logging
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod, utils
from apex_rig.proportions import RigOptions
utils.log.setLevel(logging.DEBUG)
bpy.ops.wm.read_factory_settings(use_empty=True)
o = RigOptions.from_preset("FEMALE")
arm = rigmod.build_rig(bpy.context, o, replace=True).arm
bpy.context.view_layer.update()
bad=[]
for pb in arm.pose.bones:
    d=(pb.head-pb.bone.head_local).length
    if d>2e-3: bad.append((pb.name, round(d,4)))
print("off-rest (>2mm):", bad, flush=True)
for bn in ("hand.L","hand.R","foot.L","foot.R","head"):
    print(bn,"pose",tuple(round(v,3) for v in arm.pose.bones[bn].head),"rest",tuple(round(v,3) for v in arm.data.bones[bn].head_local), flush=True)
pb=arm.pose.bones["root"]
print("pole angles:", {k: round(float(pb[k]),1) for k in pb.keys() if k.startswith("pole_angle")}, flush=True)
