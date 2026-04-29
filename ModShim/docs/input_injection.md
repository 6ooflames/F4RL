# Input Injection Layer

To ensure the Fallout 4 engine recognizes commands from the AI Agent as legitimate player interactions, the ModShim avoids high-level Windows API calls (which are easily blocked or ignored) and instead utilizes low-level hardware emulation.

## ⌨️ Keyboard Injection (DirectInput)

The shim uses `keybd_event` with **DirectInput Scancodes**. Unlike Virtual Key codes, which are subject to software-level keyboard layouts and translation, scancodes represent the actual physical position of the key on a hardware keyboard.

### Implementation Details
*   **Scancode Mapping**: The shim uses `MapVirtualKeyA(..., MAPVK_VK_TO_VSC)` to translate standard Windows Virtual Keys into the hardware-level scan codes used by the engine.
*   **The Tilde (~) Command Flow**: To execute arbitrary engine commands, the shim performs the following sequence:
    1.  Press `DIK_TILDE` (Scancode `0x29`).
    2.  Wait briefly for the console UI to drop down.
    3.  Iterate through the command string, pressing and releasing each character's scancode.
    4.  Press `DIK_RETURN` (Enter) to submit the command.
    5.  Press `DIK_TILDE` again to close the console.

## 🖱️ Mouse Injection

For looking around (yaw/pitch), the shim emulates physical mouse movement using `mouse_event`.

*   **Mechanism**: It uses the `MOUSEEVENTF_MOVE` flag.
*   **Resolution**: The agent provides `delta_yaw` and `delta_pitch` as floats. The shim scales these by `100.0f` and casts them to integers to provide a smooth, high-frequency movement stream.
*   **Button Interaction**: Left and Right mouse button clicks are simulated using `MOUSEEVENTF_LEFTDOWN`/`UP` and `MOUSEEVENTF_RIGHTDOWN`/`UP`.

## 🕹️ Game Actions

Specific gameplay actions are mapped to dedicated scancodes:

| Action | Key/Button | Scancode/Event |
| :--- | :--- | :--- |
| **Movement** | W, A, S, D | `DIK_W`, `DIK_A`, `DIK_S`, `DIK_D` |
| **Jump** | Spacebar | `DIK_SPACE` |
| **Interact** | 'E' Key | `DIK_E` |
| **Combat** | Left Click | `MOUSEEVENTF_LEFTDOWN/UP` |
| **Aim/Secondary** | Right Click | `MOUSEEVENTF_RIGHTDOWN/UP` |

## ⚠️ Safety and Robustness

### The `SAFE_READ` Macro
Because the shim performs memory reads on pointers that may become invalid during cell transitions (e.g., when a `Cell` or `Actor` is unloaded), all reads are wrapped in a `SAFE_READ` macro. This macro verifies that the pointer is within a valid user-space range before attempting a dereference, preventing the most common causes of plugin-induced crashes.

### Thread Isolation
All input injection and memory scanning occur within a **detached background thread**. This prevents the main F4SE plugin loading process from blocking and avoids the ABI-related crashes that occur when attempting to use the F4SE-managed `ITaskDelegate` interface with the MinGW compiler.