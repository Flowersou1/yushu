# G1 武术动作仿真项目

为 **Unitree G1 EDU+** 人形机器人开发武术动作：关键帧编动作 → MuJoCo 仿真验证 → RL 训练（自平衡）→ 真机部署。
铁律：**一切动作先在仿真跑通验证，才能上真机**；真机首次必须吊装、低速。

---

## 仓库里有什么（已包含）
- `g1/` —— G1 机器人模型（`scene_29dof.xml` + 网格，29 自由度）。**编动作/仿真都靠它。**
- `g1_dance/` —— 我们写的工具：
  - `choreographer.py` —— **动作编辑器 GUI**（拖滑块摆姿势、实时预览、存关键帧、导出 CSV）。组员编动作用这个。
  - `combine_routines.py` —— 把多人编的 CSV 拼成全套。
  - `make_motion.py` / `make_motion_test.py` —— 关键帧脚本（备选，纯代码编）。
  - `check_clip.py` —— 用 MuJoCo 碰撞检测**逐帧查穿模**（判穿模只信它）。
  - `verify_csv.py` / `elbow_diag.py` —— 查关节坐标/肘内角（判动作对错的权威方法）。
  - `render_ref.py` —— 渲染参考动作视频。
  - `组员编动作说明.md` —— **组员看这个上手编动作**。
  - `routine.csv` —— 已编好的拳法 routine（零穿模、肘真伸直，可作保底/示例）。
- `CLAUDE.md` —— 项目完整背景、关节约定、踩过的坑（改动作前必看）。
- `团队教程_从零跑通G1武术仿真.md` —— 完整管线教程（环境/训练/部署）。

## ❗ 不在仓库里、需要自己下载的（按需）

### 1. MuJoCo（Python 包）—— 【必需，人人装】
编动作/仿真都要。一行搞定：
```
pip install mujoco
```

### 2. unitree_mujoco（G1 仿真器，可选）—— 【只在做 RL/平衡仿真时需要】
仓库里的 `g1/` 模型够编动作用。如果要跑 g1-mechdance 平衡仿真/RL，需要完整 unitree_mujoco：
- 下载：https://github.com/unitreerobotics/unitree_mujoco （Code → Download ZIP，需挂代理）
- 解压到本项目同级目录。

### 3. SMPL / SMPLX 模型（可选）—— 【只在做"视频→动作"提取(GVHMR)时需要】
- SMPL：注册 https://smpl.is.tue.mpg.de/ 下载。
- SMPLX：注册 https://smpl-x.is.tue.mpg.de/ 下载 v1.1（NPZ 版）。
- ⚠️ 这俩**注册才能用、禁止再分发**，所以不在仓库里，每人自己注册下载。

### 4. Python 环境
- 编动作/仿真：Python 3.10+，`pip install mujoco numpy opencv-python`。
- RL 训练：见 `团队教程_从零跑通G1武术仿真.md`（WSL2 + mjlab）。

---

## 快速开始：编一段动作（组员）

1. `pip install mujoco`
2. `python g1_dance\choreographer.py` —— 拖滑块摆姿势、存关键帧、导出 CSV。
3. 详细看 **`g1_dance\组员编动作说明.md`**。

## 完整管线（负责人）

```
组员用 choreographer.py 编动作 → 导出 CSV
        ↓
combine_routines.py 拼成全套 routine.csv
        ↓
check_clip.py 逐帧查穿模（必须 0 穿模）
        ↓
csv_to_npz 转 npz（见团队教程）
        ↓
mjlab RL 训练（WSL2 + 兼容 GPU）→ 自平衡策略
        ↓
play 仿真验证 → 吊装低速上真机
```

---

## G1 关节约定（改动作必看，否则白训）
详见 `CLAUDE.md`。要点（实测，别猜符号）：
- `shoulder_pitch`：**正值=手臂下垂**；**负值=前抬/上举**（-0.74≈正前方水平）。
- `elbow`：⚠️ **手臂伸直 ≈ +1.3~1.5（正值）**，不是 0；elbow=0 只是 90° 直角。
- 抱架肘弯不能深于 -1.0（会穿模）。
- 判动作对错**只信 `check_clip.py` / `verify_csv.py` 的数字**，不靠肉眼看图。

## 路线现状
- ✅ 编动作工具链（choreographer + combine）就绪。
- ✅ 拳法 routine（保底）已验证。
- ✅ mjlab RL 管线本地跑通，差兼容 GPU（A10/3090+）训自平衡。
- ⚠️ g1-mechdance 平衡器实测撑不住拳法（前倾摔），自平衡拳法走 RL。
- ⏳ GVHMR 视频提取环境装好，等兼容 GPU 跑。
