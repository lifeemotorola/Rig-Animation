import sys, math
sys.path.insert(0,'/home/user')
import bpy
from mathutils import Vector

def make(prebend_deg, chain=2, limits=True):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ad=bpy.data.armatures.new("A"); arm=bpy.data.objects.new("A",ad); bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active=arm
    bpy.ops.object.mode_set(mode='EDIT')
    e_cog=ad.edit_bones.new("cog"); e_cog.head=(0,0,0.88); e_cog.tail=(0,0,1.0)
    e_pel=ad.edit_bones.new("pelvis"); e_pel.head=(0,0.013,0.899); e_pel.tail=(0,0.01,1.108); e_pel.parent=e_cog
    hip=(0.13,0.007,0.885); knee=(0.12,-0.03,0.48); ankle=(0.114,0.017,0.08)
    # apply prebend: push knee forward by angle
    kp = Vector(knee); kp.y -= math.radians(prebend_deg)*0.24
    e_th=ad.edit_bones.new("thigh"); e_th.head=hip; e_th.tail=kp; e_th.parent=e_pel
    e_sh=ad.edit_bones.new("shin"); e_sh.head=kp; e_sh.tail=ankle; e_sh.parent=e_th; e_sh.use_connect=True
    e_ctl=ad.edit_bones.new("ctl"); e_ctl.head=ankle; e_ctl.tail=(0.114,-0.08,0.03)
    bpy.ops.object.mode_set(mode='OBJECT')
    c=arm.pose.bones["shin"].constraints.new('IK'); c.target=arm; c.subtarget="ctl"; c.chain_count=chain; c.use_stretch=True
    if limits:
        for bn,rng in (("thigh",(-1.9,0.9)),("shin",(0.02,2.35))):
            pb=arm.pose.bones[bn]; pb.use_ik_limit_x=True; pb.ik_min_x, pb.ik_max_x = rng
    bpy.context.view_layer.update()
    pel=arm.pose.bones["pelvis"]
    e=(arm.data.bones["pelvis"].matrix_local.inverted() @ pel.matrix).to_euler()
    return arm, tuple(round(v,5) for v in e), tuple(round(v,4) for v in arm.pose.bones["shin"].head)

for pb_deg in (0, 5, 8.9, 20):
    arm,e,shin = make(pb_deg)
    print(f"prebend={pb_deg} pelvis_delta={e} shin_head={shin}", flush=True)
