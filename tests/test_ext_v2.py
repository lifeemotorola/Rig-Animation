import bpy, os
bpy.ops.preferences.addon_enable(module="bl_ext.user_default.surigandanim")
from bl_ext.user_default.surigandanim import (rig as rigmod, skin_body, deform, poses,
                                           animation as anim, properties, ui_icons, fit)
print("extension:", rigname := rigmod.RIG_NAME if hasattr(rigmod,'RIG_NAME') else "apex", flush=True)
bpy.ops.wm.read_homefile(use_empty=True)
st = properties.settings(bpy.context)
st.add_mannequin = True; st.mannequin_resolution = 0.02
print("build:", bpy.ops.apex.build_rig(), flush=True)
arm = bpy.context.view_layer.objects.active
body = [o for o in bpy.data.objects if o.type=='MESH' and o.parent==arm][0]
print("rig:", arm.name, len(arm.data.bones), "mesh:", len(body.data.vertices), flush=True)
print("deform check:", bpy.ops.apex.deform_check(), "|", st.deform_report, flush=True)
print("  ", st.deform_details, flush=True)
print("pose:", bpy.ops.apex.apply_pose(pose="COMBAT"), flush=True)
print("motion:", bpy.ops.apex.add_motion_pick(motion="WALK"), flush=True)
walk = anim.get_motion_action(arm, "WALK")
cov = deform.animation_coverage(arm, body, walk)
print("animation coverage:", cov["moving"], "/", cov["total"], "static:", cov["static_bones"], flush=True)
print("heatmap:", bpy.ops.apex.weight_op(tool="HEATMAP"), flush=True)
print("preserve:", bpy.ops.apex.preserve_volume(enabled=True), flush=True)
print("corrective:", bpy.ops.apex.corrective_smooth(), flush=True)
print("previews:", {k: bool(ui_icons.icon_id(k, {"preset":"FEMALE","pose":"RELAXED","motion":"WALK","skin":"APEX"}[k])) for k in ("preset","pose","motion","skin")}, flush=True)
print("panels:", len([n for n in dir(bpy.types) if n.startswith("APEX_PT")]), flush=True)
st.export_path = "/home/user/out/v2_export.glb"; st.export_selection = True
print("export:", bpy.ops.apex.export(), os.path.getsize("/home/user/out/v2_export.glb"), flush=True)
