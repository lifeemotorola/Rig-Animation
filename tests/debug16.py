import sys
sys.path.insert(0,'/home/user')
import bpy
from surigandanim import rig as rigmod
from surigandanim.proportions import RigOptions
bpy.ops.wm.read_factory_settings(use_empty=True)
o = RigOptions.from_preset("FEMALE")
arm = rigmod.build_rig(bpy.context, o, replace=True).arm
bpy.context.view_layer.update()
def spine():
    bpy.context.view_layer.update(); return tuple(round(v,3) for v in arm.pose.bones["spine_01"].head)
print("baseline", spine(), flush=True)
pb=arm.pose.bones["thigh.L"]
print("thigh ik flags: use_ik_linear_control", pb.use_ik_linear_control, "lin_weight", pb.ik_linear_weight, "rot_weight", pb.ik_rotation_weight, "lock_ik", (pb.lock_ik_x,pb.lock_ik_y,pb.lock_ik_z), "ik_stretch", pb.ik_stretch, flush=True)
# experiment 1: lock_ik on all four chain roots
for bn in ("thigh.L","thigh.R","upper_arm.L","upper_arm.R"):
    p=arm.pose.bones[bn]
    p.lock_ik_x=True; p.lock_ik_y=True; p.lock_ik_z=True
print("chain roots lock_ik", spine(), flush=True)
# experiment 2: use_ik_linear_control on chain roots
for bn in ("thigh.L","thigh.R","upper_arm.L","upper_arm.R"):
    p=arm.pose.bones[bn]
    p.use_ik_linear_control=True; p.ik_linear_weight=0.0
print("linear_control weight 0", spine(), flush=True)
# experiment 3: set ik_stretch=0 on all
for p in arm.pose.bones: p.ik_stretch=0.0
print("all ik_stretch 0", spine(), flush=True)
# experiment 4: pelvis lock location
for bn in ("pelvis","cog","root"):
    arm.pose.bones[bn].lock_location=(True,True,True)
print("pelvis loc locked", spine(), flush=True)
