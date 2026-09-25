## 概述

**仓库地址**: https://github.com/unitreerobotics/unitree_sdk2

**最新版本**: v2.0.2 (2025-07-07) | **Stars**: 1.2k+ | **Forks**: 360+

unitree_sdk2 是宇树科技官方提供的第二代机器人软件开发工具包，基于 Cyclone DDS 实现底层通信，支持 C++ 开发。覆盖的机器人型号包括 **Go2、B2、B2W、H1、H2、G1** 等全线产品，支持高层语义 API（运动控制）和底层电机指令（直接关节控制）两个开发层级。

**Python 绑定**在独立仓库 [unitree_sdk2_python](https://github.com/unitreerobotics/unitree_sdk2_python) 中。

---

## 系统架构

SDK 采用五层分层设计，从上到下依次为：

| 层级 | 组件 | 职责 |
|---|---|---|
| 1 | High-Level Semantic APIs | 任务级命令：站立、行走、执行动作 |
| 2 | Robot Platform Clients | 各机型专用客户端实现 (G1, H1, B2, GO2 等) |
| 3 | Communication Wrappers | 类型安全的 C++ DDS 发布/订阅封装 |
| 4 | DDS Foundation | Cyclone DDS 实时发布-订阅通信 |
| 5 | Hardware Interfaces | 直接对接电机、传感器等硬件 |

用户可根据需求选择任意抽象层级进行开发。

---

## 环境要求

| 项目 | 要求 |
|---|---|
| 操作系统 | Ubuntu 20.04 LTS |
| CPU 架构 | aarch64 或 x86_64 |
| 编译器 | GCC 9.4.0+ |
| CMake | 3.10 及以上 |

### 安装系统依赖

```bash
sudo apt-get update
sudo apt-get install -y cmake g++ build-essential \
    libyaml-cpp-dev libeigen3-dev libboost-all-dev \
    libspdlog-dev libfmt-dev
```

---

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/unitreerobotics/unitree_sdk2.git
cd unitree_sdk2
```

### 2. 编译示例

```bash
mkdir build && cd build
cmake ..
make -j$(nproc)
```

编译完成后，60+ 个示例可执行文件位于 `build/bin/` 目录下。

### 3. 安装 SDK 到系统（供自有项目引用）

默认安装到系统路径：

```bash
mkdir build && cd build
cmake ..
sudo make install
```

指定安装路径（推荐 `/opt/unitree_robotics`）：

```bash
cmake .. -DCMAKE_INSTALL_PREFIX=/opt/unitree_robotics
sudo make install
```

自有项目引用 SDK 的 CMake 配置见 `example/cmake_sample/CMakeLists.txt`。

---

## DDS 通信机制

### Topic 命名

所有实时 topic 以 `rt/` 为前缀，采用分层命名：

```
rt/<功能>[/<左右侧>][/<子组件>]
```

### 核心 Topic 一览

| Topic | 消息类型 | 方向 | 说明 |
|---|---|---|---|
| rt/lowcmd | unitree_hg::LowCmd_ | 指令 | 底层电机控制指令（人形机器人） |
| rt/lowstate | unitree_hg::LowState_ | 状态 | 机器人状态反馈（电机、IMU、传感器） |
| rt/arm_sdk | unitree_hg::LowCmd_ | 指令 | 手臂单独控制指令 |
| rt/sportmodestate | unitree_go::SportModeState_ | 状态 | 四足运动模式状态 |
| rt/dex3/left/cmd | unitree_hg::HandCmd_ | 指令 | Dex3 左手控制指令 |
| rt/dex3/left/state | unitree_hg::HandState_ | 状态 | Dex3 左手状态反馈 |
| rt/dex3/right/cmd | unitree_hg::HandCmd_ | 指令 | Dex3 右手控制指令 |
| rt/dex3/right/state | unitree_hg::HandState_ | 状态 | Dex3 右手状态反馈 |
| rt/wirelesscontroller | unitree_go::WirelessController_ | 状态 | 无线手柄/摇杆输入 |
| rt/secondary_imu | unitree_hg::IMUState_ | 状态 | 辅助 IMU（H2 双 IMU 系统） |

### IDL 命名空间

- **unitree_hg** (Humanoid Generation)：G1、H1、H2、R1 等人形机器人
- **unitree_go**：Go2、B2、B2W、Go2W 等四足机器人

### 消息结构 (LowCmd_ 底层电机指令)

```cpp
struct LowCmd_ {
    uint8_t head[2];         // 帧头: 0xFE 0xEF
    uint8_t level_flag;      // 级别标志: 0xFF
    uint8_t gpio;            // GPIO
    MotorCmd_ motor_cmd[35]; // 电机指令数组 (G1 用 29 个)
    uint32_t crc;            // CRC32 校验
};

struct MotorCmd_ {
    uint8_t mode;  // 伺服模式: 0x01
    float q;        // 目标角度 (rad)
    float dq;       // 目标速度 (rad/s)
    float kp;       // 位置刚度
    float kd;       // 速度阻尼
    float tau;      // 前馈力矩
};
```

---

## 控制层级

### 高层控制 (High-Level / LocoClient)

通过 RPC 风格客户端 API 发任务级命令，机器人内部自行处理运动学与平衡。

```cpp
// 初始化
ChannelFactory::Instance()->Init(0, "enp3s0");
G1LocoClient client;
client.SetTimeout(10.0f);
client.Init();

// 执行任务
client.Damp();              // 阻尼模式
client.Start();             // 激活运动状态
client.Squat2StandUp();     // 蹲姿恢复站立
client.Move(0.3, 0, 0);    // 前进 0.3 m/s
client.WaveHand(0);         // 挥手动作
```

G1 支持的 FSM 命令：

| 命令 | FSM ID | 说明 |
|---|---|---|
| Damp() | 1 | 阻尼模式 |
| Start() | 500 | 激活运动控制 |
| StandUp() | - | 站起 |
| Squat2StandUp() | 706 | 蹲姿恢复站立 |
| Lie2StandUp() | 702 | 躺姿恢复站立 |
| Move(vx, vy, vyaw) | 7105 | 世界坐标系速度移动 |
| WaveHand(0/1) | Task | 挥手任务 |

### 底层控制 (Low-Level / 直接关节控制)

直接发送 LowCmd_ 到 `rt/lowcmd` topic，以 200-500 Hz 实时控制每个电机。

典型流程：

1. 初始化 DDS 通道
2. 创建 ChannelPublisher 发布者
3. 创建 ChannelSubscriber 订阅状态反馈
4. 主循环中以固定频率发送电机指令

```cpp
ChannelFactory::Instance()->Init(0, "enp3s0");
auto publisher = std::make_shared<ChannelPublisher<LowCmd_>>("rt/lowcmd");
auto subscriber = std::make_shared<ChannelSubscriber<LowState_>>("rt/lowstate");
publisher->Init();
subscriber->Init();

LowCmd_ cmd;
cmd.head[0] = 0xFE; cmd.head[1] = 0xEF;
cmd.level_flag = 0xFF;

for (int i = 0; i < 29; i++) {
    cmd.motor_cmd[i].mode = 0x01;   // 伺服模式
    cmd.motor_cmd[i].q = target_q[i];
    cmd.motor_cmd[i].dq = 0.0;
    cmd.motor_cmd[i].kp = 60.0;
    cmd.motor_cmd[i].kd = 1.5;
    cmd.motor_cmd[i].tau = 0.0;
}

cmd.crc = CRC32().Crc(cmd);
publisher->Write(cmd);
```

---

## Sim-to-Real 工作流

SDK 通过切换 DDS 通道参数实现仿真与真机无缝切换：

### 仿真模式

```cpp
// domain_id=1（区别于实物默认的 0），interface="lo"（本地回环）
ChannelFactory::Instance()->Init(1, "lo");
```

### 真机模式

```cpp
// domain_id=0，interface="enp3s0"（机器人连接的物理网卡）
ChannelFactory::Instance()->Init(0, "enp3s0");
```

### 命令行切换典型模式

```cpp
if (argc < 2) {
    ChannelFactory::Instance()->Init(1, "lo");     // 仿真
} else {
    ChannelFactory::Instance()->Init(0, argv[1]);   // 真机
}
```

运行：

```bash
./stand_go2              # 仿真模式
./stand_go2 enp3s0       # 真机模式
```

---

## 各机器人关键参数

| 机器人 | IDL 命名空间 | 关节数 | 手部 | 特殊说明 |
|---|---|---|---|---|
| G1 | unitree_hg | 29 | Dex3 (7电机/手) | rt/arm_sdk 独立手臂控制 |
| H1 | unitree_hg | - | - | 虚拟挂带调试模式 |
| H2 | unitree_hg | 31 | - | 双 IMU 系统 |
| Go2/B2 | unitree_go | 12 | - | SportModeState 反馈 |
| Go2W/B2W | unitree_go | - | - | 轮式 |

---

## Python SDK (独立仓库)

```bash
git clone https://github.com/unitreerobotics/unitree_sdk2_python.git
cd unitree_sdk2_python
pip install -e .
```

Python SDK 提供与 C++ SDK 一致的接口，示例包括 G1 高层/底层控制、Go2 运动模式等。

DDS 通信需要 CycloneDDS，如报错则设置环境变量：

```bash
export CYCLONEDDS_HOME=/path/to/cyclonedds
```

---

## MuJoCo 仿真集成 (unitree_mujoco)

宇树提供 [unitree_mujoco](https://github.com/unitreerobotics/unitree_mujoco) 项目，将 unitree_sdk2 与 MuJoCo 物理引擎集成：

```
unitree_mujoco/
  simulate/          # C++ 仿真器 (SDK + MuJoCo)
  simulate_python/   # Python 仿真器
  unitree_robots/    # 各机器人 MJCF 模型
  terrain_tool/      # 地形生成工具
  example/           # Sim-to-Real 例程
```

仿真配置 (`simulate/config.yaml`)：

```yaml
robot: "go2"
robot_scene: "scene.xml"
domain_id: 1             # DDS domain 区别于实物
interface: "lo"          # 本地回环
enable_elastic_band: 0   # H1 虚拟挂带
```

**与 g1_dance 的关系**：你的 g1_dance 直接调用 MuJoCo C API（跳过 DDS），更轻量、适合动作编辑调试。真机部署时需要改为通过 unitree_sdk2 的 DDS 通道发送指令。

---

## 参考资源

- 官方文档: https://support.unitree.com/home/zh/developer
- C++ SDK: https://github.com/unitreerobotics/unitree_sdk2
- Python SDK: https://github.com/unitreerobotics/unitree_sdk2_python
- MuJoCo 仿真: https://github.com/unitreerobotics/unitree_mujoco
- ROS2: https://github.com/unitreerobotics/unitree_ros2
