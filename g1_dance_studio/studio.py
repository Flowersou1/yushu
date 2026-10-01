"""
G1 Dance Studio — 一站式动作编排 / 仿真 / 导出

相对 unitree_mujoco：
  - 不用 DDS / Ubuntu / 复杂配置，Windows 双击即可
  - 滑块调姿 + 时间线关键帧，所见即所得
  - 一键导出 YAML 动作 / 稠密 CSV 轨迹

快捷键（MuJoCo 窗口）：
  空格 暂停/继续   R 重播   S 慢动作切换
"""

from __future__ import annotations

import os
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from src.joint_map import JointMap
from src.mujoco_native_backend import MUJOCO_AVAILABLE, MujocoNativeBackend
from src.trajectory import TrajectoryGenerator


def app_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# Joint groups for UI
LEG_WAIST = [
    "left_hip_pitch",
    "left_hip_roll",
    "left_hip_yaw",
    "left_knee",
    "left_ankle_pitch",
    "left_ankle_roll",
    "right_hip_pitch",
    "right_hip_roll",
    "right_hip_yaw",
    "right_knee",
    "right_ankle_pitch",
    "right_ankle_roll",
    "waist_yaw",
    "waist_roll",
    "waist_pitch",
]
ARMS = [
    "left_shoulder_pitch",
    "left_shoulder_roll",
    "left_shoulder_yaw",
    "left_elbow",
    "left_wrist_roll",
    "left_wrist_pitch",
    "left_wrist_yaw",
    "right_shoulder_pitch",
    "right_shoulder_roll",
    "right_shoulder_yaw",
    "right_elbow",
    "right_wrist_roll",
    "right_wrist_pitch",
    "right_wrist_yaw",
]
UPPER_BODY = [
    "waist_yaw",
    "waist_roll",
    "waist_pitch",
] + ARMS


class DanceStudioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("G1 Dance Studio — 动作编排 / 仿真 / 导出")
        self.root.geometry("1180x780")
        self.root.minsize(1000, 640)

        self.base_dir = app_base_dir()
        self.config_path = os.path.join(self.base_dir, "config", "robot_g1_29dof.yaml")
        self.xml_path = os.path.join(self.base_dir, "assets", "g1", "scene_29dof.xml")
        self.dances_dir = os.path.join(self.base_dir, "dances")
        self.exports_dir = os.path.join(self.base_dir, "exports")
        os.makedirs(self.dances_dir, exist_ok=True)
        os.makedirs(self.exports_dir, exist_ok=True)

        self.joint_map = JointMap(self.config_path)
        self.dt = 0.01
        self.trajectory = TrajectoryGenerator(self.joint_map, dt=self.dt)
        self.current_file = None
        self.dirty = False

        self.sliders = {}  # name -> (scale, value_label)
        self.selected_index = None
        self.play_mode = False  # False=edit, True=play
        self.play_t = 0.0
        self.running = True
        self._syncing_sliders = False

        # Vars
        self.frame_name_var = tk.StringVar(value="关键帧")
        self.frame_time_var = tk.StringVar(value="0.00")
        self.interval_var = tk.StringVar(value="1.0")
        self.upper_only_var = tk.BooleanVar(value=False)
        self.lock_base_var = tk.BooleanVar(value=True)
        self.wire_var = tk.BooleanVar(value=True)
        self.kinematic_var = tk.BooleanVar(value=False)
        self.speed_var = tk.StringVar(value="1.0")
        self.status_var = tk.StringVar(value="就绪")
        self.time_var = tk.StringVar(value="t = 0.00 / 0.00 s")
        self.file_var = tk.StringVar(value="未保存的新动作")

        if not MUJOCO_AVAILABLE:
            messagebox.showerror("缺少依赖", "请先安装 mujoco：\npip install mujoco pyyaml")
            root.destroy()
            return

        mode = "anchored_physics"
        self.backend = MujocoNativeBackend(xml_path=self.xml_path, dt=self.dt, mode=mode)
        self.current_q = [0.0] * self.joint_map.num_joints

        self._build_ui()
        self._load_default_demo()

        self.sim_thread = threading.Thread(target=self._physics_loop, daemon=True)
        self.sim_thread.start()
        self._ui_tick()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ================================================================== UI
    def _build_ui(self):
        # --- menubar / top toolbar
        toolbar = ttk.Frame(self.root, padding=(8, 6))
        toolbar.pack(side=tk.TOP, fill=tk.X)

        for text, cmd in [
            ("新建", self.cmd_new),
            ("打开 YAML", self.cmd_open),
            ("保存", self.cmd_save),
            ("另存为", self.cmd_save_as),
            ("导出 CSV 轨迹", self.cmd_export_csv),
            ("导出关键帧表", self.cmd_export_table),
            ("导出真机脚本", self.cmd_export_player),
        ]:
            ttk.Button(toolbar, text=text, command=cmd).pack(side=tk.LEFT, padx=3)
        ttk.Label(
            toolbar,
            text="关节序=官方G1JointIndex | 真机推荐 arm_sdk",
        ).pack(side=tk.RIGHT, padx=6)

        ttk.Label(toolbar, textvariable=self.file_var).pack(side=tk.LEFT, padx=12)

        # --- transport
        transport = ttk.LabelFrame(self.root, text="播放 / 仿真模式", padding=8)
        transport.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 6))

        ttk.Button(transport, text="▶ 播放动作", command=self.cmd_play).pack(side=tk.LEFT, padx=3)
        ttk.Button(transport, text="⏸ 暂停", command=self.cmd_pause).pack(side=tk.LEFT, padx=3)
        ttk.Button(transport, text="⏹ 停止并回到编辑", command=self.cmd_stop_edit).pack(
            side=tk.LEFT, padx=3
        )
        ttk.Button(transport, text="⏮ 重播", command=self.cmd_replay).pack(side=tk.LEFT, padx=3)

        ttk.Label(transport, text="倍速").pack(side=tk.LEFT, padx=(12, 2))
        speed = ttk.Combobox(
            transport,
            textvariable=self.speed_var,
            values=["0.2", "0.5", "1.0", "1.5", "2.0"],
            width=5,
            state="readonly",
        )
        speed.pack(side=tk.LEFT)
        speed.bind("<<ComboboxSelected>>", lambda e: self._apply_speed())

        ttk.Checkbutton(
            transport,
            text="锁定骨盆(调姿)",
            variable=self.lock_base_var,
            command=self._apply_mode,
        ).pack(side=tk.LEFT, padx=8)
        ttk.Checkbutton(
            transport,
            text="虚拟挂带(自由站立时托举)",
            variable=self.wire_var,
            command=self._apply_mode,
        ).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(
            transport,
            text="纯运动学预览(无物理)",
            variable=self.kinematic_var,
            command=self._apply_mode,
        ).pack(side=tk.LEFT, padx=4)

        ttk.Label(transport, textvariable=self.time_var, width=22).pack(side=tk.RIGHT, padx=6)

        # --- main split
        main = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        main.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=4)

        left = ttk.Frame(main)
        right = ttk.Frame(main)
        main.add(left, weight=1)
        main.add(right, weight=2)

        self._build_timeline(left)
        self._build_sliders(right)

        # --- status
        status = ttk.Frame(self.root, padding=(8, 4))
        status.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(status, textvariable=self.status_var).pack(side=tk.LEFT)
        ttk.Label(
            status,
            text="MuJoCo 窗口: 空格暂停 | R 重播 | S 慢动作    建议：先关键帧 → 改时间 → 播放 → 导出",
        ).pack(side=tk.RIGHT)

    def _build_timeline(self, parent):
        box = ttk.LabelFrame(parent, text="时间线关键帧", padding=8)
        box.pack(fill=tk.BOTH, expand=True)

        cols = ("idx", "time", "name")
        self.tree = ttk.Treeview(box, columns=cols, show="headings", height=18, selectmode="browse")
        self.tree.heading("idx", text="#")
        self.tree.heading("time", text="时间(s)")
        self.tree.heading("name", text="名称")
        self.tree.column("idx", width=36, anchor=tk.CENTER)
        self.tree.column("time", width=70, anchor=tk.CENTER)
        self.tree.column("name", width=140, anchor=tk.W)
        scroll = ttk.Scrollbar(box, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._on_select_frame)

        form = ttk.Frame(parent, padding=(0, 8, 0, 0))
        form.pack(fill=tk.X)

        ttk.Label(form, text="名称").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(form, textvariable=self.frame_name_var, width=16).grid(
            row=0, column=1, padx=4, sticky=tk.W
        )
        ttk.Label(form, text="时间(s)").grid(row=0, column=2, sticky=tk.W)
        ttk.Entry(form, textvariable=self.frame_time_var, width=8).grid(
            row=0, column=3, padx=4, sticky=tk.W
        )
        ttk.Label(form, text="自动间隔").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(form, textvariable=self.interval_var, width=8).grid(
            row=1, column=1, padx=4, sticky=tk.W
        )

        btns = ttk.Frame(parent)
        btns.pack(fill=tk.X, pady=4)
        ttk.Button(btns, text="＋ 追加当前姿态", command=self.cmd_add_frame).pack(
            side=tk.LEFT, padx=2, pady=2
        )
        ttk.Button(btns, text="更新选中帧", command=self.cmd_update_frame).pack(
            side=tk.LEFT, padx=2, pady=2
        )
        ttk.Button(btns, text="加载到滑块", command=self.cmd_load_frame).pack(
            side=tk.LEFT, padx=2, pady=2
        )
        ttk.Button(btns, text="删除", command=self.cmd_delete_frame).pack(
            side=tk.LEFT, padx=2, pady=2
        )

        btns2 = ttk.Frame(parent)
        btns2.pack(fill=tk.X)
        ttk.Button(btns2, text="上移", command=lambda: self.cmd_move_frame(-1)).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btns2, text="下移", command=lambda: self.cmd_move_frame(1)).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btns2, text="重排时间(按间隔)", command=self.cmd_retime).pack(
            side=tk.LEFT, padx=2
        )

    def _build_sliders(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill=tk.X, pady=(0, 4))
        ttk.Checkbutton(
            top,
            text="仅上半身滑块(腿隐藏，更适合第一阶段舞蹈)",
            variable=self.upper_only_var,
            command=self._rebuild_slider_panels,
        ).pack(side=tk.LEFT)
        ttk.Button(top, text="全部归零", command=self.cmd_reset_sliders).pack(side=tk.LEFT, padx=8)
        ttk.Button(top, text="左臂→右臂镜像", command=self.cmd_mirror_l2r).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="右臂→左臂镜像", command=self.cmd_mirror_r2l).pack(side=tk.LEFT, padx=2)

        self.slider_host = ttk.Frame(parent)
        self.slider_host.pack(fill=tk.BOTH, expand=True)
        self._rebuild_slider_panels()

    def _rebuild_slider_panels(self):
        for w in self.slider_host.winfo_children():
            w.destroy()
        self.sliders.clear()

        canvas = tk.Canvas(self.slider_host, highlightthickness=0)
        vsb = ttk.Scrollbar(self.slider_host, orient=tk.VERTICAL, command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=inner, anchor=tk.NW)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        if self.upper_only_var.get():
            groups = [("腰部 + 双臂", UPPER_BODY)]
        else:
            groups = [("腿部 + 腰部", LEG_WAIST), ("双臂", ARMS)]

        col = 0
        for title, names in groups:
            frame = ttk.LabelFrame(inner, text=title, padding=6)
            frame.grid(row=0, column=col, sticky=tk.N, padx=6, pady=4)
            self._fill_joint_column(frame, names)
            col += 1

        # apply current_q to new sliders
        self._push_q_to_sliders(self.current_q)

    def _fill_joint_column(self, parent, names):
        for row, j_name in enumerate(names):
            ttk.Label(parent, text=j_name, width=18).grid(row=row, column=0, sticky=tk.W)
            lo, hi = self._joint_limits(j_name)
            scale = ttk.Scale(parent, from_=lo, to=hi, orient=tk.HORIZONTAL, length=200)
            scale.set(0.0)
            scale.grid(row=row, column=1, padx=4, pady=1)
            val_lbl = ttk.Label(parent, text="0.00", width=8)
            val_lbl.grid(row=row, column=2)
            ttk.Button(
                parent, text="0", width=3, command=lambda s=scale: s.set(0.0)
            ).grid(row=row, column=3)
            scale.configure(
                command=lambda v, n=j_name: self._on_slider(n, v)
            )
            self.sliders[j_name] = (scale, val_lbl)

    def _joint_limits(self, j_name):
        lo, hi = -3.14, 3.14
        if MUJOCO_AVAILABLE and self.backend.model is not None:
            import mujoco

            jid = mujoco.mj_name2id(self.backend.model, mujoco.mjtObj.mjOBJ_JOINT, j_name)
            if jid >= 0 and self.backend.model.jnt_limited[jid]:
                lo = float(self.backend.model.jnt_range[jid][0])
                hi = float(self.backend.model.jnt_range[jid][1])
        return lo, hi

    # ================================================================== timeline helpers
    def _refresh_tree(self, select=None):
        self.tree.delete(*self.tree.get_children())
        for i, kf in enumerate(self.trajectory.keyframes):
            self.tree.insert(
                "",
                tk.END,
                iid=str(i),
                values=(i, f"{kf['time']:.2f}", kf.get("name", "")),
            )
        if select is not None and 0 <= select < len(self.trajectory.keyframes):
            self.tree.selection_set(str(select))
            self.tree.see(str(select))
            self.selected_index = select
        self.time_var.set(
            f"t = {self.play_t:.2f} / {self.trajectory.total_time:.2f} s"
        )

    def _on_select_frame(self, _evt=None):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        self.selected_index = idx
        kf = self.trajectory.get_keyframe(idx)
        if not kf:
            return
        self.frame_name_var.set(kf.get("name", "关键帧"))
        self.frame_time_var.set(f"{kf['time']:.2f}")

    def _slider_joint_dict(self):
        d = {}
        for name, (scale, _) in self.sliders.items():
            d[name] = float(scale.get())
        # if upper-only, keep previous leg values from current_q
        if self.upper_only_var.get():
            full = list(self.current_q)
            for name, val in d.items():
                i = self.joint_map.get_index(name)
                if i >= 0:
                    full[i] = val
            return self.joint_map.array_to_dict(full, skip_near_zero=False)
        # merge with full current_q so hidden joints persist when rebuilt
        full = list(self.current_q)
        for name, val in d.items():
            i = self.joint_map.get_index(name)
            if i >= 0:
                full[i] = val
        return self.joint_map.array_to_dict(full, skip_near_zero=False)

    def _on_slider(self, name, val):
        if self._syncing_sliders:
            return
        v = float(val)
        idx = self.joint_map.get_index(name)
        if idx >= 0:
            self.current_q[idx] = v
        if name in self.sliders:
            self.sliders[name][1].config(text=f"{v:.2f}")
        if not self.play_mode:
            self.backend.send_target_angles(self.current_q)

    def _push_q_to_sliders(self, q):
        self._syncing_sliders = True
        try:
            for name, (scale, lbl) in self.sliders.items():
                idx = self.joint_map.get_index(name)
                if idx < 0:
                    continue
                v = float(q[idx])
                scale.set(v)
                lbl.config(text=f"{v:.2f}")
            self.current_q = list(q)
        finally:
            self._syncing_sliders = False

    def _mark_dirty(self):
        self.dirty = True
        label = self.file_var.get()
        if not label.startswith("*"):
            self.file_var.set("*" + label)

    def _set_file_label(self, path):
        self.current_file = path
        self.dirty = False
        self.file_var.set(os.path.basename(path) if path else "未保存的新动作")

    # ================================================================== commands
    def cmd_new(self):
        if self.dirty and not messagebox.askyesno("新建", "当前有未保存修改，确定丢弃？"):
            return
        self.trajectory = TrajectoryGenerator(self.joint_map, dt=self.dt)
        self.play_mode = False
        self.play_t = 0.0
        self.current_q = [0.0] * self.joint_map.num_joints
        self._push_q_to_sliders(self.current_q)
        self.backend.send_target_angles(self.current_q)
        self.backend.snap_to_targets()
        self._refresh_tree()
        self._set_file_label(None)
        self.status_var.set("已新建空白动作")

    def cmd_open(self):
        path = filedialog.askopenfilename(
            title="打开动作 YAML",
            initialdir=self.dances_dir,
            filetypes=[("YAML", "*.yaml *.yml"), ("All", "*.*")],
        )
        if not path:
            return
        try:
            self.trajectory = TrajectoryGenerator.from_yaml(path, self.joint_map, dt=self.dt)
            self.play_mode = False
            self.play_t = 0.0
            if self.trajectory.keyframes:
                q = self.trajectory.keyframes[0].get("_q") or self.trajectory.interpolate(0)
                self._push_q_to_sliders(q)
                self.backend.send_target_angles(q)
                self.backend.snap_to_targets()
            self._refresh_tree(select=0 if self.trajectory.keyframes else None)
            self._set_file_label(path)
            self.status_var.set(f"已打开 {os.path.basename(path)}（{len(self.trajectory.keyframes)} 帧）")
        except Exception as e:
            messagebox.showerror("打开失败", str(e))

    def cmd_save(self):
        if not self.current_file:
            return self.cmd_save_as()
        try:
            self.trajectory.save_yaml(self.current_file, sparse=False)
            self._set_file_label(self.current_file)
            self.status_var.set(f"已保存 {self.current_file}")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def cmd_save_as(self):
        path = filedialog.asksaveasfilename(
            title="保存动作 YAML",
            initialdir=self.dances_dir,
            defaultextension=".yaml",
            initialfile="my_dance.yaml",
            filetypes=[("YAML", "*.yaml"), ("All", "*.*")],
        )
        if not path:
            return
        try:
            self.trajectory.save_yaml(path, sparse=False)
            self._set_file_label(path)
            self.status_var.set(f"已保存 {path}")
            messagebox.showinfo("保存成功", f"动作已保存到：\n{path}")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def cmd_export_csv(self):
        if not self.trajectory.keyframes:
            messagebox.showwarning("导出", "还没有关键帧")
            return
        path = filedialog.asksaveasfilename(
            title="导出稠密轨迹 CSV",
            initialdir=self.exports_dir,
            defaultextension=".csv",
            initialfile="trajectory_100hz.csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        try:
            self.trajectory.export_csv(path, hz=100)
            self.status_var.set(f"已导出 CSV: {path}")
            messagebox.showinfo(
                "导出成功",
                f"100Hz 轨迹已导出：\n{path}\n\n可用于分析或下游控制程序读取。",
            )
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def cmd_export_table(self):
        if not self.trajectory.keyframes:
            messagebox.showwarning("导出", "还没有关键帧")
            return
        path = filedialog.asksaveasfilename(
            title="导出关键帧表 CSV",
            initialdir=self.exports_dir,
            defaultextension=".csv",
            initialfile="keyframes.csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        try:
            self.trajectory.export_joint_table(path)
            self.status_var.set(f"已导出关键帧表: {path}")
            messagebox.showinfo("导出成功", path)
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def cmd_export_player(self):
        """Export standalone arm_sdk player .py (official example style)."""
        if not self.trajectory.keyframes:
            messagebox.showwarning("导出", "还没有关键帧")
            return
        default_name = "my_dance"
        if self.current_file:
            default_name = os.path.splitext(os.path.basename(self.current_file))[0]
        path = filedialog.asksaveasfilename(
            title="导出真机 Arm-SDK 播放脚本",
            initialdir=self.exports_dir,
            defaultextension=".py",
            initialfile=f"{default_name}_arm_sdk_player.py",
            filetypes=[("Python", "*.py")],
        )
        if not path:
            return
        try:
            from src.export_arm_sdk_script import export_arm_sdk_player

            export_arm_sdk_player(
                self.trajectory,
                path,
                dance_name=default_name,
                source_yaml=self.current_file or "",
            )
            self.status_var.set(f"已导出真机脚本: {path}")
            messagebox.showinfo(
                "导出成功",
                f"已生成官方风格 arm_sdk 播放脚本：\n{path}\n\n"
                f"上传到服务器后运行：\n"
                f"python3 {os.path.basename(path)} enp6s0\n\n"
                f"详见 使用教程.md",
            )
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def cmd_add_frame(self):
        try:
            interval = float(self.interval_var.get())
        except ValueError:
            interval = 1.0
        # if user typed a time, use it; else auto
        time_str = self.frame_time_var.get().strip()
        try:
            # When adding, prefer auto next unless list empty and time is 0
            if self.trajectory.keyframes:
                t = self.trajectory.next_auto_time(interval)
            else:
                t = float(time_str) if time_str else 0.0
        except ValueError:
            t = self.trajectory.next_auto_time(interval)

        name = self.frame_name_var.get().strip() or "关键帧"
        joints = self._slider_joint_dict()
        self.trajectory.add_keyframe(t, joints, name=name)
        self._refresh_tree(select=len(self.trajectory.keyframes) - 1)
        self.frame_time_var.set(f"{self.trajectory.next_auto_time(interval):.2f}")
        self.frame_name_var.set(f"关键帧{len(self.trajectory.keyframes) + 1}")
        self._mark_dirty()
        self.status_var.set(f"已追加关键帧 @ {t:.2f}s「{name}」")

    def cmd_update_frame(self):
        if self.selected_index is None:
            messagebox.showinfo("提示", "请先在时间线选中一帧")
            return
        try:
            t = float(self.frame_time_var.get())
        except ValueError:
            messagebox.showerror("错误", "时间必须是数字")
            return
        name = self.frame_name_var.get().strip() or "关键帧"
        joints = self._slider_joint_dict()
        self.trajectory.update_keyframe(self.selected_index, time_s=t, joints=joints, name=name)
        # re-find by time after sort
        self._refresh_tree()
        self._mark_dirty()
        self.status_var.set(f"已更新关键帧「{name}」")

    def cmd_load_frame(self):
        if self.selected_index is None:
            messagebox.showinfo("提示", "请先选中一帧")
            return
        kf = self.trajectory.get_keyframe(self.selected_index)
        if not kf:
            return
        q = kf.get("_q") or self.joint_map.map_to_array(kf["joints"])
        self.play_mode = False
        self.backend.paused = False
        self._push_q_to_sliders(q)
        self.backend.send_target_angles(q)
        self.backend.snap_to_targets()
        self.status_var.set(f"已加载帧 #{self.selected_index}「{kf.get('name', '')}」到滑块")

    def cmd_delete_frame(self):
        if self.selected_index is None:
            return
        if not messagebox.askyesno("删除", f"删除第 {self.selected_index} 帧？"):
            return
        self.trajectory.delete_keyframe(self.selected_index)
        self.selected_index = None
        self._refresh_tree()
        self._mark_dirty()
        self.status_var.set("已删除关键帧")

    def cmd_move_frame(self, direction):
        if self.selected_index is None:
            return
        i = self.selected_index
        j = i + direction
        kfs = self.trajectory.keyframes
        if not (0 <= j < len(kfs)):
            return
        # swap times so order changes after sort, or swap list then retime?
        # Swap list entries and swap their times to preserve chronology intent
        kfs[i], kfs[j] = kfs[j], kfs[i]
        kfs[i]["time"], kfs[j]["time"] = kfs[j]["time"], kfs[i]["time"]
        self.trajectory._densify()
        self._refresh_tree(select=j)
        self._mark_dirty()

    def cmd_retime(self):
        try:
            interval = float(self.interval_var.get())
        except ValueError:
            interval = 1.0
        for i, kf in enumerate(self.trajectory.keyframes):
            kf["time"] = round(i * interval, 3)
        self.trajectory._densify()
        self._refresh_tree(select=self.selected_index)
        self._mark_dirty()
        self.status_var.set(f"已按间隔 {interval}s 重排时间")

    def cmd_reset_sliders(self):
        z = [0.0] * self.joint_map.num_joints
        self._push_q_to_sliders(z)
        self.backend.send_target_angles(z)
        if not self.play_mode:
            self.backend.snap_to_targets()

    def cmd_mirror_l2r(self):
        d = self._slider_joint_dict()
        d = self.joint_map.mirror_left_to_right(d)
        q = self.joint_map.map_to_array(d)
        self._push_q_to_sliders(q)
        self.backend.send_target_angles(q)
        self.status_var.set("已镜像：左 → 右")

    def cmd_mirror_r2l(self):
        d = self._slider_joint_dict()
        d = self.joint_map.mirror_right_to_left(d)
        q = self.joint_map.map_to_array(d)
        self._push_q_to_sliders(q)
        self.backend.send_target_angles(q)
        self.status_var.set("已镜像：右 → 左")

    def cmd_play(self):
        if not self.trajectory.keyframes:
            messagebox.showwarning("播放", "请先添加关键帧")
            return
        self.play_mode = True
        self.backend.paused = False
        if self.play_t >= self.trajectory.total_time:
            self.play_t = 0.0
        self._apply_mode()
        self._apply_speed()
        self.status_var.set("播放中…（可在 MuJoCo 窗口用空格暂停）")

    def cmd_pause(self):
        self.backend.paused = not self.backend.paused
        self.status_var.set("已暂停" if self.backend.paused else "继续播放")

    def cmd_stop_edit(self):
        self.play_mode = False
        self.backend.paused = False
        self.play_t = 0.0
        self._apply_mode()
        self.backend.send_target_angles(self.current_q)
        self.backend.snap_to_targets()
        self.backend.reset_root()
        self.status_var.set("已停止，回到编辑模式")
        self.time_var.set(f"t = 0.00 / {self.trajectory.total_time:.2f} s")

    def cmd_replay(self):
        self.play_t = 0.0
        self.backend.reset_requested = False
        self.backend.paused = False
        self.play_mode = True
        self.backend.reset_root()
        q0 = self.trajectory.interpolate(0.0)
        self.backend.send_target_angles(q0)
        self.backend.snap_to_targets()
        self.status_var.set("重播")

    def _apply_speed(self):
        try:
            self.backend.playback_speed = float(self.speed_var.get())
        except ValueError:
            self.backend.playback_speed = 1.0

    def _apply_mode(self):
        if self.kinematic_var.get():
            self.backend.set_mode("kinematic")
        elif self.lock_base_var.get() and not self.play_mode:
            self.backend.set_mode("anchored_physics")
        elif self.lock_base_var.get() and self.play_mode:
            # while playing with lock: still anchored for safe upper-body review
            self.backend.set_mode("anchored_physics")
        else:
            self.backend.set_mode("normal")
        self.backend.set_virtual_wire(self.wire_var.get())

    def _load_default_demo(self):
        demo = os.path.join(self.dances_dir, "demo_punch.yaml")
        saved = os.path.join(self.dances_dir, "saved_poses.yaml")
        path = demo if os.path.isfile(demo) else (saved if os.path.isfile(saved) else None)
        if not path:
            self._refresh_tree()
            return
        try:
            self.trajectory = TrajectoryGenerator.from_yaml(path, self.joint_map, dt=self.dt)
            if self.trajectory.keyframes:
                q = self.trajectory.keyframes[0].get("_q") or self.trajectory.interpolate(0)
                self._push_q_to_sliders(q)
                self.backend.send_target_angles(q)
                self.backend.snap_to_targets()
            self._refresh_tree(select=0 if self.trajectory.keyframes else None)
            self._set_file_label(path)
            self.status_var.set(f"已加载示例 {os.path.basename(path)}")
        except Exception as e:
            print("加载示例失败:", e)
            self._refresh_tree()

    # ================================================================== loops
    def _physics_loop(self):
        while self.running:
            if not self.backend.is_viewer_alive():
                # viewer closed — keep process until UI closes
                time.sleep(0.05)
                continue

            if self.backend.reset_requested:
                self.backend.reset_requested = False
                self.play_t = 0.0
                self.backend.reset_root()
                if self.trajectory.keyframes:
                    q = self.trajectory.interpolate(0.0)
                    self.backend.send_target_angles(q)
                    self.backend.snap_to_targets()

            if self.play_mode and self.trajectory.keyframes:
                if not self.backend.paused:
                    total = self.trajectory.total_time
                    q = self.trajectory.interpolate(min(self.play_t, total))
                    self.backend.send_target_angles(q)
                    self.play_t += self.dt
                    if self.play_t > total + 0.5:
                        # hold last pose
                        self.play_t = total
            else:
                self.backend.send_target_angles(self.current_q)

            self.backend.wait()

    def _ui_tick(self):
        if not self.running:
            return
        self.time_var.set(f"t = {self.play_t:.2f} / {self.trajectory.total_time:.2f} s")
        # while playing, optionally reflect angles on labels without fighting user
        if self.play_mode and self.trajectory.keyframes:
            q = self.trajectory.interpolate(min(self.play_t, self.trajectory.total_time))
            # update value labels only
            for name, (scale, lbl) in self.sliders.items():
                idx = self.joint_map.get_index(name)
                if idx >= 0:
                    lbl.config(text=f"{q[idx]:.2f}")
        self.root.after(100, self._ui_tick)

    def _on_close(self):
        if self.dirty and not messagebox.askyesno("退出", "有未保存修改，确定退出？"):
            return
        self.running = False
        try:
            self.backend.close()
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    # nicer default font on Windows
    try:
        root.option_add("*Font", "Segoe UI 10")
    except Exception:
        pass
    DanceStudioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
