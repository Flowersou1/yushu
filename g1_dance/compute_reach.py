# -*- coding: utf-8 -*-
"""找"拳再往前送"的最佳出拳配置: 扫 shoulder_pitch/elbow/waist_yaw,
目标: 左拳 x 最大, 同时 z 在胸口[0.98,1.07], 肘留~5°弯。"""
import os, numpy as np, mujoco
WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
model = mujoco.MjModel.from_xml_path(os.path.join(WS, 'g1', 'scene_29dof.xml'))
data = mujoco.MjData(model)
def bn(i): return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
LH=next(i for i in range(model.nbody) if bn(i)=='left_wrist_yaw_link')
LEG=[-0.312,0,0,0.669,-0.363,0]
def lfist(sp, eb, wy):
    mujoco.mj_resetData(model,data); data.qpos[0:3]=[0,0,0.76]; data.qpos[3:7]=[1,0,0,0]
    data.qpos[7:36]=LEG+LEG+[wy,0,0]+[sp,0,0,eb,0,0,0]+[-0.74,-0.3,0,-1.8,0,0,0]
    mujoco.mj_forward(model,data); return data.xpos[LH].copy()

cands=[]
for sp in [-0.80,-0.74,-0.70,-0.66]:
    for eb in [-0.10,-0.05,0.0]:
        for wy in [-0.20,-0.30,-0.35]:
            h=lfist(sp,eb,wy)
            if 0.98<=h[2]<=1.07:   # 胸口高度
                cands.append((h[0], h[2], sp, eb, wy))
cands.sort(reverse=True)
print("左拳x最大(且z在胸口)的前8个组合:")
print("   拳x    拳z    shoulder_pitch  elbow  waist_yaw")
for x,z,sp,eb,wy in cands[:8]:
    print(f"   {x:+.3f}  {z:.3f}    sp={sp:+.2f}       eb={eb:+.2f}({np.degrees(abs(eb)):.0f}°) wy={wy:+.2f}({np.degrees(wy):.0f}°)")
