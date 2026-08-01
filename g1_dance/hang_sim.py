# -*- coding: utf-8 -*-
"""虚拟悬挂(锚定躯干)物理仿真: 锁住躯干(模拟吊装) + PD 控 29 关节跟踪 routine.csv。
不走 RL、不靠平衡器, 用来验证"关键帧 -> PD -> 机器人带物理地动起来"这条流程。
输出 routine_hang.mp4 (侧面)。"""
import os, sys, numpy as np, mujoco, cv2

WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
model = mujoco.MjModel.from_xml_path(os.path.join(WS, 'g1', 'scene_29dof.xml'))
data = mujoco.MjData(model)
model.vis.global_.offwidth = 1000
model.vis.global_.offheight = 1000

arr = np.loadtxt(os.path.join(WS, 'g1_dance', 'routine.csv'), delimiter=',')
FPS = 50
DT = 1.0 / FPS
model.opt.timestep = DT / 5  # 500Hz 物理, 每 100Hz 出一帧(每个画面步 5 个物理子步)

Kp = 60.0   # 关节 PD 刚度 (同 g1-mechdance)
Kd = 1.5    # 关节 PD 阻尼
Z0 = 0.76   # 定位高度(站立)
# 关掉重力(吊装下机器人不会摔), 用柔和弹簧把躯干定在 (0,0,Z0) + 保持朝向
model.opt.gravity[:] = 0
KP_B = 500.0; KD_B = 100.0   # 躯干平移(柔和, 稳定)
KP_O = 500.0; KD_O = 100.0   # 躯干朝向

# 渲染器
r = mujoco.Renderer(model, 560, 560)
cam = mujoco.MjvCamera()
cam.lookat[:] = [0.0, 0.0, 1.0]
cam.distance = 3.2
cam.azimuth = 270.0
cam.elevation = -8.0
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
OUT = os.path.join(WS, 'g1_dance', 'routine_hang.mp4')
w = cv2.VideoWriter(OUT, fourcc, FPS, (560, 560))

# 初始化到第一帧关节角
data.qpos[0:3] = [0, 0, Z0]
data.qpos[3:7] = [1, 0, 0, 0]
data.qpos[7:36] = arr[0, 7:36]
mujoco.mj_forward(model, data)

for i, row in enumerate(arr):
    target = row[7:36]  # 29 关节目标角
    # 每个物理子步都重算 PD + 悬挂力(基于当前状态), 这样 PD 稳定不发散
    for _ in range(5):
        data.qfrc_applied[:] = 0
        # 关节 PD
        data.qfrc_applied[6:35] = Kp * (target - data.qpos[7:36]) - Kd * data.qvel[6:35]
        # 躯干平移悬挂 (x,y→0; z→Z0)
        pos = data.qpos[0:3]; lv = data.qvel[0:3]
        data.qfrc_applied[0] = -KP_B * pos[0] - KD_B * lv[0]
        data.qfrc_applied[1] = -KP_B * pos[1] - KD_B * lv[1]
        data.qfrc_applied[2] = KP_B * (Z0 - pos[2]) - KD_B * lv[2]
        # 躯干朝向悬挂 (保持 identity)
        qv = data.qpos[4:7]; av = data.qvel[3:6]
        data.qfrc_applied[3:6] = -KP_O * 2.0 * qv - KD_O * av
        mujoco.mj_step(model, data)
        if not np.isfinite(data.qacc).all():
            print(f"[warn] 发散于帧 {i}, 停止"); w.release(); sys.exit()
    # 渲染
    r.update_scene(data, camera=cam)
    w.write(r.render()[:, :, ::-1])

w.release()
print('saved', OUT)
