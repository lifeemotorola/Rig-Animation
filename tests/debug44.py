import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions

bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
R = rigmod.Rig(arm)
d = [x for x in arm.animation_data.drivers if "f_middle_01.L" in x.data_path]
for x in d:
    print("path", x.data_path, "idx", x.array_index, "expr", x.driver.expression, "valid", x.driver.is_valid, "simple", x.driver.is_simple_expression, flush=True)
    print("   vars", [(v.name, v.type, v.targets[0].id, v.targets[0].data_path) for v in x.driver.variables], flush=True)
R.set_prop("finger_curl.L", 1.0)
bpy.context.view_layer.update()
for x in d:
    print("   evaluate(1):", x.evaluate(1.0), flush=True)
print("root prop:", arm.pose.bones["root"]["finger_curl.L"], flush=True)
ev = arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
print("evaluated euler:", tuple(round(v,3) for v in ev.pose.bones["f_middle_01.L"].rotation_euler), flush=True)
print("orig euler:", tuple(round(v,3) for v in arm.pose.bones["f_middle_01.L"].rotation_euler), flush=True)
print("ev rot mode:", ev.pose.bones["f_middle_01.L"].rotation_mode, "orig:", arm.pose.bones["f_middle_01.L"].rotation_mode, flush=True)
print("ev shape tip:", tuple(round(v,3) for v in ev.pose.bones["f_middle_03.L"].tail), flush=True)
