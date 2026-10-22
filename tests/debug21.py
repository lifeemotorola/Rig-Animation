import sys
sys.path.insert(0,'/home/user')
import bpy
from mathutils import Vector

def make(limits=False, locks=False, target_at_rest=True, prebend=0.0, chain=2):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ad=bpy.data.armatures.new("A"); arm=bpy.data.objects.new("A",ad); bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active=arm
    bpy.ops.object.mode_set(mode='EDIT')
    e_cog=ad.edit_bones.new("cog"); e_cog.head=(0,0,0.88); e_cog.tail=(0,0,1.0)
    e_pel=ad.edit_bones.new("pelvis"); e_pel.head=(0,0.013,0.899); e_pel.tail=(0,0.01,1.108); e_pel.parent=e_cog
    e_th=ad.edit_bones.new("thigh"); e_th.head=(0.13,0.007,0.885); e_th.tail=(0.12,-0.03+prebend,0.48); e_th.parent=e_pel
    e_sh=ad.edit_bones.new("shin"); e_sh.head=(0.12,-0.03+prebend,0.48); e_sh.tail=(0.114,0.017,0.08); e_sh.parent=e_th; e_sh.use_connect=True
    e_ctl=ad.edit_bones.new("ctl"); e_ctl.head=(0.114,0.017,0.08); e_ctl.tail=(0.114,-0.08,0.03)
    bpy.ops.object.mode_set(mode='OBJECT')
    c=arm.pose.bones["shin"].constraints.new('IK'); c.target=arm; c.subtarget="ctl"; c.chain_count=chain; c.use_stretch=True
    if limits:
        for bn,rng in (("thigh",(-1.9,0.9)),("shin",(0.02,2.35))):
            pb=arm.pose.bones[bn]; pb.use_ik_limit_x=True; pb.ik_min_x, pb.ik_max_x = rng
            pb.use_ik_limit_y=True; pb.ik_min_y, pb.ik_max_y = -0.06,0.06
            pb.use_ik_limit_z=True; pb.ik_min_z, pb.ik_max_z = -0.06,0.06
    if locks:
        for bn in ("thigh",):
            pb=arm.pose.bones[bn]; pb.lock_ik_x=pb.lock_ik_y=pb.lock_ik_z=True
    bpy.context.view_layer.update()
    pel=arm.pose.bones["pelvis"]
    e=(arm.data.bones["pelvis"].matrix_local.inverted() @ pel.matrix).to_euler()
    return arm, tuple(round(v,4) for v in e)

for limits in (False,True):
    for locks in (False,True):
        arm,e = make(limits=limits, locks=locks)
        print(f"limits={limits} locks={locks} pelvis_delta_eul={e} spine={tuple(round(v,3) for v in arm.pose.bones['shin'].head)}", flush=True)
