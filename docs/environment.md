# The Environment Implementation

The `env/` module implements a custom `gymnasium` environment that abstracts the raw shared memory data into a standard Reinforcement Learning interface.

## `ipc_schema.py`
This file serves as the "Contract" between C++ and Python. It defines the `GameStateStruct` using `ctypes`. It includes:
* **Entity Data:** Arrays of positions, health, and metadata for all active entities in the scene.
* **Global State:** Frame counters, player status, and world-wide variables.

* **Command Buffer:** A field dedicated to receiving instruction strings from the Python agent.

## `game_env.py`
The `GameEnv` class wraps the IPC schema into a `gymnasium.Env` interface.

### The Synchronization Spinlock
Because the Python training loop and the Fallout 4 engine run on independent clocks, a synchronization mechanism is required. 
* The environment implements a **Spinlock** pattern. 
* It monitors the `frame_counter` within the `GameStateStruct`.
* The Python loop "waits" (polls) until the engine increments the frame counter, ensuring that the agent never processes the same frame twice and that observations are always fresh.

### Observation Space
The observation space is designed to be **Permutation Invariant**. Because the number of entities (enemies, NPCs, items) in a scene can change dynamically, the environment uses a structure compatible with **DeepSets** or similar architectures. This allows the agent to process a variable number of input vectors without needing a fixed-size input layer.
