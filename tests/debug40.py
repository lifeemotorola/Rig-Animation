import sys
sys.path.insert(0,'/home/user')
import bpy
from surigandanim import rig as rigmod
from surigandanim.proportions import RigOptions

bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
R = rigmod.Rig(arm)
bpy.context.view_layer.update()
drv = list(arm.animation_data.drivers)
print("drivers:", len(drv), flush=True)
d0 = drv[0]
print("sample:", d0.data_path, "valid:", d0.driver.is_valid, "simple:", d0.driver.is_simple_expression, "expr:", d0.driver.expression, flush=True)
print("var target:", d0.driver.variables[0].targets[0].id, d0.driver.variables[0].targets[0].data_path, "id_type:", d0.driver.variables[0].targets[0].id_type, flush=True)
print("influence before:", arm.pose.bones["forearm.L"].constraints["APEX IK Arm"].influence, flush=True)
R.set_prop("ik_arm.L", 0.0)
bpy.context.view_layer.update()
print("influence after prop 0 + update:", arm.pose.bones["forearm.L"].constraints["APEX IK Arm"].influence, flush=True)
bpy.context.scene.frame_set(2)
print("influence after frame_set:", arm.pose.bones["forearm.L"].constraints["APEX IK Arm"].influence, flush=True)
f=[d for d in drv if 'f_middle_01.L' in d.data_path]
print("finger driver expr:", [x.driver.expression for x in f], "var path:", [x.driver.variables[0].targets[0].data_path for x in f], flush=True)
R.set_prop("finger_curl.L", 1.0)
bpy.context.scene.frame_set(3)
print("finger euler.x after curl:", arm.pose.bones["f_middle_01.L"].rotation_euler.x, flush=True)
print("props on root:", [k for k in arm.pose.bones["root"].keys()][:8], flush=True)
print("driver var target resolves:", d0.driver.variables[0].targets[0].id == arm, flush=True)
