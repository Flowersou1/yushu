#!/usr/bin/env python3
"""CLI: YAML dance -> standalone official-style arm_sdk player .py"""

from __future__ import annotations

import argparse
import os
import sys

from src.export_arm_sdk_script import export_arm_sdk_player
from src.joint_map import JointMap
from src.trajectory import TrajectoryGenerator


def main():
    p = argparse.ArgumentParser(description="Export standalone G1 arm_sdk player script")
    p.add_argument("--dance", required=True, help="Studio YAML path")
    p.add_argument(
        "--out",
        default="",
        help="Output .py path (default: exports/<name>_arm_sdk_player.py)",
    )
    args = p.parse_args()

    base = os.path.dirname(os.path.abspath(__file__))
    config = os.path.join(base, "config", "robot_g1_29dof.yaml")
    dance = args.dance if os.path.isabs(args.dance) else os.path.join(base, args.dance)
    if not os.path.isfile(dance):
        print("Not found:", dance)
        sys.exit(1)

    jm = JointMap(config)
    traj = TrajectoryGenerator.from_yaml(dance, jm)
    if not traj.keyframes:
        print("No keyframes")
        sys.exit(1)

    name = os.path.splitext(os.path.basename(dance))[0]
    out = args.out or os.path.join(base, "exports", f"{name}_arm_sdk_player.py")
    if not os.path.isabs(out):
        out = os.path.join(base, out)

    export_arm_sdk_player(traj, out, dance_name=name, source_yaml=dance)
    print("Wrote:", out)
    print("Deploy:")
    print(f"  scp {out} ubuntu@<serverip>:~/server/beigongshang/<组名>/")
    print(f"  ssh ubuntu@<serverip>")
    print(f"  cd ~/server/beigongshang/<组名>")
    print(f"  LD_LIBRARY_PATH=/usr/local/lib:. python3 {os.path.basename(out)} enp6s0")


if __name__ == "__main__":
    main()
