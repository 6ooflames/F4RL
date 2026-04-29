#!/bin/bash

# Build and Deploy script for the C++ Mod Shim
# Cross-compiles using MinGW and copies to the Fallout 4 Wine Prefix

BUILD_DIR="build"
GAME_DIR="/home/davidk/Games/Fallout 4 GOTY"
PLUGIN_DIR="$GAME_DIR/Data/F4SE/Plugins"

echo "=== Building F4RL_Shim ==="
mkdir -p $BUILD_DIR
cd $BUILD_DIR

# Run CMake using the MinGW toolchain
cmake -DCMAKE_TOOLCHAIN_FILE=../mingw-toolchain.cmake -DCMAKE_BUILD_TYPE=Release ..

# Compile
make -j$(nproc)

if [ $? -eq 0 ]; then
    echo "Build successful!"
    # Deploy
    echo "=== Deploying to Fallout 4 ==="
    mkdir -p "$PLUGIN_DIR"
    cp bin/libF4RL_Shim.dll "$PLUGIN_DIR/F4RL_Shim.dll"
    
    echo "Deployed to: $PLUGIN_DIR/F4RL_Shim.dll"

    # Generate pendant ipc_schema.py
    echo "=== Generating Python IPC Schema==="
    cd ..
    python "python generate_schema.py"
else
    echo "Build failed!"
    exit 1
fi
