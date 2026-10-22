import sys, time
sys.path.insert(0,'/home/user')
import bpy, bmesh
from mathutils import Matrix, Vector
import apex_rig
from apex_rig import rig as rigmod, skin_body, utils
apex_rig.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("FEMALE"), replace=True).arm

t=time.time()
bm = bmesh.new()
count=0
for bone in arm.data.bones:
    key=None
    for cand in (bone.name, bone.name.split(".")[0]):
        if cand in skin_body.BODY_BONES: key=cand; break
    if key is None: continue
    r=skin_body.BODY_BONES[key][0]
    steps = int(max(3, min(48, round(bone.length/(max(r,1e-4)*0.32)))))
    for i in range(steps+1):
        skin_body._ellipsoid(bm, bone.head_local.lerp(bone.tail_local, i/steps), (bone.tail_local-bone.head_local), r, 1.0, 1.0)
        count+=1
print("spheres", count, "bmesh time", round(time.time()-t,2), flush=True)
mesh = bpy.data.meshes.new("m"); 
t=time.time(); bm.to_mesh(mesh); bm.free(); print("to_mesh", round(time.time()-t,2), "verts", len(mesh.vertices), flush=True)
ob = bpy.data.objects.new("b", mesh); bpy.context.collection.objects.link(ob)
utils.select_only([ob]); bpy.context.view_layer.objects.active=ob
for voxel in (0.02,):
    m = ob.modifiers.new("R","REMESH"); m.mode='VOXEL'; m.voxel_size=voxel; m.adaptivity=0.012
    t=time.time(); bpy.ops.object.modifier_apply(modifier=m.name); print("remesh", voxel, round(time.time()-t,2), "verts", len(ob.data.vertices), flush=True)
m = ob.modifiers.new("S","SMOOTH"); m.factor=0.75; m.iterations=6
t=time.time(); bpy.ops.object.modifier_apply(modifier=m.name); print("smooth", round(time.time()-t,2), flush=True)
