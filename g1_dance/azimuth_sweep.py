# -*- coding: utf-8 -*-
"""给抱架帧(15)在4个方位角各拍一张, 找最清楚的视角。"""
import os, numpy as np, mujoco, cv2
WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
model = mujoco.MjModel.from_xml_path(os.path.join(WS,'g1','scene_29dof.xml'))
data = mujoco.MjData(model)
arr = np.loadtxt(os.path.join(WS,'g1_dance','test.csv'), delimiter=',')
model.vis.global_.offwidth = 1000
model.vis.global_.offheight = 1000
r = mujoco.Renderer(model, 560, 560)

def shoot(f, az, path):
    row=arr[f]
    mujoco.mj_resetData(model, data)
    data.qpos[0:3]=row[0:3]; q=row[3:7]; data.qpos[3:7]=[q[3],q[0],q[1],q[2]]
    data.qpos[7:36]=row[7:36]
    mujoco.mj_forward(model, data)
    cam=mujoco.MjvCamera()
    cam.lookat[:]=[0,0,1.05]; cam.distance=3.2; cam.azimuth=az; cam.elevation=-8
    r.update_scene(data, camera=cam)
    cv2.imwrite(path, r.render()[:,:,::-1])

for az in [0,90,180,270]:
    shoot(15, az, os.path.join(WS,'g1_dance',f'guard_az{az}.png'))
    print('shot', az)
