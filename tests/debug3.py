import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions
bpy.ops.wm.read_factory_settings(use_empty=True)
opts = RigOptions.from_preset("FEMALE"); opts.ik_arms=False; opts.ik_legs=False
arm = rigmod.build_rig(bpy.context, opts, replace=True).arm
bpy.context.view_layer.update()
pb_root = arm.pose.bones["root"]
def show(tag):
    bpy.context.view_layer.update()
    head = arm.pose.bones["head"].head
    pel = arm.pose.bones["pelvis"]
    print(f"{tag:28s} head={tuple(round(v,3) for v in head)} pelvis_q={tuple(round(v,3) for v in pel.rotation_quaternion)} pelvis_scale={tuple(round(v,3) for v in pel.scale)} pelvis_mat_z={tuple(round(v,3) for v in pel.matrix.col[1][:])}", flush=True)
show("rest")
pb_root["ik_arm.L"]=1
show("ik_arm.L=1")
pb_root["ik_arm.L"]=0; pb_root["ik_leg.L"]=1
show("ik_leg.L=1")
pb_root["ik_leg.L"]=0
show("all off")
# mute the arm ik constraint and enable
con = [c for c in arm.pose.bones["forearm.L"].constraints if c.type=='IK'][0]
con.influence=1.0; con.mute=True
show("arm ik infl=1 muted")
con.mute=False
show("arm ik infl=1 unmuted")
# inspect stretch
for bn in ("forearm.L","shin.L","upper_arm.L","thigh.L"):
    pb=arm.pose.bones[bn]
    print(bn, "scale", tuple(round(v,4) for v in pb.scale), "ik_stretch", round(pb.ik_stretch,4), "loc", tuple(round(v,4) for v in pb.location), flush=True)
print("head pose matrix:", [round(v,3) for v in arm.pose.bones["head"].matrix.to_translation()], flush=True)
print("pelvis pose matrix rot:", [ [round(v,3) for v in row] for row in arm.pose.bones["pelvis"].matrix.to_3x3()], flush=True)
