import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions
bpy.ops.wm.read_factory_settings(use_empty=True)
o = RigOptions.from_preset("FEMALE")
arm = rigmod.build_rig(bpy.context, o, replace=True).arm
bpy.context.view_layer.update()
bad=[]
for pb in arm.pose.bones:
    rest = pb.bone.head_local
    delta = (pb.head - rest).length
    if delta > 1e-4: bad.append((pb.name, round(delta,4)))
print("bones off rest:", bad[:12], "count", len(bad), flush=True)
for bn in ("hand.L","hand.R","foot.L","foot.R","head","spine_01"):
    print(bn, "pose", tuple(round(v,3) for v in arm.pose.bones[bn].head), "rest", tuple(round(v,3) for v in arm.data.bones[bn].head_local), flush=True)
pb=arm.pose.bones["root"]
print("pole angles:", {k: round(float(pb[k]),1) for k in pb.keys() if k.startswith("pole_angle")}, flush=True)
for s in ("L","R"):
    for lim,b in (("arm","forearm"),("leg","shin")):
        for c in arm.pose.bones[f"{b}.{s}"].constraints:
            if c.type=='IK': print(lim,s,"pole_angle_deg",round(c.pole_angle*57.2958,1), flush=True)
print("IK chain members:", [p.name for p in arm.pose.bones if p.is_in_ik_chain], flush=True)
# check axes after roll fix
for bn in ("spine_02","chest","head","cog"):
    m=arm.data.bones[bn].matrix_local.to_3x3()
    print("axes",bn,"X",tuple(round(v,2) for v in m.col[0]),"Y",tuple(round(v,2) for v in m.col[1]),"Z",tuple(round(v,2) for v in m.col[2]), flush=True)
