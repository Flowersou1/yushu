# G1 武术动作仿真（mechdance）

真人武术/舞蹈视频 → 动作提取 → Unitree G1 MuJoCo 仿真，团队协作项目。
本仓库包含：官方 G1 仿真模型、动作编排工具脚本、以及全流程教程。

## 仓库结构

```
├── g1/                    宇树官方 G1 MuJoCo 模型（xml + STL 网格，勿改）
├── g1_dance/              动作编排工具（组员日常用这个）
│   ├── choreographer.py   动作编排主脚本
│   ├── make_motion.py     生成动作
│   ├── combine_routines.py 合并多段动作
│   ├── check_clip.py / verify_csv.py / render_ref.py  校验与渲染
│   ├── 技术要点.md
│   └── 组员编动作说明.md  ← 新组员从这里开始
├── docs/                  教程（按下面顺序读）
└── 第三方声明 THIRD_PARTY_NOTICES.txt
```

## 新组员上手顺序

1. `docs/g1-mechdance_指南.md` —— 项目总览
2. `g1_dance/组员编动作说明.md` —— 怎么编自己的动作
3. `docs/团队教程_从零跑通G1武术仿真.md` —— 从零跑通完整仿真
4. 进阶：`docs/GVHMR_容器部署与完整训练教程.md`（真人视频 → 动作捕捉 → 训练）、
   `docs/服务器RL筛选.md`（服务器 RL 环境筛选）、`docs/unitree_sdk2_指南.md`（官方 SDK）

## 环境与数据说明

- 仿真依赖 MuJoCo + 官方 `unitree_sdk2`（github.com/unitreerobotics/unitree_sdk2），
  离线包不再随仓库分发，请从官方仓库下载对应 release/分支。
- 训练数据、录屏、服务器环境快照为一次性产物，不入库；组员按教程在算力平台
  重新生成即可。
