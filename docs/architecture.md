# System Architecture

The F4RL architecture is built on a closed-loop, bidirectional communication bridge between the Fallout 4 game engine and a Python-based Reinforcement Learning agent.

## The Communication Loop

The system functions through a three-tier hierarchy:

1. **The Game Engine (Fallout 4):** The source of truth. It processes game logic, physics, and entity states.
2. **The Middleware (`ModShim`):** A C++ F4SE plugin that hooks into the engine. It performs two critical tasks:
    * **Exfiltration:** Captures internal game state (positions, health, etc.) and writes it to a specific Shared Memory segment.
    * **Command Execution:** Listens for specific command strings (e.g., `tgm`) passed from Python to trigger engine-side changes.
3. **The Trainer (Python/CleanRL):** The intelligence layer. It reads the Shared Memory, processes the data into tensors, and sends actions/commands back through the bridge.

## Shared Memory Interface
Communication is handled via a structured shared memory segment located at `Z:\dev\shm\F4RL_IPC`. 

The data structure is defined in `env/ipc_schema.py` using `ctypes`. This ensures that both the C++ plugin and the Python environment share an identical memory layout, allowing for high-speed, zero-copy data access.

### Data Flow
* **Inbound (Game $\to$ Agent):** `GameStateStruct` $\to$ `ctypes` $\to$ `Gymnasium Observation Space`.
* **Outbound (Agent $\to$ Game):** `Command String` $\to$ `Shared Memory` $\to$ `F4SE Plugin Hook` $\to$ `Engine Command Execution`.

## Future Development: Command Expansion
While the system currently focuses on observation, the architecture is designed to support a "Command Buffer." This will allow the agent to not only react to the world but to actively manipulate the environment (e.g., toggling God Mode via `tgm` to facilitate training in high-danger zones).
