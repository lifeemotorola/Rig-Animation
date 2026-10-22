import sys, time
sys.path.insert(0,'/home/user')
import bpy
from surigandanim import rig as rigmod, skin, skin_body, utils
from surigandanim.proportions import RigOptions
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
R = rigmod.Rig(arm)
t=time.time()
body = skin_body.add_mannequin(bpy.context, arm, resolution=0.02)
print("body verts:", len(body.data.vertices), "build %.2fs"%(time.time()-t), flush=True)
rep = skin.weight_report(body, arm)
print("report:", rep, flush=True)
mods = [(m.name, m.type, getattr(m,'object',None) and m.object.name) for m in body.modifiers]
print("mods:", mods, flush=True)
# deformation test: curl fingers + move arm IK, verify verts near hand move
dg = bpy.context.evaluated_depsgraph_get()
def eval_co():
    bpy.context.view_layer.update()
    ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.data
    return [me.vertices[i].co.copy() for i in range(0, len(me.vertices), 37)]
c0 = eval_co()
R.set_ik("arm","L",0.0); R.set_prop("finger_curl.L",1.4)
c1 = eval_co()
moved = sum(1 for a,b in zip(c0,c1) if (a-b).length>1e-4)
print("verts moved by hand IK off + curl:", moved, "/", len(c0), flush=True)
maxd = max((a-b).length for a,b in zip(c0,c1))
print("max delta:", round(maxd,4), flush=True)
R.set_ik("arm","L",1.0); R.set_prop("finger_curl.L",0.0)
