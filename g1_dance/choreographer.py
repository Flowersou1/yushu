# -*- coding: utf-8 -*-
"""G1 动作编辑器 v3（给组员编动作 + 导入测试已有动作）。
用法: python choreographer.py
- 拖滑块摆姿势 → 右侧 MuJoCo 实时显示。每行 [↺] 该关节归零。
- 【下身→站立】/【上身→抱架】分上下身重置。
- 【导入CSV】导入已有动作(routine.csv/组员导出的CSV)→载入关键帧→可播放测试/改/再导出。
- 填时间→【存关键帧】；【▶播放预览】；【导出CSV】。
"""
import os, numpy as np, mujoco, mujoco.viewer, tkinter as tk
from tkinter import ttk, messagebox, filedialog, font as tkfont

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(HERE)
MODEL = os.path.join(WS, 'g1', 'scene_29dof.xml')
FPS = 50
Z_STAND = 0.76
FONTSIZE = 14
RIGHTFS = 17
DEFAULT_ROOT = [0.0, 0.0, Z_STAND, 1.0, 0.0, 0.0, 0.0]   # [x,y,z, qw,qx,qy,qz]

model = mujoco.MjModel.from_xml_path(MODEL)
data = mujoco.MjData(model)
model.vis.global_.offwidth = 1000
model.vis.global_.offheight = 1000

JOINTS = []
GROUP = {}
BODY = {}
for j in range(model.njnt):
    n = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, j)
    if n == 'floating_base_joint':
        continue
    lo, hi = model.jnt_range[j]
    JOINTS.append((n, int(model.jnt_qposadr[j]), float(np.degrees(lo)), float(np.degrees(hi))))
    if 'hip' in n or 'knee' in n or 'ankle' in n:
        GROUP[n] = '左腿' if n.startswith('left') else '右腿'
    elif 'waist' in n:
        GROUP[n] = '腰'
    else:
        GROUP[n] = '左臂' if n.startswith('left') else '右臂'
    BODY[n] = '下身' if ('hip' in n or 'knee' in n or 'ankle' in n or 'waist' in n) else '上身'

SAFE_LEG = {'hip_pitch': np.degrees(-0.312), 'hip_roll': 0.0, 'hip_yaw': 0.0,
            'knee': np.degrees(0.669), 'ankle_pitch': np.degrees(-0.363), 'ankle_roll': 0.0}
PRESET_STAND = {}
for n, _, _, _ in JOINTS:
    PRESET_STAND[n] = 0.0
    for side in ('left_', 'right_'):
        for jn, val in SAFE_LEG.items():
            if n == side + jn:
                PRESET_STAND[n] = val
PRESET_GUARD = dict(PRESET_STAND)
PRESET_GUARD.update({
    'left_shoulder_pitch': np.degrees(-0.70), 'right_shoulder_pitch': np.degrees(-0.70),
    'left_shoulder_roll': np.degrees(0.3), 'right_shoulder_roll': np.degrees(-0.3),
    'left_elbow': np.degrees(-0.7), 'right_elbow': np.degrees(-0.7),
})


def ease(x):
    return 0.5 - 0.5 * np.cos(np.pi * np.clip(x, 0, 1))


class App:
    def __init__(self, root):
        self.root = root
        root.title("G1 动作编辑器 v3")
        root.geometry('1200x900')
        for fn in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont'):
            tkfont.nametofont(fn).configure(size=FONTSIZE)
        self.rfont = tkfont.Font(family='TkDefaultFont', size=RIGHTFS)
        self.sliders = {}
        self.val_lbls = {}
        self.keyframes = []   # [(time, {name:deg}, [root7]), ...]
        self.playing = False

        main = ttk.Frame(root); main.pack(fill=tk.BOTH, expand=True)
        right = ttk.Frame(main, padding=12, width=360); right.pack(side=tk.RIGHT, fill=tk.Y)
        right.pack_propagate(False)
        self.rfont = self.rfont

        left = ttk.Frame(main); left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canv = tk.Canvas(left, highlightthickness=0); canv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(left, orient=tk.VERTICAL, command=canv.yview); sb.pack(side=tk.RIGHT, fill=tk.Y)
        canv.configure(yscrollcommand=sb.set)
        inner = ttk.Frame(canv)
        win_id = canv.create_window((0, 0), window=inner, anchor='nw')
        canv.bind('<Configure>', lambda e: (canv.itemconfigure(win_id, width=e.width),
                                            canv.configure(scrollregion=canv.bbox('all'))))
        inner.bind('<Configure>', lambda e: canv.configure(scrollregion=canv.bbox('all')))
        for grp in ['左腿', '右腿', '腰', '左臂', '右臂']:
            lf = ttk.LabelFrame(inner, text=grp, padding=6); lf.pack(fill=tk.X, padx=10, pady=5)
            for n, adr, lo, hi in JOINTS:
                if GROUP[n] != grp: continue
                row = ttk.Frame(lf); row.pack(fill=tk.X, padx=8, pady=2)
                short = n.replace('left_', 'L·').replace('right_', 'R·').replace('_joint', '')
                ttk.Label(row, text=short, width=20, anchor='w').pack(side=tk.LEFT)
                s = tk.Scale(row, from_=lo, to=hi, orient=tk.HORIZONTAL,
                             font=('TkDefaultFont', FONTSIZE), command=lambda v, nn=n: self.on_slide(nn, v))
                s.set(0.0); s.pack(side=tk.LEFT, fill=tk.X, expand=True)
                self.sliders[n] = s
                self.val_lbls[n] = ttk.Label(row, text='0°', width=7); self.val_lbls[n].pack(side=tk.LEFT, padx=(4, 8))
                ttk.Button(row, text='↺', width=3, command=lambda nn=n: self.reset_one(nn)).pack(side=tk.LEFT)
        canv.bind_all('<MouseWheel>', lambda e: canv.yview_scroll(int(-e.delta / 120), 'units'))

        # 右：控制
        tk.Label(right, text="时间(秒):", font=self.rfont).pack(anchor='w')
        self.t_entry = tk.Entry(right, font=self.rfont); self.t_entry.insert(0, '0.0'); self.t_entry.pack(fill=tk.X)
        tk.Button(right, text="存关键帧", font=self.rfont, command=self.save_kf).pack(fill=tk.X, pady=6)
        ttk.Separator(right).pack(fill=tk.X, pady=5)
        tk.Button(right, text="📂 导入CSV(已有动作)", font=self.rfont, command=self.import_csv).pack(fill=tk.X, pady=3)
        ttk.Separator(right).pack(fill=tk.X, pady=5)
        tk.Label(right, text="局部重置：", font=self.rfont).pack(anchor='w')
        tk.Button(right, text="下身→站立(腿+腰)", font=self.rfont,
                  command=lambda: self.apply_subset(PRESET_STAND, {'下身'})).pack(fill=tk.X, pady=2)
        tk.Button(right, text="上身→抱架(双臂)", font=self.rfont,
                  command=lambda: self.apply_subset(PRESET_GUARD, {'上身'})).pack(fill=tk.X, pady=2)
        tk.Button(right, text="全部→站立", font=self.rfont,
                  command=lambda: self.apply_subset(PRESET_STAND, {'下身', '上身'})).pack(fill=tk.X, pady=2)
        tk.Button(right, text="全部归零", font=self.rfont,
                  command=lambda: self.apply_subset({n: 0.0 for n, _, _, _ in JOINTS}, {'下身', '上身'})).pack(fill=tk.X, pady=2)
        ttk.Separator(right).pack(fill=tk.X, pady=6)
        tk.Button(right, text="▶ 播放预览", font=self.rfont, command=self.play).pack(fill=tk.X, pady=3)
        tk.Button(right, text="导出 CSV", font=self.rfont, command=self.export_csv).pack(fill=tk.X, pady=3)
        tk.Button(right, text="清空关键帧", font=self.rfont, command=self.clear_kf).pack(fill=tk.X)
        ttk.Separator(right).pack(fill=tk.X, pady=6)
        tk.Label(right, text="关键帧列表:", font=self.rfont).pack(anchor='w')
        self.kf_list = tk.Text(right, height=8, font=self.rfont); self.kf_list.pack(fill=tk.BOTH, expand=True)

        self.apply_subset(PRESET_STAND, {'下身', '上身'})
        self.viewer = mujoco.viewer.launch_passive(model, data)
        self.update_loop()

    def on_slide(self, name, v):
        self.val_lbls[name].config(text=f'{float(v):.0f}°')

    def reset_one(self, name):
        self.sliders[name].set(0.0); self.val_lbls[name].config(text='0°')

    def apply_subset(self, preset, groups):
        for n, _, _, _ in JOINTS:
            if BODY[n] in groups:
                v = preset.get(n, 0.0)
                self.sliders[n].set(v); self.val_lbls[n].config(text=f'{v:.0f}°')

    def cur_pose(self):
        return {n: float(s.get()) for n, s in self.sliders.items()}

    def write_qpos(self, pose, root=None):
        if root is None:
            root = DEFAULT_ROOT
        data.qpos[0:3] = root[0:3]
        data.qpos[3:7] = root[3:7]
        for n, adr, _, _ in JOINTS:
            data.qpos[adr] = np.radians(pose.get(n, 0.0))
        mujoco.mj_forward(model, data)

    def set_pose_full(self, pose, root):
        for n, _, _, _ in JOINTS:
            self.sliders[n].set(pose.get(n, 0.0))
        self.write_qpos(pose, root)

    def save_kf(self):
        try:
            t = float(self.t_entry.get())
        except ValueError:
            t = 0.0
        pose = self.cur_pose()
        self.keyframes = [k for k in self.keyframes if abs(k[0] - t) > 1e-3]
        self.keyframes.append((t, pose, list(DEFAULT_ROOT)))
        self.keyframes.sort(key=lambda x: x[0])
        self.refresh_list(); self.write_qpos(pose, DEFAULT_ROOT)

    def import_csv(self):
        path = filedialog.askopenfilename(initialdir=HERE, title="导入动作CSV",
                                          filetypes=[('CSV', '*.csv')])
        if not path:
            return
        try:
            arr = np.loadtxt(path, delimiter=',')
        except Exception as e:
            messagebox.showerror("导入失败", str(e)); return
        kfs = []
        for i, row in enumerate(arr):
            t = i / FPS
            # root: CSV=[x,y,z,qx,qy,qz,qw] -> [x,y,z,qw,qx,qy,qz]
            root = [float(row[0]), float(row[1]), float(row[2]),
                    float(row[6]), float(row[3]), float(row[4]), float(row[5])]
            pose = {JOINTS[k][0]: float(np.degrees(row[7 + k])) for k in range(len(JOINTS))}
            kfs.append((t, pose, root))
        self.keyframes = kfs
        self.refresh_list()
        if kfs:
            self.set_pose_full(kfs[0][1], kfs[0][2])
        messagebox.showinfo("导入完成", f"{len(kfs)} 帧 @ {FPS}fps, 总时长 {len(kfs)/FPS:.1f}s\n点【▶播放预览】测试")

    def clear_kf(self):
        self.keyframes = []; self.refresh_list()

    def refresh_list(self):
        self.kf_list.delete('1.0', tk.END)
        for t, _, _ in self.keyframes:
            self.kf_list.insert(tk.END, f"t={t:.2f}s\n")

    def play(self):
        if len(self.keyframes) < 2 or self.playing:
            return
        self.playing = True
        kfs = sorted(self.keyframes, key=lambda x: x[0])
        dur = kfs[-1][0]

        def interp(t):
            for i in range(len(kfs) - 1):
                t0, p0, r0 = kfs[i]; t1, p1, r1 = kfs[i + 1]
                if t0 <= t <= t1:
                    a = ease((t - t0) / max(t1 - t0, 1e-9))
                    pose = {n: p0[n] + (p1[n] - p0[n]) * a for n in p0}
                    root = [r0[k] + (r1[k] - r0[k]) * a for k in range(7)]
                    return pose, root
            return kfs[-1][1], kfs[-1][2]

        fi = [0]; nf = int(dur * FPS)

        def step():
            if fi[0] > nf:
                self.playing = False; return
            t = fi[0] / FPS
            pose, root = interp(t)
            self.set_pose_full(pose, root)
            self.t_entry.delete(0, tk.END); self.t_entry.insert(0, f'{t:.2f}')
            fi[0] += 1
            self.root.after(int(1000 / FPS), step)
        step()

    def export_csv(self):
        if len(self.keyframes) < 2:
            messagebox.showerror("错误", "至少 2 个关键帧"); return
        path = filedialog.asksaveasfilename(initialdir=HERE, defaultextension='.csv',
                                             filetypes=[('CSV', '*.csv')], title="导出动作CSV")
        if not path:
            return
        kfs = sorted(self.keyframes, key=lambda x: x[0]); dur = kfs[-1][0]

        def interp(t):
            for i in range(len(kfs) - 1):
                t0, p0, r0 = kfs[i]; t1, p1, r1 = kfs[i + 1]
                if t0 <= t <= t1:
                    a = ease((t - t0) / max(t1 - t0, 1e-9))
                    pose = [p0[n] + (p1[n] - p0[n]) * a for n, _, _, _ in JOINTS]
                    root = [r0[k] + (r1[k] - r0[k]) * a for k in range(7)]
                    return pose, root
            return [kfs[-1][1][n] for n, _, _, _ in JOINTS], kfs[-1][2]

        rows = []
        for fi_n in range(int(dur * FPS) + 1):
            pose_deg, root = interp(fi_n / FPS)
            rads = np.radians(pose_deg)
            # root [x,y,z,qw,qx,qy,qz] -> [x,y,z,qx,qy,qz,qw]
            xyzw = [root[0], root[1], root[2], root[4], root[5], root[6], root[3]]
            rows.append(xyzw + list(rads))
        np.savetxt(path, np.array(rows), delimiter=',', fmt='%.5f')
        messagebox.showinfo("完成", f"导出 {len(rows)} 帧 @ {FPS}fps\n{path}")

    def update_loop(self):
        if not self.playing:
            self.write_qpos(self.cur_pose(), DEFAULT_ROOT)
        if self.viewer.is_running():
            self.viewer.sync()
        self.root.after(30, self.update_loop)


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
