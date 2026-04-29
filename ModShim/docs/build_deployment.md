# Build & Deployment Guide

This guide provides instructions for compiling the `ModShim` plugin and deploying it to a running Fallout 4 instance.

## 🛠 Prerequisites

To build the shim, you need the following tools installed on your development environment:

*   **MinGW-w64**: A GCC-based compiler for Windows. This is critical as the shim is specifically designed to be compatible with MinGW's ABI.
*   **CMake**: The build system generator.
*   **Fallout 4 (v1.10.163)**: The target game version.
*   **F4SE**: The Fallout 4 Script Extender must be installed in your Fallout 4 directory.

## 🔨 Building the Plugin

The project uses CMake for its build process. It is recommended to use a separate build directory to keep the source tree clean.

1.  **Navigate to the ModShim directory**:
    ```bash
    cd ModShim
    ```

2.  **Create a build directory**:
    ```bash
    mkdir build && cd build
    ```

3.  **Configure the project**:
    Use the provided MinGW toolchain file to ensure the correct compiler settings are applied.
    ```bash
    cmake .. -DCMAKE_TOOLCHAIN_FILE=../mingw-toolchain.cmake
    ```

4.  **Compile**:
    ```bash
    make
    ```

After a successful build, the compiled plugin will be located at:
`ModShim/build/bin/libF4RL_Shim.dll`

## 🚀 Deployment

Once the `.dll` is built, follow these steps to deploy it:

1.  **Copy the DLL**: Copy `libF4RL_Shim.dll` to your Fallout 4 `Data/F4SE/Plugins/` directory.
    *   *Note: If the `Plugins` folder does not exist, create it.*
2.  **Configure the IPC Path**: Ensure that the path specified in `main.cpp` (line 316) exists and is accessible via Wine/Linux. 
    *   The current default is `Z:\\dev\\shm\\F4RL_IPC`.
    *   If you are running on a different path, you must update this in the source code and recompile.
3.  **Launch the Game**: Start Fallout 4 using the `f4se_loader.exe`.
4.  **Verify**: Check the Fallout 4 logs or the `frame_counter` in the shared memory to confirm that the `AgentLoop` thread has started and is incrementing.

## ⚠️ Troubleshooting

| Issue | Possible Cause | Solution |
| :--- | :--- | :--- |
| **Plugin fails to load** | Incorrect F4SE version or missing dependencies. | Ensure F4SE is correctly installed and `libF4RL_Shim.dll` is in the correct `Plugins` folder. |
| **Game crashes on startup** | ABI mismatch or invalid memory offsets. | Ensure you are using the MinGW toolchain and that the game version matches the offsets in `main.cpp`. |
| **Python Agent cannot connect** | Incorrect IPC file path or permission issues. | Verify the path in `main.cpp` exists and that the Python process has read/write access to it. |
| **Input not working** | DirectInput scancodes mismatch. | Verify that the `DirectInput` scancodes in `main.cpp` match the expected hardware mapping. |