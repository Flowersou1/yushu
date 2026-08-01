# -*- coding: utf-8 -*-
"""搜不穿模的抱架配置: 双臂对称设为候选抱架, 查手臂自穿模(肩link vs 腕link)。
找出: 无穿模 + 拳在胸口高度z[1.0,1.15] + 拳在身侧y>=0.14 的配置。"""
import os, numpy as np, mujoco
WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
model = mujoco.MjModel.from_xml_path(os.path.join(WS, 'g1', 'scene_29dof.xml'))
data = mujoco.MjData(model)
def bn(i): return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
LH=next(i for i in range(model.nbody) if bn(i)=='left_wrist_yaw_link')
def bog(gid): return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, model.geom_bodyid[gid])
def is_uparm(n):  # 上臂(肩部)link
    nl=n.lower(); return ('shoulder' in nl) and ('wrist' not in nl)
def is_farm(n):   # 前臂/腕/手 link
    nl=n.lower(); return ('wrist' in nl) or ('forearm' in nl) or ('hand' in nl)

LEG=[-0.312,0,0,0.669,-0.363,0]
def test(sp, roll, eb):
    aL=[sp, roll, 0, eb, 0,0,0]; aR=[sp, -roll, 0, eb, 0,0,0]
    mujoco.mj_resetData(model,data); data.qpos[0:3]=[0,0,0.76]; data.qpos[3:7]=[1,0,0,0]
    data.qpos[7:36]=LEG+LEG+[0,0,0]+aL+aR
    mujoco.mj_forward(model,data)
    worst=0.0
    for c in range(data.ncon):
        con=data.contact[c]
        if con.dist>=0: continue
        b1,b2=bog(con.geom1),bog(con.geom2)
        if (is_uparm(b1) and is_farm(b2)) or (is_farm(b1) and is_uparm(b2)):
            worst=min(worst, con.dist)
    return data.xpos[LH].copy(), worst*1000  # mm

print("无穿模(worst>-1mm)且拳在胸口两侧的抱架候选:")
print("  sp     roll  elbow   左拳(x,y,z)            穿模mm")
found=[]
for sp in [-0.74,-0.6,-0.5,-0.4,-0.3,0.3,0.5]:
    for roll in [0.3,0.5,0.7,0.9]:
        for eb in [-1.6,-1.3,-1.0,-0.7]:
            h,w=test(sp,roll,eb)
            if w>-1.0 and 1.0<=h[2]<=1.16 and h[1]>=0.13:
                found.append((sp,roll,eb,h,w))
for sp,roll,eb,h,w in found:
    print(f"  {sp:+.2f}  {roll:.1f}  {eb:+.2f}  ({h[0]:+.2f},{h[1]:+.2f},{h[2]:+.2f})  {w:+.1f}")
print("候选数:", len(found))
