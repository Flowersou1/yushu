# -*- coding: utf-8 -*-
"""肘关节诊断:
1) 当前 test.csv 各关键帧的 左肘关节指令值 + 几何肘角(上臂vs前臂夹角, 180=直)
2) "大臂朝下"护架(shoulder_pitch=+0.4)能容许多深的肘弯而不穿模"""
import os, numpy as np, mujoco
WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
model = mujoco.MjModel.from_xml_path(os.path.join(WS, 'g1', 'scene_29dof.xml'))
data = mujoco.MjData(model)
def bn(i): return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
def bid(n): return next(i for i in range(model.nbody) if bn(i)==n)
def jid(n): return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n)
BSH=bid('left_shoulder_pitch_link'); BWR=bid('left_wrist_yaw_link')
JEL=jid('left_elbow_joint')

def geom_elbow_deg():
    sh=data.xpos[BSH]; el=data.xanchor[JEL]; wr=data.xpos[BWR]
    v1=el-sh; v2=wr-el
    c=np.dot(v1,v2)/(np.linalg.norm(v1)*np.linalg.norm(v2)+1e-9)
    return np.degrees(np.arccos(np.clip(c,-1,1)))

print("== 1) 当前 test.csv 肘诊断 (左臂) ==")
arr=np.loadtxt(os.path.join(WS,'g1_dance','test.csv'), delimiter=',')
print("  帧   t     肘指令值   几何肘角(180=直)")
for f in [25, 45, 57, 70, 85, 100, 124]:
    row=arr[f]
    mujoco.mj_resetData(model,data); data.qpos[0:3]=row[0:3]; q=row[3:7]; data.qpos[3:7]=[q[3],q[0],q[1],q[2]]; data.qpos[7:36]=row[7:36]
    mujoco.mj_forward(model,data)
    print(f"  {f:3d}  {f/50:.2f}s  {row[25]:+.3f}     {geom_elbow_deg():.0f}°")

print("\n== 2) 大臂朝下护架(shoulder_pitch=+0.4, roll=0.3) 扫肘弯深度, 查穿模 ==")
LEG=[-0.312,0,0,0.669,-0.363,0]
print("  elbow   几何肘角   拳(x,y,z)            最深穿模mm")
for eb in [-1.0,-1.3,-1.5,-1.8,-2.0,-2.3]:
    aL=[0.4,0.3,0,eb,0,0,0]; aR=[0.4,-0.3,0,eb,0,0,0]
    mujoco.mj_resetData(model,data); data.qpos[0:3]=[0,0,0.76]; data.qpos[3:7]=[1,0,0,0]
    data.qpos[7:36]=LEG+LEG+[0,0,0]+aL+aR; mujoco.mj_forward(model,data)
    w=0.0
    for c in range(data.ncon):
        if data.contact[c].dist<0: w=min(w,data.contact[c].dist)
    print(f"  {eb:+.2f}  {geom_elbow_deg():.0f}°     ({data.xpos[BWR][0]:+.2f},{data.xpos[BWR][1]:+.2f},{data.xpos[BWR][2]:+.2f})  {w*1000:+.1f}")
