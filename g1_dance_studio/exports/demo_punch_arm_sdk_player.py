#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G1 Arm-SDK dance player — structure aligned with official:
  unitree_sdk2_python/example/g1/high_level/g1_arm7_sdk_dds_example.py

Dance: demo_punch
Source YAML: C:/Users/24668/Desktop/yushu-action/g1_dance/dances/demo_punch.yaml

Usage (Ubuntu server, robot on wire):
  python3 demo_punch_arm_sdk_player.py enp6s0

Safety:
  - Robot should be in standing / loco balance mode
  - Only waist + dual arms via rt/arm_sdk
  - Keep emergency stop ready; clear swing range
"""

from __future__ import annotations

import sys
import time

import numpy as np

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_
from unitree_sdk2py.utils.crc import CRC
from unitree_sdk2py.utils.thread import RecurrentThread


# ---------------------------------------------------------------------------
# Official G1JointIndex (g1_arm7_sdk_dds_example.py / g1_low_level_example.py)
# ---------------------------------------------------------------------------
class G1JointIndex:
    LeftHipPitch = 0
    LeftHipRoll = 1
    LeftHipYaw = 2
    LeftKnee = 3
    LeftAnklePitch = 4
    LeftAnkleRoll = 5
    RightHipPitch = 6
    RightHipRoll = 7
    RightHipYaw = 8
    RightKnee = 9
    RightAnklePitch = 10
    RightAnkleRoll = 11
    WaistYaw = 12
    WaistRoll = 13
    WaistPitch = 14
    LeftShoulderPitch = 15
    LeftShoulderRoll = 16
    LeftShoulderYaw = 17
    LeftElbow = 18
    LeftWristRoll = 19
    LeftWristPitch = 20
    LeftWristYaw = 21
    RightShoulderPitch = 22
    RightShoulderRoll = 23
    RightShoulderYaw = 24
    RightElbow = 25
    RightWristRoll = 26
    RightWristPitch = 27
    RightWristYaw = 28
    kNotUsedJoint = 29  # Arm SDK enable weight


ARM_JOINTS = [
    G1JointIndex.LeftShoulderPitch, G1JointIndex.LeftShoulderRoll,
    G1JointIndex.LeftShoulderYaw, G1JointIndex.LeftElbow,
    G1JointIndex.LeftWristRoll, G1JointIndex.LeftWristPitch,
    G1JointIndex.LeftWristYaw,
    G1JointIndex.RightShoulderPitch, G1JointIndex.RightShoulderRoll,
    G1JointIndex.RightShoulderYaw, G1JointIndex.RightElbow,
    G1JointIndex.RightWristRoll, G1JointIndex.RightWristPitch,
    G1JointIndex.RightWristYaw,
    G1JointIndex.WaistYaw, G1JointIndex.WaistRoll, G1JointIndex.WaistPitch,
]

# Embedded dance (motor index -> rad), from G1 Dance Studio
KEYFRAMES = [
    {"time": 0.0000, "name": "起势", "q": {15: 0.000000, 16: 0.000000, 17: 0.000000, 18: 0.000000, 19: 0.000000, 20: 0.000000, 21: 0.000000, 22: 0.000000, 23: 0.000000, 24: 0.000000, 25: 0.000000, 26: 0.000000, 27: 0.000000, 28: 0.000000, 12: 0.000000, 13: 0.000000, 14: 0.000000}},
    {"time": 2.0000, "name": "蓄力", "q": {15: 0.000000, 16: 0.000000, 17: 0.000000, 18: 0.000000, 19: 0.000000, 20: 0.000000, 21: 0.000000, 22: -0.500000, 23: 0.000000, 24: 0.000000, 25: 1.000000, 26: 0.000000, 27: 0.000000, 28: 0.000000, 12: -0.200000, 13: 0.000000, 14: 0.000000}},
    {"time": 2.5000, "name": "出拳", "q": {15: -0.200000, 16: 0.100000, 17: 0.000000, 18: 0.000000, 19: 0.000000, 20: 0.000000, 21: 0.000000, 22: -1.000000, 23: 0.000000, 24: 0.000000, 25: 0.100000, 26: 0.000000, 27: 0.000000, 28: 0.000000, 12: 0.300000, 13: 0.000000, 14: 0.000000}},
    {"time": 3.5000, "name": "收拳", "q": {15: -0.200000, 16: 0.100000, 17: 0.000000, 18: 0.000000, 19: 0.000000, 20: 0.000000, 21: 0.000000, 22: -0.500000, 23: 0.000000, 24: 0.000000, 25: 1.000000, 26: 0.000000, 27: 0.000000, 28: 0.000000, 12: 0.000000, 13: 0.000000, 14: 0.000000}},
    {"time": 5.0000, "name": "回零", "q": {15: 0.000000, 16: 0.000000, 17: 0.000000, 18: 0.000000, 19: 0.000000, 20: 0.000000, 21: 0.000000, 22: 0.000000, 23: 0.000000, 24: 0.000000, 25: 0.000000, 26: 0.000000, 27: 0.000000, 28: 0.000000, 12: 0.000000, 13: 0.000000, 14: 0.000000}},
]


def interpolate_q(t: float) -> dict:
    """Linear interpolate sparse q-dicts over KEYFRAMES."""
    if not KEYFRAMES:
        return {}
    if t <= KEYFRAMES[0]["time"]:
        return dict(KEYFRAMES[0]["q"])
    if t >= KEYFRAMES[-1]["time"]:
        return dict(KEYFRAMES[-1]["q"])
    for i in range(len(KEYFRAMES) - 1):
        k1, k2 = KEYFRAMES[i], KEYFRAMES[i + 1]
        if k1["time"] <= t <= k2["time"]:
            span = k2["time"] - k1["time"]
            r = 0.0 if span <= 1e-9 else (t - k1["time"]) / span
            out = {}
            keys = set(k1["q"]) | set(k2["q"])
            for j in keys:
                a = k1["q"].get(j, 0.0)
                b = k2["q"].get(j, a)
                out[j] = a + (b - a) * r
            return out
    return dict(KEYFRAMES[-1]["q"])


class Custom:
    """Control loop style matches official g1_arm7_sdk_dds_example.Custom."""

    def __init__(self):
        self.time_ = 0.0
        self.control_dt_ = 0.02  # official arm_sdk period
        self.kp = 60.0
        self.kd = 1.5
        self.low_cmd = unitree_hg_msg_dds__LowCmd_()
        self.low_state = None
        self.first_update_low_state = False
        self.crc = CRC()
        self.done = False
        self.total_time = KEYFRAMES[-1]["time"] if KEYFRAMES else 0.0
        self.engage_s = 2.0
        self.release_s = 1.0
        self.phase = "engage"  # engage -> play -> release -> done

    def Init(self):
        self.arm_sdk_publisher = ChannelPublisher("rt/arm_sdk", LowCmd_)
        self.arm_sdk_publisher.Init()
        self.lowstate_subscriber = ChannelSubscriber("rt/lowstate", LowState_)
        self.lowstate_subscriber.Init(self.LowStateHandler, 10)

    def Start(self):
        self.lowCmdWriteThreadPtr = RecurrentThread(
            interval=self.control_dt_, target=self.LowCmdWrite, name="control"
        )
        while not self.first_update_low_state:
            time.sleep(0.1)
        self.lowCmdWriteThreadPtr.Start()

    def LowStateHandler(self, msg: LowState_):
        self.low_state = msg
        if not self.first_update_low_state:
            self.first_update_low_state = True

    def _write_targets(self, target_map: dict, blend: float, enable_w: float):
        blend = float(np.clip(blend, 0.0, 1.0))
        self.low_cmd.motor_cmd[G1JointIndex.kNotUsedJoint].q = float(enable_w)
        for j in ARM_JOINTS:
            cur = float(self.low_state.motor_state[j].q)
            des = float(target_map.get(j, cur))
            q = (1.0 - blend) * cur + blend * des
            self.low_cmd.motor_cmd[j].tau = 0.0
            self.low_cmd.motor_cmd[j].q = q
            self.low_cmd.motor_cmd[j].dq = 0.0
            self.low_cmd.motor_cmd[j].kp = self.kp
            self.low_cmd.motor_cmd[j].kd = self.kd
        self.low_cmd.crc = self.crc.Crc(self.low_cmd)
        self.arm_sdk_publisher.Write(self.low_cmd)

    def LowCmdWrite(self):
        self.time_ += self.control_dt_
        t = self.time_

        if self.phase == "engage":
            ratio = float(np.clip(t / self.engage_s, 0.0, 1.0))
            q0 = interpolate_q(0.0)
            self._write_targets(q0, blend=ratio, enable_w=1.0)
            if t >= self.engage_s:
                self.phase = "play"
                self.time_ = 0.0
                print("[phase] play dance")

        elif self.phase == "play":
            q = interpolate_q(t)
            self._write_targets(q, blend=1.0, enable_w=1.0)
            if t >= self.total_time:
                self.phase = "release"
                self.time_ = 0.0
                print("[phase] release arm_sdk")

        elif self.phase == "release":
            ratio = float(np.clip(t / self.release_s, 0.0, 1.0))
            q_end = interpolate_q(self.total_time)
            self._write_targets(q_end, blend=1.0, enable_w=(1.0 - ratio))
            if t >= self.release_s:
                self.phase = "done"
                self.done = True
                print("[phase] done")


if __name__ == "__main__":
    print("WARNING: Clear the area. Keep remote e-stop ready.")
    print("This script uses official rt/arm_sdk (waist + arms only).")
    dur = KEYFRAMES[-1]["time"] if KEYFRAMES else 0.0
    print("Dance duration: %.2f s, frames: %d" % (dur, len(KEYFRAMES)))
    input("Press Enter to continue...")

    if len(sys.argv) > 1:
        ChannelFactoryInitialize(0, sys.argv[1])
    else:
        print("Usage: python3 %s <network_interface>" % sys.argv[0])
        print("Example: python3 %s enp6s0" % sys.argv[0])
        sys.exit(1)

    custom = Custom()
    custom.Init()
    custom.Start()

    while True:
        time.sleep(0.5)
        if custom.done:
            print("Done!")
            sys.exit(0)
