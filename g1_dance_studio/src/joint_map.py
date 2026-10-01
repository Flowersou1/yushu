import yaml

try:
    from src.g1_official import SNAKE_TO_INDEX, assert_joint_map_matches_official
except ImportError:
    from g1_official import SNAKE_TO_INDEX, assert_joint_map_matches_official  # type: ignore


class JointMap:
    """G1 29-DoF joint name <-> motor index mapping (official G1JointIndex order)."""

    def __init__(self, config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        self.joints = config.get("joints", {}) or dict(SNAKE_TO_INDEX)
        self.limits = config.get("limits", {}) or {}
        self.meta = config.get("meta", {}) or {}
        self.control = config.get("control", {}) or {}
        # Fail fast if someone reorders joints away from official SDK
        assert_joint_map_matches_official(self.joints)
        self.num_joints = max(self.joints.values()) + 1 if self.joints else 29

        # Stable name order by motor index
        self.names_by_index = [""] * self.num_joints
        for name, idx in self.joints.items():
            if 0 <= idx < self.num_joints:
                self.names_by_index[idx] = name

    def get_index(self, joint_name):
        return self.joints.get(joint_name, -1)

    def get_name(self, index):
        if 0 <= index < len(self.names_by_index):
            return self.names_by_index[index]
        return ""

    def map_to_array(self, joint_dict, default_val=0.0, base=None):
        """Map named joints to a full motor array.

        If base is given, start from a copy of base and overwrite named joints.
        This makes sparse keyframes hold unspecified joints.
        """
        if base is not None:
            arr = list(base)
            if len(arr) < self.num_joints:
                arr = arr + [default_val] * (self.num_joints - len(arr))
            elif len(arr) > self.num_joints:
                arr = arr[: self.num_joints]
        else:
            arr = [default_val] * self.num_joints

        for name, value in (joint_dict or {}).items():
            idx = self.get_index(name)
            if 0 <= idx < self.num_joints:
                arr[idx] = float(value)
        return arr

    def array_to_dict(self, arr, skip_near_zero=False, eps=1e-3):
        """Convert full motor array to named joint dict."""
        out = {}
        for i, val in enumerate(arr):
            name = self.get_name(i)
            if not name:
                continue
            v = float(val)
            if skip_near_zero and abs(v) < eps:
                continue
            out[name] = v
        return out

    def mirror_left_to_right(self, joint_dict):
        """Mirror left arm/leg joints onto right side (sign flip for roll/yaw-like)."""
        # (left, right, sign) — roll/yaw usually flip sign across sagittal plane
        pairs = [
            ("left_hip_pitch", "right_hip_pitch", 1),
            ("left_hip_roll", "right_hip_roll", -1),
            ("left_hip_yaw", "right_hip_yaw", -1),
            ("left_knee", "right_knee", 1),
            ("left_ankle_pitch", "right_ankle_pitch", 1),
            ("left_ankle_roll", "right_ankle_roll", -1),
            ("left_shoulder_pitch", "right_shoulder_pitch", 1),
            ("left_shoulder_roll", "right_shoulder_roll", -1),
            ("left_shoulder_yaw", "right_shoulder_yaw", -1),
            ("left_elbow", "right_elbow", 1),
            ("left_wrist_roll", "right_wrist_roll", -1),
            ("left_wrist_pitch", "right_wrist_pitch", 1),
            ("left_wrist_yaw", "right_wrist_yaw", -1),
        ]
        out = dict(joint_dict)
        for left, right, sign in pairs:
            if left in out:
                out[right] = float(out[left]) * sign
        return out

    def mirror_right_to_left(self, joint_dict):
        pairs = [
            ("right_hip_pitch", "left_hip_pitch", 1),
            ("right_hip_roll", "left_hip_roll", -1),
            ("right_hip_yaw", "left_hip_yaw", -1),
            ("right_knee", "left_knee", 1),
            ("right_ankle_pitch", "left_ankle_pitch", 1),
            ("right_ankle_roll", "left_ankle_roll", -1),
            ("right_shoulder_pitch", "left_shoulder_pitch", 1),
            ("right_shoulder_roll", "left_shoulder_roll", -1),
            ("right_shoulder_yaw", "left_shoulder_yaw", -1),
            ("right_elbow", "left_elbow", 1),
            ("right_wrist_roll", "left_wrist_roll", -1),
            ("right_wrist_pitch", "left_wrist_pitch", 1),
            ("right_wrist_yaw", "left_wrist_yaw", -1),
        ]
        out = dict(joint_dict)
        for right, left, sign in pairs:
            if right in out:
                out[left] = float(out[right]) * sign
        return out
