# G1 MechDance - 宇树 G1 人形机器人武术/舞蹈动作编辑器

**项目地址**: https://github.com/Silence-313/g1-mechdance

基于 MuJoCo 物理引擎的 G1 人形机器人动作编排工具。通过 YAML 定义关键帧姿势，自动生成连续平滑轨迹，在仿真器中实时播放 29 自由度全身动作。

---

## 项目结构

```
g1-mechdance/
  run.bat                       # Windows 一键启动脚本
  main_player.py                # 动作播放器：读取舞蹈 YAML，MuJoCo 渲染播放
  tune_pose.py                  # Tkinter 调姿器：滑块实时调整关节，保存关键帧
  config/
    robot_g1_29dof.yaml         # 29 个关节的名称 -> 数组索引映射
  dances/
    demo_punch.yaml             # 范例动作：5 秒右臂出拳
    saved_poses.yaml            # 调姿器保存的关键帧片段（追加写入）
  src/
    __init__.py
    joint_map.py                # 关节名称与数组索引的互转
    trajectory.py               # 从 YAML 关键帧线性插值生成连续轨迹
    mujoco_native_backend.py    # 核心后端：直接调用 MuJoCo C API
    simulator_backend.py        # 真机后端：通过 unitree_sdk2 DDS 发送指令
```

---

## 环境要求

| 项目 | 要求 |
|---|---|
| 操作系统 | Windows / Linux（需图形界面用于 MuJoCo viewer） |
| Python | 3.8+ |
| MuJoCo | Python 绑定 + viewer |
| PyYAML | pip install pyyaml |
| MuJoCo 模型 | [unitree_mujoco](https://github.com/unitreerobotics/unitree_mujoco) 中的 G1 场景文件 |

### Python 依赖安装

```bash
pip install mujoco pyyaml
```

> tkinter 为 Python 标准库，通常无需额外安装。

### MuJoCo 模型路径

项目默认从 `../unitree_mujoco/unitree_robots/g1/scene_29dof.xml` 加载 G1 模型。确保 `g1_dance` 和 `unitree_mujoco` 在同一父目录下。

---

## 快速开始

### 方式一：一键播放范例动作

直接双击 `run.bat` 或运行：

```bash
D:\python\python.exe main_player.py
```

脚本会：
1. 加载 `dances/demo_punch.yaml`（5 秒右臂出拳动作）
2. 打开 MuJoCo 可视化窗口，显示 G1 机器人
3. 3 秒倒计时后自动播放动作
4. 播放结束后保持最终姿势

### 方式二：交互式调姿

```bash
D:\python\python.exe tune_pose.py
```

打开 Tkinter 图形界面：
- **左列**：腿部 + 腰部关节（15 个滑块）
- **右列**：双臂关节（14 个滑块）
- 拖动滑块实时驱动 MuJoCo 中的机器人
- 数值标签同步显示目标角度和真实角度（偏差过大时标红，提示物理碰撞阻碍）
- 点击「追加保存」将当前姿势追加到 `dances/saved_poses.yaml`

---

## 核心架构

### 数据流

```
YAML 关键帧  -->  TrajectoryGenerator  -->  MujocoNativeBackend  -->  MuJoCo 渲染
                      (线性插值)              (PD 控制器 + 物理引擎)
```

### 1. 关节映射 (joint_map.py)

`config/robot_g1_29dof.yaml` 定义了 G1 全部 29 个关节的名称和数组索引：

```
Legs (12):     左/右髋 pitch/roll/yaw, 膝, 踝 pitch/roll        [0-11]
Waist (3):     yaw, roll, pitch                                  [12-14]
Left Arm (7):  肩 pitch/roll/yaw, 肘, 腕 roll/pitch/yaw          [15-21]
Right Arm (7): 肩 pitch/roll/yaw, 肘, 腕 roll/pitch/yaw          [22-28]
```

`map_to_array()` 将带名称的关节字典转换为 29 维浮点数组。

### 2. 轨迹生成 (trajectory.py)

- 读取 YAML 中的 `keyframes` 列表，按时间排序
- 在两个相邻关键帧之间做**线性插值**
- `interpolate(t)`：给定时间 t，返回插值后的 29 维目标角度数组
- `total_time`：最后一个关键帧的时间，即动作总时长

### 3. MuJoCo 后端 (mujoco_native_backend.py)

直接调用 MuJoCo Python C API，不经过 DDS 通道，规避了 unitree_sdk2 在 Windows 上的安装困难。

**三种工作模式**：

| 模式 | 说明 | 适用场景 |
|---|---|---|
| `normal` | 虚拟悬挂（torso 施加向上的力抵消重力 + 弹簧阻尼维持高度） | 全身动作播放，防止机器人摔倒 |
| `anchored_physics` | 锁定底座位置，但肢体保留物理碰撞和重力 | 调姿器：安全地调试手臂/腿部姿势 |
| `kinematic` | 纯运动学模式，绕过物理引擎直接设关节角 | 快速预览，无物理真实性 |

**PD 控制器参数**：

```
Kp = 60.0      # 位置刚度
Kd = 1.5       # 速度阻尼
tau = Kp * (target - q) - Kd * dq
```

**控制频率**：
- 宏观控制周期：10ms（100Hz）
- 物理子步骤：2ms（500Hz），每个控制周期内迭代 5 次 MuJoCo 物理步

**虚拟悬挂力**（`normal` 模式）：
- 恒定向上力 = 机器人总质量 x 重力加速度，抵消重力
- 弹簧力 = 5000 x 高度误差，维持初始高度
- 阻尼力 = 200 x 垂直速度，防止震荡

### 4. 真机后端 (simulator_backend.py)

通过 unitree_sdk2 的 DDS 通信直接控制真实 G1 机器人：

- 发布 `rt/lowcmd` topic，消息类型 `unitree_hg::LowCmd_`
- 每个电机设置：mode=0x01（伺服）、目标角度 q、刚度 Kp=60、阻尼 Kd=1.5
- 控制周期与仿真一致：100Hz
- 附带 CRC32 校验

当前项目默认使用 MuJoCo 仿真后端，真机部署时切换到此类即可。

---

## 舞蹈 YAML 格式

完整范例见 `dances/demo_punch.yaml`，核心结构：

```yaml
keyframes:
  - time: 0.0         # 关键帧时间（秒）
    joints:           # 只需列出非零关节
      left_shoulder_pitch: 0.0
      right_elbow: 0.0
      waist_yaw: 0.0

  - time: 2.0         # 2 秒时的目标姿势
    joints:
      right_shoulder_pitch: -0.5
      right_elbow: 1.0
      waist_yaw: -0.2

  - time: 5.0         # 动作结束，恢复初始
    joints:
      right_shoulder_pitch: 0.0
      right_elbow: 0.0
      waist_yaw: 0.0
```

- 关节不写则默认 0.0 rad（零位 = 自然下垂）
- 关键帧之间自动线性插值
- 角度单位为弧度

---

## G1 关节参数

| 关节类别 | 数量 | 关节名称 |
|---|---|---|
| 左腿 | 6 | left_hip_pitch, left_hip_roll, left_hip_yaw, left_knee, left_ankle_pitch, left_ankle_roll |
| 右腿 | 6 | right_hip_pitch, right_hip_roll, right_hip_yaw, right_knee, right_ankle_pitch, right_ankle_roll |
| 腰部 | 3 | waist_yaw, waist_roll, waist_pitch |
| 左臂 | 7 | left_shoulder_pitch, left_shoulder_roll, left_shoulder_yaw, left_elbow, left_wrist_roll, left_wrist_pitch, left_wrist_yaw |
| 右臂 | 7 | right_shoulder_pitch, right_shoulder_roll, right_shoulder_yaw, right_elbow, right_wrist_roll, right_wrist_pitch, right_wrist_yaw |

速度限制：`velocity_scale: 0.2`，加速度限制：`acceleration_scale: 0.2`。

---

## 典型工作流

### 创作新舞蹈

1. **启动调姿器**：`python tune_pose.py`
2. **逐姿势调试**：拖动滑块调整每个关节角度，观察 MuJoCo 中的机器人姿态
3. **保存关键帧**：每调好一个姿势，填入动作批注并点击「追加保存」
4. **整理舞蹈文件**：将 `dances/saved_poses.yaml` 中的关键帧复制到新 YAML 文件，手动修改每个关键帧的 `time` 字段
5. **播放验证**：修改 `main_player.py` 中的 `dance_path` 指向新文件，运行播放

### 真机部署

1. 在仿真器中完成动作编排和验证
2. 将 `main_player.py` 中的 `MujocoNativeBackend` 替换为 `SimulatorBackend`
3. 通过以太网连接 G1 机器人
4. 设置正确的 DDS 通道参数（`domain_id=0, interface="enp3s0"`）

---

## 技术要点

- **避免摔倒**：`normal` 模式下的虚拟悬挂力模拟实验室测试环境，机器人底座悬空但高度锁定
- **碰撞检测**：`anchored_physics` 模式下底座锁死，但肢体间的物理碰撞和重力仍然生效，能真实反映关节限位冲突
- **实时反馈**：调姿器中数值标签会对比目标角度和真实角度，偏差 > 0.05 rad 时标红，帮助发现关节碰撞或限位问题
- **CRC 校验**：真机后端每次发送指令前计算 CRC32，确保数据完整性
- **跨平台**：核心逻辑（trajectory, joint_map）与平台无关，Windows 用 MuJoCo 仿真，Linux 可切换到真机后端

---

## 依赖项目

| 项目 | 用途 | 地址 |
|---|---|---|
| unitree_mujoco | G1 MJCF 模型文件 | https://github.com/unitreerobotics/unitree_mujoco |
| unitree_sdk2 | 真机 DDS 通信（可选） | https://github.com/unitreerobotics/unitree_sdk2 |
| MuJoCo | 物理引擎 | https://github.com/google-deepmind/mujoco |
