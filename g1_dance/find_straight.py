# -*- coding: utf-8 -*-
"""彻底查清: 哪个 elbow 值让手臂真正伸直(拳离肩最远 + 内角接近180°)。
固定 shoulder_pitch=-0.70(出拳位), 扫 elbow, 打印 拳位/拳到肩距离/肘内角。"""
import os, numpy as np, mujoco
WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
model = mujoco.MjModel.from_xml_path(os.path.join(WS, 'g1', 'scene_29dof.xml'))
data = mujoco.MjData(model)
def bn(i): return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
def bid(n): return next(i for i in range(model.nbody) if bn(i)==n)
def jid(n): return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n)
BSH=bid('left_shoulder_pitch_link'); BWR=bid('left_wrist_yaw_link'); JEL=jid('left_elbow_joint')
LEG=[-0.312,0,0,0.669,-0.363,0]

def meas(eb, sp=-0.70, roll=0.15):
    mujoco.mj_resetData(model,data); data.qpos[0:3]=[0,0,0.76]; data.qpos[3:7]=[1,0,0,0]
    data.qpos[7:36]=LEG+LEG+[0,0,0]+[sp,roll,0,eb,0,0,0]+[0.4,-0.3,0,-1.0,0,0,0]
    mujoco.mj_forward(model,data)
    sh=data.xpos[BSH]; el=data.xanchor[JEL]; wr=data.xpos[BWR]
    interior=np.degrees(np.arccos(np.clip(np.dot(sh-el, wr-el)/(np.linalg.norm(sh-el)*np.linalg.norm(wr-el)+1e-9),-1,1)))
    return wr.copy(), np.linalg.norm(wr-sh), interior

print("shoulder_pitch=-0.70, 扫 elbow (找拳离肩最远=最直):")
print("  elbow   拳(x,y,z)              拳到肩距离  肘内角(180=直)")
best=(0,-1);
for eb in np.arange(-1.5, 1.6, 0.25):
    h,d,ang=meas(eb)
    if d>best[0]: best=(d,eb)
    print(f"  {eb:+.2f}  ({h[0]:+.2f},{h[1]:+.2f},{h[2]:+.2f})  {d:.3f}      {ang:.0f}°")
print(f"\n最直(拳离肩最远 {best[0]:.3f}m) 的 elbow = {best[1]:+.2f}")
print("\n也测一下 elbow 全正值范围(可能伸直方向在正):")
for eb in [0.5,1.0,1.5,2.0]:
    h,d,ang=meas(eb)
    print(f"  {eb:+.2f}  ({h[0]:+.2f},{h[1]:+.2f},{h[2]:+.2f})  距离{d:.3f}  内角{ang:.0f}°")
