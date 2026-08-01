# -*- coding: utf-8 -*-
"""确认 MuJoCo 能否检测'手臂穿胸': 1)看 contype/conaffinity 2)故意把手塞进胸口看报不报。"""
import os, numpy as np, mujoco
WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
model = mujoco.MjModel.from_xml_path(os.path.join(WS, 'g1', 'scene_29dof.xml'))
data = mujoco.MjData(model)
def bn(i): return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
def bog(gid): return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, model.geom_bodyid[gid])

print("geom总数:", model.ngeom)

# 故意: 左臂横抱塞进胸口 (shoulder_roll 大, elbow 弯, 手往身前中线塞)
LEG=[-0.312,0,0,0.669,-0.363,0]
mujoco.mj_resetData(model,data); data.qpos[0:3]=[0,0,0.76]; data.qpos[3:7]=[1,0,0,0]
# 左臂: 肩前屈0, 外展1.2(横举), 肘弯-1.5 -> 把手塞向胸口前方
data.qpos[7:36]=LEG+LEG+[0,0,0]+[0.0,1.2,0.0,-1.5,0,0,0]+[-0.74,-0.3,0,-1.0,0,0,0]
mujoco.mj_forward(model,data)
LH=next(i for i in range(model.nbody) if bn(i)=='left_wrist_yaw_link')
print(f"\n故意穿胸姿势: 左手={data.xpos[LH]} (若x小y近0, 手在胸口)")
print(f"  ncon={data.ncon}")
chest_hits=0
for c in range(data.ncon):
    con=data.contact[c]; b1=bog(con.geom1); b2=bog(con.geom2)
    if con.dist<0:
        print(f"    穿透 {con.dist*1000:.1f}mm: {b1} <-> {b2}")
        if ('torso' in (b1+b2).lower() or 'chest' in (b1+b2).lower() or 'spine' in (b1+b2).lower()):
            chest_hits+=1
print(f"  含躯干/胸的穿透: {chest_hits} 处", "-> 说明能检测穿胸" if chest_hits>0 else "-> ⚠️检测不到穿胸(被过滤), 需几何复核")
