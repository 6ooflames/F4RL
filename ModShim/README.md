# F4RL ModShim

F4RL ModShim is a C++ F4SE (Fallout 4 Script Extender) plugin that acts as a high-performance bridge between the Fallout 4 game engine and an external AI agent. It facilitates real-time state extraction (player position, nearby entities) and hardware-level input injection (movement, mouse, and console commands) via a shared-memory IPC mechanism.

## 🚀 Overview

The shim enables a closed-loop control system where an external agent (typically a Python-based RL agent) can observe the game environment and execute actions as if they were coming from a local user.

## 📖 Documentation

For detailed information on the system, please refer to the [docs/](./docs/) directory:

*   **[Architecture](./docs/architecture.md)**: High-level system overview, component interconnections, and the "block-out" of the communication loop.
*   **[Protocol](./docs/protocol.md)**: Technical specifications of the IPC shared memory structure and the data contract between C++ and Python.
*   **[Input Injection](./docs/input_injection.md)**: Detailed explanation of how the shim emulates DirectInput and Windows Mouse events.
*   **[Build & Deployment](./docs/build_deployment.md)**: Instructions on setting up the MinGW environment, compiling the plugin, and deploying it to Fallout 4.

## 🛠 Key Features

*   **Low Latency**: Uses shared memory (backed by a file) for near-instantaneous data transfer.
*   **Hardware Emulation**: Uses hardware scancodes and `mouse_event` to ensure compatibility with the engine's input processing.
*   **Entity Awareness**: Scans the current cell and global process lists to provide a localized view of the game world.
*   **Command Injection**: Allows the external agent to execute arbitrary engine console commands.

## 🛠 Requirements

*   **Fallout 4** (Version 1.10.163 recommended)
*   **F4SE** (Fallout 4 Script Extender)
*   **MinGW-w64** (for building)
*   **CMake** (for building)