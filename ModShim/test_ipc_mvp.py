import os
import time
import mmap
import struct
import ctypes

# 64 closest entities max for now to keep serialization fast
MAX_ENTITIES = 64
MAX_WAYPOINTS = 32

class EntityData(ctypes.Structure):
    _pack_ = 1
    _layout_ = 'ms'
    _fields_ = [
        ("formId", ctypes.c_uint32),
        ("typeId", ctypes.c_uint32),
        ("x", ctypes.c_float),
        ("y", ctypes.c_float),
        ("z", ctypes.c_float),
    ]

class WaypointData(ctypes.Structure):
    _pack_ = 1
    _layout_ = 'ms'
    _fields_ = [
        ("x", ctypes.c_float),
        ("y", ctypes.c_float),
        ("z", ctypes.c_float),
    ]

class GameStateStruct(ctypes.Structure):
    _pack_ = 1
    _layout_ = 'ms'
    _fields_ = [
        # Actions
        ("delta_yaw", ctypes.c_float),
        ("delta_pitch", ctypes.c_float),
        ("discrete_action", ctypes.c_uint8),
        
        # Player State
        ("player_x", ctypes.c_float),
        ("player_y", ctypes.c_float),
        ("player_z", ctypes.c_float),
        ("player_yaw", ctypes.c_float),
        ("player_pitch", ctypes.c_float),
        
        # Diagnostics
        ("frame_counter", ctypes.c_uint32),
        ("debug_val1", ctypes.c_uint32),
        ("debug_val2", ctypes.c_uint32),
        
        # Environment State
        ("num_entities", ctypes.c_uint32),
        ("entities", EntityData * MAX_ENTITIES),
        
        ("num_waypoints", ctypes.c_uint32),
        ("waypoints", WaypointData * MAX_WAYPOINTS),
    ]

def test_bridge():
    """
    Checks /dev/shm/F4RL_IPC for the GameStateStruct and prints Player XYZ.
    """
    print("Waiting for F4RL_Shim to initialize shared memory...")
    file_path = '/dev/shm/F4RL_IPC'
    
    # Wait for the file to exist and be big enough
    while not os.path.exists(file_path) or os.path.getsize(file_path) < 4096:
        time.sleep(1.0)
        
    print("Found IPC File. Connecting...")
    with open(file_path, "r+b") as f:
        mm = mmap.mmap(f.fileno(), 4096)
        
        print(f"Connected! Expected Struct Size: {ctypes.sizeof(GameStateStruct)} bytes")
        try:
            while True:
                mm.seek(0)
                data = mm.read(ctypes.sizeof(GameStateStruct))
                state = GameStateStruct.from_buffer_copy(data)
                
                print(f"[F{state.frame_counter:06d}] "
                      f"Pos: ({state.player_x:.2f}, {state.player_y:.2f}, {state.player_z:.2f}) | "
                      f"Yaw: {state.player_yaw:.2f} | Pitch: {state.player_pitch:.2f} | "
                      f"Ent: {state.num_entities} | DBG: {state.debug_val1:08X}, {state.debug_val2}")
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\nTest cancelled.")
            mm.close()

if __name__ == "__main__":
    print("=== Python IPC Receiver MVP ===")
    print("Please launch Fallout 4 via your Wine Prefix.")
    test_bridge()
