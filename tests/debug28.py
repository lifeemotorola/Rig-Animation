import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions

def pel(arm):
    bpy.context.view_layer.update()
    p=arm.pose.bones["pelvis"]
    e=(arm.data.bones["pelvis"].matrix_local.inverted() @ p.matrix).to_euler()
    return round(e.x,4)

bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
print("full rig pelvis_x", pel(arm), flush=True)
keep = {"root","cog","pelvis","spine_01","thigh.L","shin.L","foot.L","toe.L","foot_ik.L","toe_ik.L"}
bpy.ops.object.mode_set(mode='EDIT')
for eb in list(arm.data.edit_bones):
    if eb.name not in keep:
        arm.data.edit_bones.remove(eb)
bpy.ops.object.mode_set(mode='OBJECT')
print("trimmed rig pelvis_x", pel(arm), flush=True)
# properties toggles
pb=arm.pose.bones["thigh.L"]
print("thigh flags: ik_stretch",pb.ik_stretch,"lin_control",pb.use_ik_linear_control,"lin_weight",pb.ik_linear_weight,"rot_weight",pb.ik_rotation_weight,"rot_control",pb.use_ik_rotation_control,"lock",(pb.lock_ik_x,pb.lock_ik_y,pb.lock_ik_z),"limits",(pb.use_ik_limit_x,pb.use_ik_limit_y,pb.use_ik_limit_z), flush=True)
pb.ik_stretch=1.0
print("thigh ik_stretch=1", pel(arm), flush=True)
pb.ik_stretch=0.0; pb.use_ik_linear_control=True; pb.ik_linear_weight=1.0
print("linear control on weight 1", pel(arm), flush=True)
pb.use_ik_linear_control=False; pb.ik_linear_weight=0.0
pb.use_ik_rotation_control=True; pb.ik_rotation_weight=1.0
print("rot control on", pel(arm), flush=True)
pb.use_ik_rotation_control=False
# what is the pelvis rotation axis? and which leg
print("pelvis rot", tuple(round(v,4) for v in (arm.data.bones['pelvis'].matrix_local.inverted() @ arm.pose.bones['pelvis'].matrix).to_euler()), flush=True)
# try disconnecting the IK (influence 0) then 1
con=[c for c in arm.pose.bones["shin.L"].constraints if c.type=='IK'][0]
con.influence=0.0; print("infl 0", pel(arm), flush=True)
con.influence=1.0
# set target to the shin tail exactly in world using matrix assignment
ctl=arm.pose.bones["foot_ik.L"]
tl = arm.pose.bones["shin.L"].tail.copy()
m = ctl.matrix.copy(); m.translation = tl; ctl.matrix = m
print("target at shin tail", pel(arm), "shin tail", tuple(round(v,3) for v in arm.pose.bones['shin.L'].tail), "target", tuple(round(v,3) for v in ctl.head), flush=True)
# print remaining bones
print("bones:", [b.name for b in arm.data.bones], flush=True)
