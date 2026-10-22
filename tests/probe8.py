import sys
sys.path.insert(0,'/home/user')
import bpy, numpy as np
import apex_rig
from apex_rig import rig as rigmod, skin_body, utils
apex_rig.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("FEMALE"), replace=True).arm
body = skin_body.add_mannequin(bpy.context, arm, resolution=0.012)
me = body.data
n=len(me.vertices); co=np.empty(n*3); me.vertices.foreach_get("co", co); co=co.reshape(n,3)
H = co[:,2].max()-co[:,2].min(); floor = co[:,2].min()
print("H", round(H,4), "floor", round(floor,4))
# crotch: lowest z where a gap at x~0 closes
cx = 0.5*(co[:,0].min()+co[:,0].max())
bins = np.arange(0.15,0.62,0.01)*H + floor
prev=None
for z in bins:
    band = co[(co[:,2]>=z)&(co[:,2]<z+0.01*H)]
    if len(band)==0: continue
    minx = np.abs(band[:,0]-cx).min()
    if minx < 0.035*H:
        print("crotch frac", round((z-floor)/H,3), " (minx/H", round(minx/H,3),")")
        break
# shoulders: widest z band above 0.7H
for frac in (0.70,0.75,0.78,0.80,0.82):
    band = co[(co[:,2]>=floor+frac*H)&(co[:,2]<floor+(frac+0.02)*H)]
    if len(band)==0: continue
    print("width frac", frac, "half-span/H", round(np.abs(band[:,0]-cx).max()/H,3))
# hip joint z from rig
print("pelvis head z / H:", round((arm.data.bones['pelvis'].head_local.z-floor)/H,3))
print("shoulder z / H:", round((arm.data.bones['upper_arm.L'].head_local.z-floor)/H,3))
print("ankle z / H:", round((arm.data.bones['foot.L'].head_local.z-floor)/H,3))
