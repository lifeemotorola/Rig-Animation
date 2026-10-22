import sys, os, time
sys.path.insert(0,'/home/user')
import bpy
import surigandanim
from surigandanim import animation as anim, rig as rigmod, utils

surigandanim.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
st = scene.apex_settings
st.height = 1.68; st.add_mannequin = True; st.mannequin_resolution = 0.014
t0 = time.time()
bpy.ops.apex.build_rig()
arm = utils.active_armature(require_apex=True)
body = [o for o in bpy.data.objects if o.type=='MESH' and o.parent==arm][0]
print(f"BUILD+SKIN {round(time.time()-t0,2)}s  bones={len(arm.data.bones)} verts={len(body.data.vertices)}", flush=True)

st.motion_push_nla = True; st.export_bake_actions = True
for key in ("BREATHE","WALK","RUN","IDLE","LOOK","FINGERS","SETTLE","WEIGHT","SNEAK"):
    st.motion = key
    bpy.ops.apex.add_motion()
tracks = [(t.name, round(t.strips[0].frame_start), round(t.strips[0].frame_end)) for t in arm.animation_data.nla_tracks]
print("NLA tracks:", len(tracks), tracks[:3], "...", flush=True)
print("actions:", len(bpy.data.actions), flush=True)
scene.frame_start, scene.frame_end = 1, int(max(t[2] for t in tracks))
# scrub everything to catch evaluation errors
for f in range(1, scene.frame_end+1, 3):
    scene.frame_set(f)
bpy.context.view_layer.update()
print("scrubbed", scene.frame_end, "frames ok", flush=True)

st.export_selection = True
for preset, path in (("GLTF_GLB","/home/user/out/apex_full.glb"), ("FBX_UNITY","/home/user/out/apex_full.fbx")):
    st.export_preset = preset; st.export_path = path
    t0=time.time(); r = bpy.ops.apex.export()
    print(preset, r, os.path.getsize(path), "bytes", round(time.time()-t0,2), "s", flush=True)
bpy.ops.wm.save_as_mainfile(filepath="/home/user/out/apex_full.blend")
print("blend saved", os.path.getsize("/home/user/out/apex_full.blend"), flush=True)
