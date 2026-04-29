import sys
import os
import math
import numpy as np
import pickle
import time
from collections import deque

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from env.game_env import GamePlayerEnv

class NavigationExpert:
    def __init__(self):
        self.target_form_id = None
        self.target_xyz = None

        # Stuck detection
        self.pos_history = deque(maxlen=60) # Last 2 seconds (at 30hz)
        self.stuck_frames = 0
        self.backing_up_frames = 0

    def get_smooth_aim(self, player_xyz, player_yaw_pitch, target_xyz):
        """Calculates yaw/pitch using a Proportional Controller to prevent rubber-banding."""
        px, py, pz = player_xyz
        tx, ty, tz = target_xyz
        pyaw, ppitch = player_yaw_pitch

        # Calculate desired angles
        dx = tx - px
        dy = ty - py

        desired_yaw = math.atan2(dy, dx)

        dz = tz - pz
        dist_2d = math.sqrt(dx**2 + dy**2)
        desired_pitch = math.atan2(dz, dist_2d)

        # --- FIX: Clamp Pitch to the Horizon ---
        # Forces the agent to look forward, not at the floor/sky
        desired_pitch = np.clip(desired_pitch, -0.25, 0.25)
        # ---------------------------------------

        yaw_delta = (desired_yaw - pyaw + math.pi) % (2 * math.pi) - math.pi
        pitch_delta = desired_pitch - ppitch

        P_GAIN = 0.35
        norm_yaw = np.clip(yaw_delta * P_GAIN, -1.0, 1.0)
        norm_pitch = np.clip(pitch_delta * P_GAIN, -1.0, 1.0)

        if abs(yaw_delta) < 0.05: norm_yaw = 0.0
        if abs(pitch_delta) < 0.05: norm_pitch = 0.0

        return np.array([norm_yaw, norm_pitch], dtype=np.float32)

    def analyze_obstacles(self, entities, player_xyz, player_yaw):
        """
        Only reacts to obstacles that are actually IN FRONT of the player.
        Returns a steering suggestion (None, 'Left', or 'Right').
        """
        px, py, pz = player_xyz

        closest_dist = float('inf')
        steer_dir = None

        for ent in entities:
            if np.all(ent == 0): continue

            ex, ey, ez = ent[0], ent[1], ent[2]

            # Vector to entity
            dx = ex - px
            dy = ey - py
            dist = math.sqrt(dx**2 + dy**2 + (ez - pz)**2)

            if dist > 50.0: continue # Ignore far away things

            # Calculate angle relative to our current heading
            angle_to_ent = math.atan2(dy, dx)
            relative_angle = (angle_to_ent - player_yaw + math.pi) % (2 * math.pi) - math.pi

            # If obstacle is within a 60-degree cone in front of us (-30 to +30 deg)
            if abs(relative_angle) < (math.pi / 3.0):
                if dist < closest_dist:
                    closest_dist = dist
                    # If obstacle is slightly right, steer left. If left, steer right.
                    steer_dir = 3 if relative_angle > 0 else 4 # 3 = A (Left), 4 = D (Right)

        return steer_dir

    def check_if_stuck(self, current_xyz):
        """Detects if the agent is walking into a wall based on position history."""
        self.pos_history.append(current_xyz)

        if len(self.pos_history) < 60: return False

        # Compare current pos to where we were 2 seconds ago
        old_px, old_py, old_pz = self.pos_history[0]
        px, py, pz = current_xyz
        dist_moved = math.sqrt((px - old_px)**2 + (py - old_py)**2)

        if dist_moved < 30.0: # Moved less than 30 units in 2 seconds
            self.stuck_frames += 1
        else:
            self.stuck_frames = max(0, self.stuck_frames - 2)

        # Trigger backup routine if stuck for a sustained moment
        if self.stuck_frames > 6:
            self.backing_up_frames = 15 # Back up for .5 seconds
            self.stuck_frames = 0
            self.pos_history.clear()

        return self.backing_up_frames > 0

    def should_jump(self, current_xyz, target_xyz=None):
        """Returns True (1) if the agent should press the Jump button."""

        # 1. Jump to dislodge if we are stuck
        # (Jumping while backing up is a great way to get unstuck from rocks)
        if self.backing_up_frames > 0:
            # Alternate jumping every few frames so it doesn't just hold the key down
            return 1 if (self.backing_up_frames % 4 == 0) else 0

        # 2. Jump if the target is physically above us and we are getting close
        if target_xyz:
            px, py, pz = current_xyz
            tx, ty, tz = target_xyz

            dist_2d = math.sqrt((tx - px)**2 + (ty - py)**2)
            z_diff = tz - pz # Positive means target is higher than us

            # If the target is within 300 units, but at least 50 units higher than our feet
            if dist_2d < 300.0 and z_diff > 50.0:
                # Randomize the jump slightly so it "hops" up hills instead of flying
                import random
                return 1 if random.random() > 0.8 else 0

        return 0

    def select_target(self, entities, player_xyz):
        """Finds the target designated by the Environment."""
        for ent in entities:
            if ent[7] == 1.0:  # Index 7 is our new 'is_target' flag
                return (ent[0], ent[1], ent[2])
        return None

def run_expert_collection(episodes=10, max_steps=1500, save_path="expert_data.pkl", target_cell=None):
    env = GamePlayerEnv()
    dataset =[]

    print(f"Starting Expert Autopilot Data Collection (Saving to {save_path})...")

    for ep in range(episodes):
        obs, _ = env.reset(options={"cell_name": target_cell})
        expert = NavigationExpert()
        print(f"Episode {ep+1} started in {target_cell}.")

        for step in range(max_steps):
            player_state = obs["player_state"]
            entities = obs["entities"]
            px, py, pz = player_state[0:3]
            pyaw, ppitch = player_state[3:5]
            player_xyz = (px, py, pz)

            # --- Expert Logic ---
            action = {
                "mouse_delta": np.array([0.0, 0.0], dtype=np.float32),
                "movement": 0, # Idle
                "jump": False,
                "buttons": np.zeros(4, dtype=np.int8)
            }

            target_xyz = expert.select_target(entities, player_xyz)

            # 1. Stuck Check (Override everything if jumping past / backing up)
            if expert.check_if_stuck(player_xyz):
                if target_xyz[2] <= player_xyz[2]:
                    action["jump"] = True
                action["movement"] = 2 # 'S' - Back up
                expert.backing_up_frames -= 1
            else:
                # 2. Target Selection

                if target_xyz is not None:
                    # 3. Aiming
                    action["mouse_delta"] = expert.get_smooth_aim(player_xyz, (pyaw, ppitch), target_xyz)

                    # 4. Obstacle Avoidance vs Forward Movement
                    steer = expert.analyze_obstacles(entities, player_xyz, pyaw)
                    if steer:
                        action["movement"] = steer # 3 (A) or 4 (D)
                    else:
                        action["movement"] = 1 # 1 (W) - Move forward toward target

            # Save the transition
            dataset.append({
                "obs": obs,
                "action": action
            })

            # Step the environment
            next_obs, reward, terminated, truncated, _ = env.step(action)
            obs = next_obs

            if terminated or truncated:
                break

            time.sleep(1/30.0)

    env.close()

    print(f"Collected {len(dataset)} transitions. Saving...")
    with open(save_path, "wb") as f:
        pickle.dump(dataset, f)
    print("Done!")

if __name__ == "__main__":
    run_expert_collection(episodes=10, max_steps=1500)
