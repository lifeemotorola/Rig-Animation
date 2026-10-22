import bpy, os
from bl_ext.user_default import apex_rig as ext
from bl_ext.user_default.apex_rig import properties as ext_props

print("extension imported:", ext.__version__, flush=True)
bpy.ops.wm.read_homefile(use_empty=True)
st = ext_props.settings(bpy.context)
st.add_mannequin = True
st.mannequin_resolution = 0.03
print("build:", bpy.ops.apex.build_rig(), flush=True)
arm = bpy.context.view_layer.objects.active
print("rig:", arm.name, len(arm.data.bones), "mesh:", [o.name for o in bpy.data.objects if o.type=='MESH' and o.parent==arm], flush=True)
st.motion = "RUN"; st.motion_push_nla = True
print("motion:", bpy.ops.apex.add_motion(), flush=True)
print("actions:", [a.name for a in bpy.data.actions], flush=True)
print("nla tracks:", [t.name for t in arm.animation_data.nla_tracks], flush=True)
st.export_path = "/home/user/out/from_extension.glb"
print("export:", bpy.ops.apex.export(), flush=True)
print("glb size:", os.path.getsize("/home/user/out/from_extension.glb"), flush=True)
print("panels:", [n for n in dir(bpy.types) if n.startswith("APEX_PT")], flush=True)
