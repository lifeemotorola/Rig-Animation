
import sys, math
sys.path.insert(0,'/home/user')
import bpy, mathutils
from mathutils import Euler, Vector
import apex_rig
from apex_rig import rig as rigmod, skin_body, utils, properties, fit
apex_rig.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
st = properties.settings(bpy.context)

src = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("MALE"), replace=True).arm
body = skin_body.add_mannequin(bpy.context, src, resolution=0.014)
GT_X = (mathutils.Matrix.Translation(Vector((3.2,-1.7,0.55)))
        @ Euler((0,0,math.radians(120))).to_matrix().to_4x4()
        @ mathutils.Matrix.Diagonal((0.85,0.85,0.85,1.0)))
GT = {b: GT_X @ src.data.bones[b].head_local for b in ("pelvis","head","hand.L","foot.L","chest")}
body.parent = None
body.matrix_world = GT_X
rigmod.delete_rig(src)
utils.select_only([body]); bpy.context.view_layer.objects.active = body

print("analyze:", bpy.ops.apex.analyze_character(), "|", st.detected_summary, flush=True)
print("panel values: H", round(st.detected_height,3), "arm", round(st.detected_arm_angle,1),
      "facing", st.detected_facing, "leg", round(st.detected_leg_len,3), flush=True)
print("rig:", bpy.ops.apex.rig_character(), flush=True)
arm = bpy.context.view_layer.objects.active
print("active:", arm.name, arm.type, "bones:", len(arm.data.bones), "meshes:", [o.name for o in bpy.data.objects if o.type=='MESH' and o.type=='MESH' and o.animation_data is None and o.parent==arm], flush=True)
print("fit report:", st.detected_fit, flush=True)
errs = []
for bn, gt in GT.items():
    new = arm.matrix_world @ arm.data.bones[bn].head_local
    errs.append((new-gt).length)
    print(f"  {bn:8s} {(new-gt).length:.4f}", flush=True)
print("MAX landmark error:", round(max(errs),4), flush=True)
print("check op:", bpy.ops.apex.check_fit(), "|", st.detected_fit, flush=True)
# refit operator on a moved character
body.matrix_world = (mathutils.Matrix.Translation(Vector((-1.0, 2.0, 0.0)))
                     @ Euler((0,0,math.radians(-35))).to_matrix().to_4x4()
                     @ mathutils.Matrix.Diagonal((1.1,1.1,1.1,1.0)))
utils.select_only([arm, body]); bpy.context.view_layer.objects.active = arm
print("refit:", bpy.ops.apex.fit_rig(), flush=True)
print("rig now at", tuple(round(v,2) for v in arm.location), "scale", round(arm.scale[0],3),
      "rot", round(math.degrees(arm.rotation_quaternion.to_euler().z),1), flush=True)
# deformation still works after refit?
utils.refresh(arm)
R = rigmod.Rig(arm)
dg = bpy.context.evaluated_depsgraph_get()
ev = body.evaluated_get(dg); before = [ev.data.vertices[i].co.copy() for i in range(0, len(ev.data.vertices), 97)]
R.set_prop("finger_curl.L", 1.0); R.set_ik("arm","L",1.0)
m = arm.pose.bones["hand_ik.L"].matrix.copy(); m.translation += Vector((0,0,0.25)); arm.pose.bones["hand_ik.L"].matrix = m
utils.refresh(arm)
ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get()); after = [ev.data.vertices[i].co.copy() for i in range(0, len(ev.data.vertices), 97)]
moved = sum(1 for a,b in zip(before,after) if (a-b).length > 1e-4)
print("verts deformed after refit:", moved, "/", len(before), flush=True)
