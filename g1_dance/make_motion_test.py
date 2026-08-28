# -*- coding: utf-8 -*-
"""5秒直拳测试:
抱架1s → 左直拳(0.3出+0.15停+0.35收) → 停 → 右直拳 → 抱架。
腿全程稳定站立。输出 test.csv: [root_xyz, qx,qy,qz,qw, 29关节]"""
import os, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'test.csv')

LEG = [-0.312, 0.0, 0.0, 0.669, -0.363, 0.0]

SP_G = -0.70   # 抱架大臂角(拳收胸前)
SP_P = -1.10   # 出拳大臂角(让伸直的手臂水平向前, 拳在胸口高)
GL = [SP_G, 0.3, 0.0, -0.7, 0.0, 0.0, 0.0]    # 左抱架(肘屈-0.7, 内角~56°, 拳在胸前)
GR = [SP_G, -0.3, 0.0, -0.7, 0.0, 0.0, 0.0]   # 右抱架
PL = [SP_P, 0.15, 0.0, 1.3, 0.0, 0.0, 0.0]    # 左冲拳(肘伸到+1.3, 内角~160°近伸直, 手臂水平向前)
PR = [SP_P, -0.15, 0.0, 1.3, 0.0, 0.0, 0.0]   # 右冲拳
# 注: 实测 G1 肘"伸直"≈+1.5(内角167°), elbow=0 只是90°直角。以前用负值/0 → 出拳时手臂一直弯着。

# (t秒, 腰yaw, 左臂, 右臂)  腰转向出拳方: 左拳-0.40/右拳+0.40
SEQ = [
    (0.00,  0.00, GL, GR),    # 抱架
    (1.00,  0.00, GL, GR),    # 停1s
    (1.30, -0.40, PL, GR),    # 左直拳 出(0.3s) 肘从屈到伸
    (1.45, -0.40, PL, GR),    # 顿(0.15s)
    (1.80,  0.00, GL, GR),    # 收(0.35s) 肘重新屈
    (2.10,  0.00, GL, GR),    # 停
    (2.40,  0.40, GL, PR),    # 右直拳 出
    (2.55,  0.40, GL, PR),    # 顿
    (2.90,  0.00, GL, GR),    # 收
    (3.20,  0.00, GL, GR),    # 抱架收势
]
FPS = 50
DUR = SEQ[-1][0]

def ease_out(t):
    t = np.clip(t, 0, 1)
    return 1 - (1 - t) ** 2     # 快攻(爆发感)

def interp(tf):
    for i in range(len(SEQ) - 1):
        t0, w0, a0, b0 = SEQ[i]
        t1, w1, a1, b1 = SEQ[i + 1]
        if t0 <= tf <= t1:
            a = ease_out((tf - t0) / max(t1 - t0, 1e-9))
            return (w0 + (w1 - w0) * a,
                    np.array(a0) + (np.array(a1) - np.array(a0)) * a,
                    np.array(b0) + (np.array(b1) - np.array(b0)) * a)
    return SEQ[-1][1], np.array(SEQ[-1][2]), np.array(SEQ[-1][3])

rows = []
for fi in range(int(DUR * FPS) + 1):
    tf = fi / FPS
    wy, aL, aR = interp(tf)
    p = LEG + LEG + [wy, 0.0, 0.0] + list(aL) + list(aR)
    rows.append([0.0, 0.0, 0.76, 0.0, 0.0, 0.0, 1.0] + list(p))

np.savetxt(OUT, np.array(rows), delimiter=',', fmt='%.5f')
print('wrote', OUT, 'frames=', len(rows), 'dur=%.1fs' % DUR, 'fps=', FPS)
