import sys
sys.path.insert(0,'/home/user')
import bpy
from surigandanim import rig as rigmod
from surigandanim.proportions import RigOptions

def pel(arm):
    bpy.context.view_layer.update()
    p=arm.pose.bones["pelvis"]
    e=(arm.data.bones["pelvis"].matrix_local.inverted() @ p.matrix).to_euler()
    return tuple(round(v,4) for v in e)
def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm

arm=build(); print("base", pel(arm), flush=True)
for pb in arm.pose.bones:
    pb.lock_location=(False,False,False); pb.lock_scale=(False,False,False)
print("locks cleared", pel(arm), flush=True)
for pb in arm.pose.bones:
    pb.rotation_mode='QUATERNION'
print("all quat", pel(arm), flush=True)
arm=build()
# delete every constraint except leg IK
for pb in arm.pose.bones:
    for c in list(pb.constraints):
        if not (c.type=='IK' and 'Leg' in c.name):
            pb.constraints.remove(c)
print("only leg IK", pel(arm), flush=True)
arm=build()
for pb in arm.pose.bones:
    for c in list(pb.constraints):
        if not (c.type=='IK' and 'Arm' in c.name):
            pb.constraints.remove(c)
print("only arm IK", pel(arm), flush=True)
arm=build()
for pb in arm.pose.bones:
    for c in list(pb.constraints):
        if c.type!='IK': pb.constraints.remove(c)
print("only IK", pel(arm), flush=True)
# check is_in_ik_chain and pelvis parent
arm=build()
print("pelvis in chain:", arm.pose.bones["pelvis"].is_in_ik_chain, [p.name for p in arm.pose.bones if p.is_in_ik_chain], flush=True)
print("thigh parent:", arm.pose.bones["thigh.L"].parent.name, "connect:", arm.data.bones["thigh.L"].use_connect, flush=True)
print("pelvis parent:", arm.pose.bones["pelvis"].parent.name, "connect:", arm.data.bones["pelvis"].use_connect, flush=True)
print("pelvis bbone:", arm.data.bones["pelvis"].bbone_segments, flush=True)
