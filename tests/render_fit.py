import sys, math
sys.path.insert(0,'/home/user')
import bpy, mathutils
from mathutils import Euler, Vector
import surigandanim
from surigandanim import rig as rigmod, skin_body, utils, properties, fit, animation as anim

surigandanim.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'; scene.cycles.device='CPU'; scene.cycles.samples=40
scene.cycles.use_denoising = True
scene.render.resolution_x = 800; scene.render.resolution_y = 1100
scene.view_settings.look = 'AgX - Medium High Contrast' if 'AgX - Medium High Contrast' in [i.identifier for i in scene.view_settings.bl_rna.properties['look'].enum_items] else 'None'

# 1) a pre-existing character: own transform, own (foreign) skeleton
src = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("FEMALE"), replace=True).arm
body = skin_body.add_mannequin(bpy.context, src, resolution=0.012)
from surigandanim import mocap
mocap.rename_to_style(rigmod.Rig(src), "MIXAMO")
X = (mathutils.Matrix.Translation(Vector((0.0, 0.0, 0.0)))
     @ Euler((0,0,math.radians(35))).to_matrix().to_4x4())
body.parent = src; body.matrix_parent_inverse = src.matrix_world.inverted()
src.parent = None
src.matrix_world = X
bpy.context.view_layer.update()
# 2) user selects the mesh and runs Rig My Character
bpy.ops.object.select_all(action='DESELECT')
body.select_set(True); bpy.context.view_layer.objects.active = body
st = properties.settings(bpy.context)
print("ANALYZE", bpy.ops.apex.analyze_character(), st.detected_summary, flush=True)
print("RIG", bpy.ops.apex.rig_character(), st.detected_fit, flush=True)
arm = bpy.context.view_layer.objects.active
print("final rig at", tuple(round(v,2) for v in arm.location), "rot", round(math.degrees(arm.rotation_quaternion.to_euler().z),1), flush=True)

# 3) animate it
st.motion = "WALK"; st.motion_push_nla = False
bpy.ops.apex.add_motion()
walk = anim.get_motion_action(arm, "WALK")
arm.animation_data.action = walk
try: arm.animation_data.action_slot = walk.slots[0]
except Exception: pass
scene.frame_set(7)
bpy.context.view_layer.update()

# 4) lighting + camera
bpy.ops.mesh.primitive_plane_add(size=14, location=(0,0,0))
floor = bpy.context.object
mat = bpy.data.materials.new("Floor"); mat.use_nodes=True
b = mat.node_tree.nodes.get("Principled BSDF")
b.inputs["Base Color"].default_value=(0.17,0.18,0.20,1); b.inputs["Roughness"].default_value=0.55
floor.data.materials.append(mat)
def light(name, loc, energy, size, color=(1,1,1)):
    d = bpy.data.lights.new(name, type='AREA'); d.energy=energy; d.size=size; d.color=color
    o = bpy.data.objects.new(name, d); bpy.context.collection.objects.link(o); o.location=loc
    o.rotation_euler = (Vector((0,0,1.0))-Vector(loc)).to_track_quat('-Z','Y').to_euler()
light("Key", (2.4,-3.0,3.0), 650, 2.5, (1.0,0.96,0.9))
light("Fill", (-3.0,-1.2,1.8), 170, 3.0, (0.75,0.84,1.0))
light("Rim", (-0.4,3.2,2.6), 420, 2.0, (1.0,0.95,0.92))
light("Bounce", (0,-1.6,0.15), 35, 3.0, (1.0,0.9,0.85))
world = bpy.data.worlds.new("W"); scene.world=world; world.use_nodes=True
world.node_tree.nodes["Background"].inputs[0].default_value=(0.035,0.038,0.045,1)
cam_data = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam); scene.camera=cam
cam.location = (2.0, -3.2, 1.25)
target = Vector((0.0, 0.0, 0.92))
cam.rotation_euler = (target-cam.location).to_track_quat('-Z','Y').to_euler()
cam_data.lens = 60
scene.render.filepath = "/home/user/out/apex_fitted.png"
bpy.ops.render.render(write_still=True)
print("RENDERED", scene.render.filepath, flush=True)
