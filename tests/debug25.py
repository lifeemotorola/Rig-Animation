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
for bn in ("thigh.L","thigh.R"):
    p=arm.pose.bones[bn]; p.lock_ik_x=p.lock_ik_y=p.lock_ik_z=False
print("thigh lock_ik off", pel(arm), flush=True)
for bn in ("thigh.L","thigh.R"):
    p=arm.pose.bones[bn]; p.use_ik_limit_x=p.use_ik_limit_y=p.use_ik_limit_z=False
print("thigh ik limits off", pel(arm), flush=True)

arm=build()
bpy.ops.object.mode_set(mode='EDIT')
arm.data.edit_bones["thigh.L"].parent=None; arm.data.edit_bones["thigh.R"].parent=None
bpy.ops.object.mode_set(mode='OBJECT')
print("thigh unparented", pel(arm), flush=True)

arm=build()
bpy.ops.object.mode_set(mode='EDIT')
arm.data.edit_bones["thigh.L"].use_connect=True; arm.data.edit_bones["thigh.R"].use_connect=True
bpy.ops.object.mode_set(mode='OBJECT')
print("thigh connected", pel(arm), flush=True)

arm=build()
# move IK targets to exactly the current ankle and disable stretch on constraint
for side in ("L","R"):
    for c in arm.pose.bones[f"shin.{side}"].constraints:
        if c.type=='IK':
            c.use_stretch=False; c.use_tail=True
print("use_tail True", pel(arm), flush=True)

arm=build()
# does the pelvis rotation persist if we disable 'use_ik_limit' on shin?
for bn in ("shin.L","shin.R"):
    p=arm.pose.bones[bn]; p.use_ik_limit_x=p.use_ik_limit_y=p.use_ik_limit_z=False
print("shin ik limits off", pel(arm), flush=True)
