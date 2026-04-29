import sys
import os

from env.game_env import GamePlayerEnv
import torch

def test_gym():
    print(f"PyTorch Version: {torch.__version__}")
    print(f"ROCm Available: {torch.cuda.is_available()} (PyTorch sees ROCm as CUDA)")
    if torch.cuda.is_available():
        print(f"Device Name: {torch.cuda.get_device_name(0)}")

    print("\n--- Initializing Gym Environment ---")
    env = GamePlayerEnv()
    
    print("\n--- Testing Reset ---")
    obs, info = env.reset()
    print("Observation Keys:", obs.keys())
    print("Player State Shape:", obs["player_state"].shape)
    print("Entities Shape:", obs["entities"].shape)
    
    print("\n--- Testing Step ---")
    action = env.action_space.sample()
    print("Sampled Action:", {k: v.shape if hasattr(v, 'shape') else v for k, v in action.items()})
    
    next_obs, reward, terminated, truncated, info = env.step(action)
    print("Step Reward:", reward)
    print("Terminated:", terminated)
    
    env.close()
    print("\nEnvironment test successful!")

if __name__ == "__main__":
    test_gym()
