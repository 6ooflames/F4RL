// MinGW compatibility shim — MUST be included before any F4SE header.
// Replaces MSVC's force-included common/IPrefix.h with MinGW-safe typedefs.
#include "f4se_compat.h"

#include <thread>
#include <atomic>
#include <chrono>

#include "IPCSerialization.h"
#include "ScanCodesDirectInput.h"

// F4SE Headers (these rely on UInt32 etc. from f4se_compat.h)
#include "f4se/PluginAPI.h"

std::atomic<bool> g_running = true;
GameStateStruct* g_ipcData = nullptr;

// Relocation offsets for Fallout 4 1.10.163
const uintptr_t G_PLAYER_OFFSET       = 0x05AA4388;
const uintptr_t G_PROCESSLISTS_OFFSET = 0x05AA3D00; // Common offset for 1.10.163

const uintptr_t POS_OFFSET        = 0xD0;   
const uintptr_t ROT_OFFSET        = 0xC0;   
const uintptr_t PARENTCELL_OFFSET = 0xB8;   
const uintptr_t BASEFORM_OFFSET   = 0xE0;   
const uintptr_t FORMID_OFFSET     = 0x14;   
const uintptr_t FORMTYPE_OFFSET   = 0x1A;   

const uintptr_t TARRAY_ENTRIES_OFFSET  = 0x00;
const uintptr_t TARRAY_COUNT_OFFSET    = 0x10;
const uintptr_t CELL_OBJECTLIST_OFFSET = 0x70;

struct NiPoint3 {
    float x, y, z;
};

// Helper: check if a pointer is likely valid (not null and in user space)
static bool IsValidPtr(uintptr_t ptr) {
    return ptr > 0x10000 && ptr < 0x00007FFFFFFFFFFFf;
}

// Fallback for MinGW since __try is not available.
// We use IsValidPtr to avoid the most common crashes in the background thread.
#define SAFE_READ(type, addr, fallback) (IsValidPtr(addr) ? *(type*)(addr) : fallback)

// Scan the player's current cell and the global process list for entities
void ScanNearbyEntities(uintptr_t baseAddr, uintptr_t playerObj) {
    if (!g_ipcData || !playerObj) return;

    uint32_t written = 0;

    // 1. Scan Current Cell
    uintptr_t parentCell = SAFE_READ(uintptr_t, playerObj + PARENTCELL_OFFSET, 0);
    g_ipcData->debug_val1 = (uint32_t)(parentCell & 0xFFFFFFFF);

    if (parentCell) {
        uintptr_t entries = SAFE_READ(uintptr_t, parentCell + CELL_OBJECTLIST_OFFSET + TARRAY_ENTRIES_OFFSET, 0);
        uint32_t  count   = SAFE_READ(uint32_t, parentCell + CELL_OBJECTLIST_OFFSET + TARRAY_COUNT_OFFSET, 0);
        
        g_ipcData->debug_val2 = count;

        if (entries && count > 0 && count < 10000) {
            for (uint32_t i = 0; i < count && written < MAX_ENTITIES; i++) {
                uintptr_t refr = SAFE_READ(uintptr_t, entries + i * 8, 0);
                if (!refr || refr == playerObj) continue;

                float ex = SAFE_READ(float, refr + POS_OFFSET, 0.0f);
                float ey = SAFE_READ(float, refr + POS_OFFSET + 4, 0.0f);
                float ez = SAFE_READ(float, refr + POS_OFFSET + 8, 0.0f);
                if (ex == 0.0f && ey == 0.0f && ez == 0.0f) continue;

                uintptr_t baseForm = SAFE_READ(uintptr_t, refr + BASEFORM_OFFSET, 0);
                uint8_t typeId = baseForm ? SAFE_READ(uint8_t, baseForm + FORMTYPE_OFFSET, 0) : 0;

                g_ipcData->entities[written].formId = SAFE_READ(uint32_t, refr + FORMID_OFFSET, 0);
                g_ipcData->entities[written].typeId = (uint32_t)typeId;
                g_ipcData->entities[written].x = ex;
                g_ipcData->entities[written].y = ey;
                g_ipcData->entities[written].z = ez;
                written++;
            }
        }
    }

    // 2. Scan Process List (if we have space left)
    if (written < MAX_ENTITIES) {
        uintptr_t processLists = SAFE_READ(uintptr_t, baseAddr + G_PROCESSLISTS_OFFSET, 0);
        if (processLists) {
            // High-process actors list is usually at offset 0x40 of ProcessLists
            // It's a tArray<Actor*>
            uintptr_t actorsBase = processLists + 0x40;
            uintptr_t entries = SAFE_READ(uintptr_t, actorsBase + TARRAY_ENTRIES_OFFSET, 0);
            uint32_t  count   = SAFE_READ(uint32_t, actorsBase + TARRAY_COUNT_OFFSET, 0);

            if (entries && count > 0 && count < 1000) {
                for (uint32_t i = 0; i < count && written < MAX_ENTITIES; i++) {
                    uintptr_t actor = SAFE_READ(uintptr_t, entries + i * 8, 0);
                    if (!actor || actor == playerObj) continue;

                    // Check if already written (could optimize with a set, but for 64 items it's fine)
                    bool duplicate = false;
                    uint32_t actorFormId = SAFE_READ(uint32_t, actor + FORMID_OFFSET, 0);
                    for(uint32_t j=0; j<written; j++) {
                        if(g_ipcData->entities[j].formId == actorFormId) { duplicate = true; break; }
                    }
                    if(duplicate) continue;

                    float ex = SAFE_READ(float, actor + POS_OFFSET, 0.0f);
                    float ey = SAFE_READ(float, actor + POS_OFFSET + 4, 0.0f);
                    float ez = SAFE_READ(float, actor + POS_OFFSET + 8, 0.0f);
                    
                    g_ipcData->entities[written].formId = actorFormId;
                    g_ipcData->entities[written].typeId = 43; // kFormType_ACHR
                    g_ipcData->entities[written].x = ex;
                    g_ipcData->entities[written].y = ey;
                    g_ipcData->entities[written].z = ez;
                    written++;
                }
            }
        }
    }

    g_ipcData->num_entities = written;
}

static uint8_t g_last_movement = 0;
static bool g_last_jump = false;
static bool g_last_lmb = false;
static bool g_last_rmb = false;
static bool g_last_e = false;

// Helper to send DirectInput-compatible Hardware Scancodes
void SendDirectInputKey(uint8_t scancode, bool isDown) {
    DWORD flags = KEYEVENTF_SCANCODE;
    if (!isDown) {
        flags |= KEYEVENTF_KEYUP;
    }
    // Arg 1 (bVk) is ignored when KEYEVENTF_SCANCODE is used.
    // Arg 2 (bScan) is our hardware scancode.
    keybd_event(0, scancode, flags, 0);
}

void InjectConsoleCommand(const std::string& cmd) {
    // const uint8_t SCAN_TILDE = 0x29; // Hardware scancode for ~
    // const uint8_t SCAN_ENTER = 0x1C; // Hardware scancode for Enter
    // const uint8_t SCAN_LSHIFT = 0x2A; // Hardware scancode for Left Shift

    // 1. Open Console
    SendDirectInputKey(DIK_TILDE, true);
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
    SendDirectInputKey(DIK_TILDE, false);
    std::this_thread::sleep_for(std::chrono::milliseconds(100)); // Wait for UI drop-down

    // 2. Type the command string
    for (char c : cmd) {
        // Find the Windows Virtual Key
        short vk = VkKeyScanA(c);
        bool shift = (vk >> 8) & 1;
        uint8_t virtualKey = vk & 0xFF;

        // Translate the Virtual Key into a DirectInput Hardware Scancode
        uint8_t scancode = MapVirtualKeyA(virtualKey, MAPVK_VK_TO_VSC);

        if (shift) SendDirectInputKey(DIK_LSHIFT, true);

        SendDirectInputKey(scancode, true);
        std::this_thread::sleep_for(std::chrono::milliseconds(15)); // Short delay to simulate real typing
        SendDirectInputKey(scancode, false);

        if (shift) SendDirectInputKey(DIK_LSHIFT, false);
    }

    // 3. Press Enter
    SendDirectInputKey(DIK_RETURN, true);
    std::this_thread::sleep_for(std::chrono::milliseconds(15));
    SendDirectInputKey(DIK_RETURN, false);
    std::this_thread::sleep_for(std::chrono::milliseconds(100)); // Give engine time to parse the command

    // 4. Close Console
    SendDirectInputKey(DIK_TILDE, true);
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
    SendDirectInputKey(DIK_TILDE, false);
}

// Upgraded Movement Injector to use strict DirectInput Scancodes
void InjectMovement(uint8_t action) {
    if (action == g_last_movement) return;

    // Release previous key
    if (g_last_movement == 1) SendDirectInputKey(DIK_W, false);
    if (g_last_movement == 2) SendDirectInputKey(DIK_S, false);
    if (g_last_movement == 3) SendDirectInputKey(DIK_A, false);
    if (g_last_movement == 4) SendDirectInputKey(DIK_D, false);

    // Press new key
    if (action == 1) SendDirectInputKey(DIK_W, true);
    if (action == 2) SendDirectInputKey(DIK_S, true);
    if (action == 3) SendDirectInputKey(DIK_A, true);
    if (action == 4) SendDirectInputKey(DIK_D, true);


    g_last_movement = action;
}

void Jumping(bool jump) {
    if (jump == g_last_jump) return;

    SendDirectInputKey(DIK_SPACE, jump);

}

void InjectActionButtons(bool lmb, bool rmb, bool e_key) {
    // Left Mouse Button
    if (lmb != g_last_lmb) {
        DWORD flag = lmb ? MOUSEEVENTF_LEFTDOWN : MOUSEEVENTF_LEFTUP;
        mouse_event(flag, 0, 0, 0, 0);
        g_last_lmb = lmb;
    }

    // Right Mouse Button
    if (rmb != g_last_rmb) {
        DWORD flag = rmb ? MOUSEEVENTF_RIGHTDOWN : MOUSEEVENTF_RIGHTUP;
        mouse_event(flag, 0, 0, 0, 0);
        g_last_rmb = rmb;
    }

    // E (Interact) Key
    if (e_key != g_last_e) {
        SendDirectInputKey(DIK_E, e_key); // DIK_E is 0x12
        g_last_e = e_key;
    }
}
// Background thread — avoids the MSVC/MinGW vtable ABI mismatch that
// breaks ITaskDelegate (GCC emits 2 destructor vtable entries vs MSVC's 1,
// so F4SE calls the wrong slot when it tries to invoke Run()).
void AgentLoop() {
    uintptr_t baseAddr = (uintptr_t)GetModuleHandleA(NULL);
    uintptr_t g_player_ptr = baseAddr + G_PLAYER_OFFSET;

    while (g_running) {
        // Heartbeat — Python can watch this to confirm the loop is alive
        g_ipcData->frame_counter++;
        if (g_ipcData) {
            // Block during command execution
            if (g_ipcData->execute_command == 1) {
                // Safely read up to 64 characters, avoiding missing null-terminator crashes
                size_t safe_len = strnlen(g_ipcData->command_string, 64);
                std::string cmd(g_ipcData->command_string, safe_len);

                // Inject the command via keyboard (DirectInput)
                InjectConsoleCommand(cmd);

                std::this_thread::sleep_for(std::chrono::milliseconds(1200));

                // Phase 1: Wait for Player Object and Valid Cell
                while (true) {
                    uintptr_t playerObj = SAFE_READ(uintptr_t, g_player_ptr, 0);
                    if (playerObj) {
                        uintptr_t parentCell = SAFE_READ(uintptr_t, playerObj + PARENTCELL_OFFSET, 0);
                        float px = SAFE_READ(float, playerObj + POS_OFFSET, 0.0f);

                        // Ensure cell is valid AND we are not stuck at exactly 0,0,0 (a common transient loading state)
                        if (parentCell != 0 && px != 0.0f) {
                            break;
                        }
                    }
                    std::this_thread::sleep_for(std::chrono::milliseconds(200));
                }

                // Phase 2: Physics Stability Check (Replaces Entity Heuristic)
                // When a cell finishes loading, the player drops onto the NavMesh.
                // We wait until the Z-coordinate stops changing, meaning Havok has settled.
                float last_z = -99999.0f;
                int stable_frames = 0;

                while (true) {
                    uintptr_t playerObj = SAFE_READ(uintptr_t, g_player_ptr, 0);
                    float current_z = playerObj ? SAFE_READ(float, playerObj + POS_OFFSET + 8, 0.0f) : 0.0f;

                    // If Z hasn't moved more than 0.5 units
                    if (abs(current_z - last_z) < 0.5f) {
                        stable_frames++;
                    } else {
                        stable_frames = 0; // Reset if we are still falling
                    }

                    last_z = current_z;

                    // If Z has been stable for 4 consecutive polls (~800ms)
                    if (stable_frames >= 4) break;

                    std::this_thread::sleep_for(std::chrono::milliseconds(200));
                }


                // Extra safety padding before unleashing the RL Agent
                std::this_thread::sleep_for(std::chrono::milliseconds(500));

                // Tell Python we are done loading
                g_ipcData->execute_command = 0;
                continue; // Skip the rest of this frame
            }

            // Read Player State
            uintptr_t playerObj = SAFE_READ(uintptr_t, g_player_ptr, 0);
            if (playerObj) {
                g_ipcData->player_x = SAFE_READ(float, playerObj + POS_OFFSET, 0.0f);
                g_ipcData->player_y = SAFE_READ(float, playerObj + POS_OFFSET + 4, 0.0f);
                g_ipcData->player_z = SAFE_READ(float, playerObj + POS_OFFSET + 8, 0.0f);

                // Rot Z is Yaw, Rot X is Pitch in Bethesda games
                g_ipcData->player_yaw   = SAFE_READ(float, playerObj + ROT_OFFSET + 8, 0.0f); // NiPoint3.z
                g_ipcData->player_pitch = SAFE_READ(float, playerObj + ROT_OFFSET, 0.0f);     // NiPoint3.x

                // Scan nearby entities from the current cell and process list
                ScanNearbyEntities(baseAddr, playerObj);
            }

            // Read Actions and Inject
            // 1. Mouse Deltas
            if (g_ipcData->delta_yaw != 0.0f || g_ipcData->delta_pitch != 0.0f) {
                int dx = (int)(g_ipcData->delta_yaw * 100.0f);
                int dy = (int)(g_ipcData->delta_pitch * 100.0f);

                if (dx != 0 || dy != 0) {
                    mouse_event(MOUSEEVENTF_MOVE, dx, dy, 0, 0);
                    g_ipcData->delta_yaw = 0.0f;
                    g_ipcData->delta_pitch = 0.0f;
                }
            }

            // 2. Movement Actions
            InjectMovement(g_ipcData->discrete_action);
            Jumping(g_ipcData->jump);

            // 3. Combat & Interaction Actions
            InjectActionButtons(g_ipcData->click_lmb, g_ipcData->click_rmb, g_ipcData->press_e);
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(5)); // ~200Hz
    }
}

// F4SE Plugin Entry Point
extern "C" {
__declspec(dllexport) bool F4SEPlugin_Query(const F4SEInterface *f4se,
                                            PluginInfo *info) {
  info->infoVersion = 1;
  info->name = "F4RL_Shim";
  info->version = 1;
  return true;
}

__declspec(dllexport) bool F4SEPlugin_Load(const F4SEInterface *f4se) {
  // Create or open the real file on the Linux host via Wine's Z: drive
  HANDLE hFile =
      CreateFileA("Z:\\dev\\shm\\F4RL_IPC", GENERIC_READ | GENERIC_WRITE,
                  FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_ALWAYS,
                  FILE_ATTRIBUTE_NORMAL, NULL);

  if (hFile == INVALID_HANDLE_VALUE) {
    return false; // Failed to open host file
  }

  // Ensure the file is at least 4096 bytes
  SetFilePointer(hFile, 4096, NULL, FILE_BEGIN);
  SetEndOfFile(hFile);
  SetFilePointer(hFile, 0, NULL, FILE_BEGIN);

  // Create Shared Memory Mapping backed by the real file
  HANDLE hMapFile =
      CreateFileMappingA(hFile,          // File handle
                         NULL,           // Default security
                         PAGE_READWRITE, // Read/write access
                         0,              // Max object size (high-order DWORD)
                         4096,           // Max object size (low-order DWORD)
                         NULL);

  if (hMapFile == NULL) {
    CloseHandle(hFile);
    return false;
  }

  void* pBuf = MapViewOfFile(hMapFile,
                             FILE_MAP_ALL_ACCESS,
                             0, 0, 4096);

  if (pBuf == NULL) {
    CloseHandle(hMapFile);
    CloseHandle(hFile);
    return false;
  }

  // Clear memory and cast to our struct
  memset(pBuf, 0, 4096);
  g_ipcData = (GameStateStruct*)pBuf;

  // Write a magic marker so Python can confirm the plugin loaded
  // (frame_counter will start incrementing once the thread starts)
  g_ipcData->frame_counter = 1;

  // Launch background thread
  std::thread(AgentLoop).detach();

  return true;
}
}

