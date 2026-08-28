# -*- coding: utf-8 -*-
"""把任意 mjlab CSV 参考动作渲染成视频 + 关键帧PNG。
用法: python render_ref.py [csv路径] [输出mp4路径] [方位角azimuth] [每帧重复(>1=慢放)]
默认: test.csv -> test_ref.mp4, az=270(侧)。az=0为正面。"""
import os, sys, numpy as np, mujoco, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(HERE)
CSV = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'test.csv')
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'test_ref.mp4')
AZ = float(sys.argv[3]) if len(sys.argv) > 3 else 270.0
REPEAT = int(sys.argv[4]) if len(sys.argv) > 4 else 1
SNAPS = {0.16, 0.44, 0.78}   # 抱架/左拳峰/右拳峰 (3.2s)

model = mujoco.MjModel.from_xml_path(os.path.join(WS, 'g1', 'scene_29dof.xml'))
data = mujoco.MjData(model)
model.vis.global_.offwidth = 1000
model.vis.global_.offheight = 1000

arr = np.loadtxt(CSV, delimiter=',')
n = arr.shape[0]
print('csv:', os.path.basename(CSV), 'frames:', n)

r = mujoco.Renderer(model, 560, 560)
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
w = cv2.VideoWriter(OUT, fourcc, 30.0, (560, 560))

cam = mujoco.MjvCamera()
cam.lookat[:] = [0.0, 0.0, 1.05]
cam.distance = 3.2
cam.azimuth = AZ
cam.elevation = -8.0

snapset = {int(frac * (n - 1)) for frac in SNAPS}
for i, row in enumerate(arr):
    mujoco.mj_resetData(model, data)
    data.qpos[0:3] = row[0:3]
    q = row[3:7]
    data.qpos[3:7] = [q[3], q[0], q[1], q[2]]   # xyzw -> wxyz
    data.qpos[7:36] = row[7:36]
    mujoco.mj_forward(model, data)
    r.update_scene(data, camera=cam)
    img = r.render()[:, :, ::-1]
    for _ in range(REPEAT):
        w.write(img)
    if i in snapset:
        stem = os.path.splitext(os.path.basename(OUT))[0]
        cv2.imwrite(os.path.join(os.path.dirname(OUT), f'{stem}_f{i}.png'), img)

w.release()
print('saved', OUT)
