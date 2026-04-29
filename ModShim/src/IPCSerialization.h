#pragma once
#include <cstdint>

#pragma pack(push, 1)

// 64 closest entities max for now to keep serialization fast
constexpr int MAX_ENTITIES = 64;
constexpr int MAX_WAYPOINTS = 32;

struct EntityData {
    uint32_t formId;
    uint32_t typeId; // Optional classification
    float x;
    float y;
    float z;
};

struct WaypointData {
    float x;
    float y;
    float z;
};

struct GameStateStruct {
    // Command Buffer for Automation
    uint8_t execute_command;
    char command_string[64];
    // Actions (Agent -> Game)
    float delta_yaw;
    float delta_pitch;

    float lidar_distances[16];

    uint8_t discrete_action; // WASD mappings
    bool jump; // SPACEBAR pressed
    bool click_lmb;
    bool click_rmb;
    bool press_e;


    // Agent state (Game -> Agent)
    float player_x;
    float player_y;
    float player_z;
    float player_yaw;
    float player_pitch;
    uint16_t player_health;
    uint16_t player_rads;
    uint16_t player_actionpoints;

    // Diagnostics
    uint32_t frame_counter; // Increments every tick — proves the loop is alive
    uint32_t debug_val1;    // For internal debugging
    uint32_t debug_val2;    // For internal debugging

    // Environment State
    uint32_t num_entities;
    EntityData entities[MAX_ENTITIES];
    
    uint32_t num_waypoints;
    WaypointData waypoints[MAX_WAYPOINTS];
};

#pragma pack(pop)
