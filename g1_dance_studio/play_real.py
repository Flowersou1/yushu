"""
Play a Studio YAML dance on real G1 — official SDK paths.

Usage (on Ubuntu server connected to robot):
  python play_real.py --iface enp6s0 --dance dances/demo_punch.yaml --path arm_sdk
  python play_real.py --iface enp6s0 --dance dances/my.yaml --path lowcmd   # hang robot!

Defaults to arm_sdk (recommended for upper-body dance while loco balances).
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from src.g1_official import ARM_SDK_JOINTS, DT_ARM_SDK, DT_LOW_LEVEL, G1_NUM_MOTOR
from src.joint_map import JointMap
from src.trajectory import TrajectoryGenerator


def main():
    parser = argparse.ArgumentParser(description="Play G1 dance YAML on real robot")
    parser.add_argument("--iface", required=True, help="network interface, e.g. enp6s0")
    parser.add_argument("--dance", required=True, help="path to YAML from Dance Studio")
    parser.add_argument(
        "--path",
        choices=["arm_sdk", "lowcmd"],
        default="arm_sdk",
        help="arm_sdk=upper body (safe default); lowcmd=full body (dangerous)",
    )
    parser.add_argument("--domain", type=int, default=0)
    parser.add_argument("--speed", type=float, default=1.0, help="playback speed scale")
    parser.add_argument("--dry-run", action="store_true", help="no SDK, only print")
    args = parser.parse_args()

    base = os.path.dirname(os.path.abspath(__file__))
    config = os.path.join(base, "config", "robot_g1_29dof.yaml")
    joint_map = JointMap(config)
    dance_path = args.dance
    if not os.path.isabs(dance_path):
        dance_path = os.path.join(base, dance_path)

    traj = TrajectoryGenerator.from_yaml(dance_path, joint_map, dt=0.01)
    if not traj.keyframes:
        print("No keyframes in", dance_path)
        sys.exit(1)

    print("=== G1 Real Playback ===")
    print(f"file: {dance_path}")
    print(f"frames: {len(traj.keyframes)}  duration: {traj.total_time:.2f}s")
    print(f"path: {args.path}  iface: {args.iface}")
    print("Joint indices follow official G1JointIndex (0..28).")
    if args.path == "lowcmd":
        print("WARNING: lowcmd takes full motor control. Hang the robot. Clear area.")
    else:
        print("Arm SDK: only waist+arms; keep loco/balance standing.")
    input("Press Enter to continue (Ctrl+C to abort)...")

    if args.dry_run:
        from src.robot_backend import dry_run_print_command

        q = traj.interpolate(0.0)
        dry_run_print_command(q, path=args.path)
        print("dry-run done")
        return

    from src.robot_backend import ArmSdkBackend, LowCmdBackend

    if args.path == "arm_sdk":
        backend = ArmSdkBackend(args.iface, domain_id=args.domain)
        dt = DT_ARM_SDK / max(args.speed, 0.05)
        # smooth engage 2s from current pose
        print("Engaging arm_sdk (blend in 2s)...")
        t_eng = 0.0
        while t_eng < 2.0:
            q = traj.interpolate(0.0)
            backend.send_target_angles(q, blend=t_eng / 2.0)
            backend.wait()
            t_eng += DT_ARM_SDK
    else:
        backend = LowCmdBackend(args.iface, domain_id=args.domain, release_motion=True)
        dt = DT_LOW_LEVEL / max(args.speed, 0.05)
        print("Lowcmd engage (blend to start pose 3s)...")
        t_eng = 0.0
        while t_eng < 3.0:
            q = traj.interpolate(0.0)
            backend.send_target_angles(q, blend=t_eng / 3.0)
            time.sleep(DT_LOW_LEVEL)
            t_eng += DT_LOW_LEVEL

    print("Playing...")
    t = 0.0
    total = traj.total_time
    try:
        while t <= total:
            q = traj.interpolate(t)
            if args.path == "arm_sdk":
                backend.send_target_angles(q, blend=1.0)
                backend.wait()
                t += DT_ARM_SDK * args.speed
            else:
                backend.send_target_angles(q, blend=1.0)
                time.sleep(DT_LOW_LEVEL)
                t += DT_LOW_LEVEL * args.speed
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        if args.path == "arm_sdk":
            print("Releasing arm_sdk...")
            backend.release()
        print("Done.")


if __name__ == "__main__":
    main()
