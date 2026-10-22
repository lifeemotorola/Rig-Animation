import bpy
def out(*a): print(" ".join(str(x) for x in a), flush=True)
sc=bpy.context.scene
ad=bpy.data.armatures.new("A"); arm=bpy.data.objects.new("A",ad); sc.collection.objects.link(arm)
bpy.context.view_layer.objects.active=arm
bpy.ops.object.mode_set(mode='EDIT'); eb=ad.edit_bones.new("root"); eb.head=(0,0,0); eb.tail=(0,1,0)
bpy.ops.object.mode_set(mode='OBJECT')
arm.animation_data_create()
act=bpy.data.actions.new("Empty")
arm.animation_data.action=act
out("empty slots:", len(act.slots), "layers:", len(act.layers))
slot=act.slots.new(id_type='OBJECT', name=arm.name)
out("slot:", slot.identifier)
try:
    layer=act.layers.new("Base"); out("layer ok", layer.name)
    strip=layer.strips.new(type='KEYFRAME'); out("strip ok", strip.type, hasattr(strip,'channelbag'))
    cb=strip.channelbag(slot, ensure=True); out("channelbag ok", cb is not None)
    fc=cb.fcurves.new('pose.bones["root"]["ik_arm.L"]'); out("fcurve customprop ok", fc.data_path)
    fc2=cb.fcurves.new('pose.bones["root"].location', index=1); out("fcurve array ok", fc2.array_index)
except Exception as e:
    out("direct creation err", repr(e))
# assign slot then key nla
arm.animation_data.action_slot=slot
arm.pose.bones["root"]["ik_arm.L"]=0.5
try:
    arm.pose.bones["root"].keyframe_insert('["ik_arm.L"]', frame=1)
    out("key custom prop ok")
except Exception as e:
    out("key custom prop err", repr(e))
arm.pose.bones["root"].location=(0,0.5,0)
bpy.ops.object.mode_set(mode='POSE')
arm.pose.bones["root"].keyframe_insert('location',frame=1)
bpy.ops.object.mode_set(mode='OBJECT')
out("slot count now:", len(act.slots), [(s.identifier) for s in act.slots])
# NLA with explicit slot
tr=arm.animation_data.nla_tracks.new(); tr.name="APEX Test"
st=tr.strips.new("Breathing", 1, act)
out("strip created:", st.name, "slot:", st.action_slot.identifier if st.action_slot else None)
try:
    st.action_slot=act.slots[0]; out("slot assigned:", st.action_slot.identifier)
except Exception as e: out("slot assign err", repr(e))
st.blend_type='ADD'; st.use_animated_influence=False
tr.mute=True
out("nla ok tracks:", [t.name for t in arm.animation_data.nla_tracks])
# check evaluated action via cb
layer=act.layers[0]; strip=layer.strips[0]; cb=strip.channelbag(act.slots[0])
out("fcurves:", [(f.data_path, f.array_index, len(f.keyframe_points)) for f in cb.fcurves])
# driver on pose bone custom prop -> is it animatable? drivers read prop value
out("prop value", arm.pose.bones["root"]["ik_arm.L"])
# fcurve groups?
out("cb attrs:", [a for a in dir(cb) if a in ('fcurves','groups','clear','channelbag','channelbags')])
# check action.frame_range with slot set
out("frame_range:", tuple(act.frame_range))
