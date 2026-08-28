# -*- coding: utf-8 -*-
"""完整上半身拳术 routine (必选拳术, 腿全程稳定站立, Arm SDK 友好):
起势抱架 → 左三冲拳 → 右三冲拳 → 左推掌 → 右推掌 → 顶肘(右) → 收势。
关节符号已修正: shoulder_pitch 负=前抬; elbow 伸直=+1.3(正值!), 0只是90°弯。
输出 routine.csv: [root_x,root_y,root_z, qx,qy,qz,qw, 29关节], 顺序 左腿6/右腿6/腰3/左臂7/右臂7
腿: hip_pitch,hip_roll,hip_yaw,knee,ankle_pitch,ankle_roll | 腰: yaw,roll,pitch
臂: shoulder_pitch,shoulder_roll,shoulder_yaw,elbow,wrist_roll,wrist_pitch,wrist_yaw"""
import os, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'routine.csv')

LEG = [-0.312, 0.0, 0.0, 0.669, -0.363, 0.0]   # 稳定站立, 全程不变
Z = 0.76
SP_G = -0.70   # 抱架大臂角
SP_P = -1.10   # 出拳/推掌/顶肘 大臂角(让伸直手臂水平向前)

GL = [SP_G, 0.3, 0.0, -0.7, 0.0, 0.0, 0.0]    # 左抱架(肘屈-0.7, 内角~59°)
GR = [SP_G, -0.3, 0.0, -0.7, 0.0, 0.0, 0.0]
PL = [SP_P, 0.15, 0.0, 1.3, 0.0, 0.0, 0.0]    # 左冲拳/推掌(肘伸+1.3, 内角~165°, 臂前伸)
PR = [SP_P, -0.15, 0.0, 1.3, 0.0, 0.0, 0.0]
EL = [SP_P, 0.15, 0.0, -0.7, 0.0, 0.0, 0.0]   # 左顶肘(大臂前伸, 肘屈, 肘尖前顶)
ER = [SP_P, -0.15, 0.0, -0.7, 0.0, 0.0, 0.0]

# (t秒, 腰yaw, 左臂, 右臂)  腰转向发力方
E = [
    (0.0,  0.00, GL, GR),    # 起势抱架
    (1.0,  0.00, GL, GR),    # 停
    # 左三冲拳 (每拳: 出0.15 停0.10 收0.25)
    (1.3, -0.35, PL, GR), (1.45, -0.35, PL, GR), (1.8, 0.0, GL, GR), (1.95, 0.0, GL, GR),
    (2.15,-0.35, PL, GR), (2.30, -0.35, PL, GR), (2.65, 0.0, GL, GR), (2.80, 0.0, GL, GR),
    (3.0, -0.35, PL, GR), (3.15, -0.35, PL, GR), (3.5,  0.0, GL, GR), (3.7,  0.0, GL, GR),
    # 右三冲拳
    (4.0,  0.35, GL, PR), (4.15,  0.35, GL, PR), (4.5,  0.0, GL, GR), (4.65, 0.0, GL, GR),
    (4.85, 0.35, GL, PR), (5.0,   0.35, GL, PR), (5.35, 0.0, GL, GR), (5.5,  0.0, GL, GR),
    (5.7,  0.35, GL, PR), (5.85,  0.35, GL, PR), (6.2,  0.0, GL, GR), (6.4,  0.0, GL, GR),
    # 左推掌 (出0.4 停0.6 收0.4)
    (6.8, -0.35, PL, GR), (7.4, -0.35, PL, GR), (7.8, 0.0, GL, GR),
    # 右推掌
    (8.1,  0.35, GL, PR), (8.7,  0.35, GL, PR), (9.1, 0.0, GL, GR),
    # 顶肘(右) (顶0.4 停0.4 收0.4)
    (9.5,  0.30, GL, ER), (10.0, 0.30, GL, ER), (10.4, 0.0, GL, GR),
    # 收势
    (10.8, 0.0, GL, GR), (11.8, 0.0, GL, GR),
]
FPS = 50
DUR = E[-1][0]

def ease_out(t):
    t = np.clip(t, 0, 1); return 1 - (1 - t) ** 2

def interp(tf):
    for i in range(len(E) - 1):
        t0, w0, a0, b0 = E[i]; t1, w1, a1, b1 = E[i + 1]
        if t0 <= tf <= t1:
            a = ease_out((tf - t0) / max(t1 - t0, 1e-9))
            return (w0 + (w1 - w0) * a,
                    np.array(a0) + (np.array(a1) - np.array(a0)) * a,
                    np.array(b0) + (np.array(b1) - np.array(b0)) * a)
    return E[-1][1], np.array(E[-1][2]), np.array(E[-1][3])

rows = []
for fi in range(int(DUR * FPS) + 1):
    tf = fi / FPS; wy, aL, aR = interp(tf)
    p = LEG + LEG + [wy, 0.0, 0.0] + list(aL) + list(aR)
    rows.append([0.0, 0.0, Z, 0.0, 0.0, 0.0, 1.0] + list(p))

np.savetxt(OUT, np.array(rows), delimiter=',', fmt='%.5f')
print('wrote', OUT, 'frames=', len(rows), 'dur=%.1fs' % DUR)
