import sys
sys.path.insert(0,'/home/user')
import bpy
from surigandanim import rig as rigmod
from surigandanim.proportions import RigOptions
from mathutils import Vector

def pel(arm):
    bpy.context.view_layer.update()
    p=arm.pose.bones["pelvis"]
    return round((arm.data.bones["pelvis"].matrix_local.inverted() @ p.matrix).to_euler().x,4)

bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
print("base", pel(arm), flush=True)
pb=arm.pose.bones["foot_ik.L"]
m=pb.matrix.copy()
for dz in (0.0, -0.02, -0.05, -0.10, 0.05):
    mm=m.copy(); mm.translation.z += dz; pb.matrix=mm
    print(f"target z {dz:+.2f} -> pelvis_x {pel(arm)} shin_tail={tuple(round(v,3) for v in arm.pose.bones['shin.L'].tail)} target={tuple(round(v,3) for v in pb.head)}", flush=True)
# now move target forward (away)
pb.matrix=m
for dy in (-0.05, -0.15):
    mm=m.copy(); mm.translation.y += dy; pb.matrix=mm
    print(f"target y {dy:+.2f} -> pelvis_x {pel(arm)}", flush=True)
# disable stretch entirely and retest at rest
pb.matrix=m
for side in ("L","R"):
    for c in arm.pose.bones[f"shin.{side}"].constraints:
        if c.type=='IK': c.use_stretch=False
print("no stretch at rest", pel(arm), flush=True)
# set ik_stretch on thigh to 0 and lock_ik off
for side in ("L","R"):
    p2=arm.pose.bones[f"thigh.{side}"]; p2.ik_stretch=0.0
    p2.lock_ik_x=p2.lock_ik_y=p2.lock_ik_z=False
print("thigh stretch 0 locks off", pel(arm), flush=True)
