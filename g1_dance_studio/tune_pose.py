import os
import sys
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import threading
import time

from src.joint_map import JointMap
from src.mujoco_native_backend import MujocoNativeBackend, MUJOCO_AVAILABLE

class PoseTunerApp:
    def __init__(self, root, joint_map, backend):
        self.root = root
        self.joint_map = joint_map
        self.backend = backend
        self.root.title("G1 全身姿态调试器 (29 DoF)")
        
        # 分组关注的关节列表
        self.leg_waist_joints = [
            "left_hip_pitch", "left_hip_roll", "left_hip_yaw", "left_knee", "left_ankle_pitch", "left_ankle_roll",
            "right_hip_pitch", "right_hip_roll", "right_hip_yaw", "right_knee", "right_ankle_pitch", "right_ankle_roll",
            "waist_yaw", "waist_roll", "waist_pitch"
        ]
        
        self.arm_joints = [
            "left_shoulder_pitch", "left_shoulder_roll", "left_shoulder_yaw", "left_elbow", "left_wrist_roll", "left_wrist_pitch", "left_wrist_yaw",
            "right_shoulder_pitch", "right_shoulder_roll", "right_shoulder_yaw", "right_elbow", "right_wrist_roll", "right_wrist_pitch", "right_wrist_yaw"
        ]
        
        self.active_joints = self.leg_waist_joints + self.arm_joints
        
        self.sliders = {}
        self.current_q = [0.0] * self.joint_map.num_joints
        
        self.create_widgets()
        
        # 启动后台物理更新线程
        self.running = True
        self.sim_thread = threading.Thread(target=self.physics_loop)
        self.sim_thread.daemon = True
        self.sim_thread.start()
        
        # 启动 UI 轮询更新，用于显示实际角度和标红
        self.ui_update_loop()

    def build_joint_column(self, parent_frame, joint_list):
        row_idx = 0
        for j_name in joint_list:
            ttk.Label(parent_frame, text=j_name, width=18).grid(row=row_idx, column=0, sticky=tk.W)
            
            # 从 MuJoCo 模型中动态获取官方的关节极限角度
            limit_min = -3.14
            limit_max = 3.14
            if MUJOCO_AVAILABLE:
                import mujoco
                joint_id = mujoco.mj_name2id(self.backend.model, mujoco.mjtObj.mjOBJ_JOINT, j_name)
                if joint_id >= 0 and self.backend.model.jnt_limited[joint_id]:
                    limit_min = self.backend.model.jnt_range[joint_id][0]
                    limit_max = self.backend.model.jnt_range[joint_id][1]
            
            # 建立滑块，应用官方上下限
            slider = ttk.Scale(parent_frame, from_=limit_min, to=limit_max, orient=tk.HORIZONTAL, length=200)
            slider.set(0.0)
            slider.grid(row=row_idx, column=1, padx=5, pady=2)
            
            # 数值显示: "目标 (实际)"
            val_label = ttk.Label(parent_frame, text="0.00 (0.00)", width=16)
            val_label.grid(row=row_idx, column=2)
            
            # 重置按钮
            reset_btn = ttk.Button(parent_frame, text="复位", width=4,
                                   command=lambda s=slider: s.set(0.0))
            reset_btn.grid(row=row_idx, column=3, padx=2)
            
            self.sliders[j_name] = (slider, val_label)
            
            # 绑定滑动事件
            slider.configure(command=lambda val, name=j_name: self.on_slider_change(name, val))
            
            row_idx += 1

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(main_frame, text="拖动滑块实时调整关节角度 (rad)，点击复位归零", 
                  font=("Helvetica", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 10))
        
        # 分为左右两列
        left_frame = ttk.LabelFrame(main_frame, text="腿部与腰部", padding="5")
        left_frame.grid(row=1, column=0, padx=10, sticky=tk.N)
        
        right_frame = ttk.LabelFrame(main_frame, text="双臂", padding="5")
        right_frame.grid(row=1, column=1, padx=10, sticky=tk.N)
        
        self.build_joint_column(left_frame, self.leg_waist_joints)
        self.build_joint_column(right_frame, self.arm_joints)
            
        # 打印 YAML 按钮与全局复位按钮
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=2, column=0, columnspan=2, pady=15)
        
        # 底盘锁定开关
        self.lock_base_var = tk.BooleanVar(value=True)
        chk = ttk.Checkbutton(bottom_frame, text="锁定底盘 (松开可进行物理平衡测试)", 
                              variable=self.lock_base_var, command=self.toggle_anchor)
        chk.pack(side=tk.LEFT, padx=10)
        
        # 挂带开关
        self.wire_var = tk.BooleanVar(value=True)
        chk_wire = ttk.Checkbutton(bottom_frame, text="开启虚拟挂带", 
                                   variable=self.wire_var, command=self.toggle_wire)
        chk_wire.pack(side=tk.LEFT, padx=10)
        
        ttk.Button(bottom_frame, text="全局复位 (归零)", 
                   command=self.reset_all).pack(side=tk.LEFT, padx=10)
                   
        self.annotation_var = tk.StringVar(value="关键帧")
        ttk.Label(bottom_frame, text="动作批注:").pack(side=tk.LEFT, padx=(10, 2))
        ttk.Entry(bottom_frame, textvariable=self.annotation_var, width=20).pack(side=tk.LEFT)
                   
        ttk.Button(bottom_frame, text="追加保存 (YAML)", 
                   command=self.print_yaml).pack(side=tk.LEFT, padx=(2, 10))
        
    def toggle_anchor(self):
        if self.lock_base_var.get():
            # 开启锁定：拉回锚点
            self.backend.data.qpos[0:7] = self.backend.anchor_qpos
            self.backend.data.qvel[0:6] = 0.0
            self.backend.mode = "anchored_physics"
        else:
            # 取消锁定：恢复真实重力坠落
            self.backend.mode = "normal"
            
    def toggle_wire(self):
        self.backend.use_virtual_wire = self.wire_var.get()
            
    def reset_all(self):
        for j_name in self.active_joints:
            self.sliders[j_name][0].set(0.0)
            
    def on_slider_change(self, j_name, val):
        val_float = float(val)
        # 不在这里更新 text，交给 ui_update_loop 统一刷新
        
        # 更新目标数组
        idx = self.joint_map.get_index(j_name)
        if idx >= 0:
            self.current_q[idx] = val_float
            
    def ui_update_loop(self):
        if not self.running:
            return
            
        for j_name in self.active_joints:
            slider, label = self.sliders[j_name]
            target_val = float(slider.get())
            
            idx = self.joint_map.get_index(j_name)
            if idx >= 0:
                # 从底层获取真实角度
                actual_val = self.backend.data.qpos[7 + idx]
                
                # 如果真实角度与目标角度偏差超过 0.05 rad (约3度)，说明物理碰撞阻挡了关节运动，或者还没转到位
                if abs(target_val - actual_val) > 0.05:
                    label.config(text=f"{target_val:.2f} ({actual_val:.2f})", foreground="red")
                else:
                    label.config(text=f"{target_val:.2f} ({actual_val:.2f})", foreground="black")
                    
        # 50毫秒后再次刷新
        self.root.after(50, self.ui_update_loop)
            
    def physics_loop(self):
        """后台线程：不断将当前设定的角度发送给 MuJoCo"""
        while self.running:
            self.backend.send_target_angles(self.current_q)
            self.backend.wait()

    def print_yaml(self):
        annotation = self.annotation_var.get().strip()
        if not annotation:
            annotation = "关键帧"
            
        lines = []
        lines.append(f"  - time: 1.00  # <--- 【{annotation}】 请在此修改对应时间")
        lines.append("    joints:")
        for j_name in self.active_joints:
            val = float(self.sliders[j_name][0].get())
            if abs(val) > 0.001:
                lines.append(f"      {j_name}: {val:.3f}")
        yaml_content = "\n".join(lines)
        
        print("\n# === 保存的姿态 ===")
        print(yaml_content)
        print("# ==================\n")
        
        # 写入文件，即使是被打包，舞蹈文件也应该保存在真实目录下的 dances 文件夹
        # 获取真正的执行目录，而不是临时解压目录
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
        else:
            exe_dir = os.path.dirname(os.path.abspath(__file__))
            
        save_dir = os.path.join(exe_dir, "dances")
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, "saved_poses.yaml")
        
        try:
            with open(save_path, "a", encoding="utf-8") as f:
                f.write(yaml_content + "\n\n")
            messagebox.showinfo("保存成功", f"当前姿态已成功追加保存到文件：\n{save_path}")
        except Exception as e:
            messagebox.showerror("保存失败", f"无法保存文件：\n{e}")


def main():
    if not MUJOCO_AVAILABLE:
        print("必须安装 mujoco 库才能运行调姿器！")
        return
        
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    config_path = os.path.join(base_dir, "config", "robot_g1_29dof.yaml")
    xml_path = os.path.join(base_dir, "assets", "g1", "scene_29dof.xml")
    
    joint_map = JointMap(config_path)
    # 使用锚定物理模式 (anchored_physics)，开启物理引擎与碰撞，但锁死机器人底盘使其悬浮固定
    backend = MujocoNativeBackend(xml_path=xml_path, dt=0.01, mode="anchored_physics")
    
    # 启动 Tkinter
    root = tk.Tk()
    app = PoseTunerApp(root, joint_map, backend)
    
    # 当关掉窗口时退出程序
    def on_closing():
        app.running = False
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
