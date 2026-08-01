# -*- coding: utf-8 -*-
import os, math, mujoco, cv2
WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
model = mujoco.MjModel.from_xml_path(os.path.join(WS, 'g1', 'scene_29dof.xml'))
data = mujoco.MjData(model)
model.vis.global_.offwidth = 1000; model.vis.global_.offheight = 1000
addr, rng = {}, {}
for i in range(model.njnt):
    nm = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i)
    if nm == 'floating_base_joint': continue
    addr[nm] = model.jnt_qposadr[i]; rng[nm] = model.jnt_range[i]
def render_pose(overrides, name):
    mujoco.mj_resetData(model, data)
    for j, v in overrides.items():
        lo, hi = rng[j]; data.qpos[addr[j]] = max(lo, min(hi, v))
    mujoco.mj_forward(model, data)
    r = mujoco.Renderer(model, 640, 640)
    r.update_scene(data, camera=-1)
    cv2.imwrite(os.path.join(WS, 'g1_dance', name), r.render()[:, :, ::-1])
    print('saved', name)
# 左肩 pitch 扫描（看哪个角度手臂朝下）
for deg in (-90, -45, 0, 45, 90):
    render_pose({'left_shoulder_pitch_joint': math.radians(deg)}, f'calib_lsp_{deg:+04d}.png')
# 左肘
render_pose({'left_elbow_joint': math.radians(90)}, 'calib_le_90.png')
# 双腿微蹲（髋屈+膝屈）
render_pose({'left_hip_pitch_joint': 0.7, 'left_knee_joint': 1.2,
             'right_hip_pitch_joint': 0.7, 'right_knee_joint': 1.2}, 'calib_squat.png')
print('DONE')
