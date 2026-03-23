import socket
import struct
import json
import threading
import time

# --- PIP-BOY PROTOCOL CONSTANTS ---
# Fallout 4 broadcasts its availability on UDP 28000, but we can just 
# connect directly to TCP 27000 if we know it's on localhost.
TCP_PORT = 27000 
MAGIC_KEEPALIVE = b'{"lang":"en","version":"1.0"}'

class PipBoyRelay:
    def __init__(self):
        self.session_data = {
            "location": "Connecting to Pip-Boy...",
            "hp": "0/0",
            "ap": "0/0",
            "level": "0",
            "conditions": "OFFLINE"
        }
        self.connected = False
        self.sock = None
        self.run_thread = threading.Thread(target=self._connection_loop, daemon=True)
        self.run_thread.start()

    def get_session(self):
        return self.session_data

    def _connection_loop(self):
        while True:
            try:
                if not self.connected:
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sock.settimeout(5.0)
                    print("Attempting to connect to Fallout 4 Pip-Boy App...")
                    self.sock.connect(('127.0.0.1', TCP_PORT))
                    
                    # Handshake
                    self.sock.send(MAGIC_KEEPALIVE)
                    self.connected = True
                    print("Pip-Boy Link Established!")
                    
                self._read_stream()
                
            except Exception as e:
                self.connected = False
                if self.sock:
                    self.sock.close()
                self.session_data["location"] = "OFFLINE - Waiting for Game..."
                time.sleep(3) # Wait before retrying

    def _read_stream(self):
        # The protocol sends a 32-bit length integer, followed by JSON data
        while self.connected:
            length_data = self._recv_exactly(4)
            if not length_data:
                raise ConnectionError("Stream closed")
            
            msg_length = struct.unpack('<I', length_data)[0]
            msg_data = self._recv_exactly(msg_length)
            
            if msg_data:
                # Fallout 4 actually sends BSON/JSON hybrid depending on the packet type, 
                # but the bulk updates are plain JSON.
                try:
                    # Ignore the first byte which is the packet type (1-5)
                    packet_type = msg_data[0]
                    if packet_type == 3 or packet_type == 4: # Data update packets
                        payload = msg_data[1:].decode('utf-8', errors='ignore')
                        self._parse_game_data(payload)
                except Exception as e:
                    pass # Ignore malformed packets

    def _recv_exactly(self, n):
        data = bytearray()
        while len(data) < n:
            packet = self.sock.recv(n - len(data))
            if not packet:
                return None
            data.extend(packet)
        return data

    def _parse_game_data(self, payload):
        try:
            data = json.loads(payload)
            
            # The PipBoy JSON structure is heavily nested. We search for the keys we need.
            # E.g., PlayerInfo -> HP, Map -> Location
            if "Stats" in data and "PlayerInfo" in data["Stats"]:
                p_info = data["Stats"]["PlayerInfo"]
                curr_hp = p_info.get("CurrHP", 0)
                max_hp = p_info.get("MaxHP", 0)
                curr_ap = p_info.get("CurrAP", 0)
                max_ap = p_info.get("MaxAP", 0)
                
                self.session_data["hp"] = f"{int(curr_hp)}/{int(max_hp)}"
                self.session_data["ap"] = f"{int(curr_ap)}/{int(max_ap)}"
                
            if "Map" in data and "World" in data["Map"]:
                self.session_data["location"] = data["Map"]["World"].get("Location", "Commonwealth")
                
            if "PlayerInfo" in data and "Level" in data["PlayerInfo"]:
                self.session_data["level"] = str(data["PlayerInfo"]["Level"])

        except json.JSONDecodeError:
            pass

# Initialize the global relay
pipboy_relay = PipBoyRelay()
