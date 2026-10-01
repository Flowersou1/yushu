import os
import sys
import time
from src.joint_map import JointMap
from src.trajectory import TrajectoryGenerator
from src.mujoco_native_backend import MujocoNativeBackend, MUJOCO_AVAILABLE

def main():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    config_path = os.path.join(base_dir, "config", "robot_g1_29dof.yaml")
    dance_path = os.path.join(base_dir, "dances", "saved_poses.yaml")
    
    print(">>> 正在初始化武术动作播放器...")
    # 1. 加载关节映射
    joint_map = JointMap(config_path)
    
    # 2. 建立轨迹生成器
    dt = 0.01  # 控制频率 100Hz
    trajectory = TrajectoryGenerator.from_yaml(dance_path, joint_map, dt)
    
    # 3. 连接仿真器
    # 对于 Windows 用户，宇树官方 SDK 安装困难，我们使用直接调用 MuJoCo API 的后端
    xml_path = os.path.join(base_dir, "assets", "g1", "scene_29dof.xml")
    if not os.path.isfile(xml_path):  # 仓库布局：模型在根目录 g1/（打包版仍用内置 assets）
        xml_path = os.path.join(os.path.dirname(base_dir), "g1", "scene_29dof.xml")
    backend = MujocoNativeBackend(xml_path=xml_path, dt=dt)
    # 关闭虚拟挂带，进行真实的物理平衡倒地测试
    backend.use_virtual_wire = False
    
    total_time = trajectory.total_time
    print(f">>> 动作总时长: {total_time:.2f} 秒。控制频率: {1/dt} Hz。")
    print(">>> 准备就绪，3秒后自动开始播放动作...")
    for i in range(3, 0, -1):
        print(f">>> 倒计时 {i} ...")
        # 非阻塞等待，保持后端物理引擎可能需要的更新
        for _ in range(int(1.0 / dt)):
            backend.wait()
    
    print(">>> 动作播放中... (按 S 切换慢动作，按 R 重新开始，按空格暂停)")
    start_time = time.time()
    t = 0.0
    
    while True:
        # 如果用户关闭了画面窗口，自动退出程序
        if MUJOCO_AVAILABLE and hasattr(backend, 'viewer') and not backend.viewer.is_running():
            print(">>> 窗口已关闭，程序退出。")
            break
            
        # 处理重置请求
        if backend.reset_requested:
            t = 0.0
            backend.reset_requested = False
            # 重置到底盘的初始悬空/站立高度
            if hasattr(backend, 'anchor_qpos'):
                backend.data.qpos[0:7] = backend.anchor_qpos
            backend.data.qvel[:] = 0.0
            
            # 将所有关节瞬间恢复到初始角度
            target_q = trajectory.interpolate(0.0)
            backend.send_target_angles(target_q)
            if MUJOCO_AVAILABLE:
                for i in range(backend.num_motors):
                    backend.data.qpos[7+i] = target_q[i]
                    backend.data.qvel[6+i] = 0.0
        
        # a) 插值计算当前时间的关节角度
        if t <= total_time:
            target_q = trajectory.interpolate(t)
        else:
            # 动作结束，保持最后姿态
            target_q = trajectory.interpolate(total_time)
            
        # b) 发送给仿真器底层
        backend.send_target_angles(target_q)
        
        # 仅打印右肘部的角度，看看数值变化
        right_elbow_idx = joint_map.get_index("right_elbow")
        if not MUJOCO_AVAILABLE and int(t * 100) % 50 == 0:
            print(f"[Time {t:.2f}s] 右肘(Right Elbow) 目标角度: {target_q[right_elbow_idx]:.2f} rad")
            
        # c) 等待下一个周期
        backend.wait()
        
        # 只有在未暂停时才更新时间
        if not backend.paused:
            t += dt

if __name__ == "__main__":
    main()
