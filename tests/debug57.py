import sys
sys.path.insert(0,'/home/user')
import bpy
from mathutils import Vector
import surigandanim
from surigandanim import rig as rigmod, utils
surigandanim.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("FEMALE"), replace=True).arm
R = rigmod.Rig(arm)
def test(dz, tag=""):
    f = arm.pose.bones["foot_ik.L"]
    m = f.matrix.copy(); m.translation = m.translation + Vector((0,0,dz))
    f.matrix = m; utils.refresh(arm)
    err_tail = (arm.pose.bones["shin.L"].tail - f.head).length
    err_heel = (arm.pose.bones["foot.L"].head - f.head).length
    knee = arm.pose.bones["thigh.L"].tail
    print(f"{tag} dz={dz:+.3f} err_tail={err_tail:.4f} err_foot={err_heel:.4f} knee={tuple(round(v,3) for v in knee)}", flush=True)
    f.matrix = m; f.matrix.translation = f.matrix.translation - Vector((0,0,dz)); utils.refresh(arm)
for dz in (-0.02, -0.04, -0.06, -0.08, -0.12, 0.10, 0.14):
    test(dz)
# stiffness ablation
for bone in ("thigh.L","shin.L"):
    pb = arm.pose.bones[bone]; pb.ik_stiffness_y = 0.0; pb.ik_stiffness_z = 0.0
test(-0.08, "no-stiffness")
for bone in ("thigh.L","shin.L"):
    pb = arm.pose.bones[bone]; pb.ik_stiffness_y = 0.75; pb.ik_stiffness_z = 0.75
# with cog lowered instead
cog = arm.pose.bones["cog"]; m = cog.matrix.copy(); m.translation.z -= 0.08; cog.matrix = m; utils.refresh(arm)
print("cog down 8cm, foot.L err:", round((arm.pose.bones["foot.L"].head - arm.pose.bones["foot_ik.L"].head).length,4), flush=True)
