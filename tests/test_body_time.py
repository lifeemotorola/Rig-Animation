import sys, time
sys.path.insert(0,'/home/user')
import bpy
import apex_rig
from apex_rig import rig as rigmod, skin_body, skin
apex_rig.register()
for voxel in (0.0192, 0.024, 0.030):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    arm = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("FEMALE"), replace=True).arm
    t=time.time()
    body = skin_body.build_mannequin_mesh(bpy.context, arm, voxel_size=voxel)
    tb=time.time()-t
    t=time.time(); skin.skin_mesh(arm, body); ts=time.time()-t
    print(f"voxel {voxel}: verts {len(body.data.vertices)} build {tb:.1f}s skin {ts:.1f}s", flush=True)
