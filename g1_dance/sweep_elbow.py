# -*- coding: utf-8 -*-
"""扫描 elbow 正负方向。固定几个 shoulder_pitch, 扫 elbow, 打印左手位置。
目标: 找抱架配置(拳抬到下巴高度 z≈1.2, y≈+0.2)。"""
import os, numpy as np, mujoco
WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
model = mujoco.MjModel.from_xml_path(os.path.join(WS, 'g1', 'scene_29dof.xml'))
data = mujoco.MjData(model)
def bname(i): return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
hand_id = next(i for i in range(model.nbody) if bname(i)=='left_wrist_yaw_link')

def setLA(spitch, sroll, syaw, elbow):
    mujoco.mj_resetData(model, data)
    data.qpos[0:3]=[0,0,0.76]; data.qpos[3:7]=[1,0,0,0]
    LEG=[-0.312,0,0,0.669,-0.363,0]
    q=LEG+LEG+[0,0,0]+[spitch,sroll,syaw,elbow,0,0,0]+[0,0,0,0,0,0,0]
    data.qpos[7:36]=q
    mujoco.mj_forward(model, data)

print("== 在不同 shoulder_pitch 下扫描 elbow ==")
for sp in [-1.2, -0.74, -0.3, 0.4]:
    print(f"\n-- shoulder_pitch={sp:+.2f} --")
    for eb in np.arange(-1.6, 1.6+0.001, 0.8):
        setLA(sp, 0.0, 0.0, eb)
        h=data.xpos[hand_id]
        tag=""
        if 1.15<=h[2]<=1.32 and 0.10<=h[1]<=0.30 and -0.05<=h[0]<=0.20: tag="  <-- 接近抱架(拳在下巴)"
        print(f"   elbow={eb:+.2f}  左手=({h[0]:+.2f},{h[1]:+.2f},{h[2]:+.2f}){tag}")
