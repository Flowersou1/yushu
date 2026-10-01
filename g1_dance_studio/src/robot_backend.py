"""
Real-robot backends aligned with official unitree_sdk2_python G1 examples.

Two paths (do not mix casually):

1) Arm SDK  — g1_arm7_sdk_dds_example.py
   - Topic: rt/arm_sdk
   - Enable: motor_cmd[29].q = 1
   - Control waist + dual arm only; legs stay on built-in balance/loco
   - control_dt ≈ 0.02 s

2) Low-level — g1_low_level_example.py
   - Topic: rt/lowcmd
   - Must MotionSwitcherClient.ReleaseMode() first
   - Full 29 motors, per-joint Kp/Kd, mode_pr, mode_machine
   - control_dt = 0.002 s
   - YOU own balance — hang the robot for first tests

Safety: this module never auto-starts; call only after operator confirm.
"""

from __future__ import annotations

import time
from typing import List, Optional, Sequence

from src.g1_official import (
    ARM_SDK_JOINTS,
    DT_ARM_SDK,
    DT_LOW_LEVEL,
    G1_NUM_MOTOR,
    G1JointIndex,
    KD_LOW_LEVEL,
    KP_ARM_SDK,
    KP_LOW_LEVEL,
    KD_ARM_SDK,
    Mode,
    TOPIC_ARM_SDK,
    TOPIC_LOWCMD,
    TOPIC_LOWSTATE,
)

try:
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize
    from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber
    from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
    from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_
    from unitree_sdk2py.utils.crc import CRC
    from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import (
        MotionSwitcherClient,
    )

    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False


class ArmSdkBackend:
    """Upper-body dance path — mirrors g1_arm7_sdk_dds_example.py."""

    def __init__(self, network_interface: str, domain_id: int = 0):
        if not SDK_AVAILABLE:
            raise RuntimeError(
                "unitree_sdk2py 未安装。真机请在 Ubuntu + 官方 SDK 环境运行。"
            )
        self.dt = DT_ARM_SDK
        self.crc = CRC()
        self.low_cmd = unitree_hg_msg_dds__LowCmd_()
        self.low_state = None
        self._got_state = False

        ChannelFactoryInitialize(domain_id, network_interface)
        self.pub = ChannelPublisher(TOPIC_ARM_SDK, LowCmd_)
        self.pub.Init()
        self.sub = ChannelSubscriber(TOPIC_LOWSTATE, LowState_)
        self.sub.Init(self._on_state, 10)

        # wait for first state
        t0 = time.time()
        while not self._got_state and time.time() - t0 < 10.0:
            time.sleep(0.05)
        if not self._got_state:
            raise RuntimeError("超时未收到 rt/lowstate，请检查网卡与机器人连接")

    def _on_state(self, msg):
        self.low_state = msg
        self._got_state = True

    def enable_arm_sdk(self, weight: float = 1.0):
        """motor_cmd[29].q : 1=enable arm_sdk, 0=release (official)."""
        self.low_cmd.motor_cmd[G1JointIndex.kNotUsedJoint].q = float(weight)

    def send_target_angles(self, target_q: Sequence[float], blend: float = 1.0):
        """
        Send waist+arms targets. Legs are NOT commanded (loco owns them).
        blend in [0,1]: mix toward target from current measured q (smooth start).
        """
        blend = max(0.0, min(1.0, float(blend)))
        self.enable_arm_sdk(1.0)
        for j in ARM_SDK_JOINTS:
            cur = float(self.low_state.motor_state[j].q)
            des = float(target_q[j]) if j < len(target_q) else cur
            q = (1.0 - blend) * cur + blend * des
            self.low_cmd.motor_cmd[j].tau = 0.0
            self.low_cmd.motor_cmd[j].q = q
            self.low_cmd.motor_cmd[j].dq = 0.0
            self.low_cmd.motor_cmd[j].kp = KP_ARM_SDK
            self.low_cmd.motor_cmd[j].kd = KD_ARM_SDK
        self.low_cmd.crc = self.crc.Crc(self.low_cmd)
        self.pub.Write(self.low_cmd)

    def release(self):
        """Fade out arm_sdk control (official stage 4)."""
        for w in [0.75, 0.5, 0.25, 0.0]:
            self.enable_arm_sdk(w)
            self.low_cmd.crc = self.crc.Crc(self.low_cmd)
            self.pub.Write(self.low_cmd)
            time.sleep(self.dt)

    def wait(self):
        time.sleep(self.dt)


class LowCmdBackend:
    """Full-body low-level — mirrors g1_low_level_example.py. Dangerous without hang."""

    def __init__(self, network_interface: str, domain_id: int = 0, release_motion: bool = True):
        if not SDK_AVAILABLE:
            raise RuntimeError(
                "unitree_sdk2py 未安装。真机请在 Ubuntu + 官方 SDK 环境运行。"
            )
        self.dt = DT_LOW_LEVEL
        self.crc = CRC()
        self.low_cmd = unitree_hg_msg_dds__LowCmd_()
        self.low_state = None
        self.mode_machine_ = 0
        self._got_mode = False

        ChannelFactoryInitialize(domain_id, network_interface)

        if release_motion:
            msc = MotionSwitcherClient()
            msc.SetTimeout(5.0)
            msc.Init()
            status, result = msc.CheckMode()
            while result and result.get("name"):
                msc.ReleaseMode()
                status, result = msc.CheckMode()
                time.sleep(1)

        self.pub = ChannelPublisher(TOPIC_LOWCMD, LowCmd_)
        self.pub.Init()
        self.sub = ChannelSubscriber(TOPIC_LOWSTATE, LowState_)
        self.sub.Init(self._on_state, 10)

        t0 = time.time()
        while not self._got_mode and time.time() - t0 < 10.0:
            time.sleep(0.05)
        if not self._got_mode:
            raise RuntimeError("超时未收到 lowstate.mode_machine")

    def _on_state(self, msg):
        self.low_state = msg
        if not self._got_mode:
            self.mode_machine_ = self.low_state.mode_machine
            self._got_mode = True

    def send_target_angles(
        self,
        target_q: Sequence[float],
        mode_pr: int = Mode.PR,
        blend: float = 1.0,
    ):
        blend = max(0.0, min(1.0, float(blend)))
        self.low_cmd.mode_pr = mode_pr
        self.low_cmd.mode_machine = self.mode_machine_
        for i in range(G1_NUM_MOTOR):
            cur = float(self.low_state.motor_state[i].q)
            des = float(target_q[i]) if i < len(target_q) else cur
            q = (1.0 - blend) * cur + blend * des
            self.low_cmd.motor_cmd[i].mode = 1  # enable
            self.low_cmd.motor_cmd[i].tau = 0.0
            self.low_cmd.motor_cmd[i].q = q
            self.low_cmd.motor_cmd[i].dq = 0.0
            self.low_cmd.motor_cmd[i].kp = KP_LOW_LEVEL[i]
            self.low_cmd.motor_cmd[i].kd = KD_LOW_LEVEL[i]
        self.low_cmd.crc = self.crc.Crc(self.low_cmd)
        self.pub.Write(self.low_cmd)

    def wait(self):
        time.sleep(self.dt)


def dry_run_print_command(target_q: Sequence[float], path: str = "arm_sdk"):
    """Print what would be sent — for Windows authoring machines without SDK."""
    print(f"[dry-run] path={path} motors={len(target_q)}")
    if path == "arm_sdk":
        print(f"  topic={TOPIC_ARM_SDK} enable motor[29].q=1")
        for j in ARM_SDK_JOINTS:
            print(f"  motor[{j}].q={target_q[j]:.4f} kp={KP_ARM_SDK} kd={KD_ARM_SDK}")
    else:
        print(f"  topic={TOPIC_LOWCMD} mode_pr=PR")
        for i in range(min(G1_NUM_MOTOR, len(target_q))):
            print(
                f"  motor[{i}].q={target_q[i]:.4f} kp={KP_LOW_LEVEL[i]} kd={KD_LOW_LEVEL[i]}"
            )
