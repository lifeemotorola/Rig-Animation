import sys, os
sys.path.insert(0,'/home/user')
import bpy
import surigandanim
from surigandanim import const

surigandanim.register()
print("registered", surigandanim.__version__, flush=True)
print("operator:", hasattr(bpy.ops.apex, "build_rig"), flush=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
st = bpy.context.scene.apex_settings
st.preset = "FEMALE"; st.height = 1.68; st.build = 0.42
st.add_mannequin = True
st.mannequin_resolution = 0.02

try:
    res = bpy.ops.apex.build_rig()
    print("build op:", res, flush=True)
except Exception as e:
    import traceback; traceback.print_exc()

rig = [o for o in bpy.data.objects if o.type=="ARMATURE"]
print("armatures:", [o.name for o in rig], flush=True)
body = [o for o in bpy.data.objects if o.type=="MESH"]
print("meshes:", [(o.name, len(o.data.vertices)) for o in body], flush=True)

arm = rig[0]
print("bones:", len(arm.data.bones), "actions:", len(bpy.data.actions), flush=True)
# motion operator
st.motion = "WALK"
st.motion_push_nla = True
try:
    print("motion op:", bpy.ops.apex.add_motion(), flush=True)
except Exception:
    import traceback; traceback.print_exc()
print("actions now:", [a.name for a in bpy.data.actions], flush=True)
print("nla:", [(t.name, [s.name for s in t.strips]) for t in (arm.animation_data.nla_tracks if arm.animation_data else [])], flush=True)
# skin report
bpy.context.view_layer.objects.active = arm
for o in bpy.data.objects: o.select_set(o is arm)
try:
    print("weights:", bpy.ops.apex.weight_report(), flush=True)
except Exception:
    import traceback; traceback.print_exc()
# panel draw smoke test
import bpy
for pcls in ("APEX_PT_main","APEX_PT_controls","APEX_PT_skin","APEX_PT_animation","APEX_PT_retarget","APEX_PT_export"):
    cls = getattr(bpy.types, pcls, None)
    print("panel", pcls, "->", bool(cls), flush=True)
