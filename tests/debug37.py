import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
bpy.context.view_layer.update()
bad=[(pb.name, round((pb.head-pb.bone.head_local).length,4)) for pb in arm.pose.bones if (pb.head-pb.bone.head_local).length>2e-3]
print("off-rest:", bad, flush=True)
print("pole angles:", {k: round(float(arm.pose.bones['root'][k]),1) for k in arm.pose.bones['root'].keys() if k.startswith("pole_angle")}, flush=True)
def test(ctl_name, end, off):
    ctl=arm.pose.bones[ctl_name]; m=ctl.matrix.copy(); m.translation += Vector(off); ctl.matrix=m
    bpy.context.view_layer.update()
    err=round((arm.pose.bones[end].head-ctl.head).length,4)
    ctl.matrix=m.copy(); ctl.matrix.translation = m.translation - Vector(off)
    bpy.context.view_layer.update()
    return err
print("foot +14z", test("foot_ik.L","foot.L",(0,0,0.14)), "foot -8z", test("foot_ik.L","foot.L",(0,0,-0.08)),
      "foot +10y", test("foot_ik.L","foot.L",(0,0.10,0)), "hand +14z", test("hand_ik.L","hand.L",(0,0,0.14)),
      "hand +12x R", test("hand_ik.R","hand.R",(0.12,0,0)), flush=True)
# pole sensitivity
ikc=[c for c in arm.pose.bones["shin.L"].constraints if c.type=='IK'][0]
ctl=arm.pose.bones["foot_ik.L"]; m=ctl.matrix.copy(); m.translation += Vector((0,0.05,0.12)); ctl.matrix=m
bpy.context.view_layer.update(); k0=tuple(round(v,3) for v in arm.pose.bones["shin.L"].head)
ikc.pole_angle += 0.8; bpy.context.view_layer.update(); k1=tuple(round(v,3) for v in arm.pose.bones["shin.L"].head)
print("knee pole sensitivity:", k0, k1, "moved:", k0!=k1, flush=True)
# pelvis stays put when posing limbs
p=arm.pose.bones["pelvis"]
print("pelvis delta:", tuple(round(v,4) for v in (arm.data.bones['pelvis'].matrix_local.inverted() @ p.matrix).to_euler()), flush=True)
