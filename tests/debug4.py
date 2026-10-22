import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions
bpy.ops.wm.read_factory_settings(use_empty=True)
opts = RigOptions.from_preset("FEMALE")   # IK defaults ON
arm = rigmod.build_rig(bpy.context, opts, replace=True).arm
pb_root = arm.pose.bones["root"]
def show(tag):
    bpy.context.view_layer.update()
    print(f"{tag:26s} head={tuple(round(v,3) for v in arm.pose.bones['head'].head)} spine1={tuple(round(v,3) for v in arm.pose.bones['spine_01'].head)} footL={tuple(round(v,3) for v in arm.pose.bones['foot.L'].head)}", flush=True)
show("as built")
for p in ("ik_arm.L","ik_arm.R","ik_leg.L","ik_leg.R"):
    pb_root[p]=0.0
show("props set 0 after")
for p in ("ik_arm.L","ik_arm.R","ik_leg.L","ik_leg.R"):
    pb_root[p]=1.0
show("props back to 1")
# now check control transforms
for bn in ("hand_ik.L","foot_ik.L","toe_ik.L"):
    pb=arm.pose.bones[bn]
    print(bn,"loc",tuple(round(v,4) for v in pb.location),"rest head",tuple(round(v,3) for v in arm.data.bones[bn].head_local),"pose head",tuple(round(v,3) for v in pb.head), flush=True)
# check rest of torso bones and bbone
for bn in ("pelvis","spine_01","spine_02","chest","neck","head"):
    b=arm.data.bones[bn]
    print(bn,"bbone segs", b.bbone_segments, "rest head", tuple(round(v,4) for v in b.head_local), "rest tail", tuple(round(v,4) for v in b.tail_local), "pose head", tuple(round(v,4) for v in arm.pose.bones[bn].head), flush=True)
