import sys, math
sys.path.insert(0,'/home/user')
import bpy
from mathutils import Vector
import apex_rig
from apex_rig import rig as rigmod, animation as anim, utils

apex_rig.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 40
scene.cycles.use_denoising = True
scene.render.resolution_x = 800
scene.render.resolution_y = 1100
scene.render.film_transparent = False
scene.view_settings.look = 'AgX - Medium High Contrast' if 'AgX - Medium High Contrast' in [i.identifier for i in scene.view_settings.bl_rna.properties['look'].enum_items] else 'None'

arm = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("FEMALE"), replace=True).arm
from apex_rig import skin_body
body = skin_body.add_mannequin(bpy.context, arm, resolution=0.010)
walk = anim.create_motion(arm, "WALK")
arm.animation_data.action = walk
try: arm.animation_data.action_slot = walk.slots[0]
except Exception: pass
scene.frame_set(25)
bpy.context.view_layer.update()

# ground
bpy.ops.mesh.primitive_plane_add(size=12, location=(0,0,0))
floor = bpy.context.object
mat = bpy.data.materials.new("Floor"); mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (0.18, 0.19, 0.21, 1)
bsdf.inputs["Roughness"].default_value = 0.55
floor.data.materials.append(mat)

def light(name, loc, energy, size, color=(1,1,1)):
    d = bpy.data.lights.new(name, type='AREA'); d.energy = energy; d.size = size; d.color = color
    o = bpy.data.objects.new(name, d); bpy.context.collection.objects.link(o); o.location = loc
    direction = Vector((0,0,1.0)) - Vector(loc)
    o.rotation_euler = direction.to_track_quat('-Z','Y').to_euler()
    return o

light("Key", (2.6,-3.0,3.1), 700, 2.5, (1.0,0.96,0.9))
light("Fill", (-3.2,-1.4,1.9), 180, 3.0, (0.75,0.84,1.0))
light("Rim", (-0.6,3.4,2.8), 450, 2.0, (1.0,0.95,0.92))
light("Bounce", (0,-1.6,0.15), 40, 3.0, (1.0,0.9,0.85))

world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.035,0.038,0.045,1)
world.node_tree.nodes["Background"].inputs[1].default_value = 1.0

cam_data = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam); scene.camera = cam
cam.location = (2.15, -3.35, 1.30)
target = Vector((0.0, 0.0, 0.92))
cam.rotation_euler = (target - cam.location).to_track_quat('-Z','Y').to_euler()
cam_data.lens = 62

scene.render.filepath = "/home/user/out/apex_preview.png"
bpy.ops.render.render(write_still=True)
print("RENDERED", scene.render.filepath, flush=True)
