import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions

bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
R = rigmod.Rig(arm)
def val():
    bpy.context.view_layer.update()
    return round(arm.evaluated_get(bpy.context.evaluated_depsgraph_get()).pose.bones['f_ring_01.L'].rotation_euler.x,3)
print("existing driver value (curl=0):", val(), flush=True)
R.set_prop("finger_curl.L", 1.0)
print("existing driver value (curl=1):", val(), flush=True)
# fresh driver on object prop
arm["test_curl"] = 1.0
pb = arm.pose.bones["f_ring_02.L"]; pb.rotation_mode='XYZ'
fc = pb.driver_add("rotation_euler", 0); d=fc.driver; d.type='SCRIPTED'; d.expression='v*2'
v=d.variables.new(); v.name='v'; v.type='SINGLE_PROP'; v.targets[0].id=arm; v.targets[0].data_path='["test_curl"]'
bpy.context.view_layer.update()
print("fresh driver obj prop:", round(arm.evaluated_get(bpy.context.evaluated_depsgraph_get()).pose.bones['f_ring_02.L'].rotation_euler.x,3), flush=True)
# fresh driver reading pose bone prop
arm["test_curl2"] = 1.0
pb = arm.pose.bones["f_ring_03.L"]
fc = pb.driver_add("rotation_euler", 0); d=fc.driver; d.type='SCRIPTED'; d.expression='v*3'
v=d.variables.new(); v.name='v'; v.type='SINGLE_PROP'; v.targets[0].id=arm; v.targets[0].data_path='pose.bones["root"]["finger_curl.L"]'
R.set_prop("finger_curl.L", 1.0)
bpy.context.view_layer.update()
print("fresh driver pose prop:", round(arm.evaluated_get(bpy.context.evaluated_depsgraph_get()).pose.bones['f_ring_03.L'].rotation_euler.x,3), flush=True)
print("orig euler f_ring_01:", tuple(round(x,3) for x in arm.pose.bones['f_ring_01.L'].rotation_euler), flush=True)
print("drivers count:", len(arm.animation_data.drivers), flush=True)
for x in arm.animation_data.drivers:
    if "f_ring_01.L" in x.data_path:
        print("  ", x.data_path, x.array_index, x.driver.expression, x.driver.is_valid, [t.targets[0].data_path for t in x.driver.variables], flush=True)
