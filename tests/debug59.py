import sys, math
sys.path.insert(0,'/home/user')
import bpy, numpy as np
from mathutils import Vector
import surigandanim
from surigandanim import rig as rigmod, skin_body, fit, utils
surigandanim.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("MALE"), replace=True).arm
body = skin_body.add_mannequin(bpy.context, arm, resolution=0.014)
body.parent = None
rigmod.delete_rig(arm)
bpy.context.view_layer.objects.active = body
pts = fit._evaluated_points([body])
zmin, zmax = pts[:,2].min(), pts[:,2].max(); H = zmax-zmin
print("H", round(H,3), "facing raw:", tuple(round(v,3) for v in fit._facing_from_feet(pts[pts[:,2]<=zmin+0.10*H])), flush=True)
info = fit.measure_mesh([body])
print("facing key", info.facing_key, "crotch", info.crotch_frac, "arm", round(info.arm_angle,1), "leg", round(info.leg_len,3), flush=True)
# crotch bins
local, rot = fit._character_space(pts, info.facing_vec)
cx = local[(local[:,2]>=zmin+0.42*H)&(local[:,2]<=zmin+0.52*H)][:,0].mean()
print("cx", round(cx,4), flush=True)
for frac in np.arange(0.20,0.50,0.02):
    z = zmin+frac*H
    band = local[(local[:,2]>=z-0.004*H)&(local[:,2]<=z+0.004*H)]
    if len(band): print(f"  z={frac:.2f}H min|x|={np.abs(band[:,0]-cx).min():.4f} ({(np.abs(band[:,0]-cx).min())/H:.3f}H) n={len(band)}", flush=True)
