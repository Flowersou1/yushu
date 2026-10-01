import time

try:
    import mujoco
    import mujoco.viewer

    MUJOCO_AVAILABLE = True
except ImportError:
    MUJOCO_AVAILABLE = False
    print("WARNING: mujoco 库未安装，无法启动原生仿真。")


class MujocoNativeBackend:
    """Local MuJoCo sim for G1 pose edit + dance playback (no DDS required)."""

    def __init__(self, xml_path, dt=0.01, mode="anchored_physics"):
        self.dt = dt
        self.mode = mode  # kinematic | anchored_physics | normal
        self.use_virtual_wire = True
        self.paused = False
        self.reset_requested = False
        self.playback_speed = 1.0
        self.viewer = None
        self.running = True

        def key_callback(keycode):
            # Space / R / S — same shortcuts as before
            if keycode == 32:
                self.paused = not self.paused
                state = "暂停" if self.paused else "继续"
                print(f"\n========== 【{state}】空格切换 ==========")
            elif keycode in (82, 114):  # R/r
                self.reset_requested = True
                print("\n========== 【重播】R ==========")
            elif keycode in (83, 115):  # S/s
                if abs(self.playback_speed - 1.0) < 1e-6:
                    self.playback_speed = 0.2
                    print("\n========== 【慢动作】0.2x ==========")
                else:
                    self.playback_speed = 1.0
                    print("\n========== 【正常速度】1.0x ==========")

        if not MUJOCO_AVAILABLE:
            self.model = None
            self.data = None
            self.num_motors = 29
            self.target_q = [0.0] * self.num_motors
            return

        self.model = mujoco.MjModel.from_xml_path(xml_path)
        self.data = mujoco.MjData(self.model)
        self.model.opt.timestep = 0.002
        mujoco.mj_forward(self.model, self.data)

        self.viewer = mujoco.viewer.launch_passive(
            self.model, self.data, key_callback=key_callback
        )

        self.num_motors = int(self.model.nu)
        self.Kp = 300.0
        self.Kd = 10.0
        self.target_q = [0.0] * self.num_motors

        try:
            self.torso_body_id = self.model.body("torso_link").id
        except Exception:
            self.torso_body_id = 1

        self.robot_mass = mujoco.mj_getTotalmass(self.model)
        self.gravity = abs(float(-self.model.opt.gravity[2]))
        self.hover_force = self.robot_mass * self.gravity
        self.initial_z = float(self.data.qpos[2])
        self.anchor_qpos = self.data.qpos[0:7].copy()

        print(
            f">>> MuJoCo 启动 | motors={self.num_motors} | mass={self.robot_mass:.1f}kg | mode={self.mode}"
        )
        time.sleep(0.2)

    # ------------------------------------------------------------------ state
    def is_viewer_alive(self):
        if not MUJOCO_AVAILABLE or self.viewer is None:
            return False
        return self.viewer.is_running()

    def get_joint_q(self):
        if not MUJOCO_AVAILABLE:
            return list(self.target_q)
        return [float(self.data.qpos[7 + i]) for i in range(self.num_motors)]

    def get_root_z(self):
        if not MUJOCO_AVAILABLE:
            return 0.0
        return float(self.data.qpos[2])

    def set_mode(self, mode):
        if mode not in ("kinematic", "anchored_physics", "normal"):
            return
        self.mode = mode
        if mode == "anchored_physics" and MUJOCO_AVAILABLE:
            self.data.qpos[0:7] = self.anchor_qpos
            self.data.qvel[0:6] = 0.0

    def set_virtual_wire(self, enabled):
        self.use_virtual_wire = bool(enabled)

    def snap_to_targets(self):
        """Instantly place joints at targets (useful when loading a keyframe)."""
        if not MUJOCO_AVAILABLE:
            return
        for i in range(self.num_motors):
            self.data.qpos[7 + i] = self.target_q[i]
            self.data.qvel[6 + i] = 0.0
        if self.mode == "anchored_physics":
            self.data.qpos[0:7] = self.anchor_qpos
            self.data.qvel[0:6] = 0.0
        mujoco.mj_forward(self.model, self.data)

    def reset_root(self):
        if not MUJOCO_AVAILABLE:
            return
        self.data.qpos[0:7] = self.anchor_qpos
        self.data.qvel[:] = 0.0
        for i in range(self.num_motors):
            self.data.qpos[7 + i] = self.target_q[i]
            self.data.qvel[6 + i] = 0.0
        mujoco.mj_forward(self.model, self.data)

    def send_target_angles(self, target_q):
        for i in range(min(self.num_motors, len(target_q))):
            self.target_q[i] = float(target_q[i])

    def wait(self):
        if not MUJOCO_AVAILABLE:
            time.sleep(self.dt)
            return

        while self.paused:
            if not self.is_viewer_alive():
                break
            self.viewer.sync()
            time.sleep(0.01)

        if self.mode == "kinematic":
            for i in range(self.num_motors):
                self.data.qpos[7 + i] = self.target_q[i]
                self.data.qvel[6 + i] = 0.0
            # Pure preview keeps pelvis fixed so the figure doesn't drift
            self.data.qpos[0:7] = self.anchor_qpos
            self.data.qvel[0:6] = 0.0
            mujoco.mj_forward(self.model, self.data)
            if self.is_viewer_alive():
                self.viewer.sync()
            time.sleep(self.dt / max(self.playback_speed, 0.05))
            return

        steps = max(1, int(self.dt / self.model.opt.timestep))
        for _ in range(steps):
            if not self.is_viewer_alive():
                break

            for i in range(self.num_motors):
                q = self.data.qpos[7 + i]
                dq = self.data.qvel[6 + i]
                tau = self.Kp * (self.target_q[i] - q) - self.Kd * dq
                self.data.ctrl[i] = tau

            if self.mode == "normal" and self.use_virtual_wire:
                z_error = self.initial_z - self.data.qpos[2]
                z_vel = self.data.qvel[2]
                spring_force = 5000.0 * z_error - 200.0 * z_vel
                self.data.xfrc_applied[self.torso_body_id, 2] = self.hover_force + spring_force
            else:
                self.data.xfrc_applied[self.torso_body_id, 2] = 0.0

            try:
                mujoco.mj_step(self.model, self.data)
            except Exception as e:
                print(f"\n[警告] 物理步进失败: {e} → 已暂停，可按 R 重置")
                self.paused = True
                break

            if self.mode == "anchored_physics":
                self.data.qpos[0:7] = self.anchor_qpos
                self.data.qvel[0:6] = 0.0

        if self.is_viewer_alive():
            self.viewer.sync()

        sleep_time = self.dt / max(self.playback_speed, 0.05)
        time.sleep(sleep_time)

    def close(self):
        self.running = False
        # passive viewer is closed by user; nothing mandatory
