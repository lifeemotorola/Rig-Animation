import sys, math
sys.path.insert(0,'/home/user')
import bpy
from mathutils import Vector

def test(use_tail):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ad=bpy.data.armatures.new("A"); arm=bpy.data.objects.new("A",ad); bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active=arm
    bpy.ops.object.mode_set(mode='EDIT')
    e1=ad.edit_bones.new("thigh"); e1.head=(0,0,1.0); e1.tail=(0,0.05,0.55)
    e2=ad.edit_bones.new("shin"); e2.head=(0,0.05,0.55); e2.tail=(0,0,0.1); e2.parent=e1; e2.use_connect=True
    e3=ad.edit_bones.new("ctl"); e3.head=(0,0.4,0.1); e3.tail=(0,0.4,0.5)   # head A=(0,0.4,0.1), tail B=(0,0.4,0.5)
    bpy.ops.object.mode_set(mode='OBJECT')
    c=arm.pose.bones["shin"].constraints.new('IK'); c.target=arm; c.subtarget="ctl"; c.chain_count=2; c.use_tail=use_tail
    bpy.context.view_layer.update()
    tail = arm.pose.bones["shin"].tail
    print(f"use_tail={use_tail}: shin tail={tuple(round(v,3) for v in tail)}  (target head A=(0,0.4,0.1) tail B=(0,0.4,0.5))", flush=True)
    print("   thigh rot:", tuple(round(v,3) for v in arm.pose.bones['thigh'].rotation_quaternion), "shin rot:", tuple(round(v,3) for v in arm.pose.bones['shin'].rotation_quaternion), flush=True)

test(False)
test(True)
