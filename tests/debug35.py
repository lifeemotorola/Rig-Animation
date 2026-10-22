import sys
sys.path.insert(0,'/home/user')
import bpy
from surigandanim import rig as rigmod
from surigandanim.proportions import RigOptions
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
bpy.context.view_layer.update()
bad=[(pb.name, round((pb.head-pb.bone.head_local).length,4)) for pb in arm.pose.bones if (pb.head-pb.bone.head_local).length>2e-3]
print("off-rest:", bad, flush=True)
print("pole angles:", {k: round(float(arm.pose.bones['root'][k]),1) for k in arm.pose.bones['root'].keys() if k.startswith("pole_angle")}, flush=True)
def follow_test(name, ctl_name, end_name, offset):
    ctl=arm.pose.bones[ctl_name]; m=ctl.matrix.copy(); m.translation += Vector(offset); ctl.matrix=m
    bpy.context.view_layer.update()
    d=(arm.pose.bones[end_name].head-ctl.head).length
    print(f"{name}: end={tuple(round(v,3) for v in arm.pose.bones[end_name].head)} target={tuple(round(v,3) for v in ctl.head)} dist={round(d,4)}", flush=True)
follow_test("foot +15cm z","foot_ik.L","foot.L",(0,0,0.15))
follow_test("foot -8cm z (crouch)","foot_ik.L","foot.L",(0,0,-0.08))
follow_test("hand +10cm z","hand_ik.L","hand.L",(0,0,0.10))
follow_test("hand +12cm x","hand_ik.R","hand.R",(0.12,0,0))
# pelvis at rest after leg move?
p=arm.pose.bones["pelvis"]
print("pelvis delta after moves:", tuple(round(v,4) for v in (arm.data.bones['pelvis'].matrix_local.inverted() @ p.matrix).to_euler()), flush=True)
