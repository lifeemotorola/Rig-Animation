import sys, time
sys.path.insert(0,'/home/user')
import bpy
import apex_rig
from apex_rig import rig as rigmod, skin_body, skin, utils
apex_rig.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("FEMALE"), replace=True).arm
t=time.time()
body = skin_body.add_mannequin(bpy.context, arm, resolution=0.012)
print("verts:", len(body.data.vertices), "faces:", len(body.data.polygons), "time", round(time.time()-t,2), flush=True)
print("report:", skin.weight_report(body, arm), flush=True)
print("dims:", tuple(round(v,3) for v in body.dimensions), flush=True)
bpy.ops.wm.save_as_mainfile(filepath="/home/user/out/body_test.blend")
