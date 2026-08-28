# -*- coding: utf-8 -*-
"""逐帧检测 CSV 的穿模: 用 MuJoCo 碰撞检测。
用法: python check_clip.py [csv路径]
默认: g1_dance/test.csv
"""
import os, sys, numpy as np, mujoco
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(HERE)
MODEL = os.path.join(WS, 'g1', 'scene_29dof.xml')
CSV = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'test.csv')

model = mujoco.MjModel.from_xml_path(MODEL)
data = mujoco.MjData(model)

print("disableflags=", model.opt.disableflags, "mjDSBL_CONTACT bit=", int(mujoco.mjtDisableBit.mjDSBL_CONTACT))
print("nexclude(显式排除对)=", model.nexclude)

def body_of_geom(gid):
    return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, model.geom_bodyid[gid])

arr = np.loadtxt(CSV, delimiter=',')
pairs = defaultdict(lambda: [0, 9e9])
print("csv:", os.path.basename(CSV), "frames:", len(arr))
print("\n扫描每帧 (报告所有穿透对, 不限手臂):")
for f in range(0, len(arr)):
    row = arr[f]
    mujoco.mj_resetData(model, data)
    data.qpos[0:3] = row[0:3]; q = row[3:7]; data.qpos[3:7] = [q[3], q[0], q[1], q[2]]; data.qpos[7:36] = row[7:36]
    mujoco.mj_forward(model, data)
    for c in range(data.ncon):
        con = data.contact[c]
        if con.dist >= -0.0005:
            continue
        b1, b2 = body_of_geom(con.geom1), body_of_geom(con.geom2)
        key = tuple(sorted([b1, b2]))
        pairs[key][0] += 1; pairs[key][1] = min(pairs[key][1], con.dist)
if not pairs:
    print("  [OK] 没检测到任何穿模")
else:
    print(f"  共 {len(pairs)} 种穿透对 (按最严重排序):")
    for (b1, b2), (cnt, depth) in sorted(pairs.items(), key=lambda x: x[1][1]):
        print(f"   {b1}  <->  {b2}   {cnt}次  最深{depth*1000:.1f}mm")
