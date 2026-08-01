# -*- coding: utf-8 -*-
"""检查 抱架->冲拳 的左拳轨迹: 应主要沿 +x(前) 移动, z 几乎不变(直线前冲, 非弧形荡)。
对比旧(大臂甩) vs 新(大臂固定,只伸肘)。"""
import os, numpy as np, mujoco
WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
model = mujoco.MjModel.from_xml_path(os.path.join(WS, 'g1', 'scene_29dof.xml'))
data = mujoco.MjData(model)
def bname(i): return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
LH = next(i for i in range(model.nbody) if bname(i)=='left_wrist_yaw_link')

def left_fist(sp, roll, eb):
    mujoco.mj_resetData(model, data)
    data.qpos[0:3]=[0,0,0.76]; data.qpos[3:7]=[1,0,0,0]
    LEG=[-0.312,0,0,0.669,-0.363,0]
    q=LEG+LEG+[0,0,0]+[sp,roll,0,eb,0,0,0]+[0,0,0,0,0,0,0]
    data.qpos[7:36]=q
    mujoco.mj_forward(model, data)
    return data.xpos[LH].copy()

def traj(name, g, p, n=7):
    print(f"\n== {name} ==")
    print("  抱架g=", g, " 冲拳p=", p)
    pts=[]
    for i in range(n):
        a=i/(n-1)
        cfg=[g[k]+(p[k]-g[k])*a for k in range(4)]  # sp,roll,yaw(0),eb 线性插值
        pts.append(left_fist(cfg[0],cfg[1],cfg[3]))
    for i,pt in enumerate(pts):
        print(f"  {i} 左拳=({pt[0]:+.2f},{pt[1]:+.2f},{pt[2]:+.2f})")
    s,e=pts[0],pts[-1]
    dx,dy,dz=e[0]-s[0],e[1]-s[1],e[2]-s[2]
    zrange=max(p[2] for p in pts)-min(p[2] for p in pts)
    print(f"  位移 Δx={dx:+.2f}(前) Δy={dy:+.2f} Δz={dz:+.2f}  | z波动={zrange:.2f}(越小越直)")

# 旧(大臂甩): guard sp=+0.4 -> punch sp=-0.74
traj("旧(大臂甩, 像招手)", [0.4,0.3,0,-1.5], [-0.74,0.0,0,0.0])
# 新(大臂固定, 只伸肘): guard sp=-0.74 -> punch sp=-0.74
traj("新(大臂固定, 只弹肘)", [-0.74,0.3,0,-1.6], [-0.74,0.0,0,0.0])
