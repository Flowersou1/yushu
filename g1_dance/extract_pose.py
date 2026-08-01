# -*- coding: utf-8 -*-
"""
Phase 1 - 第一步：视频 -> 人体姿态(33个3D关键点) + 骨架叠加视频 + 关键点数据。

用法（在 g1_dance 目录下）：
    python extract_pose.py                 # 默认处理 source.mp4
    python extract_pose.py 别的视频.mp4     # 处理指定视频

输出（在 g1_dance\\out\\）：
    pose_overlay.mp4   把识别到的骨架画在原视频上，方便检查抠得对不对
    landmarks.npz      每帧的 33 个关键点（图像坐标 + 3D 世界坐标，米），供下一步重定向用
"""
import os, sys, time
import numpy as np
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

WS = r'C:\Users\24668\Desktop\mujoco-3.10.0-windows-x86_64'
G1D = os.path.join(WS, 'g1_dance')
OUT = os.path.join(G1D, 'out')
os.makedirs(OUT, exist_ok=True)

VIDEO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(G1D, 'source.mp4')
TASK = os.path.join(G1D, 'models', 'pose_landmarker_full.task')
OUT_MP4 = os.path.join(OUT, 'pose_overlay.mp4')
OUT_NPZ = os.path.join(OUT, 'landmarks.npz')

# BlazePose 33 点的身体主干连接（不画脸/手指细节，保持清爽）
BODY = [
    (11, 12),                                   # 两肩
    (11, 13), (13, 15),                         # 左臂
    (12, 14), (14, 16),                         # 右臂
    (11, 23), (12, 24), (23, 24),               # 躯干
    (23, 25), (25, 27), (27, 29), (27, 31),     # 左腿
    (24, 26), (26, 28), (28, 30), (28, 32),     # 右腿
]


def main():
    assert os.path.exists(TASK), f'模型不存在: {TASK}（先运行过下载步骤）'
    cap = cv2.VideoCapture(VIDEO)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f'视频: {os.path.basename(VIDEO)}  {W}x{H}  fps={fps:.1f}  帧数={total}')

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(OUT_MP4, fourcc, fps, (W, H))

    base = python.BaseOptions(model_asset_path=TASK)
    opts = vision.PoseLandmarkerOptions(
        base_options=base,
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.4,
        min_tracking_confidence=0.4,
    )
    det = vision.PoseLandmarker.create_from_options(opts)

    world_all, image_all, mask = [], [], []
    t0 = time.time()
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ts_ms = int(idx * 1000.0 / fps)
        res = det.detect_for_video(mp_img, ts_ms)

        overlay = frame.copy()
        if res.pose_landmarks:
            pl = res.pose_landmarks[0]            # 33 normalized: x,y in [0,1], z 相对
            wl = res.pose_world_landmarks[0]      # 33 米制 3D，原点在髋中心
            image_all.append([[lm.x, lm.y, lm.z] for lm in pl])
            world_all.append([[lm.x, lm.y, lm.z] for lm in wl])
            mask.append(1)
            pts = [(int(lm.x * W), int(lm.y * H)) for lm in pl]
            for a, b in BODY:
                cv2.line(overlay, pts[a], pts[b], (0, 255, 0), 3)
            for p in pts:
                cv2.circle(overlay, p, 4, (0, 0, 255), -1)
        else:
            image_all.append([[0, 0, 0]] * 33)
            world_all.append([[0, 0, 0]] * 33)
            mask.append(0)
        writer.write(overlay)
        idx += 1
        if idx % 100 == 0:
            print(f'  处理 {idx}/{total} 帧, 用时 {time.time()-t0:.0f}s', flush=True)

    cap.release()
    writer.release()
    det.close()

    np.savez(OUT_NPZ,
             world=np.array(world_all, dtype=np.float32),     # [N,33,3] 米
             image=np.array(image_all, dtype=np.float32),     # [N,33,3] 归一化
             mask=np.array(mask, dtype=np.uint8),             # [N] 1=检测到
             fps=np.float32(fps))
    detected = int(sum(mask))
    print(f'\n完成！共 {idx} 帧，检测到人体 {detected} 帧 ({100*detected/max(idx,1):.0f}%)')
    print(f'骨架叠加视频: {OUT_MP4}')
    print(f'关键点数据:   {OUT_NPZ}')


if __name__ == '__main__':
    main()
