# -*- coding: utf-8 -*-
"""设计低位护架 + 验证出拳直线轨迹。
1) 找护架: 大臂朝下(sp正) + 肘弯-1.0(前臂上), 拳在胸口z[0.97,1.06], 不穿模
2) 出拳: 从护架直线前伸到(sp=-0.70,roll=0.15,eb=-0.08), 逐采样查穿模+轨迹直度"""
import os, numpy as np, mujoco
WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
model = mujoco.MjModel.from_xml_path(os.path.join(WS, 'g1', 'scene_29dof.xml'))
data = mujoco.MjData(model)
def bn(i): return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
LH=next(i for i in range(model.nbody) if bn(i)=='left_wrist_yaw_link')
def bog(gid): return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, model.geom_bodyid[gid])
LEG=[-0.312,0,0,0.669,-0.363,0]

def setup(wy, aL, aR):
    mujoco.mj_resetData(model,data); data.qpos[0:3]=[0,0,0.76]; data.qpos[3:7]=[1,0,0,0]
    data.qpos[7:36]=LEG+LEG+[wy,0,0]+aL+aR; mujoco.mj_forward(model,data)
def clip_mm():
    w=0.0
    for c in range(data.ncon):
        con=data.contact[c]
        if con.dist>=0: continue
        w=min(w, con.dist)
    return w*1000

print("== 1) 低位护架候选 (eb=-1.0, 双臂对称) ==")
print("  sp    roll  左拳(x,y,z)              穿模mm")
cands=[]
for sp in [0.6,0.5,0.4,0.3,0.2,0.1]:
    for roll in [0.2,0.3,0.4]:
        aL=[sp,roll,0,-1.0,0,0,0]; aR=[sp,-roll,0,-1.0,0,0,0]
        setup(0,aL,aR); h=data.xpos[LH].copy(); w=clip_mm()
        if w>-1 and 0.96<=h[2]<=1.07 and h[1]>=0.12:
            cands.append((sp,roll,h,w)); print(f"  {sp:+.2f}  {roll:.1f}  ({h[0]:+.2f},{h[1]:+.2f},{h[2]:+.2f})  {w:+.1f}")

# 选 sp=0.4, roll=0.3 做护架
sp_g, roll_g = 0.4, 0.3
GL=[sp_g, roll_g,0,-1.0,0,0,0]; GR=[sp_g,-roll_g,0,-1.0,0,0,0]
P =[-0.70, 0.15,0,-0.08,0,0,0]
print(f"\n== 2) 出拳轨迹 护架(sp={sp_g},roll={roll_g},eb=-1.0) -> 冲拳(sp=-0.70,roll=0.15,eb=-0.08), 腰-0.35 ==")
print("  a     左拳(x,y,z)             穿模mm")
zs=[]; xs=[]
for a in np.linspace(0,1,8):
    aL=[GL[k]+(P[k]-GL[k])*a for k in range(7)]
    setup(-0.35, aL, GR)
    h=data.xpos[LH].copy(); w=clip_mm(); xs.append(h[0]); zs.append(h[2])
    print(f"  {a:.2f}  ({h[0]:+.2f},{h[1]:+.2f},{h[2]:+.2f})  {w:+.1f}")
print(f"  前伸 Δx={xs[-1]-xs[0]:+.2f}  z波动={max(zs)-min(zs):.2f} (小=直)  起末z={zs[0]:.2f}->{zs[-1]:.2f}")
