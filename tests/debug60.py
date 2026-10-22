import sys, math, time
sys.path.insert(0,'/home/user')
import bpy, numpy as np, mathutils
from mathutils import Euler, Vector
import surigandanim
from surigandanim import rig as rigmod, fit, properties
surigandanim.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
# ground truth: HEROIC rig rendered at world scale 1.15 and rotated -25 deg
res = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("HEROIC"), replace=True)
src = res.arm
X = (mathutils.Matrix.Translation(Vector((-2.5,4.0,0.2)))
     @ Euler((0,0,math.radians(-25))).to_matrix().to_4x4()
     @ mathutils.Matrix.Diagonal((1.15,1.15,1.15,1.0)))
lm = fit._match_landmarks(src)
targets = {k: X @ b.head_local for k,b in lm.items()}
from surigandanim.proportions import RigOptions
base = RigOptions.from_preset("CUSTOM", height=1.92*1.15, arm_angle=40, leg_len=1.02)
t0=time.time()
prof, (R,t), err = fit.solve_profile(targets, base)
print(f"solve {round(time.time()-t0,2)}s RMS {err*100:.2f} cm")
print("solved:", {k: round(v,3) for k,v in prof.items()})
print("truth :", dict(height=round(1.92*1.15,3), leg_len=1.02, arm_len=1.03, shoulder=1.14, hip=0.98, head_scale=0.93, arm_angle=40.0))
# verify with actual bones
opts = RigOptions.from_preset("CUSTOM")
fit.apply_to_options(fit.CharacterInfo(height=prof["height"], floor=0, center=(0,0), facing_vec=Vector((0,-1,0))), opts)
