# -*- coding: utf-8 -*-
"""扫描 left_shoulder_pitch 从 -pi~+pi(肘伸直0,其他0), 打印左手末端世界坐标。
目的: 找出让左手伸到身体正前方水平(肩高、x最大)的那个 shoulder_pitch 值。"""
import os, numpy as np, mujoco

WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
model = mujoco.MjModel.from_xml_path(os.path.join(WS, 'g1', 'scene_29dof.xml'))
data = mujoco.MjData(model)

def bname(i): return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
# 找左手末端(wrist_yaw, 最靠外) 和 左肩(shoulder_pitch_link)
hand_id = sh_id = None
for i in range(model.nbody):
    n = bname(i).lower()
    if n == 'left_wrist_yaw_link': hand_id = i
    if n == 'left_shoulder_pitch_link': sh_id = i
print("hand:", bname(hand_id), " shoulder:", bname(sh_id))

def pose_left_arm(spitch, sroll=0.0, syaw=0.0, elbow=0.0):
    mujoco.mj_resetData(model, data)
    data.qpos[0:3] = [0.0, 0.0, 0.76]
    data.qpos[3:7] = [1.0, 0.0, 0.0, 0.0]
    LEG = [-0.312, 0.0, 0.0, 0.669, -0.363, 0.0]
    L = LEG + LEG + [0,0,0]
    L += [spitch, sroll, syaw, elbow, 0,0,0]          # 左臂
    L += [0,0,0,0, 0,0,0]                               # 右臂保持0(下垂)
    data.qpos[7:36] = L
    mujoco.mj_forward(model, data)

print("\n== 扫描 shoulder_pitch (肘伸直 elbow=0, roll/yaw=0) ==")
print("  spitch   左手(x,y,z)      相对肩(dx,dy,dz)  到肩距离")
results = []
for sp in np.arange(-3.14, 3.14+0.001, 0.4):
    pose_left_arm(sp)
    h = data.xpos[hand_id]; s = data.xpos[sh_id]
    d = h - s
    results.append((sp, h.copy(), d.copy()))
    print(f"  {sp:+.2f}  ({h[0]:+.2f},{h[1]:+.2f},{h[2]:+.2f})  ({d[0]:+.2f},{d[1]:+.2f},{d[2]:+.2f})  {np.linalg.norm(d):.2f}")

# 找 x 最大(最前) 和 z 最大(最高) 的
fwd = max(results, key=lambda r: r[1][0])
up  = max(results, key=lambda r: r[1][2])
print(f"\n手 x 最大(最前): spitch={fwd[0]:+.2f} 手=({fwd[1][0]:+.2f},{fwd[1][1]:+.2f},{fwd[1][2]:+.2f})")
print(f"手 z 最大(最高): spitch={up[0]:+.2f}  手=({up[1][0]:+.2f},{up[1][1]:+.2f},{up[1][2]:+.2f})")
