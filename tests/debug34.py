import sys
sys.path.insert(0,'/home/user')
import bpy
from mathutils import Vector

def run(use_tail, chain, target_head=(0,0.4,0.1), target_tail=(0,0.4,0.5), pole=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ad=bpy.data.armatures.new("A"); arm=bpy.data.objects.new("A",ad); bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active=arm
    bpy.ops.object.mode_set(mode='EDIT')
    e1=ad.edit_bones.new("thigh"); e1.head=(0,0,1.0); e1.tail=(0,0.05,0.55)
    e2=ad.edit_bones.new("shin"); e2.head=(0,0.05,0.55); e2.tail=(0,0,0.1); e2.parent=e1; e2.use_connect=True
    e3=ad.edit_bones.new("ctl"); e3.head=target_head; e3.tail=target_tail
    p=None
    if pole:
        e4=ad.edit_bones.new("pole"); e4.head=(0,-0.5,0.55); e4.tail=(0,-0.6,0.55); p="pole"
    bpy.ops.object.mode_set(mode='OBJECT')
    c=arm.pose.bones["shin"].constraints.new('IK'); c.target=arm; c.subtarget="ctl"; c.chain_count=chain; c.use_tail=use_tail
    if pole:
        c.pole_target=arm; c.pole_subtarget=p
    bpy.context.view_layer.update()
    knee=arm.pose.bones["thigh"].tail; tip=arm.pose.bones["shin"].tail
    print(f"tail={use_tail} chain={chain} pole={pole}: knee={tuple(round(v,3) for v in knee)} tip={tuple(round(v,3) for v in tip)} dist_to_head={round((tip-Vector(target_head)).length,3)} dist_to_tail={round((tip-Vector(target_tail)).length,3)}", flush=True)

run(False,2)
run(True,2)
run(False,0)
run(True,0)
run(False,2,pole=True)
run(True,2,pole=True)
