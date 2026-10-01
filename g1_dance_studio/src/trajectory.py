import csv
import os
from copy import deepcopy

import yaml


class TrajectoryGenerator:
    """Keyframe dance track with linear interpolation and export helpers."""

    def __init__(self, joint_map, dt=0.01, keyframes=None):
        self.joint_map = joint_map
        self.dt = dt
        self.keyframes = []
        if keyframes:
            self.set_keyframes(keyframes)

    # ------------------------------------------------------------------ load/save
    @classmethod
    def from_yaml(cls, yaml_path, joint_map, dt=0.01):
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            keyframes = []
        elif isinstance(data, list):
            keyframes = data
        elif isinstance(data, dict):
            keyframes = data.get("keyframes", []) or []
        else:
            keyframes = []

        traj = cls(joint_map, dt=dt)
        traj.set_keyframes(keyframes)
        return traj

    def set_keyframes(self, keyframes):
        cleaned = []
        for i, kf in enumerate(keyframes or []):
            if not isinstance(kf, dict):
                continue
            time_s = float(kf.get("time", 0.0))
            joints = dict(kf.get("joints") or {})
            name = str(kf.get("name") or kf.get("annotation") or f"帧{i}")
            # Preserve trailing comment-style names if present in older files
            cleaned.append({"time": time_s, "name": name, "joints": joints})
        cleaned.sort(key=lambda k: k["time"])
        self.keyframes = cleaned
        # densify sparse joint dicts so missing joints hold previous values
        self._densify()

    def _densify(self):
        if not self.keyframes:
            return
        full = [0.0] * self.joint_map.num_joints
        for kf in self.keyframes:
            full = self.joint_map.map_to_array(kf["joints"], base=full)
            kf["joints"] = self.joint_map.array_to_dict(full, skip_near_zero=False)
            kf["_q"] = list(full)

    def ensure_q_cache(self):
        if not self.keyframes:
            return
        if any("_q" not in kf for kf in self.keyframes):
            self._densify()

    @property
    def total_time(self):
        if not self.keyframes:
            return 0.0
        return float(self.keyframes[-1]["time"])

    def interpolate(self, t):
        """Linear interpolation of joint angles at time t."""
        self.ensure_q_cache()
        n = self.joint_map.num_joints
        if not self.keyframes:
            return [0.0] * n

        if t <= self.keyframes[0]["time"]:
            return list(self.keyframes[0]["_q"])
        if t >= self.keyframes[-1]["time"]:
            return list(self.keyframes[-1]["_q"])

        for i in range(len(self.keyframes) - 1):
            k1 = self.keyframes[i]
            k2 = self.keyframes[i + 1]
            if k1["time"] <= t <= k2["time"]:
                span = k2["time"] - k1["time"]
                ratio = 0.0 if span <= 1e-9 else (t - k1["time"]) / span
                a, b = k1["_q"], k2["_q"]
                return [x + (y - x) * ratio for x, y in zip(a, b)]
        return list(self.keyframes[-1]["_q"])

    # ------------------------------------------------------------------ edit API
    def add_keyframe(self, time_s, joints, name="关键帧"):
        q = self.joint_map.map_to_array(joints)
        kf = {
            "time": float(time_s),
            "name": str(name or "关键帧"),
            "joints": self.joint_map.array_to_dict(q, skip_near_zero=False),
            "_q": q,
        }
        self.keyframes.append(kf)
        self.keyframes.sort(key=lambda k: k["time"])
        self._densify()
        return self.keyframes.index(kf) if kf in self.keyframes else len(self.keyframes) - 1

    def update_keyframe(self, index, time_s=None, joints=None, name=None):
        if not (0 <= index < len(self.keyframes)):
            return False
        kf = self.keyframes[index]
        if time_s is not None:
            kf["time"] = float(time_s)
        if name is not None:
            kf["name"] = str(name)
        if joints is not None:
            q = self.joint_map.map_to_array(joints)
            kf["joints"] = self.joint_map.array_to_dict(q, skip_near_zero=False)
            kf["_q"] = q
        self.keyframes.sort(key=lambda k: k["time"])
        self._densify()
        return True

    def delete_keyframe(self, index):
        if 0 <= index < len(self.keyframes):
            del self.keyframes[index]
            self._densify()
            return True
        return False

    def get_keyframe(self, index):
        if 0 <= index < len(self.keyframes):
            return self.keyframes[index]
        return None

    def next_auto_time(self, interval=1.0):
        if not self.keyframes:
            return 0.0
        return float(self.keyframes[-1]["time"]) + float(interval)

    # ------------------------------------------------------------------ export
    def to_serializable(self, sparse=False):
        """YAML-friendly structure (official motor indices embedded)."""
        try:
            from src.g1_official import IDL_NAMES_PR, SNAKE_TO_INDEX
        except ImportError:
            from g1_official import IDL_NAMES_PR, SNAKE_TO_INDEX  # type: ignore

        frames = []
        for kf in self.keyframes:
            joints = kf["joints"]
            if sparse:
                joints = {
                    k: round(float(v), 4)
                    for k, v in joints.items()
                    if abs(float(v)) > 1e-3
                }
            else:
                joints = {k: round(float(v), 4) for k, v in joints.items()}
            # Parallel array in official motor order for easy LowCmd mapping
            q_full = self.joint_map.map_to_array(joints)
            motor_q = [round(float(x), 4) for x in q_full]
            frames.append(
                {
                    "time": round(float(kf["time"]), 3),
                    "name": kf.get("name", "关键帧"),
                    "joints": joints,
                    "motor_q": motor_q,  # index == G1JointIndex / LowCmd.motor_cmd[i]
                }
            )
        return {
            "meta": {
                "robot": "g1_29dof",
                "idl": "unitree_hg",
                "angle_unit": "rad",
                "time_unit": "s",
                "control_hz": int(round(1.0 / self.dt)) if self.dt > 0 else 100,
                "motor_order": "G1JointIndex 0..28 (see unitree_sdk2_python)",
                "idl_names_pr": IDL_NAMES_PR,
                "snake_to_index": SNAKE_TO_INDEX,
                "recommended_real_path": "arm_sdk",
                "topics": {
                    "arm_sdk": "rt/arm_sdk",
                    "lowcmd": "rt/lowcmd",
                    "lowstate": "rt/lowstate",
                },
            },
            "keyframes": frames,
        }

    def save_yaml(self, path, sparse=False):
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        data = self.to_serializable(sparse=sparse)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        return path

    def export_csv(self, path, hz=None):
        """Bake full trajectory to dense CSV.

        Columns: time, q0..q28 (official motor index), then snake names.
        Ready to map to LowCmd.motor_cmd[i].q
        """
        hz = hz or (int(round(1.0 / self.dt)) if self.dt > 0 else 100)
        step = 1.0 / float(hz)
        total = self.total_time
        n = self.joint_map.num_joints
        names = [n for n in self.joint_map.names_by_index if n]

        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            header = ["time"] + [f"q{i}" for i in range(n)] + names
            writer.writerow(header)
            t = 0.0
            if not self.keyframes:
                writer.writerow([0.0] + [0.0] * n + [0.0] * len(names))
            else:
                while t <= total + 1e-9:
                    q = self.interpolate(t)
                    row = [round(t, 4)] + [round(q[i], 6) for i in range(n)]
                    for name in names:
                        idx = self.joint_map.get_index(name)
                        row.append(round(q[idx], 6))
                    writer.writerow(row)
                    t += step
        return path

    def export_joint_table(self, path):
        """Export keyframe table only (one row per keyframe)."""
        names = [n for n in self.joint_map.names_by_index if n]
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["index", "time", "name"] + names)
            for i, kf in enumerate(self.keyframes):
                q = kf.get("_q") or self.joint_map.map_to_array(kf["joints"])
                row = [i, round(float(kf["time"]), 3), kf.get("name", "")]
                for name in names:
                    idx = self.joint_map.get_index(name)
                    row.append(round(q[idx], 6))
                writer.writerow(row)
        return path

    def clone(self):
        other = TrajectoryGenerator(self.joint_map, dt=self.dt)
        other.set_keyframes(deepcopy([{k: v for k, v in kf.items() if k != "_q"} for kf in self.keyframes]))
        return other
