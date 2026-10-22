import sys
import bpy
def cube_driver(expr, var="k", prop=3.0, enable_scripts=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if enable_scripts:
        bpy.context.preferences.filepaths.use_scripts_auto_execute = True
    bpy.ops.mesh.primitive_cube_add()
    c = bpy.context.object
    c["k"] = prop
    fc = c.driver_add("location", 0)
    d = fc.driver; d.type='SCRIPTED'; d.expression=expr
    v = d.variables.new(); v.name=var; v.type='SINGLE_PROP'; v.targets[0].id=c; v.targets[0].data_path='["k"]'
    bpy.context.view_layer.update()
    return c.location.x, fc.evaluate(1.0), d.is_simple_expression, d.is_valid

for expr in ("k", "k*1.25", "k*2", "k+1", "sin(k)"):
    print(expr, "->", cube_driver(expr), flush=True)
print("with autoexec:", cube_driver("k*1.25", enable_scripts=True), flush=True)
# named variable other than k
print("var c:", cube_driver("c*2", var="c"), flush=True)
