# -*- coding: utf-8 -*-
"""逐帧检测 test.csv 的穿模: 用 MuJoCo 碰撞检测, 找手臂(肩/肘/腕/前臂/上臂)
与躯干(胸/腰/骨盆/脊) 或 另一条手臂 之间的穿透(dist<0)。"""
import os, numpy as np, mujoco
WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
model = mujoco.MjModel.from_xml_path(os.path.join(WS, 'g1', 'scene_29dof.xml'))
data = mujoco.MjData(model)

# 确保碰撞没被全局关掉
print("disableflags=", model.opt.disableflags, "mjDSBL_CONTACT bit=", int(mujoco.mjtDisableBit.mjDSBL_CONTACT))
print("nexclude(显式排除对)=", model.nexclude)

def body_of_geom(gid):
    return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, model.geom_bodyid[gid])
def is_arm(n):
    nl=n.lower(); return any(k in nl for k in ['shoulder','elbow','wrist','forearm','upperarm','upper_arm','hand'])
def is_torso(n):
    nl=n.lower(); return any(k in nl for k in ['torso','chest','waist','pelvis','spine','head','body'])

arr = np.loadtxt(os.path.join(WS,'g1_dance','test.csv'), delimiter=',')
from collections import defaultdict
pairs=defaultdict(lambda:[0, 9e9])   # (b1,b2) -> [count, worst_depth]
print("\n扫描每帧 (报告所有穿透对, 不限手臂):")
for f in range(0, len(arr)):
    row=arr[f]
    mujoco.mj_resetData(model, data)
    data.qpos[0:3]=row[0:3]; q=row[3:7]; data.qpos[3:7]=[q[3],q[0],q[1],q[2]]; data.qpos[7:36]=row[7:36]
    mujoco.mj_forward(model, data)
    for c in range(data.ncon):
        con=data.contact[c]
        if con.dist >= -0.0005:
            continue
        b1, b2 = body_of_geom(con.geom1), body_of_geom(con.geom2)
        key=tuple(sorted([b1,b2]))
        pairs[key][0]+=1; pairs[key][1]=min(pairs[key][1], con.dist)
if not pairs:
    print("  [OK] 没检测到任何穿模")
else:
    print(f"  共 {len(pairs)} 种穿透对 (按最严重排序):")
    for (b1,b2),(cnt,depth) in sorted(pairs.items(), key=lambda x:x[1][1]):
        print(f"   {b1}  <->  {b2}   {cnt}次  最深{depth*1000:.1f}mm")
