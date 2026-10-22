import sys
sys.path.insert(0,'/home/user')
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add()
cube = bpy.context.object
cube["k"] = 0.0
fc = cube.driver_add("location", 0)
d = fc.driver; d.type='SCRIPTED'; d.expression='k'
v = d.variables.new(); v.name='k'; v.type='SINGLE_PROP'; v.targets[0].id=cube; v.targets[0].data_path='["k"]'
cube["k"]=2.0
print("after set: loc.x", cube.location.x, "simple", d.is_simple_expression, "valid", d.is_valid, flush=True)
bpy.context.view_layer.update()
print("after view_layer.update:", cube.location.x, flush=True)
bpy.context.view_layer.depsgraph.update()
print("after depsgraph.update:", cube.location.x, flush=True)
bpy.context.scene.frame_set(1)
print("after frame_set:", cube.location.x, flush=True)
cube.update_tag()
bpy.context.view_layer.update()
print("after update_tag:", cube.location.x, flush=True)
# evaluated object
ev = cube.evaluated_get(bpy.context.evaluated_depsgraph_get())
print("evaluated loc.x:", ev.location.x, "orig:", cube.location.x, flush=True)
# try keyframed driver? and check autoexec setting
print("autoexec:", bpy.app.autoexec_fail if hasattr(bpy.app,'autoexec_fail') else "?", flush=True)
try:
    print("use_scripts_auto_execute:", bpy.context.preferences.filepaths.use_scripts_auto_execute, flush=True)
except Exception as e: print("pref err", e, flush=True)
