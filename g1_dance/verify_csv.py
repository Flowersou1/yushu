# -*- coding: utf-8 -*-
"""校验 test.csv 关键帧: 抱架/左拳峰/右拳峰 的左右手坐标 + 腰yaw。确定性判动作。"""
import os, sys, numpy as np, mujoco
WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
CSV = sys.argv[1] if len(sys.argv)>1 else os.path.join(WS,'g1_dance','test.csv')
model = mujoco.MjModel.from_xml_path(os.path.join(WS, 'g1', 'scene_29dof.xml'))
data = mujoco.MjData(model)
def bn(i): return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
def bid(n): return next(i for i in range(model.nbody) if bn(i)==n)
LH=bid('left_wrist_yaw_link'); RH=bid('right_wrist_yaw_link')
LSH=bid('left_shoulder_pitch_link'); RSH=bid('right_shoulder_pitch_link')
arr = np.loadtxt(CSV, delimiter=',')
n=arr.shape[0]
def at(t): return min(int(t*50), n-1)   # 50fps
def show(t, name):
    f=at(t); row=arr[f]
    mujoco.mj_resetData(model,data); data.qpos[0:3]=row[0:3]; q=row[3:7]; data.qpos[3:7]=[q[3],q[0],q[1],q[2]]; data.qpos[7:36]=row[7:36]
    mujoco.mj_forward(model,data)
    lh,rh=data.xpos[LH],data.xpos[RH]; lx,rx=data.xpos[LSH][0],data.xpos[RSH][0]
    print(f"[{name} t={t:.1f}s 帧{f}] 左拳=({lh[0]:+.2f},{lh[1]:+.2f},{lh[2]:+.2f}) 右拳=({rh[0]:+.2f},{rh[1]:+.2f},{rh[2]:+.2f}) 腰yaw={row[19]:+.2f} 左肩x={lx:+.2f} 右肩x={rx:+.2f}")
print("csv:", os.path.basename(CSV), "帧数:", n)
show(0.5, "抱架")
show(1.4, "左直拳峰")
show(2.5, "右直拳峰")
print("\n判定: 左拳峰 左拳x≈+0.26且肘近伸直; 右拳峰 右拳x≈+0.26; 腰yaw左拳时应为负(左肩x>右肩x)。")
