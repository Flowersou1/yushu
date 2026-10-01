# G1 Dance Studio

Windows 上一站式 **G1 动作编排 / MuJoCo 仿真 / 数据导出** 工具。

不需要 `unitree_mujoco` 的 DDS、Ubuntu 和复杂配置；本地 MuJoCo 即可完成关键帧调试与完整播放。

## 完整教程

请先看：**[使用教程.md](使用教程.md)**（编排 → 导出 → 服务器上真机）。  
官方对齐说明：[OFFICIAL_ALIGNMENT.md](OFFICIAL_ALIGNMENT.md)。

## 启动

```bat
cd g1_dance_studio
python app.py
```

或双击 `run.bat`。

依赖：

```bat
pip install mujoco pyyaml
```

## 能做什么

| 功能 | 说明 |
|------|------|
| 滑块调姿 | 29 DoF，带官方关节限位；可「仅上半身」 |
| 时间线关键帧 | 追加 / 更新 / 删除 / 上下移 / 按间隔重排时间 |
| 自动时间 | 新增帧按「自动间隔」递增，不用手写 1.00 |
| 加载到滑块 | 选中历史帧继续微调 |
| 左右镜像 | 左臂→右臂 / 右臂→左臂 |
| 完整仿真 | 锁定骨盆调姿、虚拟挂带、纯运动学、自由物理 |
| 播放 | 播放 / 暂停 / 停止回编辑 / 重播 / 倍速 |
| 导出 | YAML 动作、100Hz CSV 轨迹、关键帧表 CSV |

### MuJoCo 窗口快捷键

- `空格` 暂停 / 继续  
- `R` 重播  
- `S` 慢动作切换  

## 推荐工作流

1. 勾选 **锁定骨盆** + **仅上半身**（第一阶段舞蹈）  
2. 拖滑块摆造型 → 填名称 → **追加当前姿态**  
3. 多拍几帧 → **播放动作** 看插值  
4. 不满意：选中帧 → **加载到滑块** → 改完 **更新选中帧**  
5. **保存 YAML**；需要稠密数据时 **导出 CSV 轨迹**  

真机部署时，YAML/CSV 仍要接到你们服务器上的控制程序（见仓库根目录 `connection-guide.md`）。本工具解决的是「编排难、仿真麻烦」。

## 和 unitree_mujoco / 官方 SDK 的关系

| | unitree_mujoco | G1 Dance Studio |
|--|----------------|-----------------|
| 目标 | Sim2Real 底层 DDS 联调 | 动作设计与快速预览 |
| 环境 | 多在 Ubuntu + SDK2 | Windows + MuJoCo 即可 |
| 编排 | 无时间线 UI | 关键帧时间线 |
| 导出 | 需自己写 | YAML / CSV 一键 |
| 关节下标 | 官方 G1JointIndex | **同一套 0–28** |

日常编舞用 Studio；真机用官方通路播放：

```bash
# Ubuntu + 连上机器人后（推荐上半身 Arm SDK）
python play_real.py --iface enp6s0 --dance dances/demo_punch.yaml --path arm_sdk
```

对齐细节见 [OFFICIAL_ALIGNMENT.md](OFFICIAL_ALIGNMENT.md)。

## 目录

```
g1_dance_studio/
  app.py / studio.py     # 入口与主界面
  tune_pose.py           # 旧版独立调姿（保留）
  main_player.py         # 旧版独立播放（保留）
  config/                # 关节索引
  dances/                # 动作 YAML
  exports/               # 导出目录（自动创建）
  assets/g1/             # MJCF + 网格
  src/                   # joint_map / trajectory / backend
```
