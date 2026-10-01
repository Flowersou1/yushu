"""
DDS bridge to unitree_mujoco / sim — aligned with official LowCmd fields.

Prefer ArmSdkBackend / LowCmdBackend in robot_backend.py for real robot.
This class is the older sim-oriented publisher (rt/lowcmd on domain 1 / lo).
"""

from __future__ import annotations

import time

from src.g1_official import (
    G1_NUM_MOTOR,
    KD_LOW_LEVEL,
    KP_LOW_LEVEL,
    Mode,
    TOPIC_LOWCMD,
)

try:
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher
    from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
    from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_
    from unitree_sdk2py.utils.crc import CRC

    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    print("WARNING: unitree_sdk2py 未安装 — SimulatorBackend 仅占位。")


class SimulatorBackend:
    """Publish LowCmd like g1_low_level_example (for unitree_mujoco)."""

    def __init__(self, domain_id=1, interface="lo"):
        self.dt = 0.01
        if not SDK_AVAILABLE:
            return
        ChannelFactoryInitialize(domain_id, interface)
        self.low_cmd_puber = ChannelPublisher(TOPIC_LOWCMD, LowCmd_)
        self.low_cmd_puber.Init()
        self.crc = CRC()
        self.cmd = unitree_hg_msg_dds__LowCmd_()
        self.cmd.mode_pr = Mode.PR
        self.cmd.mode_machine = 0
        for i in range(G1_NUM_MOTOR):
            self.cmd.motor_cmd[i].mode = 0x01
            self.cmd.motor_cmd[i].q = 0.0
            self.cmd.motor_cmd[i].dq = 0.0
            self.cmd.motor_cmd[i].kp = float(KP_LOW_LEVEL[i])
            self.cmd.motor_cmd[i].kd = float(KD_LOW_LEVEL[i])
            self.cmd.motor_cmd[i].tau = 0.0

    def send_target_angles(self, target_q):
        if not SDK_AVAILABLE:
            return
        self.cmd.mode_pr = Mode.PR
        for i in range(min(G1_NUM_MOTOR, len(target_q))):
            self.cmd.motor_cmd[i].mode = 0x01
            self.cmd.motor_cmd[i].q = float(target_q[i])
            self.cmd.motor_cmd[i].dq = 0.0
            self.cmd.motor_cmd[i].kp = float(KP_LOW_LEVEL[i])
            self.cmd.motor_cmd[i].kd = float(KD_LOW_LEVEL[i])
            self.cmd.motor_cmd[i].tau = 0.0
        self.cmd.crc = self.crc.Crc(self.cmd)
        self.low_cmd_puber.Write(self.cmd)

    def wait(self):
        time.sleep(self.dt)
