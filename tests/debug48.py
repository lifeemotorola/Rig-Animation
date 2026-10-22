import bpy
def make():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ad = bpy.data.armatures.new("A"); arm = bpy.data.objects.new("A", ad)
    bpy.context.collection.objects.link(arm); bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = ad.edit_bones.new("b"); eb.head=(0,0,0); eb.tail=(0,0,1)
    bpy.ops.object.mode_set(mode='OBJECT')
    pb = arm.pose.bones["b"]; pb.rotation_mode='XYZ'
    arm["curl"] = 1.0
    fc = pb.driver_add("rotation_euler", 0)
    d = fc.driver; d.type='SCRIPTED'; d.expression='curl*1.5'
    v = d.variables.new(); v.name='curl'; v.type='SINGLE_PROP'; v.targets[0].id=arm; v.targets[0].data_path='["curl"]'
    bpy.context.view_layer.update()
    return arm, pb
def val(arm):
    bpy.context.view_layer.update()
    return round(arm.evaluated_get(bpy.context.evaluated_depsgraph_get()).pose.bones['b'].rotation_euler.x,3)

arm, pb = make()
print("no action, after update:", val(arm), flush=True)
bpy.context.scene.frame_set(1)
print("no action, after frame_set(1):", val(arm), flush=True)
arm.animation_data_create()
act = bpy.data.actions.new("Empty")
arm.animation_data.action = act
print("empty action:", val(arm), flush=True)
bpy.context.scene.frame_set(5)
print("empty action + frame_set:", val(arm), flush=True)
# now unassign action but keep animation_data
arm.animation_data.action = None
print("action removed again:", val(arm), flush=True)
