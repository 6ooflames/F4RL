import ctypes

MAX_ENTITIES = 64
MAX_WAYPOINTS = 32

class EntityData(ctypes.Structure):
    _pack_ = 1
    _layout_ = 'ms'
    _fields_ =[
        ("formId", ctypes.c_uint32),
        ("typeId", ctypes.c_uint32), # Optional classification
        ("x", ctypes.c_float),
        ("y", ctypes.c_float),
        ("z", ctypes.c_float),
    ]

class WaypointData(ctypes.Structure):
    _pack_ = 1
    _layout_ = 'ms'
    _fields_ =[
        ("x", ctypes.c_float),
        ("y", ctypes.c_float),
        ("z", ctypes.c_float),
    ]

class GameStateStruct(ctypes.Structure):
    _pack_ = 1
    _layout_ = 'ms'
    _fields_ =[
        # Command Buffer for Automation
        ("execute_command", ctypes.c_uint8),
        ("command_string", ctypes.c_char * 64),
        # Actions (Agent -> Game)
        ("delta_yaw", ctypes.c_float),
        ("delta_pitch", ctypes.c_float),
        ("discrete_action", ctypes.c_uint8), # WASD mappings
        ("jump", ctypes.c_bool), # SPACEBAR pressed
        ("click_lmb", ctypes.c_bool),
        ("click_rmb", ctypes.c_bool),
        ("press_e", ctypes.c_bool),


        # Agent state (Game -> Agent)
        ("player_x", ctypes.c_float),
        ("player_y", ctypes.c_float),
        ("player_z", ctypes.c_float),
        ("player_yaw", ctypes.c_float),
        ("player_pitch", ctypes.c_float),
        ("player_health", ctypes.c_uint16),
        ("player_rads", ctypes.c_uint16),
        ("player_actionpoints", ctypes.c_uint16),

        # Diagnostics
        ("frame_counter", ctypes.c_uint32), # Increments every tick — proves the loop is alive
        ("debug_val1", ctypes.c_uint32), # For internal debugging
        ("debug_val2", ctypes.c_uint32), # For internal debugging

        # Environment State
        ("num_entities", ctypes.c_uint32),
        ("entities", EntityData * MAX_ENTITIES),

        ("num_waypoints", ctypes.c_uint32),
        ("waypoints", WaypointData * MAX_WAYPOINTS),
    ]
