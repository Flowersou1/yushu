# GVHMR CPU 强制运行包装器 (v2)
# RTX 5060(Blackwell) 不支持 GVHMR 的 torch2.3 GPU 内核，本脚本把推理路径全部压到 CPU。
# 用法(~/GVHMR 下): CUDA_VISIBLE_DEVICES="" .venv/bin/python run_cpu_demo.py --video=xxx.mp4 --static_cam
import sys, runpy, pathlib
import torch
import torch.nn as nn

# 1) 所有 .cuda() 方法变 no-op（张量/模型留在 CPU）
torch.Tensor.cuda = lambda self, *a, **k: self
nn.Module.cuda = lambda self, *a, **k: self

# 2) to_cuda（搬运 batch 到 cuda）变恒等
try:
    import hmr4d.utils.net_utils as _nu
    _nu.to_cuda = lambda x, *a, **k: x
except Exception as e:
    print("[wrapper] patch net_utils 失败:", e)

# 3) YOLO(Ultralytics) 选设备强制 CPU（解决 tracker "device":"cuda" 报错）
try:
    import ultralytics.utils.torch_utils as _utu
    _utu.select_device = lambda *a, **k: torch.device("cpu")
    import ultralytics.engine.predictor as _pred
    _pred.select_device = lambda *a, **k: torch.device("cpu")
    print("[wrapper] Ultralytics select_device -> cpu")
except Exception as e:
    print("[wrapper] Ultralytics patch 跳过:", e)

# 4) GPU 日志行别崩
torch.cuda.get_device_name = lambda *a, **k: "CPU(forced)"
torch.cuda.get_device_properties = lambda *a, **k: None

# 5) 文件级:把 preproc 里 device 字符串 "cuda" 改成 "cpu"（tracker / vitpose pose_utils）
for f in [
    "hmr4d/utils/preproc/tracker.py",
    "hmr4d/utils/preproc/vitpose_pytorch/src/vitpose_infer/pose_utils/pose_utils.py",
]:
    p = pathlib.Path(f)
    if p.exists():
        t = p.read_text(encoding="utf-8")
        t2 = t.replace('"device": "cuda"', '"device": "cpu"').replace("device='cuda'", "device='cpu'")
        if t != t2:
            p.write_text(t2, encoding="utf-8")
            print("[wrapper] device->cpu 已改:", f)

# 6) 生成 demo_cpu.py: Renderer 的 device="cuda" -> "cpu"
src = open("tools/demo/demo.py", encoding="utf-8").read()
src = src.replace('device="cuda"', 'device="cpu"')
open("tools/demo/demo_cpu.py", "w", encoding="utf-8").write(src)

sys.argv = ["demo_cpu.py"] + sys.argv[1:]
print("[wrapper] 强制 CPU 模式，开始运行 demo_cpu ...")
runpy.run_path("tools/demo/demo_cpu.py", run_name="__main__")
