import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
ad = bpy.data.armatures.new("A"); arm = bpy.data.objects.new("A", ad)
bpy.context.collection.objects.link(arm); bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = ad.edit_bones.new("b"); eb.head=(0,0,0); eb.tail=(0,0,1)
bpy.ops.object.mode_set(mode='OBJECT')
pb = arm.pose.bones["b"]; pb.rotation_mode='XYZ'
arm["curl"] = 0.0
fc = pb.driver_add("rotation_euler", 0)
d = fc.driver; d.type='SCRIPTED'; d.expression='curl*1.5'
v = d.variables.new(); v.name='curl'; v.type='SINGLE_PROP'; v.targets[0].id=arm; v.targets[0].data_path='["curl"]'
bpy.context.view_layer.update()
def show(tag):
    bpy.context.view_layer.update()
    ev = arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
    e = ev.pose.bones['b']
    print(tag, "euler", tuple(round(x,3) for x in e.rotation_euler), "matrix Y col", tuple(round(x,3) for x in e.matrix.col[1][:3]), flush=True)
show("curl=0")
arm["curl"]=1.0
show("curl=1")
# now compare with keyframes
pb2 = arm.pose.bones["b"]
pb2.rotation_mode='XYZ'
arm.animation_data_create()
act = bpy.data.actions.new("T"); arm.animation_data.action = act
pb2.rotation_euler=(0.4,0,0); pb2.keyframe_insert("rotation_euler", frame=1)
bpy.context.scene.frame_set(1)
show("keyframed 0.4")
# driver still present? print channels
print("drivers:", [(x.data_path, x.array_index) for x in arm.animation_data.drivers], flush=True)
