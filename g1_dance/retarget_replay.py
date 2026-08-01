# -*- coding: utf-8 -*-
"""
Phase 1 - 第二步：关键点 -> G1 29关节角 -> MuJoCo 运动学回放 -> 视频 + CSV。

⚠️ 这是 v1 粗版：把人手算的关节角映射到 G1，符号/偏置先按经验设，跑出来一起看哪里不对再调。
用法（在 g1_dance 目录下）：python retarget_replay.py
输入: out/landmarks.npz , g1/scene_29dof.xml
输出: out/g1_replay.mp4  (G1 跟着视频动作的运动学回放)
      out/motion.csv    (时间 + 29 关节角，度；可喂给后续 RL 模仿学习)
"""
import os, math
import numpy as np
import mujoco, cv2

WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
G1D = os.path.join(WS, 'g1_dance'); OUT = os.path.join(G1D, 'out')
NPZ = os.path.join(OUT, 'landmarks.npz')
XML = os.path.join(WS, 'g1', 'scene_29dof.xml')
OUT_MP4 = os.path.join(OUT, 'g1_replay.mp4')
OUT_CSV = os.path.join(OUT, 'motion.csv')

# ====== 可调区：mediapipe 世界坐标 -> 机器人坐标系的符号 ======
# mediapipe world 经验约定: x=右(+) y=下(+) z=朝相机(+)
# 机器人坐标系: X=前 Y=左 Z=上
def to_robot(p):
    x, y, z = p
    return np.array([-z, -x, -y])   # 前=-z, 左=-x, 上=-y   ← 不对就改这里的符号

# BlazePose 关键点索引
LSH, RSH, LEL, REL, LWR, RWR = 11, 12, 13, 14, 15, 16
LHIP, RHIP, LKN, RKN, LANK, RANK = 23, 24, 25, 26, 27, 28


def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def ang_between(a, b):
    return math.acos(max(-1, min(1, unit(a) @ unit(b))))


def retarget(w):
    """w: [33,3] mediapipe 世界坐标(米) -> dict{joint_name: 弧度}"""
    p = [to_robot(w[i]) for i in range(33)]
    sh_mid = (p[LSH] + p[RSH]) / 2
    hip_mid = (p[LHIP] + p[RHIP]) / 2
    out = {}

    # ---- 手臂 ----
    for side, sh, el, wr, pre, side_sign in [('L', LSH, LEL, LWR, 'left', 1),
                                             ('R', RSH, REL, RWR, 'right', -1)]:
        upper = p[el] - p[sh]
        fore = p[wr] - p[el]
        shoulder_pitch = math.atan2(upper[0], upper[2])                 # 前/后抬
        shoulder_roll = math.atan2(upper[1], math.hypot(upper[0], upper[2])) * side_sign  # 外展
        elbow = math.pi - ang_between(upper, fore)                      # 屈肘
        out[f'{pre}_shoulder_pitch_joint'] = shoulder_pitch
        out[f'{pre}_shoulder_roll_joint'] = shoulder_roll
        out[f'{pre}_shoulder_yaw_joint'] = 0.0
        out[f'{pre}_elbow_joint'] = elbow
        out[f'{pre}_wrist_roll_joint'] = 0.0
        out[f'{pre}_wrist_pitch_joint'] = 0.0
        out[f'{pre}_wrist_yaw_joint'] = 0.0

    # ---- 腿 ----
    for side, hip, kn, ank, pre, side_sign in [('L', LHIP, LKN, LANK, 'left', 1),
                                               ('R', RHIP, RKN, RANK, 'right', -1)]:
        thigh = p[kn] - p[hip]
        shin = p[ank] - p[kn]
        hip_pitch = math.atan2(thigh[0], thigh[2])                      # 抬腿前/后
        hip_roll = math.atan2(thigh[1], math.hypot(thigh[0], thigh[2])) * side_sign
        knee = math.pi - ang_between(thigh, shin)                       # 屈膝
        out[f'{pre}_hip_pitch_joint'] = hip_pitch
        out[f'{pre}_hip_roll_joint'] = hip_roll
        out[f'{pre}_hip_yaw_joint'] = 0.0
        out[f'{pre}_knee_joint'] = knee
        out[f'{pre}_ankle_pitch_joint'] = 0.0
        out[f'{pre}_ankle_roll_joint'] = 0.0

    # ---- 腰 ----
    torso = sh_mid - hip_mid
    waist_pitch = math.atan2(torso[0], torso[2])
    waist_roll = math.atan2(torso[1], math.hypot(torso[0], torso[2]))
    sh_v = p[RSH] - p[LSH]; hip_v = p[RHIP] - p[LHIP]
    waist_yaw = math.atan2(sh_v[1], sh_v[0]) - math.atan2(hip_v[1], hip_v[0])
    out['waist_pitch_joint'] = waist_pitch
    out['waist_roll_joint'] = waist_roll
    out['waist_yaw_joint'] = waist_yaw
    return out


def main():
    d = np.load(NPZ)
    world, mask, fps = d['world'], d['mask'], float(d['fps'])
    N = len(world)
    print(f'加载 {N} 帧, fps={fps:.1f}, 检测到 {int(mask.sum())} 帧')

    model = mujoco.MjModel.from_xml_path(XML)
    data = mujoco.MjData(model)
    model.vis.global_.offwidth = 1000
    model.vis.global_.offheight = 1000

    addr, rng, jnames = {}, {}, []
    for i in range(model.njnt):
        nm = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i)
        if nm == 'floating_base_joint':
            continue
        addr[nm] = model.jnt_qposadr[i]
        rng[nm] = model.jnt_range[i]
        jnames.append(nm)

    r = mujoco.Renderer(model, 720, 720)
    writer = cv2.VideoWriter(OUT_MP4, cv2.VideoWriter_fourcc(*'mp4v'), fps, (720, 720))
    csv = open(OUT_CSV, 'w', encoding='utf-8')
    csv.write('time,' + ','.join(jnames) + '\n')

    for i in range(N):
        mujoco.mj_resetData(model, data)
        if mask[i]:
            for nm, a in retarget(world[i]).items():
                lo, hi = rng[nm]
                data.qpos[addr[nm]] = max(lo, min(hi, a))
        mujoco.mj_forward(model, data)
        r.update_scene(data, camera=-1)
        writer.write(r.render()[:, :, ::-1])
        csv.write(f'{i/fps:.3f},' + ','.join(f'{data.qpos[addr[nm]]:.4f}' for nm in jnames) + '\n')
        if i % 200 == 0:
            print(f'  回放 {i}/{N}', flush=True)

    writer.release(); csv.close()
    print('SAVED', OUT_MP4)
    print('SAVED', OUT_CSV)


if __name__ == '__main__':
    main()
