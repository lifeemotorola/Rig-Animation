import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bpy
from mathutils import Vector
import apex_rig
from apex_rig import rig as rigmod, skin_body, poses, utils, deform

apex_rig.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"; scene.cycles.device = "CPU"; scene.cycles.samples = 48
scene.cycles.use_denoising = True
scene.render.resolution_x = 560; scene.render.resolution_y = 720
scene.view_settings.look = 'AgX - Medium High Contrast'

world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.045, 0.05, 0.06, 1)

def area(name, loc, energy, size, color=(1, 1, 1)):
    d = bpy.data.lights.new(name, 'AREA'); d.energy = energy; d.size = size; d.color = color
    o = bpy.data.objects.new(name, d); bpy.context.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector((0, 0, 0.9)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
area("Key", (2.4, -3.0, 3.0), 520, 2.6, (1.0, 0.96, 0.9))
area("Fill", (-3.0, -1.4, 1.7), 150, 3.0, (0.72, 0.82, 1.0))
area("Rim", (-0.5, 3.2, 2.6), 380, 2.0, (1.0, 0.95, 0.92))

bpy.ops.mesh.primitive_plane_add(size=16, location=(0, 0, 0))
floor = bpy.context.object
mat = bpy.data.materials.new("Floor"); mat.use_nodes = True
b = mat.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.16, 0.17, 0.19, 1); b.inputs["Roughness"].default_value = 0.6
floor.data.materials.append(mat)

cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
bpy.context.collection.objects.link(cam); scene.camera = cam
cam.data.lens = 62

POSES = ("RELAXED", "COMBAT", "CROUCH", "HERO", "WAVE", "SIT")
OUT = "/home/user/out"
for key in POSES:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"; scene.cycles.device = "CPU"; scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 560; scene.render.resolution_y = 720
    scene.view_settings.look = 'AgX - Medium High Contrast'
    world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.045, 0.05, 0.06, 1)
    area("Key", (2.4, -3.0, 3.0), 520, 2.6, (1.0, 0.96, 0.9))
    area("Fill", (-3.0, -1.4, 1.7), 150, 3.0, (0.72, 0.82, 1.0))
    area("Rim", (-0.5, 3.2, 2.6), 380, 2.0, (1.0, 0.95, 0.92))
    bpy.ops.mesh.primitive_plane_add(size=16, location=(0, 0, 0))
    floor = bpy.context.object
    mat = bpy.data.materials.new("Floor"); mat.use_nodes = True
    bb = mat.node_tree.nodes["Principled BSDF"]
    bb.inputs["Base Color"].default_value = (0.16, 0.17, 0.19, 1); bb.inputs["Roughness"].default_value = 0.6
    floor.data.materials.append(mat)

    arm = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("FEMALE"), replace=True).arm
    body = skin_body.add_mannequin(bpy.context, arm, resolution=0.013)
    deform.set_preserve_volume(arm, True)
    poses.apply_pose(arm, key)
    utils.refresh(arm)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    bpy.context.collection.objects.link(cam); scene.camera = cam; cam.data.lens = 62
    target = Vector((0.0, 0.0, 0.90))
    cam.location = (1.9, -3.1, 1.30)
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = f"{OUT}/showcase_{key.lower()}.png"
    bpy.ops.render.render(write_still=True)
    print("rendered", key, flush=True)
