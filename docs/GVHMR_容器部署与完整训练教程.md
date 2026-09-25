# Unitree G1 动作模仿： GVHMR 容器部署 + 完整训练教程

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

1. **GVHMR 服务器只负责把视频提取成 `hmr4d_results.pt`。**
2. **GMR、PKL→CSV、CSV→NPZ、reference 预览优先在成员本地完成。**
3. **短片段 RL 的目的首先是动作 QA，不是训练最终策略。**
4. **不要直接把多个 NPZ 生硬首尾拼接。**最终动作顺序确定后，回到原视频层重新剪辑，再整条重新提取。
5. **最终长序列训练由双 4090 完成。**

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

当前团队与主账号共用共享存储，因此可以直接复用现有 GVHMR 项目、模型权重和上传的 Python。

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

# 第四部分：建议做成一键脚本

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

组员以后只需要：

```bash
./run_gvhmr.sh inputs/demo/动作01.mp4 static
```

相机移动时：

```bash
./run_gvhmr.sh inputs/demo/动作01.mp4 moving
```

---

# 第五部分：成员本地 GMR 重定向

## 12. GVHMR → Unitree G1

服务器生成：

```text
hmr4d_results.pt
```

下载到成员电脑，然后在本地 GMR：

```bash
cd /root/GMR

/root/GMR/.venv/bin/python scripts/gvhmr_to_robot.py \
  --gvhmr_pred_file /path/to/xxx_hmr4d_results.pt \
  --robot unitree_g1
```

第一次在新环境使用时先执行：

```bash
python scripts/gvhmr_to_robot.py --help
```

不要凭记忆臆造当前版本不存在的参数。

本项目已验证输出一般位于：

```text
/root/GMR/retargeting_data/unitree_g1/
```

例如：

```text
newvideo_g1.pkl
```

---

## 13. GMR reference 第一轮人工检查

重点看：

- 脚是否突然飞离地面、穿地、交叉异常。
- 膝、髋、肩、肘是否出现 G1 结构明显做不了的姿态。
- root 是否突然瞬移、翻转或高度突变。
- 动作开头/结尾是否适合作为拼接点。
- “能训练”不等于“值得展示”，无意义动作可以直接删。

---

# 第六部分：PKL → CSV → NPZ

## 14. PKL → CSV

在 GMR 环境先查看：

```bash
cd /root/GMR
python scripts/batch_gmr_pkl_to_csv.py --help
```

当前项目已经成功生成过：

```text
/root/GMR/retargeting_data/unitree_g1/csv/newvideo_g1.csv
```

---

## 15. CSV → mjlab NPZ

项目已验证命令：

```bash
cd /root/g1_spinkick_example

uv run python -m mjlab.scripts.csv_to_npz \
  --input-file /root/GMR/retargeting_data/unitree_g1/csv/<name>_g1.csv \
  --output-name <name>_g1_50fps \
  --input-fps 30 \
  --output-fps 50 \
  --render False
```

当前统一：

```text
input fps：常见 30
output fps：50
```

检查 NPZ：

```bash
python - <<'PY'
import numpy as np
p = '<path/to/motion.npz>'
x = np.load(p)
print('keys:', x.files)
print('fps:', x['fps'])
print('frames:', len(x['joint_pos']))
print('duration:', len(x['joint_pos']) / float(x['fps'][0]))
PY
```

---

# 第七部分：5s / 10s RL 可训练性筛选

## 16. 为什么先做短片段

目的不是训练最终策略，而是快速回答：

```text
这个动作 G1 到底值不值得继续投入训练？
```

明显不适合 G1 的动作直接删，不要试图把所有动作硬训出来。

---

## 17. 推荐筛选参数

### 成员 RTX 5060

```text
num_envs：1024 起步
显存不足：512
max_iterations：600–800
anchor threshold：0.35
ee threshold：0.45
```

### 双 RTX 4090 服务器复核

```text
num_envs：4096
iterations：600–1000
anchor threshold：0.35
ee threshold：0.45
```

---

## 18. 当前项目工程判定阈值

主要看 `Mean episode length`：

```text
≥ 300       → ✅ 可用
150–300     → ⚠️ 较难，候选/服务器复核
< 150       → ❌ 不建议
< 80        → ❌ 基本直接删除
```

注意：

- 不要只看 reward。
- 有些困难动作会在前几百 iteration 很差，随后突然突破。
- 不能几十轮就判死。
- 但训练足够久后仍只有十几到几十 episode 的动作，通常不值得保留。

当前项目已验证：

```text
55–65s   episode 473.64   ✅
60–70s   episode 379.50   ✅
65–70s   episode 479.75   ✅
70–75s   episode 32.11    ❌
75–80s   episode 17.35    ❌
80–85s   episode 14.78    ❌
```

因此当前旧素材决策是：

```text
0–70s：保留候选主体
70s 以后：删除
```

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

```bash
PROJ=/public/home/zhouyuqin/helloworld/upload/mjlab_test/g1_spinkick_example
TRAIN="$PROJ/.venv/bin/train"

cd "$PROJ"

CUDA_VISIBLE_DEVICES=0 \
WANDB_MODE=disabled \
PYTHONUNBUFFERED=1 \
"$TRAIN" Mjlab-Tracking-Flat-Unitree-G1 \
  --env.commands.motion.motion-file /path/to/clip_5s.npz \
  --env.scene.num-envs 4096 \
  --env.terminations.anchor-pos.params.threshold 0.35 \
  --env.terminations.ee-body-pos.params.threshold 0.45 \
  --agent.max-iterations 800
```

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

组员实际只需要记住下面这套：

```text
1. 在自己电脑上裁好 5–10s / 单动作 MP4
2. 上传到 GVHMR 容器共享目录
3. SSH 容器
4. 跑 run_gvhmr.sh
5. 拿到 hmr4d_results.pt
6. 下载到自己电脑
7. 本地 GMR → G1 PKL
8. 看 reference
9. PKL → CSV → 50fps NPZ
10. 5060 做 5s/10s RL 初筛
11. episode ≥300：PASS
12. 150–300：REVIEW
13. <150：REJECT
14. 只把 PASS / REVIEW 的动作和日志交回来
```

不要提交：

```text
“这个视频挺好，直接帮我拼进去”
```

至少要提交：

```text
动作 ID
原始视频名
希望保留时间段
动作含义
是否必须
计划顺序
GVHMR 是否完成
GMR reference 是否通过
5s/10s episode
PASS / REVIEW / REJECT
备注/推荐拼接点
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

