import gymnasium as gym
import numpy as np
from gymnasium import spaces
import mmap
import struct
import ctypes
import math
import random
import time
import os

class GamePlayerEnv(gym.Env):
    """
    State-Based RL Environment for Fallout 4 via IPC Shared Memory.
    Bypasses visual RGB-D in favor of direct engine entity arrays.
    """
    
    metadata = {"render_modes": ["human"], "render_fps": 180}

    def __init__(self, render_mode=None, max_entities=64, mmap_name="F4RL_IPC", training_cells=None):
        super(GamePlayerEnv, self).__init__()
        self.render_mode = render_mode
        self.max_entities = max_entities
        self.mmap_name = mmap_name


        self.training_cells = training_cells or ["SanctuaryExt"]
        
        self.current_step = 0
        self.max_steps = 10800 # End episode after ~1 minute of actions

        # --- ACTION SPACE ---
        # 1. mouse_delta: [Delta Yaw, Delta Pitch] normalized to [-1.0, 1.0]
        # 2. movement: Discrete 5 (0: Idle, 1: W, 2: S, 3: A, 4: D)
        # 3. buttons: MultiBinary 4 (0: Attack, 1: Block, 2: Jump, 3: Interact)
        self.action_space = spaces.Dict({
            "mouse_delta": spaces.Box(low=-1.0, high=1.0, shape=(2,), dtype=np.float32),
            "movement": spaces.Discrete(5), # 0: Idle, 1: W, 2: S, 3: A, 4: D
            "jump": spaces.Discrete(2),     # 0: False, 1: True
            "click_lmb": spaces.Discrete(2),
            "click_rmb": spaces.Discrete(2),
            "press_e": spaces.Discrete(2)
        })

        # --- OBSERVATION SPACE ---
        # 1. player_state: [X, Y, Z, Yaw, Pitch, HP, AP, Is_Combat]
        # 2. entities: Matrix of shape (max_entities, 6). 
        #    Each row: [X, Y, Z, TypeID, Distance, Is_Hostile]
        self.observation_space = spaces.Dict({
        "player_state": spaces.Box(low=-np.inf, high=np.inf, shape=(8,), dtype=np.float32),
        "entities": spaces.Box(low=-np.inf, high=np.inf, shape=(self.max_entities, 8), dtype=np.float32)
        })

        self.env_target_form_id = None
        self.prev_dist_to_target = None


        # IPC State
        self.ipc_mem = None
        self._connect_ipc()

    def _connect_ipc(self):
        """
        Connects to the Memory-Mapped File created by the C++ Mod Shim.
        """
        from .ipc_schema import GameStateStruct
        self.state_struct = GameStateStruct
        self.struct_size = ctypes.sizeof(GameStateStruct)
        
        try:
            ipc_path = f"/dev/shm/{self.mmap_name}"
            
            if not os.path.exists(ipc_path):
                print(f"[Warning] IPC file {ipc_path} not found. Waiting for Mod Shim...")
                # We'll wait a bit but not block forever
                for _ in range(5):
                    if os.path.exists(ipc_path): break
                    time.sleep(1)
            
            if os.path.exists(ipc_path):
                fd = os.open(ipc_path, os.O_RDWR)
                self.ipc_mem = mmap.mmap(fd, self.struct_size)
                print("Successfully connected to Mod Shim IPC.")
            else:
                print("Could not find IPC file. Running in disconnected mode.")
        except Exception as e:
            print(f"IPC Connection Error: {e}. Running in disconnected mode.")

    def _read_state_from_ipc(self):
        """
        Reads the structured game state from the shared memory block.
        """
        if not self.ipc_mem:
            return {
                "player_state": np.zeros(8, dtype=np.float32),
                "entities": np.zeros((self.max_entities, 8), dtype=np.float32)
            }
            
        try:
            # Read from mmap into our ctypes struct
            self.ipc_mem.seek(0)
            data = self.ipc_mem.read(self.struct_size)
            state = self.state_struct.from_buffer_copy(data)
            
            # Format player_state: [X, Y, Z, Yaw, Pitch, HP, AP, Is_Combat]
            # (HP/AP/Combat not yet implemented in C++, so we keep them as 100/100/0)
            player_state = np.array([
                state.player_x, state.player_y, state.player_z,
                state.player_yaw, state.player_pitch,
                100.0, 100.0, 0.0
            ], dtype=np.float32)
            
            # Format entities: [X, Y, Z, TypeID, Distance, Is_Hostile]
            entities = np.zeros((self.max_entities, 8), dtype=np.float32)
            num_to_copy = min(state.num_entities, self.max_entities)
            
            for i in range(num_to_copy):
                ent = state.entities[i]
                # Use numpy for distance to avoid 'math' undefined issues and for speed
                dist = np.linalg.norm(np.array([ent.x - state.player_x, 
                                                ent.y - state.player_y, 
                                                ent.z - state.player_z]))
                
                is_target = 1.0 if float(ent.formId) == self.env_target_form_id else 0.0
                entities[i] =[
                    ent.x, ent.y, ent.z,
                    float(ent.typeId),
                    dist,
                    0.0, # Is_Hostile
                    float(ent.formId),
                    is_target
                ]
                
            info = {
                "frame": state.frame_counter,
                "debug1": state.debug_val1,
                "debug2": state.debug_val2
            }
                
            return {
                "player_state": player_state,
                "entities": entities
            }, info
        except Exception as e:
            print(f"Error reading IPC: {e}")
            return {
                "player_state": np.zeros(8, dtype=np.float32),
                "entities": np.zeros((self.max_entities, 8), dtype=np.float32)
            }, {}

    def _get_mapped_state(self):
        """Returns a ctypes struct mapped directly over the shared memory buffer."""
        if not self.ipc_mem: return None
        return self.state_struct.from_buffer(self.ipc_mem)

    def _write_actions_to_ipc(self, action):
        mapped_state = self._get_mapped_state()
        if mapped_state:
            mapped_state.delta_yaw = float(action["mouse_delta"][0])
            mapped_state.delta_pitch = float(action["mouse_delta"][1])
            mapped_state.discrete_action = int(action["movement"])
            mapped_state.jump = bool(action["jump"])
            mapped_state.click_lmb = bool(action.get("click_lmb", 0))
            mapped_state.click_rmb = bool(action.get("click_rmb", 0))
            mapped_state.press_e = bool(action.get("press_e", 0))

    def step(self, action):
        old_info = self._read_state_from_ipc()[1]
        old_frame = old_info.get("frame", 0)

        self._write_actions_to_ipc(action)

        # Spinlock: Wait for Fallout 4 to process the frame
        timeout = time.time() + 0.5
        while True:
            obs, info = self._read_state_from_ipc()
            if info.get("frame", 0) > old_frame or time.time() > timeout:
                break
            time.sleep(0.001) # 1ms poll

        reward = self._compute_reward(obs)

        terminated = False
        truncated = False

        # Terminate episode after max steps
        self.current_step += 1
        if self.current_step >= self.max_steps:
            truncated = True

        if info.get("frame", 0) % 100 == 0:
            print(f"IPC Tick: {info.get('frame')} | Reward: {reward:.3f}")

        return obs, reward, terminated, truncated, info


    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0

        self.env_target_form_id = None
        self.prev_dist_to_target = None

        mapped_state = self._get_mapped_state()

        # Randomly pick a cell to train in to ensure generalized learning
        if len(self.training_cells) > 1:
            cell_name = random.choice(self.training_cells)
            if mapped_state:
                command = f"coc {cell_name}".encode('utf-8')
                mapped_state.execute_command = 1
                mapped_state.command_string = command

                print(f"\n[Environment] Resetting Episode. Teleporting to: {cell_name}")
                while mapped_state.execute_command == 1:
                    time.sleep(0.1)
                time.sleep(2.0)

        obs, info = self._read_state_from_ipc()
        return obs, info

    def _compute_reward(self, obs):
        player_xyz = obs["player_state"][0:3]
        entities = obs["entities"]

        target_xyz = None
        reward = 0.0

        # 1. Check if we already have an active target
        if self.env_target_form_id is not None:
            for ent in entities:
                if ent[6] == self.env_target_form_id: # Index 6 is FormID
                    target_xyz = ent[0:3]
                    dist = np.linalg.norm(target_xyz - player_xyz)

                    if dist < 150.0:
                        # Target Reached! Huge reward and clear target
                        self.env_target_form_id = None
                        self.prev_dist_to_target = None
                        return 5.0
                    break
            # If the loop finished and target_xyz is STILL None, the target is gone.
            if target_xyz is None:
                self.env_target_form_id = None
                self.prev_dist_to_target = None

        # 2. Pick a new target if we don't have one (Matches Expert Logic)
        if self.env_target_form_id is None:
            valid_targets =[]
            for ent in entities:
                if np.all(ent == 0): continue
                dist = np.linalg.norm(ent[0:3] - player_xyz)
                if 500.0 < dist < 3000.0:
                    valid_targets.append((ent, dist))

            if valid_targets:
                valid_targets.sort(key=lambda x: x[1])
                chosen_ent = valid_targets[len(valid_targets)//2][0]
                self.env_target_form_id = chosen_ent[6]
                target_xyz = chosen_ent[0:3]
                self.prev_dist_to_target = np.linalg.norm(target_xyz - player_xyz)
                return 0.0 # Just locked on, no movement yet

        # 3. Calculate Delta-Distance Reward
        if target_xyz is not None and self.prev_dist_to_target is not None:
            curr_dist = np.linalg.norm(target_xyz - player_xyz)

            # If curr_dist is SMALLER than prev_dist, the reward is POSITIVE.
            delta_dist = self.prev_dist_to_target - curr_dist

            # Scale it so 10 units of movement = 1.0 reward
            reward = delta_dist / 10.0

            # Add a tiny penalty (-0.02) to discourage standing completely still
            reward -= 0.02

            self.prev_dist_to_target = curr_dist

            # Clip to prevent massive physics-glitch spikes
            reward = np.clip(reward, -2.0, 2.0)

        return float(reward)

    def close(self):
        if self.ipc_mem:
            self.ipc_mem.close()
