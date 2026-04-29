# Fallout 4 Reinforcement Learning (F4RL)

A high-performance, introspective Reinforcement Learning framework for Fallout 4.

## The Vision: Introspection over Pixels
Traditional approaches to Reinforcement Learning in complex 3D environments often rely on CNNs or LLMs processing RGB-D (pixel) data. While generalized, these methods are computationally expensive, suffer from high latency, and operate as "black boxes" with no insight into the underlying game state.

**F4RL changes the paradigm.** By leveraging a custom F4SE plugin (`ModShim`), this project bypasses the need for heavy computer vision. Instead, it accesses the game's internal structured data directly via shared memory. This allows for:
* **Near-Zero Latency:** High-frequency training loops synchronized with the engine.
* **True Introspection:** Direct access to entity positions, health, and game state.
* **Hardware Efficiency:** Minimal CPU/GPU overhead compared to pixel-based models.
* **Precise Fine-Tuning:** Targeted reward shaping based on actual game variables.

## Project Scope
This is a **research and development framework**. It is intended for developers, researchers, and enthusiasts to build upon. 
* **Note:** This is not a "cheating" tool or a consumer utility for Fallout 4. It is a platform for training intelligent agents within the engine's ecosystem.

## Prerequisites
To use this framework, the following components must be active:
1. **The ModShim Plugin (C++):** An F4SE plugin that hooks into the Fallout 4 engine to exfiltrate game state data.
2. **Shared Memory Bridge:** The plugin must be configured to create the shared memory segment at: `Z:\dev\shm\F4RL_IPC`.
3. **Python Environment:** A Python 3.x environment with `gymnasium`, `torch`, and `ctypes` compatibility.

## Repository Structure
* `env/`: Gymnasium environment implementation and IPC schema definitions.
* `training/`: Implementation of training algorithms (Online RL and Legacy Behavioral Cloning).
* `docs/`: Detailed technical documentation regarding architecture and logic.
* `test_env.py`: Utility for verifying the connection between the Python environment and the game.

## Getting Started
1. Ensure `ModShim` is installed and the shared memory path is accessible.
2. Run `python test_env.py` to verify that the Python environment can successfully read the `GameStateStruct`.
3. Once connectivity is confirmed, initiate training using the scripts in the `training/` directory.
