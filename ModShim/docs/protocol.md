# IPC Protocol Specification

The `F4RL_IPC` protocol defines the structure of the shared memory used for communication between the C++ ModShim and the Python Agent. To ensure compatibility across different languages and compilers, the data is packed using a single-byte alignment (`#pragma pack(push, 1)`).

## 🧱 Data Structures

### `EntityData`
Represents a single entity (Actor, NPC, etc.) discovered in the game world.

| Field | Type | Description |
| :---    | :--- | :--- |
| `formId` | `uint32_t` | The unique identifier for the object in Fallout 4. |
| `typeId` | `uint32_t` | A classification ID (e.g., 43 for `kFormType_ACHR`). |
| `x` | `float` | World-space X coordinate. |
| `y` | `float` | World-space Y coordinate. |
| `z` | `float` | World-space Z coordinate. |

### `WaypointData`
Represents a target destination for the agent.

| Field | Type | Description |
| :--- | :--- | :--- |
| `x` | `float` | Target X coordinate. |
| `y` | `float` | Target Y coordinate. |
| `z` | `float` | Target Z coordinate. |

### `GameStateStruct`
The primary structure mapped into memory. This is the "Single Source of Truth."

#### 🕹️ Command Buffer (Agent $\to$ Game)
These fields are written by the Python Agent and read by the C++ Shim.

| Field | Type | Description |
| :--- | :--- | :--- |
| `execute_command` | `uint8_t` | If `1`, the shim will execute the string in `command_string`. Set to `0` when finished. |
| `command_string` | `char[64]` | The console command to be injected. |
| `delta_yaw` | `float` | Change in yaw (look left/right). |
| `delta_pitch` | `float` | Change in pitch (look up/down). |
| `discrete_action` | `uint8_t` | Movement action (1: W, 2: S, 3: A, 4: D). |
| `jump` | `bool` | If `true`, triggers Spacebar. |
| `click_lmb` | `bool` | If `true`, triggers Left Mouse Button. |
| `click_rmb` | `bool` | If `true`, triggers Right Mouse Button. |
| `press_e` | `bool` | If `true`, triggers the 'E' (Interact) key. |

#### 👁️ State Telemetry (Game $\to$ Agent)
These fields are updated by the C++ Shim and read by the Python Agent.

| Field | Type | Description |
| :--- | :--- | :--- $\to$ |
| `player_x` | `float` | Current player X position. |
| `player_y` | `float` | Current player Y position. |
| `player_z` | `float` | Current player Z position. |
| `player_yaw` | `float` | Current player rotation (Yaw). |
| `player_pitch` | `float` | Current player rotation (Pitch). |
| `player_health` | `uint16_t` | Current player health. |
| `player_rads` | `uint16_t` | Current player radiation level. |
| `player_actionpoints` | `uint16_t` | Current player action points. |
| `frame_counter` | `uint32_t` | Incremented every tick. Used for synchronization. |
| `debug_val1` | `uint32_t` | Internal debug (e.g., Parent Cell address). |
| `debug_val2` | `uint32_t` | Internal debug (e.g., Entity count). |
| `num_entities` | `uint32_t` | Number of active entities in the `entities` array. |
| `entities` | `EntityData[64]` | Array of nearby detected entities. |
| `num_waypoints` | `uint32_t` | Number of active waypoints in the `waypoints` array. |
| `waypoints` | `WaypointData[32]` | Array of waypoints provided by the agent. |

## ⚙️ Synchronization Logic

To avoid the overhead and complexity of cross-process mutexes, the system uses a **Polling & Heartbeat** mechanism:

1.  **The Heartbeat**: The Python Agent continuously reads the `frame_counter`. 
2.  **Data Freshness**: When `frame_counter` changes, the Agent knows that the `GameStateStruct` contains a new snapshot of the game state.
3.  **Command Acknowledgement**: 
    *   The Agent sets `execute_command = 1` and populates `command_string`.
    *   The Shim detects the command, executes it, and then sets `execute_command = 0`.
    *   The Agent waits for `execute_command` to return to `0` before sending the next command.