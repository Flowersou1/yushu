# -*- coding: utf-8 -*-
"""G1 动作编辑器 v2（给组员编动作用，不用写代码）。
改进: 界面/字体放大、每关节"归零"按钮、站立/抱架分上下身。
用法: python choreographer.py
- 拖滑块摆姿势 → 右侧 MuJoCo 实时显示。
- 每行右侧 [↺] = 该关节归零。
- 【下身→站立】只重置腿+腰到站立；【上身→抱架】只重置双臂到抱架；【全部归零】全归零。
- 填时间 → 【存关键帧】；【▶播放预览】；【导出CSV】。
"""
import os, numpy as np, mujoco, mujoco.viewer, tkinter as tk
from tkinter import ttk, messagebox, filedialog, font as tkfont

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(HERE)
MODEL = os.path.join(WS, 'g1', 'scene_29dof.xml')
FPS = 50
Z_STAND = 0.76
FONTSIZE = 14    # 左侧滑块区字号
RIGHTFS = 17     # 右侧菜单栏字号(比左侧更大)

model = mujoco.MjModel.from_xml_path(MODEL)
data = mujoco.MjData(model)
model.vis.global_.offwidth = 1000
model.vis.global_.offheight = 1000

JOINTS = []
GROUP = {}   # 5 组(布局用): 左腿/右腿/腰/左臂/右臂
BODY = {}    # 2 类(分上下身用): 下身/上身
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

class App:
    def __init__(self, root):
        self.root = root
        root.title("G1 动作编辑器 v2")
        root.geometry('1200x900')
        for fn in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont'):
            tkfont.nametofont(fn).configure(size=FONTSIZE)
        rfont = tkfont.Font(family='TkDefaultFont', size=RIGHTFS)   # 右侧专用大字体
        self.sliders = {}
        self.val_lbls = {}
        self.keyframes = []
        self.playing = False

        main = ttk.Frame(root); main.pack(fill=tk.BOTH, expand=True)

        # 右：控制面板(固定宽度, 大字体)
        right = ttk.Frame(main, padding=12, width=360); right.pack(side=tk.RIGHT, fill=tk.Y)
        right.pack_propagate(False)
        self.rfont = rfont

        # 左：滑块(填满, 可滚动)
        left = ttk.Frame(main); left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canv = tk.Canvas(left, highlightthickness=0); canv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(left, orient=tk.VERTICAL, command=canv.yview); sb.pack(side=tk.RIGHT, fill=tk.Y)
        canv.configure(yscrollcommand=sb.set)
        inner = ttk.Frame(canv)
        win_id = canv.create_window((0, 0), window=inner, anchor='nw')
        # 内框宽度跟随 canvas(让滑块行填满, 不留空)
        canv.bind('<Configure>', lambda e: (canv.itemconfigure(win_id, width=e.width),
                                            canv.configure(scrollregion=canv.bbox('all'))))
        inner.bind('<Configure>', lambda e: canv.configure(scrollregion=canv.bbox('all')))

        grp_order = ['左腿','右腿','腰','左臂','右臂']
        for grp in grp_order:
            lf = ttk.LabelFrame(inner, text=grp, padding=6); lf.pack(fill=tk.X, padx=10, pady=5)
            for n, adr, lo, hi in JOINTS:
                if GROUP[n] != grp: continue
                row = ttk.Frame(lf); row.pack(fill=tk.X, padx=8, pady=2)
                short = n.replace('left_','L·').replace('right_','R·').replace('_joint','')
                ttk.Label(row, text=short, width=20, anchor='w').pack(side=tk.LEFT)
                s = tk.Scale(row, from_=lo, to=hi, orient=tk.HORIZONTAL,
                             font=('TkDefaultFont', FONTSIZE), command=lambda v, nn=n: self.on_slide(nn, v))
                s.set(0.0); s.pack(side=tk.LEFT, fill=tk.X, expand=True)
                self.sliders[n] = s
                self.val_lbls[n] = ttk.Label(row, text='0°', width=7)
                self.val_lbls[n].pack(side=tk.LEFT, padx=(4,8))
                ttk.Button(row, text='↺', width=3, command=lambda nn=n: self.reset_one(nn)).pack(side=tk.LEFT)
        canv.bind_all('<MouseWheel>', lambda e: canv.yview_scroll(int(-e.delta/120), 'units'))
        tk.Label(right, text="时间(秒):", font=self.rfont).pack(anchor='w')
        self.t_entry = tk.Entry(right, font=self.rfont); self.t_entry.insert(0, '0.0'); self.t_entry.pack(fill=tk.X)
        tk.Button(right, text="存关键帧", font=self.rfont, command=self.save_kf).pack(fill=tk.X, pady=6)
        ttk.Separator(right).pack(fill=tk.X, pady=5)
        tk.Label(right, text="局部重置：", font=self.rfont).pack(anchor='w')
        tk.Button(right, text="下身→站立(腿+腰)", font=self.rfont, command=lambda: self.apply_subset(PRESET_STAND, {'下身'})).pack(fill=tk.X, pady=2)
        tk.Button(right, text="上身→抱架(双臂)", font=self.rfont, command=lambda: self.apply_subset(PRESET_GUARD, {'上身'})).pack(fill=tk.X, pady=2)
        tk.Button(right, text="全部→站立", font=self.rfont, command=lambda: self.apply_subset(PRESET_STAND, {'下身','上身'})).pack(fill=tk.X, pady=2)
        tk.Button(right, text="全部归零", font=self.rfont, command=lambda: self.apply_subset({n:0.0 for n,_,_,_ in JOINTS}, {'下身','上身'})).pack(fill=tk.X, pady=2)
        ttk.Separator(right).pack(fill=tk.X, pady=6)
        tk.Button(right, text="▶ 播放预览", font=self.rfont, command=self.play).pack(fill=tk.X, pady=3)
        tk.Button(right, text="导出 CSV", font=self.rfont, command=self.export_csv).pack(fill=tk.X, pady=3)
        tk.Button(right, text="清空关键帧", font=self.rfont, command=self.clear_kf).pack(fill=tk.X)
        ttk.Separator(right).pack(fill=tk.X, pady=6)
        tk.Label(right, text="关键帧列表:", font=self.rfont).pack(anchor='w')
        self.kf_list = tk.Text(right, height=8, font=self.rfont); self.kf_list.pack(fill=tk.BOTH, expand=True)

        self.apply_subset(PRESET_STAND, {'下身','上身'})
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

    def write_qpos(self, pose_deg):
        data.qpos[0:3] = [0, 0, Z_STAND]; data.qpos[3:7] = [1, 0, 0, 0]
        for n, adr, _, _ in JOINTS:
            data.qpos[adr] = np.radians(pose_deg.get(n, 0.0))
        mujoco.mj_forward(model, data)

    def cur_pose(self):
        return {n: float(s.get()) for n, s in self.sliders.items()}

    def set_pose(self, pose_deg):
        for n, _, _, _ in JOINTS:
            self.sliders[n].set(pose_deg.get(n, 0.0))
        self.write_qpos(pose_deg)

    def save_kf(self):
        try: t = float(self.t_entry.get())
        except: t = 0.0
        pose = self.cur_pose()
        self.keyframes = [k for k in self.keyframes if abs(k[0]-t) > 1e-3]
        self.keyframes.append((t, pose)); self.keyframes.sort(key=lambda x: x[0])
        self.refresh_list(); self.write_qpos(pose)

    def clear_kf(self):
        self.keyframes = []; self.refresh_list()

    def refresh_list(self):
        self.kf_list.delete('1.0', tk.END)
        for t, _ in self.keyframes:
            self.kf_list.insert(tk.END, f"t={t:.2f}s\n")

    def play(self):
        if len(self.keyframes) < 2 or self.playing: return
        self.playing = True
        kfs = sorted(self.keyframes, key=lambda x: x[0]); dur = kfs[-1][0]
        def ease(x): return 0.5 - 0.5*np.cos(np.pi*np.clip(x,0,1))
        def interp(t):
            for i in range(len(kfs)-1):
                t0,p0 = kfs[i]; t1,p1 = kfs[i+1]
                if t0 <= t <= t1:
                    a = ease((t-t0)/max(t1-t0,1e-9))
                    return {n: p0[n]+(p1[n]-p0[n])*a for n in p0}
            return kfs[-1][1]
        fi=[0]; nf=int(dur*FPS)
        def step():
            if fi[0] > nf: self.playing=False; return
            t=fi[0]/FPS; self.set_pose(interp(t))
            self.t_entry.delete(0,tk.END); self.t_entry.insert(0,f'{t:.2f}')
            fi[0]+=1; self.root.after(int(1000/FPS), step)
        step()

    def export_csv(self):
        if len(self.keyframes) < 2:
            messagebox.showerror("错误","至少 2 个关键帧"); return
        path = filedialog.asksaveasfilename(initialdir=HERE, defaultextension='.csv',
                  filetypes=[('CSV','*.csv')], title="导出动作CSV")
        if not path: return
        kfs = sorted(self.keyframes, key=lambda x:x[0]); dur=kfs[-1][0]
        def ease(x): return 0.5-0.5*np.cos(np.pi*np.clip(x,0,1))
        def interp(t):
            for i in range(len(kfs)-1):
                t0,p0=kfs[i]; t1,p1=kfs[i+1]
                if t0<=t<=t1:
                    a=ease((t-t0)/max(t1-t0,1e-9)); return [p0[n]+(p1[n]-p0[n])*a for n,_,_,_ in JOINTS]
            return [kfs[-1][1][n] for n,_,_,_ in JOINTS]
        rows=[]
        for fi in range(int(dur*FPS)+1):
            rads=np.radians(interp(fi/FPS))
            rows.append([0.0,0.0,Z_STAND,0.0,0.0,0.0,1.0]+list(rads))
        np.savetxt(path, np.array(rows), delimiter=',', fmt='%.5f')
        messagebox.showinfo("完成", f"导出 {len(rows)} 帧 @ {FPS}fps\n{path}")

    def update_loop(self):
        if not self.playing:
            self.write_qpos(self.cur_pose())
        if self.viewer.is_running():
            self.viewer.sync()
        self.root.after(30, self.update_loop)

if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
