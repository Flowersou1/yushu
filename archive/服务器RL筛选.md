# Unitree G1 动作模仿：直接执行教程

版本：2026-08-11  
适用项目：真人武术/舞蹈视频 → Unitree G1 动作模仿  
当前已验证平台：高校 AI 算力平台，RTX 4090 容器，共享 `/public/home/zhouyuqin` 存储

---

## 0. 最终工作流

```text
原始真人视频
→ 视频裁切/整理
→ GVHMR：MP4 → hmr4d_results.pt
→ GMR：hmr4d_results.pt → Unitree G1 PKL
→ PKL → CSV
→ CSV → mjlab NPZ（当前统一 50 fps）
→ reference 人工检查
→ 5s/10s RL 可训练性筛选
→ 删除 G1 不适合/无展示价值的动作
→ 回到视频层重新剪最终序列
→ 整条最终视频重新 GVHMR → GMR → CSV → NPZ
→ mjlab Tracking RL curriculum 最终训练
→ 仿真回放验收
→ 最后才考虑 Sim-to-Real
```

核心原则：

1. **本地只承担视频整理、GMR 重定向、G1 reference 检查和 PKL→CSV。**
2. **GVHMR、CSV→NPZ、5s/10s RL 初筛统一放服务器，减少本地环境配置。**
3. **短片段 RL 的目的首先是动作 QA，不是训练最终策略。**
4. **不要直接把多个 NPZ 生硬首尾拼接。**最终动作顺序确定后，回到原视频层重新剪辑，再整条重新提取。
5. **困难片段复核、长序列 curriculum 和最终策略训练仍由主训练环境完成。**

---

# 先看这里：组员实际只走这 10 步

```text
1. 本地剪好单个动作 MP4
2. 上传服务器
3. 服务器 GVHMR → hmr4d_results.pt
4. 下载 PT 到本地
5. 本地 GMR → Unitree G1 PKL，并看机器人 reference
6. 本地 PKL → CSV
7. 上传 CSV 到服务器
8. 服务器 CSV → 50fps NPZ
9. 服务器切 5s/10s 并做 RL 初筛
10. 只提交 PASS / REVIEW 动作；最终编排和长序列训练由主训练环境完成
```

如果只是日常处理动作，优先看第 10、12、13、14、15、17、20 节；容器部署只需要第一次做。

---

# 第一部分：网页创建组员专用 GVHMR 容器

## 1. 推荐资源配置

当前平台实际可用配置已经验证：

```text
镜像：pytorch:pytorch1.13-py3.8-cuda11.8
GPU：RTX 4090 × 1
CPU：5 核
容器内存限制：15 GiB
共享存储：/public/home/zhouyuqin
SSH：开启
```

说明：

- 这里选择 PyTorch 1.13 镜像，是因为当前项目最早就是从这套底座成功跑通 GVHMR 的。
- **实际 GVHMR 运行不是使用镜像自带 Python 3.8 / torch 1.13。**后面会显式使用上传到共享盘里的 Python 3.10.20，并复用现有 GVHMR `.venv` 的 Python 包。
- `free -h` 可能显示宿主机数百 GiB 内存，不代表容器真的能使用那么多。当前容器 cgroup 实际限制是：

```text
16106127360 bytes = 15 GiB
```

- `/dev/shm` 当前为 15G，够本项目单任务使用。
- 不建议多人同时在同一容器并发跑多条 GVHMR，先按“一次一个视频”使用。

---

## 2. 容器创建后第一轮检查

SSH 登录新容器后执行：

```bash
hostname
whoami
nvidia-smi
nproc
free -h
df -h
```

确认 GPU：

```text
NVIDIA GeForce RTX 4090
24564 MiB 左右显存
```

确认共享盘：

```bash
ls -lah /public/home/zhouyuqin | head -50
```

当前团队共用共享存储，因此可以直接复用现有 GVHMR 项目、模型权重和上传的 Python。

---

# 第二部分：恢复当前已验证的 GVHMR 运行环境

## 3. 当前关键路径

```text
GVHMR 项目：
/public/home/zhouyuqin/helloworld/upload/GVHMR

上传的 Python 3.10.20：
/public/home/zhouyuqin/cpython-3.10.20-linux-x86_64-gnu/bin/python3.10

GVHMR 旧 venv 的包：
/public/home/zhouyuqin/helloworld/upload/GVHMR/.venv/lib/python3.10/site-packages

GVHMR checkpoints：
/public/home/zhouyuqin/helloworld/upload/GVHMR/inputs/checkpoints

libGL stub 源文件：
/public/home/zhouyuqin/helloworld/upload/gl_stub.c
```

当前 checkpoints 约 5.6G，包括：

```text
vitpose
gvhmr
body_models
dpvo
yolo
hmr2
```

---

## 4. 为什么不能直接用 `GVHMR/.venv/bin/python`

当前 `.venv/bin/python` 是旧软链接：

```text
/root/.local/share/uv/python/cpython-3.10-linux-x86_64-gnu/bin/python3.10
```

该 `/root/...` Python 已不再存在于当前容器，所以会报：

```text
Permission denied
或
command not found
```

因此当前正确方式不是直接执行 `.venv/bin/python`，而是：

```text
上传的 Python 3.10.20
+
GVHMR/.venv/lib/python3.10/site-packages
```

---

## 5. 编译 `libGL.so.1` stub

基础镜像缺少 `libGL.so.1`，而校园软件源可能被认证门户拦截，`apt install libgl1` 不稳定。

当前项目已经有成功方案：使用 `gl_stub.c` 编译一个本地 stub。

每次新容器启动后，如果 `/tmp/libGL.so.1` 不存在，执行：

```bash
cd /tmp

gcc -shared -fPIC \
  -o libGL.so.1 \
  /public/home/zhouyuqin/helloworld/upload/gl_stub.c
```

检查：

```bash
ls -lh /tmp/libGL.so.1
```

---

## 6. 设置 GVHMR 环境变量

每次打开新 SSH/WebShell 终端，先执行：

```bash
GV=/public/home/zhouyuqin/helloworld/upload/GVHMR

export PATH=/public/home/zhouyuqin/cpython-3.10.20-linux-x86_64-gnu/bin:$PATH

export PYTHONPATH="$GV:$GV/.venv/lib/python3.10/site-packages"

export LD_LIBRARY_PATH=/tmp:${LD_LIBRARY_PATH:-}
```

注意：

`PYTHONPATH` 必须同时包含：

```text
$GV
$GV/.venv/lib/python3.10/site-packages
```

如果只包含 site-packages，执行 `tools/demo/demo.py` 时可能出现：

```text
ModuleNotFoundError: No module named 'hmr4d'
```

---

## 7. 基础环境检查

```bash
python3.10 --version
```

应得到：

```text
Python 3.10.20
```

测试 OpenCV：

```bash
cd /public/home/zhouyuqin/helloworld/upload/GVHMR

python3.10 -c "import cv2; print('cv2 OK', cv2.__version__)"
```

当前已验证：

```text
cv2 OK 4.11.0
```

测试 GPU 关键包：

```bash
python3.10 -c "import torch, pytorch3d, hydra; print('torch:', torch.__version__); print('cuda:', torch.cuda.is_available()); print('gpu:', torch.cuda.get_device_name(0)); print('basic packages OK')"
```

当前已验证：

```text
torch: 2.3.0+cu121
cuda: True
gpu: NVIDIA GeForce RTX 4090
basic packages OK
```

---

# 第三部分：GVHMR 只输出 PT，不做无用人体渲染

## 8. 为什么使用 `demo_pt_only.py`

原版 `tools/demo/demo.py` 的执行顺序是：

```text
Preprocess
→ HMR4D Predict
→ torch.save(pred, hmr4d_results.pt)
→ render_incam()
→ render_global()
→ merge videos
```

当前服务器缺：

```text
inputs/checkpoints/body_models/smpl/SMPL_NEUTRAL.pkl
```

但这个文件是在最后的人体 SMPL mesh 可视化阶段才需要。

项目真正交给后续 GMR 的核心产物是：

```text
hmr4d_results.pt
```

因此不需要为了无用的 GVHMR 人体渲染补 `SMPL_NEUTRAL.pkl`。

---

## 9. 创建 `demo_pt_only.py`

保留原版 `demo.py` 不动，复制一份：

```bash
cd /public/home/zhouyuqin/helloworld/upload/GVHMR

cp tools/demo/demo.py tools/demo/demo_pt_only.py
```

把原文件最后的：

```python
# ===== Render ===== #
render_incam(cfg)
render_global(cfg)
if not Path(paths.incam_global_horiz_video).exists():
    Log.info("[Merge Videos]")
    merge_videos_horizontal([paths.incam_video, paths.global_video], paths.incam_global_horiz_video)
```

替换为：

```python
# ===== PT-only mode: skip rendering ===== #
Log.info(f"[PT-ONLY] HMR4D result ready: {paths.hmr4d_results}")
Log.info("[PT-ONLY] Skip SMPL rendering. Done.")
```

当前已验证该脚本可以正常结束，并显示：

```text
[PT-ONLY] HMR4D result ready: .../hmr4d_results.pt
[PT-ONLY] Skip SMPL rendering. Done.
```

---

## 10. 正式运行 GVHMR

假设视频为：

```text
inputs/demo/team_test.mp4
```

固定相机：

```bash
CUDA_VISIBLE_DEVICES=0 python3.10 tools/demo/demo_pt_only.py \
  --video=inputs/demo/team_test.mp4 \
  -s
```

如果相机明显移动，不使用 `-s`：

```bash
CUDA_VISIBLE_DEVICES=0 python3.10 tools/demo/demo_pt_only.py \
  --video=inputs/demo/team_test.mp4
```

正常流程应该看到：

```text
YoloV8 Tracking
ViTPose
HMR4D Predicting
...
[PT-ONLY] HMR4D result ready
```

输出默认类似：

```text
outputs/demo/team_test/hmr4d_results.pt
```

检查：

```bash
ls -lh outputs/demo/team_test/hmr4d_results.pt
```

**看到新的 `hmr4d_results.pt` 才算该视频 GVHMR 完成。**

---

# 第四部分：建议做成组员一键脚本

## 11. `run_gvhmr.sh` 推荐版

可以创建：

```text
/public/home/zhouyuqin/helloworld/upload/GVHMR/run_gvhmr.sh
```

内容：

```bash
#!/usr/bin/env bash
set -euo pipefail

GV=/public/home/zhouyuqin/helloworld/upload/GVHMR
PYROOT=/public/home/zhouyuqin/cpython-3.10.20-linux-x86_64-gnu
GLSRC=/public/home/zhouyuqin/helloworld/upload/gl_stub.c

if [ $# -lt 1 ]; then
  echo "用法: $0 <video.mp4> [static]"
  exit 1
fi

VIDEO="$1"
MODE="${2:-static}"

if [ ! -f "$VIDEO" ]; then
  echo "ERROR: 视频不存在: $VIDEO"
  exit 2
fi

if [ ! -f /tmp/libGL.so.1 ]; then
  echo "[Setup] Building /tmp/libGL.so.1"
  gcc -shared -fPIC -o /tmp/libGL.so.1 "$GLSRC"
fi

export PATH="$PYROOT/bin:$PATH"
export PYTHONPATH="$GV:$GV/.venv/lib/python3.10/site-packages"
export LD_LIBRARY_PATH="/tmp:${LD_LIBRARY_PATH:-}"

cd "$GV"

ARGS=(--video="$VIDEO")
if [ "$MODE" = "static" ]; then
  ARGS+=(-s)
fi

CUDA_VISIBLE_DEVICES=0 python3.10 tools/demo/demo_pt_only.py "${ARGS[@]}"

BASENAME=$(basename "$VIDEO")
STEM="${BASENAME%.*}"
OUT="$GV/outputs/demo/$STEM/hmr4d_results.pt"

if [ -f "$OUT" ]; then
  echo
  echo "SUCCESS: $OUT"
  ls -lh "$OUT"
else
  echo
  echo "WARNING: 未在默认位置找到 hmr4d_results.pt"
  exit 3
fi
```

加执行权限：

```bash
chmod +x run_gvhmr.sh
```

以后只需要：

```bash
./run_gvhmr.sh inputs/demo/动作01.mp4 static
```

相机移动时：

```bash
./run_gvhmr.sh inputs/demo/动作01.mp4 moving
```

---

# 第五部分：成员本地 GMR（零基础版）

## 12. 本地到底需要装什么

成员电脑只需要把 `hmr4d_results.pt` 重定向成 Unitree G1 动作，不要求在本地配置 RL。

推荐环境：

```text
Windows
└─ WSL2 Ubuntu 20.04 / 22.04
   └─ Conda
      └─ gmr（Python 3.10）
```

如果组内已经有一套能运行的 `/root/GMR`，**优先复制/复用已验证环境**，不要为了“更新”自行升级 torch、numpy、mujoco 等依赖。

如果是从零安装，GMR 官方当前安装方式为：

```bash
git clone https://github.com/YanjieZe/GMR.git
cd GMR

conda create -n gmr python=3.10 -y
conda activate gmr

pip install -e .

# 官方给出的渲染兼容修复
conda install -c conda-forge libstdcxx-ng -y
```

安装后先检查：

```bash
python --version
python -c "import mujoco, numpy; print('basic import OK')"
```

> 说明：GMR 官方在 Ubuntu 20.04 / 22.04 上测试。若项目已有机器人资产和 body model，直接复用项目内文件；缺少模型时再按 GMR 官方 README 补，不要随意改文件名。

---

## 13. 把服务器 PT 放到本地

服务器产物：

```text
hmr4d_results.pt
```

建议本地建立：

```text
/root/GMR/team_input/
```

例如：

```text
/root/GMR/team_input/M01_hmr4d_results.pt
```

不要一直叫 `hmr4d_results.pt`，否则多人/多动作很容易混淆。

---

## 14. GVHMR → Unitree G1

进入 GMR：

```bash
cd /root/GMR
```

如果使用 conda：

```bash
conda activate gmr
```

如果你拿到的是组内已经配置好的 `.venv`，就使用那套 Python。

先看参数：

```bash
python scripts/gvhmr_to_robot.py --help
```

标准 G1 重定向：

```bash
python scripts/gvhmr_to_robot.py \
  --gvhmr_pred_file /root/GMR/team_input/M01_hmr4d_results.pt \
  --robot unitree_g1 \
  --record_video
```

GMR 官方当前明确支持：

```text
GVHMR hmr4d_results.pt
→ scripts/gvhmr_to_robot.py
→ --robot unitree_g1
```

运行时通常会打开 MuJoCo 机器人窗口；`--record_video` 会尝试录像。

如果本机 `--record_video` 出现 EGL / Wayland / 白屏，**先看 MuJoCo 窗口或输出 PKL 是否正常，不要因为录像失败就判定重定向失败。**

输出通常在：

```text
/root/GMR/retargeting_data/unitree_g1/
```

找到最新 PKL：

```bash
find /root/GMR/retargeting_data/unitree_g1 \
  -maxdepth 1 -type f -name '*.pkl' \
  -printf '%TY-%Tm-%Td %TH:%TM  %p
' | sort
```

把文件改成可追踪名称，例如：

```text
M01_g1.pkl
```

---

## 15. reference 必须人工检查

看到 G1 模型后，重点检查：

- 脚是否突然飞起、穿地或异常交叉。
- 膝、髋、腰、肩、肘是否出现明显不适合 G1 的姿态。
- root 是否突然瞬移、翻转或高度突变。
- 起势和收势是否稳定。
- 动作是否真的有展示价值。

出现明显错误时，不要直接进入 RL。

需要单独回放保存的 PKL 时：

```bash
python scripts/vis_robot_motion.py \
  --robot unitree_g1 \
  --robot_motion_path /root/GMR/retargeting_data/unitree_g1/M01_g1.pkl
```

如果需要录像，可按当前脚本 `--help` 使用 `--record_video` 和 `--video_path`。

---

# 第六部分：本地 PKL → CSV

## 16. 批量转换

GMR 官方当前脚本使用 `--folder` 参数，并会自动在目标目录创建 `csv/`：

```bash
cd /root/GMR

python scripts/batch_gmr_pkl_to_csv.py \
  --folder /root/GMR/retargeting_data/unitree_g1
```

转换后：

```text
/root/GMR/retargeting_data/unitree_g1/csv/
```

检查：

```bash
ls -lh /root/GMR/retargeting_data/unitree_g1/csv/
```

把本动作对应 CSV 上传到服务器。建议命名：

```text
M01_g1.csv
```

---

# 第七部分：服务器 CSV → NPZ + RL 初筛

## 17. CSV → 50fps NPZ 放服务器做

服务器已有 mjlab，不要求组员本地再装一套。

服务器工程：

```bash
PROJ=/public/home/zhouyuqin/helloworld/upload/mjlab_test/g1_spinkick_example
```

例如把 CSV 放到：

```text
/public/home/zhouyuqin/helloworld/upload/team_motion/M01_g1.csv
```

转换：

```bash
PROJ=/public/home/zhouyuqin/helloworld/upload/mjlab_test/g1_spinkick_example

cd "$PROJ"

uv run python -m mjlab.scripts.csv_to_npz \
  --input-file /public/home/zhouyuqin/helloworld/upload/team_motion/M01_g1.csv \
  --output-name M01_g1_50fps \
  --input-fps 30 \
  --output-fps 50 \
  --render False
```

转换后务必确认实际 NPZ 路径、fps、frames 和 duration。不要只看命令最后是否出现 W&B 相关提示。

---

## 18. 服务器做 5s / 10s RL 初筛

初筛目标：

```text
判断这个动作是否值得进入最终动作库
```

团队 1×4090 容器建议先从：

```text
num_envs：2048
max_iterations：800
anchor_pos：0.35
ee_body_pos：0.45
```

开始。如果资源稳定、无 OOM，可提高到 `4096 envs`。主训练环境目前的成熟默认仍是 `4096 envs`。

判定主要看 `Mean episode length`：

```text
≥ 300       → PASS，可用
150–300     → REVIEW，较难，交主训练环境复核
< 150       → REJECT，不建议
< 80        → REJECT，通常直接删除
```

不要几十个 iteration 就下结论；困难动作可能在前几百轮后才突破。

---

# 第八部分：服务器 mjlab 短片段/最终训练

## 19. 当前服务器工程

```bash
PROJ=/public/home/zhouyuqin/helloworld/upload/mjlab_test/g1_spinkick_example
UPLOAD=/public/home/zhouyuqin/helloworld/upload
TRAIN="$PROJ/.venv/bin/train"
```

任务：

```text
Mjlab-Tracking-Flat-Unitree-G1
```

---

## 20. 标准服务器筛选命令

团队 1×4090 容器先用 2048 envs：

```bash
PROJ=/public/home/zhouyuqin/helloworld/upload/mjlab_test/g1_spinkick_example
TRAIN="$PROJ/.venv/bin/train"

cd "$PROJ"

CUDA_VISIBLE_DEVICES=0 \
WANDB_MODE=disabled \
PYTHONUNBUFFERED=1 \
"$TRAIN" Mjlab-Tracking-Flat-Unitree-G1 \
  --env.commands.motion.motion-file /path/to/clip_5s.npz \
  --env.scene.num-envs 2048 \
  --env.terminations.anchor-pos.params.threshold 0.35 \
  --env.terminations.ee-body-pos.params.threshold 0.45 \
  --agent.max-iterations 800
```

如果 2048 稳定且资源充足，可改为：

```text
--env.scene.num-envs 4096
```

困难片段复核和最终训练在主训练环境中默认使用 4096 envs。

---

## 21. Resume 的重要坑

mjlab / RSL-RL 的 resume 使用相对路径：

```text
logs/rsl_rl/g1_tracking
```

因此 **resume 前必须先：**

```bash
cd "$PROJ"
```

否则可能报：

```text
ValueError: Log path does not exist: logs/rsl_rl/g1_tracking
```

这不是 checkpoint 坏，也不是 GPU 坏，只是启动目录错误。

Warm start 示例：

```text
--agent.resume True
--agent.load-run <run>
--agent.load-checkpoint <model_x.pt>
```

---

## 22. 双 GPU 同时启动注意事项

RSL-RL 的 run 目录按秒生成。

两个任务如果同一秒启动，可能写进同一个时间戳目录。

建议：

```bash
# GPU0 任务
...

sleep 15

# GPU1 任务
...
```

`nohup: ignoring input` 是正常提示。

如果 shell 显示：

```text
Exit 1
```

优先：

```bash
tail -60 xxx.log
```

不要只看 `nvidia-smi` 猜。

---

# 第九部分：最终视频编排

## 23. 不要直接拼 NPZ

错误做法：

```text
A.npz + B.npz + C.npz
```

如果 A 最后一帧和 B 第一帧 root / joint 差异很大，就会制造 reference 瞬移，RL 很容易在拼接点直接终止。

正确流程：

1. 每个候选动作先做 5s/10s 筛选。
2. 删除不可用动作。
3. 删除“能训但没有展示价值”的动作。
4. 确定最终动作顺序。
5. 回到真人原视频层重新剪辑。
6. 尽量在站稳、收势、重心稳定、姿态接近的位置连接。
7. 必要时留 0.5–1.0 秒短过渡。
8. 得到一条完整最终视频。
9. 对这条最终视频从头重新执行：

```text
GVHMR → GMR → CSV → NPZ
```

10. 最后才进入完整策略训练。

---

# 第十部分：最终 Tracking RL Curriculum

## 24. 推荐训练思路

最终目标是：

```text
一个覆盖完整最终动作序列的 policy
```

不是把多个短 policy 拼起来。

推荐：

```text
稳定 10–20s 窗口
→ 重叠窗口
→ 逐步扩长
→ 发现困难区再切 10s / 5s 定位
→ 不重要的困难动作直接删
→ 最终扩到完整序列
```

---

## 25. 当前 termination curriculum 经验

```text
阶段             anchor_pos    ee_body_pos
coarse            0.35          0.45
intermediate A    0.33          0.40
intermediate B    0.31          0.37
medium            0.30          0.35
fine              0.25          0.30
```

旧实验经验：

```text
anchor = 0.25 通常还能接受
EE = 0.25 容易形成明显 cliff
```

因此不要激进直接跳到：

```text
0.25 / 0.25
```

---

## 26. 双 4090 环境数量经验

当前项目实测：

```text
1024 envs   ≈ 49,100 FPS
2048 envs   ≈ 78,340 FPS
4096 envs   ≈ 106,352 FPS
8192 envs   ≈ 108,942 FPS
```

8192 相比 4096 提升很小，因此：

```text
4096 envs = 当前双 4090 默认推荐值
```

---

# 第十一部分：最终仿真验收

## 27. 不能只看 reward

训练结束后必须 replay / 录像检查：

- 是否稳定跟随 reference。
- 是否频繁滑脚。
- 是否异常自碰。
- 是否出现大幅扭矩冲击。
- 拼接点是否自然。
- 是否偶尔成功、但无法稳定重复。

保存：

```text
checkpoint
训练日志
motion NPZ
回放 MP4
训练参数
```

示意：

```bash
cd /root/g1_spinkick_example

.venv/bin/python -m mjlab.scripts.play \
  Mjlab-Tracking-Flat-Unitree-G1 \
  --checkpoint-file /path/to/model_x.pt \
  --motion-file /path/to/final_motion.npz \
  --num-envs 1 \
  --video True \
  --video-length <steps>
```

具体参数以当前版本 `--help` 为准。

---

# 第十二部分：Sim-to-Real 前置条件

真实 G1 不是调试器。

仿真存在以下任一问题时，不进入实机：

```text
明显摔倒
关节打限位
脚滑严重
自碰
输出不稳定
扭矩/速度异常
```

实机前：

1. 确认仿真可重复稳定完成。
2. 确认关节位置/速度/力矩边界与真实 G1 一致。
3. 先低幅度、低速度。
4. 使用保护绳/安全区。
5. 急停必须可用。
6. 先站立、短动作，再长序列。
7. 任何重新剪辑/重新训练后的 checkpoint 都重新仿真验收。

---

# 第十三部分：组员最简日常 SOP

每天处理动作只需要记住：

```text
【本地】
1. 剪单动作 MP4
2. 上传服务器

【服务器】
3. GVHMR → hmr4d_results.pt
4. 下载 PT

【本地】
5. GMR → Unitree G1 PKL
6. 看 G1 reference
7. PKL → CSV
8. 上传 CSV

【服务器】
9. CSV → 50fps NPZ
10. 切 5s/10s
11. RL 初筛

【提交】
12. PASS / REVIEW 才交回来
```

判定：

```text
episode ≥300       PASS
150–300            REVIEW
<150               REJECT
<80                直接 REJECT
```

每个动作提交：

```text
动作 ID
原视频文件名
希望保留时间段
动作说明
是否必须
最终顺序建议
hmr4d_results.pt 是否成功
G1 reference 是否正常
CSV / NPZ 路径
Mean episode length
PASS / REVIEW / REJECT
备注与推荐拼接点
```

不要只发一句：

```text
“这个动作帮我拼进去。”
```

---

# 第十四部分：当前项目已验证的旧素材结论

当前约 93.1s 素材：

```text
0–20s       episode ≈465     ✅
15–35s      episode ≈471     ✅
30–50s      episode ≈304     ✅
45–65s      episode ≈359     ✅
55–65s      episode 473.64   ✅
60–70s      episode 379.50   ✅
65–70s      episode 479.75   ✅
70–75s      episode 32.11    ❌
75–80s      episode 17.35    ❌
80–85s      episode 14.78    ❌
```

当前决策：

```text
0–70s：候选主体
70s 后：删除
```

90s 附近即使某些动作可能可训练，也因为展示价值低而不继续投入。

---

# 第十五部分：常见故障速查

## A. `cv2: libGL.so.1 not found`

```bash
cd /tmp

gcc -shared -fPIC \
  -o libGL.so.1 \
  /public/home/zhouyuqin/helloworld/upload/gl_stub.c

export LD_LIBRARY_PATH=/tmp:${LD_LIBRARY_PATH:-}
```

---

## B. `No module named hmr4d`

确保：

```bash
GV=/public/home/zhouyuqin/helloworld/upload/GVHMR
export PYTHONPATH="$GV:$GV/.venv/lib/python3.10/site-packages"
```

---

## C. `.venv/bin/python: Permission denied`

不要直接用它。

使用：

```bash
export PATH=/public/home/zhouyuqin/cpython-3.10.20-linux-x86_64-gnu/bin:$PATH
python3.10 ...
```

---

## D. `SMPL_NEUTRAL.pkl does not exist`

这是原版 `demo.py` 最后 SMPL 人体渲染需要的文件。

当前流程不需要该渲染，使用：

```text
tools/demo/demo_pt_only.py
```

只产出 `hmr4d_results.pt` 即完成服务器任务。

---

## E. `ValueError: Log path does not exist: logs/rsl_rl/g1_tracking`

```bash
cd "$PROJ"
```

再 resume。

---

## F. GPU 暂时看不到进程

可能还在 CPU 初始化，也可能已经退出。

先：

```bash
ps -ef | grep train
```

再：

```bash
tail -60 xxx.log
```

---

## G. 两个 GPU 任务目录碰撞

两个任务启动间隔约 15 秒。

---

# 最终一句话分工

```text
组员：视频整理 → GVHMR → 本地 GMR → CSV/NPZ → reference → 5060 短片初筛

主双 4090：困难动作复核 → 最终长序列 curriculum → 最终 policy → 仿真验收
```



---

# 参考（上游官方）

- GMR 官方仓库：https://github.com/YanjieZe/GMR
- GVHMR 官方仓库：https://github.com/zju3dv/GVHMR

本文的目录、阈值、4090 参数和故障处理同时包含本项目实测经验；上游软件安装和 GMR 命令以官方仓库当前版本为准。
