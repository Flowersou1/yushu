# -*- coding: utf-8 -*-
"""用运动学直接算手在世界坐标里的精确位置(不靠看图)。
判断肩肘角度是否真的让手伸到身体正前方/伸直。"""
import os, numpy as np, mujoco

WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
XML = os.path.join(WS, 'g1', 'scene_29dof.xml')
model = mujoco.MjModel.from_xml_path(XML)
data = mujoco.MjData(model)

# 找手/手腕/手掌相关的 body
print("== 含 hand/palm/wrist/forearm 的 body ==")
cands = []
for i in range(model.nbody):
    name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
    low = name.lower()
    if any(k in low for k in ('hand', 'palm', 'wrist', 'forearm')):
        cands.append((i, name))
        print(f"  body[{i}] = {name}")
# site 也找一下
print("== 含 hand/palm 的 site ==")
for i in range(model.nsite):
    name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_SITE, i)
    if name and any(k in name.lower() for k in ('hand', 'palm')):
        print(f"  site[{i}] = {name}")

# 关节名对照
print("\n== 关节顺序(执行器/自由度) ==")
for i in range(model.njnt):
    print(f"  jnt[{i}] = {mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i)}")

# 复用测试动作的三个关键姿势
LEG = [-0.312, 0.0, 0.0, 0.669, -0.363, 0.0]
W0 = [0.0, 0.0, 0.0]
def guard(sign): return [0.4, 0.3 * sign, 0.0, 1.5, 0.0, 0.0, 0.0]
def punch():     return [1.57, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
def pose(armL, armR): return LEG + LEG + W0 + armL + armR

POSES = {
    "抱架":   pose(guard(1), guard(-1)),
    "左冲拳": pose(punch(), guard(-1)),
    "右冲拳": pose(guard(1), punch()),
}

def set_pose(p):
    mujoco.mj_resetData(model, data)
    data.qpos[0:3] = [0.0, 0.0, 0.76]
    data.qpos[3:7] = [1.0, 0.0, 0.0, 0.0]   # wxyz identity
    data.qpos[7:36] = p
    mujoco.mj_forward(model, data)

# 选左右手 body(取名字含 left/l/right/r 的)
def find_hand(side):
    for i, name in cands:
        nl = name.lower()
        if side == 'L' and ('l_' in nl or 'left' in nl):
            return i, name
        if side == 'R' and ('r_' in nl or 'right' in nl):
            return i, name
    return None, None

li, lname = find_hand('L')
ri, rname = find_hand('R')
print(f"\n左手 body = {lname}  右手 body = {rname}")

print("\n== 各姿势下左右手世界坐标 (x前 y左 z上) ==")
for name, p in POSES.items():
    set_pose(p)
    lh = data.xpos[li] if li is not None else [0,0,0]
    rh = data.xpos[ri] if ri is not None else [0,0,0]
    # 肩膀位置参考(骨盆)
    pelvis = data.xpos[1]
    print(f"[{name}] 左手=({lh[0]:+.2f},{lh[1]:+.2f},{lh[2]:+.2f}) "
          f"右手=({rh[0]:+.2f},{rh[1]:+.2f},{rh[2]:+.2f}) "
          f"骨盆=({pelvis[0]:+.2f},{pelvis[1]:+.2f},{pelvis[2]:+.2f})")
