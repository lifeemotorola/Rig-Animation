import sys, math
sys.path.insert(0,'/home/user')
import bpy
from mathutils import Vector

def make(target_offset, prebend_deg=8.9, chain=2, lock=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ad=bpy.data.armatures.new("A"); arm=bpy.data.objects.new("A",ad); bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active=arm
    bpy.ops.object.mode_set(mode='EDIT')
    e_cog=ad.edit_bones.new("cog"); e_cog.head=(0,0,0.88); e_cog.tail=(0,0,1.0)
    e_pel=ad.edit_bones.new("pelvis"); e_pel.head=(0,0.013,0.899); e_pel.tail=(0,0.01,1.108); e_pel.parent=e_cog
    hip=Vector((0.13,0.007,0.885)); ankle=Vector((0.114,0.017,0.08))
    kp=Vector((0.12,-0.03,0.48)); kp.y -= math.radians(prebend_deg)*0.24
    e_th=ad.edit_bones.new("thigh"); e_th.head=hip; e_th.tail=kp; e_th.parent=e_pel
    e_sh=ad.edit_bones.new("shin"); e_sh.head=kp; e_sh.tail=ankle; e_sh.parent=e_th; e_sh.use_connect=True
    e_ctl=ad.edit_bones.new("ctl"); e_ctl.head=ankle+Vector(target_offset); e_ctl.tail=(0.114,-0.08,0.03)
    bpy.ops.object.mode_set(mode='OBJECT')
    c=arm.pose.bones["shin"].constraints.new('IK'); c.target=arm; c.subtarget="ctl"; c.chain_count=chain; c.use_stretch=True
    if lock:
        p=arm.pose.bones["thigh"]; p.lock_ik_x=p.lock_ik_y=p.lock_ik_z=True
    bpy.context.view_layer.update()
    pel=arm.pose.bones["pelvis"]
    e=(arm.data.bones["pelvis"].matrix_local.inverted() @ pel.matrix).to_euler()
    return tuple(round(v,4) for v in e), tuple(round(v,4) for v in arm.pose.bones["shin"].head)

for off in ((0,0,0),(0,0,0.02),(0.03,0,0),(0,0.05,0)):
    print("offset",off,"no lock:", make(off), "lock:", make(off, lock=True), flush=True)
