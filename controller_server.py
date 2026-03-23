import sys
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import time
import urllib.request
import urllib.error
import os
import glob
from pipboy_relay import pipboy_relay

try:
    from pynput.keyboard import Key, Controller
    keyboard = Controller()
    print("Using pynput for keyboard control")
except ImportError as e:
    print(f"Failed to load pynput: {e}")
    sys.exit(1)

app = Flask(__name__)
CORS(app) # Allow requests from the React app

# Mapping of AI action words/phrases to keyboard presses
ACTION_MAP = {
    "loot": "e",
    "take": "e",
    "stimpack": "0",  # Assuming 0 is hotkeyed to stimpack
    "heal": "0",
    "reload": "r",
    "vats": "q",
    "pipboy": "tab",
    "crouch": "ctrl",
    "jump": "space",
    "sprint": "shift",
    "bash": "alt",
    "map": "m"
}

def get_pynput_key(key_str):
    """Convert string key representations to pynput Key objects if necessary."""
    special_keys = {
        'tab': Key.tab,
        'enter': Key.enter,
        'space': Key.space,
        'ctrl': Key.ctrl,
        'shift': Key.shift,
        'alt': Key.alt,
        'esc': Key.esc,
    }
    return special_keys.get(key_str, key_str)

@app.route('/ollama/generate', methods=['POST'])
def proxy_ollama():
    try:
        req = urllib.request.Request(
            'http://david-x570:11434/api/generate',
            data=request.get_data(),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req) as response:
            return response.read(), response.status, {'Content-Type': 'application/json'}
    except urllib.error.HTTPError as e:
        return e.read(), e.code, {'Content-Type': 'application/json'}
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/action', methods=['POST'])
def trigger_action():
    data = request.json
    action_text = data.get('action', '').lower()
    
    print(f"Received action: {action_text}")
    
    keys_to_press = []
    
    # Simple word matching to find intended keystrokes
    for word, key in ACTION_MAP.items():
        if word in action_text:
            keys_to_press.append(key)
            
    if not keys_to_press:
        # Default fallback or try to parse specific keys like "[E]"
        if "[" in action_text and "]" in action_text:
            extracted_key = action_text.split("[")[1].split("]")[0].lower()
            if len(extracted_key) == 1 or extracted_key in ['tab', 'enter', 'space', 'ctrl', 'shift', 'alt', 'esc']:
                keys_to_press.append(extracted_key)
                
    if keys_to_press:
        for key_str in keys_to_press:
            print(f"Pressing: {key_str}")
            try:
                actual_key = get_pynput_key(key_str)
                keyboard.press(actual_key)
                time.sleep(0.05) # Small delay to simulate human press
                keyboard.release(actual_key)
                time.sleep(0.1) # Delay between multi-keys
            except Exception as e:
                print(f"Failed to press {key_str}: {e}")
                
        return jsonify({"status": "success", "keys_pressed": keys_to_press})
    else:
        return jsonify({"status": "ignored", "message": "No mapped keys found"}), 400

@app.route('/session', methods=['GET'])
def get_session():
    # Return the real-time Pip-Boy app state
    data = pipboy_relay.get_session()
    
    if data and data.get("hp") != "0/0":
        return jsonify({"status": "success", "data": data})
    else:
        return jsonify({"status": "error", "message": "No valid data or game offline", "data": data}), 404

if __name__ == '__main__':
    print("Starting Fake Keyboard/Controller Server on port 8081...")
    print("Make sure this is running on the machine playing the game!")
    # Turn off reloader to avoid issues with pynput in threads
    app.run(host='0.0.0.0', port=8081, use_reloader=False)
