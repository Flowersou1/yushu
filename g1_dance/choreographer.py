# -*- coding: utf-8 -*-
"""G1 动作编辑器 v4
新: 播放暂停(按钮+空格) / JSON关键帧保存加载(稀疏无损往返) / 追加CSV(合并多段)
用法: python choreographer.py
"""
import os, json, numpy as np, mujoco, mujoco.viewer, tkinter as tk
from tkinter import ttk, messagebox, filedialog, font as tkfont

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(HERE)
MODEL = os.path.join(WS, 'g1', 'scene_29dof.xml')
FPS = 50; Z_STAND = 0.76; FONTSIZE = 14; RIGHTFS = 17
DEFAULT_ROOT = [0.0, 0.0, Z_STAND, 1.0, 0.0, 0.0, 0.0]

model = mujoco.MjModel.from_xml_path(MODEL)
data = mujoco.MjData(model)
model.vis.global_.offwidth = 1000; model.vis.global_.offheight = 1000

JOINTS, GROUP, BODY = [], {}, {}
for j in range(model.njnt):
    n = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, j)
    if n == 'floating_base_joint': continue
    lo, hi = model.jnt_range[j]
    JOINTS.append((n, int(model.jnt_qposadr[j]), float(np.degrees(lo)), float(np.degrees(hi))))
    if 'hip' in n or 'knee' in n or 'ankle' in n: GROUP[n] = '左腿' if n.startswith('left') else '右腿'
    elif 'waist' in n: GROUP[n] = '腰'
    else: GROUP[n] = '左臂' if n.startswith('left') else '右臂'
    BODY[n] = '下身' if ('hip' in n or 'knee' in n or 'ankle' in n or 'waist' in n) else '上身'

SAFE_LEG = {'hip_pitch': np.degrees(-0.312), 'knee': np.degrees(0.669), 'ankle_pitch': np.degrees(-0.363)}
PRESET_STAND = {}
for n, _, _, _ in JOINTS:
    PRESET_STAND[n] = 0.0
    for side in ('left_', 'right_'):
        for jn, val in SAFE_LEG.items():
            if n == side + jn: PRESET_STAND[n] = val
PRESET_GUARD = dict(PRESET_STAND)
PRESET_GUARD.update({'left_shoulder_pitch': np.degrees(-0.70), 'right_shoulder_pitch': np.degrees(-0.70),
    'left_shoulder_roll': np.degrees(0.3), 'right_shoulder_roll': np.degrees(-0.3),
    'left_elbow': np.degrees(-0.7), 'right_elbow': np.degrees(-0.7)})

def ease(x): return 0.5 - 0.5 * np.cos(np.pi * np.clip(x, 0, 1))

class App:
    def __init__(self, root):
        self.root = root
        root.title("G1 动作编辑器 v4"); root.geometry('1200x900')
        for fn in ('TkDefaultFont','TkTextFont','TkMenuFont'): tkfont.nametofont(fn).configure(size=FONTSIZE)
        self.rfont = tkfont.Font(family='TkDefaultFont', size=RIGHTFS)
        self.sliders = {}; self.val_lbls = {}
        self.keyframes = []   # [(time, {name:deg}, [root7])]
        self.playing = False; self.paused = False

        main = ttk.Frame(root); main.pack(fill=tk.BOTH, expand=True)
        right = ttk.Frame(main, padding=10, width=370); right.pack(side=tk.RIGHT, fill=tk.Y); right.pack_propagate(False)
        left = ttk.Frame(main); left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canv = tk.Canvas(left, highlightthickness=0); canv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(left, orient=tk.VERTICAL, command=canv.yview); sb.pack(side=tk.RIGHT, fill=tk.Y)
        canv.configure(yscrollcommand=sb.set)
        inner = ttk.Frame(canv); wid = canv.create_window((0,0), window=inner, anchor='nw')
        canv.bind('<Configure>', lambda e: (canv.itemconfigure(wid, width=e.width), canv.configure(scrollregion=canv.bbox('all'))))
        inner.bind('<Configure>', lambda e: canv.configure(scrollregion=canv.bbox('all')))
        for grp in ['左腿','右腿','腰','左臂','右臂']:
            lf = ttk.LabelFrame(inner, text=grp, padding=6); lf.pack(fill=tk.X, padx=10, pady=5)
            for n, adr, lo, hi in JOINTS:
                if GROUP[n] != grp: continue
                row = ttk.Frame(lf); row.pack(fill=tk.X, padx=8, pady=2)
                ttk.Label(row, text=n.replace('left_','L·').replace('right_','R·').replace('_joint',''), width=20, anchor='w').pack(side=tk.LEFT)
                s = tk.Scale(row, from_=lo, to=hi, orient=tk.HORIZONTAL, font=('TkDefaultFont',FONTSIZE),
                             command=lambda v,nn=n: self.on_slide(nn,v)); s.set(0.0)
                s.pack(side=tk.LEFT, fill=tk.X, expand=True); self.sliders[n] = s
                self.val_lbls[n] = ttk.Label(row, text='0°', width=7); self.val_lbls[n].pack(side=tk.LEFT, padx=(4,8))
                ttk.Button(row, text='↺', width=3, command=lambda nn=n: self.reset_one(nn)).pack(side=tk.LEFT)
        canv.bind_all('<MouseWheel>', lambda e: canv.yview_scroll(int(-e.delta/120),'units'))
        root.bind('<space>', lambda e: self.toggle_play())

        # 右面板
        f = self.rfont
        tk.Label(right, text="时间(秒):", font=f).pack(anchor='w')
        self.t_entry = tk.Entry(right, font=f); self.t_entry.insert(0,'0.0'); self.t_entry.pack(fill=tk.X)
        tk.Button(right, text="存关键帧", font=f, command=self.save_kf).pack(fill=tk.X, pady=4)
        ttk.Separator(right).pack(fill=tk.X, pady=4)
        tk.Label(right, text="▼ 文件(关键帧用JSON,训练用CSV)", font=f).pack(anchor='w')
        tk.Button(right, text="加载关键帧(JSON)", font=f, command=self.load_kf_json).pack(fill=tk.X, pady=1)
        tk.Button(right, text="保存关键帧(JSON)", font=f, command=self.save_kf_json).pack(fill=tk.X, pady=1)
        tk.Button(right, text="📂 导入CSV(测试已有)", font=f, command=self.import_csv).pack(fill=tk.X, pady=1)
        tk.Button(right, text="➕ 追加关键帧(合并)", font=f, command=self.append_kf_json).pack(fill=tk.X, pady=1)
        tk.Button(right, text="💾 导出CSV(训练)", font=f, command=self.export_csv).pack(fill=tk.X, pady=1)
        ttk.Separator(right).pack(fill=tk.X, pady=4)
        tk.Label(right, text="▼ 局部重置", font=f).pack(anchor='w')
        tk.Button(right, text="下身→站立", font=f, command=lambda: self.apply_subset(PRESET_STAND,{'下身'})).pack(fill=tk.X, pady=1)
        tk.Button(right, text="上身→抱架", font=f, command=lambda: self.apply_subset(PRESET_GUARD,{'上身'})).pack(fill=tk.X, pady=1)
        tk.Button(right, text="全部→站立", font=f, command=lambda: self.apply_subset(PRESET_STAND,{'下身','上身'})).pack(fill=tk.X, pady=1)
        tk.Button(right, text="全部归零", font=f, command=lambda: self.apply_subset({n:0.0 for n,_,_,_ in JOINTS},{'下身','上身'})).pack(fill=tk.X, pady=1)
        ttk.Separator(right).pack(fill=tk.X, pady=4)
        tk.Label(right, text="▼ 播放(空格=暂停)", font=f).pack(anchor='w')
        self.btn_play = tk.Button(right, text="▶ 播放预览", font=f, command=self.toggle_play); self.btn_play.pack(fill=tk.X, pady=1)
        tk.Button(right, text="⏹ 停止", font=f, command=self.stop_play).pack(fill=tk.X, pady=1)
        tk.Button(right, text="清空关键帧", font=f, command=self.clear_kf).pack(fill=tk.X, pady=1)
        ttk.Separator(right).pack(fill=tk.X, pady=4)
        self.kf_list = tk.Text(right, height=5, font=('TkDefaultFont',FONTSIZE)); self.kf_list.pack(fill=tk.BOTH, expand=True)

        self.apply_subset(PRESET_STAND, {'下身','上身'})
        self.viewer = mujoco.viewer.launch_passive(model, data)
        self.update_loop()

    # --- 滑块 ---
    def on_slide(self, name, v): self.val_lbls[name].config(text=f'{float(v):.0f}°')
    def reset_one(self, name): self.sliders[name].set(0.0); self.val_lbls[name].config(text='0°')
    def apply_subset(self, preset, groups):
        for n,_,_,_ in JOINTS:
            if BODY[n] in groups:
                v = preset.get(n,0.0); self.sliders[n].set(v); self.val_lbls[n].config(text=f'{v:.0f}°')
    def cur_pose(self): return {n: float(s.get()) for n,s in self.sliders.items()}
    def write_qpos(self, pose, root=None):
        if root is None: root = DEFAULT_ROOT
        data.qpos[0:3] = root[0:3]; data.qpos[3:7] = root[3:7]
        for n,adr,_,_ in JOINTS: data.qpos[adr] = np.radians(pose.get(n,0.0))
        mujoco.mj_forward(model, data)
    def set_pose_full(self, pose, root):
        for n,_,_,_ in JOINTS: self.sliders[n].set(pose.get(n,0.0))
        self.write_qpos(pose, root)

    # --- 关键帧 ---
    def save_kf(self):
        try: t = float(self.t_entry.get())
        except: t = 0.0
        pose = self.cur_pose()
        self.keyframes = [k for k in self.keyframes if abs(k[0]-t)>1e-3]
        self.keyframes.append((t, pose, list(DEFAULT_ROOT))); self.keyframes.sort(key=lambda x:x[0])
        self.refresh_list(); self.write_qpos(pose)
    def clear_kf(self): self.keyframes=[]; self.refresh_list()
    def refresh_list(self):
        self.kf_list.delete('1.0', tk.END)
        for t,_,_ in self.keyframes: self.kf_list.insert(tk.END, f"t={t:.2f}s\n")

    # --- JSON 关键帧(稀疏无损) ---
    def save_kf_json(self):
        path = filedialog.asksaveasfilename(initialdir=HERE, defaultextension='.json', filetypes=[('JSON','*.json')], title="保存关键帧")
        if not path: return
        out = [{'time':t, 'joints':pose, 'root':root} for t,pose,root in self.keyframes]
        json.dump(out, open(path,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
        messagebox.showinfo("完成", f"保存 {len(out)} 个关键帧(稀疏) → {os.path.basename(path)}")
    def load_kf_json(self):
        path = filedialog.askopenfilename(initialdir=HERE, filetypes=[('JSON','*.json')], title="加载关键帧")
        if not path: return
        try: data_in = json.load(open(path,encoding='utf-8'))
        except Exception as e: messagebox.showerror("失败",str(e)); return
        self.keyframes = [(d['time'], d['joints'], d['root']) for d in data_in]
        self.keyframes.sort(key=lambda x:x[0]); self.refresh_list()
        if self.keyframes: self.set_pose_full(self.keyframes[0][1], self.keyframes[0][2])
        messagebox.showinfo("完成", f"加载 {len(self.keyframes)} 个关键帧")

    def append_kf_json(self):
        """追加另一组关键帧(稀疏JSON), 时间偏移到当前末尾+0.5s, 用于合并多段。"""
        path = filedialog.askopenfilename(initialdir=HERE, filetypes=[('JSON','*.json')], title="追加关键帧(合并)")
        if not path: return
        try: data_in = json.load(open(path, encoding='utf-8'))
        except Exception as e: messagebox.showerror("失败", str(e)); return
        start_t = (max(t for t,_,_ in self.keyframes) + 0.5) if self.keyframes else 0.0
        for d in data_in:
            self.keyframes.append((d['time'] + start_t, d['joints'], d['root']))
        self.keyframes.sort(key=lambda x: x[0]); self.refresh_list()
        messagebox.showinfo("追加完成", f"追加 {len(data_in)} 个关键帧, 起始 t={start_t:.1f}s\n总共 {len(self.keyframes)} 个关键帧")

    # --- CSV ---
    def _csv_to_kfs(self, arr, start_t=0.0):
        kfs = []
        for i, row in enumerate(arr):
            t = start_t + i / FPS
            root = [float(row[0]),float(row[1]),float(row[2]),float(row[6]),float(row[3]),float(row[4]),float(row[5])]
            pose = {JOINTS[k][0]: float(np.degrees(row[7+k])) for k in range(len(JOINTS))}
            kfs.append((t, pose, root))
        return kfs
    def import_csv(self):
        path = filedialog.askopenfilename(initialdir=HERE, filetypes=[('CSV','*.csv')], title="导入CSV(覆盖当前)")
        if not path: return
        try: arr = np.loadtxt(path, delimiter=',')
        except Exception as e: messagebox.showerror("失败",str(e)); return
        self.keyframes = self._csv_to_kfs(arr); self.refresh_list()
        if self.keyframes: self.set_pose_full(self.keyframes[0][1], self.keyframes[0][2])
        messagebox.showinfo("完成", f"导入 {len(self.keyframes)} 帧 @ {FPS}fps")
    def append_csv(self):
        path = filedialog.askopenfilename(initialdir=HERE, filetypes=[('CSV','*.csv')], title="追加CSV(合并)")
        if not path: return
        try: arr = np.loadtxt(path, delimiter=',')
        except Exception as e: messagebox.showerror("失败",str(e)); return
        start_t = (max(t for t,_,_ in self.keyframes) + 0.5) if self.keyframes else 0.0
        self.keyframes += self._csv_to_kfs(arr, start_t)
        self.keyframes.sort(key=lambda x:x[0]); self.refresh_list()
        messagebox.showinfo("追加完成", f"追加 {len(arr)} 帧, 起始 t={start_t:.1f}s\n总共 {len(self.keyframes)} 帧")
    def export_csv(self):
        if len(self.keyframes) < 2: messagebox.showerror("错误","至少 2 个关键帧"); return
        path = filedialog.asksaveasfilename(initialdir=HERE, defaultextension='.csv', filetypes=[('CSV','*.csv')], title="导出CSV(训练)")
        if not path: return
        kfs = sorted(self.keyframes, key=lambda x:x[0]); dur = kfs[-1][0]
        def interp(t):
            for i in range(len(kfs)-1):
                t0,p0,r0 = kfs[i]; t1,p1,r1 = kfs[i+1]
                if t0<=t<=t1:
                    a = ease((t-t0)/max(t1-t0,1e-9))
                    return ([p0[n]+(p1[n]-p0[n])*a for n,_,_,_ in JOINTS],
                            [r0[k]+(r1[k]-r0[k])*a for k in range(7)])
            return ([kfs[-1][1][n] for n,_,_,_ in JOINTS], kfs[-1][2])
        rows = []
        for fi_n in range(int(dur*FPS)+1):
            pose_deg, root = interp(fi_n/FPS); rads = np.radians(pose_deg)
            rows.append([root[0],root[1],root[2], root[4],root[5],root[6],root[3]] + list(rads))
        np.savetxt(path, np.array(rows), delimiter=',', fmt='%.5f')
        messagebox.showinfo("完成", f"导出 {len(rows)} 帧 @ {FPS}fps → {os.path.basename(path)}")

    # --- 播放(暂停/停止) ---
    def toggle_play(self):
        if not self.playing:
            if len(self.keyframes) < 2: messagebox.showwarning("提示","至少 2 个关键帧"); return
            self.playing = True; self.paused = False; self.btn_play.config(text='⏸ 暂停')
            kfs = sorted(self.keyframes, key=lambda x:x[0]); dur = kfs[-1][0]
            def interp(t):
                for i in range(len(kfs)-1):
                    t0,p0,r0 = kfs[i]; t1,p1,r1 = kfs[i+1]
                    if t0<=t<=t1:
                        a = ease((t-t0)/max(t1-t0,1e-9))
                        return ({n:p0[n]+(p1[n]-p0[n])*a for n in p0}, [r0[k]+(r1[k]-r0[k])*a for k in range(7)])
                return (kfs[-1][1], kfs[-1][2])
            fi=[0]; nf=int(dur*FPS)
            def step():
                if not self.playing: return
                if fi[0] > nf:
                    self.playing=False; self.paused=False; self.btn_play.config(text='▶ 播放预览'); return
                if not self.paused:
                    t=fi[0]/FPS; pose,root=interp(t); self.set_pose_full(pose,root)
                    self.t_entry.delete(0,tk.END); self.t_entry.insert(0,f'{t:.2f}'); fi[0]+=1
                self.root.after(int(1000/FPS), step)
            step()
        elif self.paused:
            self.paused = False; self.btn_play.config(text='⏸ 暂停')
        else:
            self.paused = True; self.btn_play.config(text='▶ 继续')
    def stop_play(self):
        self.playing=False; self.paused=False; self.btn_play.config(text='▶ 播放预览')
        if self.keyframes: self.set_pose_full(self.keyframes[0][1], self.keyframes[0][2])

    def update_loop(self):
        if not self.playing: self.write_qpos(self.cur_pose())
        if self.viewer.is_running(): self.viewer.sync()
        self.root.after(30, self.update_loop)

if __name__ == '__main__':
    root = tk.Tk(); App(root); root.mainloop()
