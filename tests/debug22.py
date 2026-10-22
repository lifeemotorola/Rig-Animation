import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions

def dev(arm):
    bpy.context.view_layer.update()
    pel=arm.pose.bones["pelvis"]
    e=(arm.data.bones["pelvis"].matrix_local.inverted() @ pel.matrix).to_euler()
    return tuple(round(v,4) for v in e), round((arm.pose.bones["foot.L"].head-arm.data.bones["foot.L"].head_local).length,4)

def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm

arm=build(); print("baseline pelvis_eul/footdev:", dev(arm), flush=True)
bpy.ops.object.mode_set(mode='EDIT')
for n in ("foot_ik.L","foot_ik.R","hand_ik.L","hand_ik.R"):
    arm.data.edit_bones[n].parent = None
bpy.ops.object.mode_set(mode='OBJECT')
print("targets unparented:", dev(arm), flush=True)

arm=build()
bpy.ops.object.mode_set(mode='EDIT')
for n in ("foot_ik.L","foot_ik.R"):
    arm.data.edit_bones[n].parent = None
bpy.ops.object.mode_set(mode='OBJECT')
print("only foot targets unparented:", dev(arm), flush=True)

arm=build()
for pb in arm.pose.bones:
    if pb.name.startswith("foot_ik") or pb.name.startswith("hand_ik"):
        pb.bone.use_inherit_rotation = False
print("(no effect expected) rotations inherit off:", dev(arm), flush=True)

arm=build()
# remove leg IK on one side -> check pelvis
for side in ("L",):
    for c in list(arm.pose.bones[f"shin.{side}"].constraints):
        if c.type=='IK': arm.pose.bones[f"shin.{side}"].constraints.remove(c)
print("leg IK L removed:", dev(arm), flush=True)
arm=build()
# remove arm ik only
for side in ("L","R"):
    for c in list(arm.pose.bones[f"forearm.{side}"].constraints):
        if c.type=='IK': arm.pose.bones[f"forearm.{side}"].constraints.remove(c)
print("arm IK removed:", dev(arm), flush=True)
