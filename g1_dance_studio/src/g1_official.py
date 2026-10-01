"""
Official Unitree G1 constants aligned with unitree_sdk2_python examples.

Sources (local checkout under unitree_sdk2_python/example/g1/):
  - low_level/g1_low_level_example.py
  - high_level/g1_arm7_sdk_dds_example.py
  - assets/g1/g1_joint_index_dds.md (29 DoF motor order)

IDL: unitree_hg (G1 / H1-2). Go2 uses unitree_go — do not mix.
"""

from __future__ import annotations

G1_NUM_MOTOR = 29

# motor_cmd[29].q used by Arm SDK as enable flag (see g1_arm7_sdk_dds_example.py)
K_NOT_USED_JOINT = 29  # weight / arm_sdk enable slot


class G1JointIndex:
    """Exact indices from official g1_low_level_example.py / g1_arm7_sdk_dds_example.py."""

    # Left leg
    LeftHipPitch = 0
    LeftHipRoll = 1
    LeftHipYaw = 2
    LeftKnee = 3
    LeftAnklePitch = 4
    LeftAnkleB = 4
    LeftAnkleRoll = 5
    LeftAnkleA = 5

    # Right leg
    RightHipPitch = 6
    RightHipRoll = 7
    RightHipYaw = 8
    RightKnee = 9
    RightAnklePitch = 10
    RightAnkleB = 10
    RightAnkleRoll = 11
    RightAnkleA = 11

    WaistYaw = 12
    WaistRoll = 13  # NOTE: INVALID for g1 23dof/29dof with waist locked
    WaistA = 13
    WaistPitch = 14  # NOTE: INVALID for g1 23dof/29dof with waist locked
    WaistB = 14

    # Left arm
    LeftShoulderPitch = 15
    LeftShoulderRoll = 16
    LeftShoulderYaw = 17
    LeftElbow = 18
    LeftWristRoll = 19
    LeftWristPitch = 20  # NOTE: INVALID for g1 23dof
    LeftWristYaw = 21  # NOTE: INVALID for g1 23dof

    # Right arm
    RightShoulderPitch = 22
    RightShoulderRoll = 23
    RightShoulderYaw = 24
    RightElbow = 25
    RightWristRoll = 26
    RightWristPitch = 27  # NOTE: INVALID for g1 23dof
    RightWristYaw = 28  # NOTE: INVALID for g1 23dof

    kNotUsedJoint = 29  # Arm SDK enable weight


class Mode:
    """LowCmd.mode_pr — ankle / waist parallel encoding (low_level example)."""

    PR = 0  # Series Control for Pitch/Roll Joints
    AB = 1  # Parallel Control for A/B Joints


# Per-motor PD from g1_low_level_example.py (full-body lowcmd)
KP_LOW_LEVEL = [
    60, 60, 60, 100, 40, 40,  # legs L
    60, 60, 60, 100, 40, 40,  # legs R
    60, 40, 40,  # waist
    40, 40, 40, 40, 40, 40, 40,  # left arm
    40, 40, 40, 40, 40, 40, 40,  # right arm
]

KD_LOW_LEVEL = [
    1, 1, 1, 2, 1, 1,
    1, 1, 1, 2, 1, 1,
    1, 1, 1,
    1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1,
]

# Arm SDK example uses uniform gains on controlled joints
KP_ARM_SDK = 60.0
KD_ARM_SDK = 1.5

# Official control periods
DT_LOW_LEVEL = 0.002  # 500 Hz — g1_low_level_example
DT_ARM_SDK = 0.02  # 50 Hz — g1_arm7_sdk_dds_example

# Topics
TOPIC_LOWCMD = "rt/lowcmd"
TOPIC_LOWSTATE = "rt/lowstate"
TOPIC_ARM_SDK = "rt/arm_sdk"

# Joints controlled by Arm SDK path (legs stay with built-in loco)
ARM_SDK_JOINTS = [
    G1JointIndex.LeftShoulderPitch,
    G1JointIndex.LeftShoulderRoll,
    G1JointIndex.LeftShoulderYaw,
    G1JointIndex.LeftElbow,
    G1JointIndex.LeftWristRoll,
    G1JointIndex.LeftWristPitch,
    G1JointIndex.LeftWristYaw,
    G1JointIndex.RightShoulderPitch,
    G1JointIndex.RightShoulderRoll,
    G1JointIndex.RightShoulderYaw,
    G1JointIndex.RightElbow,
    G1JointIndex.RightWristRoll,
    G1JointIndex.RightWristPitch,
    G1JointIndex.RightWristYaw,
    G1JointIndex.WaistYaw,
    G1JointIndex.WaistRoll,
    G1JointIndex.WaistPitch,
]

# Studio / MJCF snake_name -> motor index (must match G1JointIndex)
SNAKE_TO_INDEX = {
    "left_hip_pitch": 0,
    "left_hip_roll": 1,
    "left_hip_yaw": 2,
    "left_knee": 3,
    "left_ankle_pitch": 4,
    "left_ankle_roll": 5,
    "right_hip_pitch": 6,
    "right_hip_roll": 7,
    "right_hip_yaw": 8,
    "right_knee": 9,
    "right_ankle_pitch": 10,
    "right_ankle_roll": 11,
    "waist_yaw": 12,
    "waist_roll": 13,
    "waist_pitch": 14,
    "left_shoulder_pitch": 15,
    "left_shoulder_roll": 16,
    "left_shoulder_yaw": 17,
    "left_elbow": 18,
    "left_wrist_roll": 19,
    "left_wrist_pitch": 20,
    "left_wrist_yaw": 21,
    "right_shoulder_pitch": 22,
    "right_shoulder_roll": 23,
    "right_shoulder_yaw": 24,
    "right_elbow": 25,
    "right_wrist_roll": 26,
    "right_wrist_pitch": 27,
    "right_wrist_yaw": 28,
}

# Official-style IDL names (29 DoF, mode_pr=PR)
IDL_NAMES_PR = [
    "L_LEG_HIP_PITCH",
    "L_LEG_HIP_ROLL",
    "L_LEG_HIP_YAW",
    "L_LEG_KNEE",
    "L_LEG_ANKLE_PITCH",
    "L_LEG_ANKLE_ROLL",
    "R_LEG_HIP_PITCH",
    "R_LEG_HIP_ROLL",
    "R_LEG_HIP_YAW",
    "R_LEG_KNEE",
    "R_LEG_ANKLE_PITCH",
    "R_LEG_ANKLE_ROLL",
    "WAIST_YAW",
    "WAIST_ROLL",
    "WAIST_PITCH",
    "L_SHOULDER_PITCH",
    "L_SHOULDER_ROLL",
    "L_SHOULDER_YAW",
    "L_ELBOW",
    "L_WRIST_ROLL",
    "L_WRIST_PITCH",
    "L_WRIST_YAW",
    "R_SHOULDER_PITCH",
    "R_SHOULDER_ROLL",
    "R_SHOULDER_YAW",
    "R_ELBOW",
    "R_WRIST_ROLL",
    "R_WRIST_PITCH",
    "R_WRIST_YAW",
]

INDEX_TO_SNAKE = {v: k for k, v in SNAKE_TO_INDEX.items()}


def assert_joint_map_matches_official(joints_dict: dict) -> None:
    """Raise if a yaml joints map disagrees with official indices."""
    for name, idx in SNAKE_TO_INDEX.items():
        if name in joints_dict and int(joints_dict[name]) != idx:
            raise ValueError(
                f"Joint map mismatch: {name} is {joints_dict[name]}, official is {idx}"
            )
