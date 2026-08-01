# -*- coding: utf-8 -*-
"""诊断脚本：拉取训练曲线(tensorboard事件) + 动作数据分析，定位训练平台期原因。"""
import glob, os, numpy as np

print("=" * 60)
print("1) 训练曲线 (最新值，来自 tensorboard 事件)")
print("=" * 60)
try:
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    runs = sorted(glob.glob('/root/g1_spinkick_example/logs/rsl_rl/g1_tracking/*'), key=os.path.getmtime)
    print("run 目录:", [os.path.basename(r) for r in runs])
    for run in runs[-2:]:
        ea = EventAccumulator(run)
        ea.Reload()
        tags = ea.Tags().get('scalars', [])
        if not tags:
            print("  ", os.path.basename(run), "(无事件，可能还在写)")
            continue
        steps = [ea.Scalars(t)[-1].step for t in tags]
        print(f"\n--- {os.path.basename(run)} (max step={max(steps)}) ---")
        print("  所有tag示例:", sorted(tags)[:12])
        for t in sorted(tags):
            tl = t.lower()
            if any(k in tl for k in ['reward', 'length', 'episode', 'termin', 'progress', 'motion']):
                ev = ea.Scalars(t)
                v, s = ev[-1].value, ev[-1].step
                # 也给首值看趋势
                v0 = ev[0].value if len(ev) > 0 else v
                print(f"  {t}: 最新={v:.4f} (step={s}, n={len(ev)}) 起始={v0:.4f}")
except Exception as e:
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("2) 动作数据 routine.csv 分析")
print("=" * 60)
csv = '/root/g1_spinkick_example/motions/routine.csv'
arr = np.loadtxt(csv, delimiter=',')
nframes = arr.shape[0]
print("帧数:", nframes, " 每帧维度:", arr.shape[1], " (应为36: root3+quat4+29关节)")
print("总时长: %.2fs @30fps" % (nframes / 30.0))
z = arr[:, 2]
print("root_z 范围: [%.3f, %.3f]  最低点在第%d帧 (t=%.2fs)" % (z.min(), z.max(), z.argmin(), z.argmin() / 30.0))
print("关键时刻 root_z:")
for t in [0, 2, 4, 6, 8, 10]:
    f = min(int(t * 30), nframes - 1)
    print("  t=%2ds (帧%3d): root_z=%.3f" % (t, f, arr[f, 2]))
# 帧间关节角突变检测
joints = arr[:, 7:]
diff = np.abs(np.diff(joints, axis=0))
maxdiff = diff.max(axis=1)
print("帧间最大关节角变化 top5 (可能动态难点):")
for f in np.argsort(maxdiff)[-5:][::-1]:
    print("  帧%d (t=%.2fs) 单帧最大变化=%.3f rad" % (f, f / 30.0, maxdiff[f]))
# 50% 位置 (5s) 前后的关节
mid = nframes // 2
print("50%% 位置 ~ 帧%d (t=%.2fs) 的关节角:" % (mid, mid / 30.0))
print("  ", np.round(arr[mid, 7:], 2).tolist())
