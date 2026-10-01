# G1 武术动作仿真（mechdance）

真人武术/舞蹈视频 → 动作提取 → Unitree G1 MuJoCo 仿真，团队协作项目。
本仓库包含：官方 G1 仿真模型、两套动作编排工具、以及全流程教程。

## 仓库结构

```
├── g1/                    宇树官方 G1 MuJoCo 模型（xml + STL 网格，勿改）
├── g1_dance/              动作编辑器 v4 —— 全身动作 / RL 训练 CSV 工作流
│   ├── choreographer.py   动作编排主脚本（滑块 GUI + 关键帧时间轴）
│   ├── make_motion.py     生成动作
│   ├── combine_routines.py 合并多段动作
│   ├── check_clip.py / verify_csv.py / render_ref.py  校验与渲染
│   ├── 技术要点.md
│   └── 组员编动作说明.md  ← 走这条线的组员从这里开始
├── g1_dance_studio/       G1 Dance Studio —— 图形化编舞，可直接上真机（Windows 可用）
│   ├── app.py / studio.py 工作室主程序（python app.py 或双击 run.bat）
│   ├── play_real.py       真机播放（默认 arm_sdk 只动腰+臂，带平滑接管/释放）
│   ├── 使用教程.md        ← 走这条线的组员从这里开始
│   └── OFFICIAL_ALIGNMENT.md  与官方 SDK / G1JointIndex 的对齐说明
├── docs/                  教程（按下面顺序读）
├── connection-guide.md    服务器 / 机器人连接与部署指南
└── THIRD_PARTY_NOTICES.txt
```

## 两套编排工具怎么选

| | g1_dance（动作编辑器 v4） | g1_dance_studio（Dance Studio） |
|--|--|--|
| 定位 | 全身动作（含根轨迹）→ RL 训练参考数据 | 上半身编舞为主 → 不训练、直接上真机播放 |
| 产出 | 50Hz 含根节点全轨迹 CSV（训练用）/ JSON 关键帧 | YAML（官方电机序 G1JointIndex）/ 100Hz CSV |
| 真机通路 | 服务器 RL 训练后部署（见 docs/） | `play_real.py`，默认 arm_sdk 安全通路 |
| 平台 | MuJoCo + 官方 unitree_mujoco 环境 | Windows + `pip install mujoco pyyaml` 即可 |
| 校验 | check_clip.py 碰撞检测 / verify_csv / hang_sim | 内置多模式仿真预览（锁骨盆/挂带/物理） |

两条线共用同一套官方关节序（G1JointIndex 0–28）和同一份官方模型（`g1_dance_studio`
直接引用根目录 `g1/`；单独拷出该文件夹使用时需一并带上模型）。
注意两边 CSV 列格式不同（编辑器的含根轨迹、Studio 的含表头），
暂不能直接互相套用校验脚本。

## 新组员上手顺序

1. `docs/g1-mechdance_指南.md` —— 项目总览
2. 按需选编排线：
   - 全身动作 / 训练数据线：`g1_dance/组员编动作说明.md`
   - 图形编舞 / 直接上真机线：`g1_dance_studio/使用教程.md`
3. `docs/团队教程_从零跑通G1武术仿真.md` —— 从零跑通完整仿真
4. 真机部署：`connection-guide.md`（服务器/机器人连接）+ `g1_dance_studio/play_real.py`
5. 进阶：`docs/GVHMR_容器部署与完整训练教程.md`（真人视频 → 动作捕捉 → 训练）、
   `docs/服务器RL筛选.md`（服务器 RL 环境筛选）、`docs/unitree_sdk2_指南.md`（官方 SDK）

## 环境与数据说明

- 仿真依赖 MuJoCo + 官方 `unitree_sdk2`（github.com/unitreerobotics/unitree_sdk2），
  离线包不再随仓库分发，请从官方仓库下载对应 release/分支。
- 训练数据、录屏、服务器环境快照为一次性产物，不入库；组员按教程在算力平台
  重新生成即可。
