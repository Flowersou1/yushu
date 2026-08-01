# -*- coding: utf-8 -*-
"""定位 mjlab 并读 play.py 的录像/渲染机制。"""
import mjlab, os, pathlib
mp = pathlib.Path(os.path.dirname(mjlab.__file__))
print("mjlab 路径:", mp)
sp = mp / "scripts"
if sp.is_dir():
    print("scripts:", sorted(p.name for p in sp.iterdir()))
p = sp / "play.py"
print("play.py exists:", p.exists())
if p.exists():
    lines = p.read_text(encoding="utf-8").splitlines()
    print("play.py 行数:", len(lines))
    print("=== 含 video/render/viewer/record 的行 ===")
    for i, l in enumerate(lines, 1):
        ll = l.lower()
        if any(k in ll for k in ["video", "render", "viewer", "imageio", "record", "mp4", "launch", "headless", "videomanager"]):
            print(f"{i:4d}: {l.rstrip()}")
