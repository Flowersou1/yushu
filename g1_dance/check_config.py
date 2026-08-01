# -*- coding: utf-8 -*-
"""按用户规范核算直拳配置(纯运动学, 不靠看图):
1) 抱架拳位置(胸口/下巴, 肘弯) 2) 出拳末端(前方水平, 肘留~10°不锁死)
3) 抱架->出拳轨迹是否向前不向上 4) 腰yaw转向哪边(确定左/右冲拳的腰转符号)"""
import os, numpy as np, mujoco
WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
model = mujoco.MjModel.from_xml_path(os.path.join(WS, 'g1', 'scene_29dof.xml'))
data = mujoco.MjData(model)
def bn(i): return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
def bid(n): return next(i for i in range(model.nbody) if bn(i)==n)
LH=bid('left_wrist_yaw_link'); RH=bid('right_wrist_yaw_link')
LSH=bid('left_shoulder_pitch_link'); RSH=bid('right_shoulder_pitch_link')

LEG=[-0.312,0,0,0.669,-0.363,0]
SP=-0.74
def set_all(waist_yaw, aL, aR):
    mujoco.mj_resetData(model, data)
    data.qpos[0:3]=[0,0,0.76]; data.qpos[3:7]=[1,0,0,0]
    data.qpos[7:36] = LEG+LEG+[waist_yaw,0,0]+aL+aR
    mujoco.mj_forward(model, data)

GL=[SP,0.3,0,-1.8,0,0,0]; GR=[SP,-0.3,0,-1.8,0,0,0]
print("== 1) 抱架 (腰0) ==")
set_all(0, GL, GR)
print(f"  左拳={data.xpos[LH]} 右拳={data.xpos[RH]}")

print("\n== 2) 出拳末端 (肩pitch=-0.74, 肘留~10°=-0.18, 不锁死) ==")
for eb in [0.0, -0.10, -0.18, -0.26]:
    P=[SP,0,0,eb,0,0,0]
    set_all(0, P, GR)
    h=data.xpos[LH]
    print(f"  elbow={eb:+.2f}({np.degrees(abs(eb)):.0f}°弯) 左拳=({h[0]:+.2f},{h[1]:+.2f},{h[2]:+.2f})")

print("\n== 3) 抱架->出拳 轨迹 (看是否向前不向上) ==")
P=[SP,0,0,-0.18,0,0,0]
for a in np.linspace(0,1,6):
    aL=[GL[k]+(P[k]-GL[k])*a for k in range(7)]
    set_all(0, aL, GR)
    h=data.xpos[LH]
    print(f"  {a:.1f}: 左拳=({h[0]:+.2f},{h[1]:+.2f},{h[2]:+.2f})")

print("\n== 4) 腰yaw方向 (哪个符号让左肩靠前=x更大) ==")
for wy in [-0.3, 0.0, 0.3]:
    set_all(wy, GL, GR)
    lx, rx = data.xpos[LSH][0], data.xpos[RSH][0]
    print(f"  waist_yaw={wy:+.2f}({np.degrees(wy):+.0f}°): 左肩x={lx:+.3f} 右肩x={rx:+.3f}  {'左肩更前' if lx>rx else '右肩更前'}")
