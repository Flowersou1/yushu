# -*- coding: utf-8 -*-
"""把多个组员各自编的动作 CSV 拼成一套完整 routine。
用法: python combine_routines.py 输出.csv seg1.csv seg2.csv [seg3.csv ...] [--transition 秒]
段间默认加 0.3 秒线性平滑过渡(避免接缝突变)。
每个 CSV 都是 mjlab 格式: 每帧 [root_x,root_y,root_z, qx,qy,qz,qw, 29关节], 50fps。
"""
import sys, numpy as np

FPS = 50

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    trans = 0.3
    if '--transition' in sys.argv:
        i = sys.argv.index('--transition'); trans = float(sys.argv[i+1])
    if len(args) < 3:
        print("用法: python combine_routines.py 输出.csv seg1.csv seg2.csv [...] [--transition 秒]")
        return
    out, segs = args[0], args[1:]
    arrays = [np.loadtxt(s, delimiter=',') for s in segs]
    print(f"读入 {len(segs)} 段: 帧数 {[a.shape[0] for a in arrays]}")
    result = arrays[0]
    for nxt in arrays[1:]:
        a_end = result[-1, 7:]            # 上一段结尾关节角
        b_start = nxt[0, 7:]              # 下一段起始关节角
        n_trans = int(trans * FPS)
        if n_trans > 0:
            ts = np.linspace(0, 1, n_trans)[:, None]
            blend = a_end * (1 - ts) + b_start * ts   # 关节角线性过渡
            root = np.zeros((n_trans, 7)); root[:, 2] = 0.76; root[:, 6] = 1.0
            result = np.vstack([result, np.hstack([root, blend])])
        result = np.vstack([result, nxt])
    np.savetxt(out, result, delimiter=',', fmt='%.5f')
    print(f"合成完成: {result.shape[0]} 帧, {result.shape[0]/FPS:.1f}s -> {out}")

if __name__ == '__main__':
    main()
