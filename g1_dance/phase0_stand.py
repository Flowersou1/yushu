# -*- coding: utf-8 -*-
import os, mujoco, cv2
WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
xml = os.path.join(WS, 'g1', 'scene_29dof.xml')
model = mujoco.MjModel.from_xml_path(xml)
data = mujoco.MjData(model)
mujoco.mj_resetData(model, data)
mujoco.mj_forward(model, data)
model.vis.global_.offwidth = 1000
model.vis.global_.offheight = 1000

def render_view(azimuth, name):
    r = mujoco.Renderer(model, height=720, width=720)
    r.update_scene(data, camera=-1)          # -1 = 默认自由相机
    try:
        r._camera.lookat[:] = [0, 0, 0.8]
        r._camera.distance = 3.2
        r._camera.azimuth = azimuth
        r._camera.elevation = -8.0
    except Exception as e:
        print('cam tweak skip:', e)
    px = r.render()
    out = os.path.join(WS, 'g1_dance', name)
    cv2.imwrite(out, px[:, :, ::-1])
    print('SAVED', out)

render_view(180.0, 'g1_stand_front.png')
render_view(90.0,  'g1_stand_side.png')
print('DONE - G1 pelvis height =', round(model.qpos0[2], 3), 'm')
