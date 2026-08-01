# -*- coding: utf-8 -*-
"""找最"平直"的冲拳轨迹: 抱架->出拳, 要求 拳z波动小(不抬)、向前Δx大。
扫几个 (出拳shoulder_pitch) 组合, 报告 z范围 和 Δx。"""
import os, numpy as np, mujoco
WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
model = mujoco.MjModel.from_xml_path(os.path.join(WS,'g1','scene_29dof.xml'))
data = mujoco.MjData(model)
def bn(i): return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
LH=next(i for i in range(model.nbody) if bn(i)=='left_wrist_yaw_link')
LEG=[-0.312,0,0,0.669,-0.363,0]
def fist(sp,roll,eb):
    mujoco.mj_resetData(model,data); data.qpos[0:3]=[0,0,0.76]; data.qpos[3:7]=[1,0,0,0]
    data.qpos[7:36]=LEG+LEG+[0,0,0]+[sp,roll,0,eb,0,0,0]+[-0.74,-0.3,0,-1.8,0,0,0]
    mujoco.mj_forward(model,data); return data.xpos[LH].copy()

GL=[-0.74,0.3,0,-1.8]  # 抱架(左): sp,roll,yaw,eb
print("(抱架 sp=-0.74, eb=-1.8) -> 出拳, 扫出拳 shoulder_pitch:")
for psp in [-0.74,-0.60,-0.50,-0.40]:
    P=[psp,0.0,0,-0.18]
    zs=[]; xs=[]
    for a in np.linspace(0,1,6):
        cfg=[GL[k]+(P[k]-GL[k])*a for k in range(4)]
        h=fist(cfg[0],cfg[1],cfg[3]); xs.append(h[0]); zs.append(h[2])
    zr=max(zs)-min(zs); print(f"  出拳sp={psp:+.2f}: Δx={xs[-1]-xs[0]:+.2f} z范围=[{min(zs):.2f},{max(zs):.2f}] 波动={zr:.2f}  起末z=({zs[0]:.2f}->{zs[-1]:.2f})")
