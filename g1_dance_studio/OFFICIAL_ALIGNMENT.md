# 与宇树官方资料对齐说明

对照本地仓库中的官方材料：

- `unitree_sdk2_python/example/g1/low_level/g1_low_level_example.py`
- `unitree_sdk2_python/example/g1/high_level/g1_arm7_sdk_dds_example.py`
- `g1_dance_studio/assets/g1/g1_joint_index_dds.md`
- 文档中心「基础运动开发」页面（网络受限时以 SDK 示例为准）

在线文档：  
https://support.unitree.com/home/zh/G1_developer/basic_motion_development

---

## 1. 已经对齐的部分

| 项目 | 官方 | 本仓库 Studio / 配置 |
|------|------|----------------------|
| IDL | G1 用 `unitree_hg` | `meta.idl: unitree_hg` |
| 电机数量 | 29 | 29 |
| 电机顺序 0–28 | `G1JointIndex` | `config/robot_g1_29dof.yaml` + `src/g1_official.py` **一致** |
| 角度单位 | rad | rad |
| MuJoCo actuator 顺序 | 与 LowCmd 一致 | 实测 0=`left_hip_pitch` … 28=`right_wrist_yaw` **一致** |
| 脚踝 PR/AB 双语义 | index 4/5、10/11 | 注释与 `G1JointIndex` 别名已写明 |
| 低层 Kp/Kd 表 | low_level 示例数组 | `KP_LOW_LEVEL` / `KD_LOW_LEVEL` |
| Arm SDK 增益 | kp=60, kd=1.5 | `KP_ARM_SDK` / `KD_ARM_SDK` |
| Arm SDK 使能 | `motor_cmd[29].q = 1` | `ArmSdkBackend.enable_arm_sdk` |
| 低层前释放运控 | `MotionSwitcherClient.ReleaseMode` | `LowCmdBackend` |
| 话题名 | `rt/lowcmd` / `rt/arm_sdk` / `rt/lowstate` | `g1_official.py` 常量 |
| 导出 | — | YAML `motor_q[i]`、CSV `q0..q28` 按官方 index |

**结论：动作数据的关节下标与官方 LowCmd 数组下标一致，可直接接到官方示例风格的发送循环。**

---

## 2. 刻意不同 / 尚未等同官方的部分

| 项目 | 官方真机 | 本 Studio（Windows 编排） | 说明 |
|------|----------|---------------------------|------|
| 运行环境 | Ubuntu + cyclonedds + 网卡 | 本地 MuJoCo，无 DDS | 编排与真机分离是设计选择 |
| 仿真 PD | 官方 LowCmd kp/kd | MuJoCo 内 Kp=300/Kd=10 | 仅视觉/轨迹预览，**不是**真机增益 |
| 控制周期 | lowcmd 2ms / arm_sdk 20ms | 编辑/预览 10ms | 真机播放用 `play_real.py` 官方周期 |
| 控制通路 | arm_sdk 或 lowcmd | 默认只仿真 | 真机用 `--path arm_sdk`（推荐） |
| 从当前姿态过渡 | 示例用 `low_state.q` 混合 | Studio 线性关键帧插值 | `play_real.py` 开头有 blend-in |
| mode_pr / mode_machine | low_level 必填 | 仿真可不涉及 | `LowCmdBackend` 已填 |
| 预置手臂动作 | `G1ArmActionClient` 握手等 | 无 | 那是高层原子动作，不是轨迹编舞 |

---

## 3. 官方推荐的舞蹈路径（第一阶段）

与你们流程文档一致，且与 `g1_arm7_sdk_dds_example.py` 一致：

```
机器人 Loco 站立平衡
    +
Python 只控 双臂 14 + 腰 3
    via  rt/arm_sdk
    motor_cmd[29].q = 1  使能
    结束时逐渐把 29 号置 0 释放
```

**不要**第一阶段就用 `rt/lowcmd` 控腿跳舞——官方 low_level 示例会先 `ReleaseMode`，你要自己负责全身平衡，必须吊装。

---

## 4. 数据如何接到官方发送格式

Studio 导出的每一帧：

```yaml
motor_q: [q0, q1, ..., q28]   # 下标 = G1JointIndex
```

对应官方发送（概念代码）：

```python
# Arm SDK（推荐舞蹈）
low_cmd.motor_cmd[29].q = 1.0
for j in arm_and_waist_indices:  # 12..28 中的官方 ARM_SDK_JOINTS
    low_cmd.motor_cmd[j].q = motor_q[j]
    low_cmd.motor_cmd[j].dq = 0.0
    low_cmd.motor_cmd[j].kp = 60.0
    low_cmd.motor_cmd[j].kd = 1.5
    low_cmd.motor_cmd[j].tau = 0.0
low_cmd.crc = crc.Crc(low_cmd)
pub_arm_sdk.Write(low_cmd)
```

或使用本仓库封装：

```bash
# 在已连接机器人的 Ubuntu 上
python play_real.py --iface enp6s0 --dance dances/demo_punch.yaml --path arm_sdk
```

---

## 5. 自检清单

- [x] `joints` 与 `G1JointIndex` 0–28 一致（`JointMap` 启动时 assert）
- [x] 导出含 `motor_q` / `q0..q28`
- [x] 真机 Arm SDK / LowCmd 后端按官方字段填写
- [ ] 在你的 EDU+ 固件上实测 `arm_sdk` 与 Loco 是否同时可用（**以现场固件为准**）
- [ ] 腰部 13/14 是否解锁（官方注释：腰锁死时 roll/pitch 无效）
- [ ] 23 DoF 时手腕 pitch/yaw 无效——确认机型是 29 DoF

---

## 6. 和「基础运动开发」文档的关系

该页通常覆盖：运动模式切换、LowCmd/LowState、电机顺序、安全注意。  
本仓库对齐方式是 **以 SDK 可运行示例为源码级真值**；网页若有修订，以你当前 SDK 版本 + 宇树技术支持为准。
