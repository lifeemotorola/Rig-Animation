import sys
sys.path.insert(0,'/home/user')
import bpy
from mathutils import Vector
import apex_rig
from apex_rig import rig as rigmod, utils
apex_rig.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("FEMALE"), replace=True).arm
R = rigmod.Rig(arm)
def crouch(dz):
    cog = arm.pose.bones["cog"]; m = cog.matrix.copy(); m.translation.z += dz; cog.matrix = m
    utils.refresh(arm)
    eL = (arm.pose.bones["foot.L"].head - arm.pose.bones["foot_ik.L"].head).length
    eR = (arm.pose.bones["foot.R"].head - arm.pose.bones["foot_ik.R"].head).length
    knee = arm.pose.bones["thigh.L"].tail
    print(f"cog dz={dz:+.2f}: foot err L {eL:.4f} R {eR:.4f} knee {tuple(round(v,3) for v in knee)}", flush=True)
    cog.matrix = m; cog.matrix.translation.z -= dz; utils.refresh(arm)
for dz in (-0.05, -0.10, -0.15, -0.25, -0.35):
    crouch(dz)
# reach in other directions from rest
def reach(dv, tag):
    f = arm.pose.bones["hand_ik.L"]; m = f.matrix.copy(); m.translation += Vector(dv); f.matrix = m
    utils.refresh(arm)
    err = (arm.pose.bones["hand.L"].head - f.head).length
    print(f"hand {tag}: err {err:.4f}", flush=True)
    f.matrix = m; f.matrix.translation -= Vector(dv); utils.refresh(arm)
for dv, tag in (((0,0.12,0),"back"), ((0,-0.12,0),"forward"), ((0.08,0,0),"out"),
                ((-0.10,0,0),"in"), ((0,0,-0.10),"down"), ((0.06,0.08,0.06),"mix")):
    reach(dv, tag)
