import sys
import os
import socket
import subprocess

# -----------------------------------------------------------------------------
# Import Handling
# -----------------------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from tools import netutils, constants

# -----------------------------------------------------------------------------
# Operation Handlers
# -----------------------------------------------------------------------------

def handle_connect(payload):
    """
    Launches a Python game script explicitly using the current Python interpreter.
    """
    game_path = payload.get("game_path")
    host = payload.get("host")
    port = payload.get("port")
    
    print(f"[Client] Launching game: {game_path} -> {host}:{port}", flush=True)
    
    try:
        # Use sys.executable to run 'python3' safely within the current environment
        subprocess.Popen([sys.executable, game_path, host, str(port)])
    except Exception as e:
        print(f"[Error] Failed to launch game: {e}", flush=True)

def handle_save(payload):
    file_path = payload["path"]
    file_data = payload["file data"]
    
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(file_data)
        print(f"[Client] Saved file to: {file_path}", flush=True)
    except IOError as e:
        print(f"[Error] Failed to save file: {e}", flush=True)

def handle_upload(sock, payload):
    file_path = payload["path"]
    
    if not os.path.exists(file_path):
        print(f"[Upload] File not found: {file_path}", flush=True)
        # Send Dictionary directly
        netutils.send_msg(sock, {"response": "error"})
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        print(f"[Upload] Sending file: {file_path}", flush=True)
        # Send Dictionary directly
        netutils.send_msg(sock, {
            "response": "success",
            "file data": content
        })
        
    except Exception as e:
        print(f"[Error] Failed to read file for upload: {e}", flush=True)
        netutils.send_msg(sock, {"response": "error"})

def handle_display(sock, payload):
	# print(f"[DISPLAY] {payload}")
	print(f"{payload['text']}", flush=True)

	input_req = payload.get("input")
	user_input = None

	if input_req == "none":
		return

	# Case: Text input with max length ["text", 10]
	elif (isinstance(input_req, list) and len(input_req) == 2 
			and input_req[0] == "text"):
		max_len = input_req[1]
		while True:
			val = input(f"> Enter input (max {max_len} chars): ")
			if not val.isascii():
				print("Error: ASCII only.", flush=True)
				continue
			if len(val) > max_len:
				print(f"Error: Max length is {max_len}.", flush=True)
				continue
			user_input = val
			break

	# Case: Selection (List of strings or integers)
	elif isinstance(input_req, list):
		# Convert all options to strings for consistent comparison
		options = [str(x) for x in input_req]
		
		while True:
			val = input(f"> Choose one ({', '.join(options)}): ")
			if val in options:
				user_input = val
				break
			else:
				print("Error: Invalid selection.", flush=True)

	if user_input is not None:
		# Send Dictionary directly
		netutils.send_msg(sock, {"response": user_input})

# -----------------------------------------------------------------------------
# Main Loop
# -----------------------------------------------------------------------------

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        sock.connect((constants.DEV_HOST, constants.DEV_PORT))
        print(f"[Client] Connected to {constants.DEV_HOST}:{constants.DEV_PORT}", flush=True)
    except ConnectionRefusedError:
        print("[Client] Server not available.", flush=True)
        return

    try:
        while True:
            # recv_msg returns a DICTIONARY now
            msg = netutils.recv_msg(sock)
            
            if not msg:
                print("[Client] Server closed connection.", flush=True)
                break
            
            try:
                op = msg.get("op")

                if op == "connect":
                    handle_connect(msg)
                elif op == "save":
                    handle_save(msg)
                elif op == "upload":
                    handle_upload(sock, msg)
                elif op == "display":
                    handle_display(sock, msg)
                else:
                    print(f"[Warning] Unknown op: {op}", flush=True)

            except AttributeError:
                print(f"[Error] received data was not a dictionary: {type(msg)}", flush=True)
            except Exception as e:
                print(f"[Error] Handler failed: {e}", flush=True)
                continue

    except KeyboardInterrupt:
        print("\n[Client] Exiting.", flush=True)
    finally:
        sock.close()

if __name__ == "__main__":
    main()