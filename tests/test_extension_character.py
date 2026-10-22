import bpy, math, time, sys
import mathutils
from mathutils import Euler, Vector
from bl_ext.user_default.apex_rig import rig as rigmod, skin_body, utils, properties, fit, animation

bpy.ops.wm.read_homefile(use_empty=True)
st = properties.settings(bpy.context)

# ---- simulate a user's character: rigged with a Mixamo skeleton, rotated & scaled
src = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("FEMALE"), replace=True).arm
body = skin_body.add_mannequin(bpy.context, src, resolution=0.016)
from bl_ext.user_default.apex_rig import mocap
mocap.rename_to_style(rigmod.Rig(src), "MIXAMO")
X = (mathutils.Matrix.Translation(Vector((1.5, -2.5, 0.3)))
     @ Euler((0,0,math.radians(65))).to_matrix().to_4x4()
     @ mathutils.Matrix.Diagonal((1.05,1.05,1.05,1.0)))
src.parent = None
body.parent = src
body.matrix_parent_inverse = src.matrix_world.inverted()
src.matrix_world = X
bpy.context.view_layer.update()

# user selects only the character mesh
bpy.ops.object.select_all(action='DESELECT')
body.select_set(True); bpy.context.view_layer.objects.active = body
print("selected:", bpy.context.active_object.name, flush=True)

t0 = time.time()
print("ANALYZE:", bpy.ops.apex.analyze_character(), "|", st.detected_summary, flush=True)
print("RIG:", bpy.ops.apex.rig_character(), "|", st.detected_fit, f"({round(time.time()-t0,2)}s)", flush=True)
arm = bpy.context.view_layer.objects.active
print("new rig:", arm.name, len(arm.data.bones), "at", tuple(round(v,2) for v in arm.location),
      "rot", round(math.degrees(arm.rotation_quaternion.to_euler().z),1), flush=True)
import bpy as _b
print("apex rigs in scene:", [o.name for o in _b.data.objects if utils.is_apex_rig(o)], flush=True)
print("armatures in scene:", [o.name for o in _b.data.objects if o.type=='ARMATURE'], flush=True)
bound = utils.meshes_of_armature(arm)
print("bound meshes:", [o.name for o in bound], flush=True)
print("weights:", [ (o.name, len(o.vertex_groups)) for o in bound ], flush=True)

# does it animate?
st.motion = "WALK"; st.motion_push_nla = False
print("motion:", bpy.ops.apex.add_motion(), flush=True)
errs=[]; zs=[]
for f in range(1,33):
    bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
    fl = arm.pose.bones["foot_ik.L"].head.copy()
    errs.append((arm.pose.bones["foot.L"].head-fl).length)
    zs.append(fl.z)
print(f"walk IK err max {max(errs):.4f} m, foot lift {max(zs)-min(zs):.3f} m", flush=True)
# mesh actually deforms?
dg = bpy.context.evaluated_depsgraph_get()
def sample():
    ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return [ev.data.vertices[i].co.copy() for i in range(0, len(ev.data.vertices), 211)]
bpy.context.scene.frame_set(1); bpy.context.view_layer.update(); a = sample()
bpy.context.scene.frame_set(9); bpy.context.view_layer.update(); b = sample()
moved = sum(1 for x,y in zip(a,b) if (x-y).length > 1e-3)
print("characters verts animated by the walk:", moved, "/", len(a), flush=True)
print("panel char info:", st.detected_summary, "|", st.detected_fit, flush=True)
