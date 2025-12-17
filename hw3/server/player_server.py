import socket
import threading
import sys
import os
import random
import string
import time
import subprocess

# -----------------------------------------------------------------------------
# Path Setup
# -----------------------------------------------------------------------------
sys.path.append('..')

try:
    from tools import constants, netutils
except ImportError as e:
    print(f"Error importing tools: {e}")
    print("Ensure you are running this from the 'server/' directory or 'netprog_project/' root.")
    sys.exit(1)

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def send_db_request(request_dict):
    """
    Connects to the DB Server, sends a request, receives a response,
    and closes the connection.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as db_sock:
            db_sock.connect((constants.DB_HOST, constants.DB_PORT))
            netutils.send_msg(db_sock, request_dict)
            response = netutils.recv_msg(db_sock)
            return response
    except Exception as e:
        print(f"[Server Error] DB Communication failed: {e}")
        return {}

def client_interaction(sock, text, input_type):
    """
    Helper to standardize the 'display' operation protocol.
    """
    msg = {
        "op": "display",
        "text": text,
        "input": input_type
    }
    netutils.send_msg(sock, msg)
    if input_type == "none":
        return None
    return netutils.recv_msg(sock)

def read_game_file(game_name):
    """
    Reads the client.py file for a specific game from the server's storage.
    """
    file_path = os.path.join("games", game_name, "client.py")
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"[Server Error] Could not read game file {file_path}: {e}")
        return None

def get_random_free_port():
    """
    Finds a free port in the range [GAME_PORT_L, GAME_PORT_R).
    """
    ports = list(range(constants.GAME_PORT_L, constants.GAME_PORT_R))
    random.shuffle(ports)

    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                # Bind to the interface specified in constants (usually 0.0.0.0 or localhost)
                sock.bind((constants.PLAY_HOST, port))
                return port
            except OSError:
                continue
    return None

# -----------------------------------------------------------------------------
# New Logic: Game Lobby (Room System)
# -----------------------------------------------------------------------------

def handle_game_lobby(sock, user_name, game_name, player_limit):
    """
    Manages the Create Room / Join Room / Back flow.
    """
    while True:
        menu_text = f"--- {game_name} Lobby ---\n1. Create Room\n2. Join Room\n3. Back"
        resp = client_interaction(sock, menu_text, ["1", "2", "3"])
        if not resp: break
        choice = resp.get("response")

        # === 3. BACK ===
        if choice == "3":
            return

        # === 1. CREATE ROOM ===
        elif choice == "1":
            room_name = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            
            # Send Create Request to DB
            req = {
                "op": "create room",
                "name": room_name,
                "game": game_name,
                "host": user_name,
                "player_limit": player_limit
            }
            db_resp = send_db_request(req)

            if db_resp.get("status") != "success":
                client_interaction(sock, f"Error creating room: {db_resp.get('message')}", "none")
                continue

            # HOST LOOP
            while True:
                host_menu = f"--- Room: {room_name} (Host) ---\n1. Start Game\n2. Delete Room"
                h_resp = client_interaction(sock, host_menu, ["1", "2"])
                if not h_resp: break
                h_choice = h_resp.get("response")

                if h_choice == "1": # Start Game
                    # 1. Check if room is full
                    q_req = {"op": "query room", "criteria": {"name": room_name}}
                    q_resp = send_db_request(q_req)
                    rooms = q_resp.get("data", [])
                    
                    if not rooms:
                        client_interaction(sock, "Error: Room not found.", "none")
                        break
                    
                    room_data = rooms[0]
                    current_count = 1 + len(room_data.get("guests", []))

                    if current_count < player_limit:
                        client_interaction(sock, f"Room not full ({current_count}/{player_limit}). Cannot start.", "none")
                    else:
                        # --- START GAME SEQUENCE (HOST) ---
                        
                        # A. Find Free Port
                        port = get_random_free_port()
                        if not port:
                            client_interaction(sock, "Error: No free ports available.", "none")
                            continue

                        # B. Update Room Port in DB
                        send_db_request({
                            "op": "update room port",
                            "name": room_name,
                            "port": port
                        })

                        # C. Update Status to Active
                        send_db_request({
                            "op": "update room status", 
                            "name": room_name, 
                            "status": "active"
                        })

                        # D. Launch Game Server Subprocess
                        # Path: games/game_name/server.py
                        game_server_path = os.path.join("games", game_name, "server.py")
                        
                        try:
                            # Launch the process
                            process = subprocess.Popen([sys.executable, game_server_path, '0.0.0.0', str(port)])
                            print(f"[Server] Launched {game_name} on port {port} (PID: {process.pid})")

                            # E. Send Connect Command to Client
                            client_path = os.path.join("games", user_name, game_name, "client.py")
                            connect_msg = {
                                "op": "connect",
                                "game_path": client_path,
                                "host": constants.PLAY_HOST,
                                "port": port
                            }
                            netutils.send_msg(sock, connect_msg)

                            # F. Wait for Game to End
                            # The Host Player Server thread blocks here until the game server process exits
                            process.wait()
                            print(f"[Server] Game {game_name} (PID: {process.pid}) finished.")

                        except Exception as e:
                            print(f"[Server] Failed to launch game: {e}")
                            client_interaction(sock, f"Server Error: {e}", "none")
                        
                        # G. Cleanup (Set Inactive and Port 0)
                        send_db_request({"op": "update room status", "name": room_name, "status": "inactive"})
                        send_db_request({"op": "update room port", "name": room_name, "port": 0})
                        
                        # Loop continues -> Returns to Host Menu

                elif h_choice == "2": # Delete Room
                    send_db_request({"op": "remove room", "name": room_name})
                    client_interaction(sock, "Room deleted.", "none")
                    break # Break Host Loop

        # === 2. JOIN ROOM ===
        elif choice == "2":
            # List rooms for this game
            q_req = {"op": "query room", "criteria": {"game": game_name}}
            q_resp = send_db_request(q_req)
            rooms = q_resp.get("data", [])

            if not rooms:
                client_interaction(sock, "No rooms found for this game.", "none")
                continue

            # Construct Room Selection Menu
            room_menu = "--- Available Rooms ---\n"
            valid_inputs = []
            
            for idx, r in enumerate(rooms):
                r_name = r['name']
                curr = 1 + len(r.get('guests', [])) 
                limit = r['player_limit']
                room_menu += f"{idx+1}. {r_name} (Host: {r['host']}) [{curr}/{limit}]\n"
                valid_inputs.append(str(idx+1))
            
            back_idx = len(rooms) + 1
            room_menu += f"{back_idx}. Back"
            valid_inputs.append(str(back_idx))

            r_resp = client_interaction(sock, room_menu, valid_inputs)
            if not r_resp: break
            
            sel_idx = int(r_resp.get("response"))
            if sel_idx == back_idx:
                continue

            target_room = rooms[sel_idx - 1]
            t_name = target_room['name']

            # Check Full Locally first
            curr_p = 1 + len(target_room.get('guests', []))
            if curr_p >= target_room['player_limit']:
                client_interaction(sock, "Room is full.", "none")
                continue

            # Add Guest to DB
            join_req = {
                "op": "update room guests",
                "name": t_name,
                "action": "add guest",
                "guest_name": user_name
            }
            send_db_request(join_req)
            client_interaction(sock, f"Joined {t_name}. Waiting for host...", "none")

            # GUEST WAITING LOOP
            room_deleted = False
            while True:
                time.sleep(1) # Check every 1 second
                
                # Check Room Status
                chk_req = {"op": "query room", "criteria": {"name": t_name}}
                chk_resp = send_db_request(chk_req)
                data = chk_resp.get("data", [])

                if not data:
                    room_deleted = True
                    break
                
                r_data = data[0]
                status = r_data.get("status", "inactive")
                
                if status == "active":
                    # --- START GAME SEQUENCE (GUEST) ---
                    game_port = r_data.get("port")
                    if not game_port:
                        print("[Server] Error: Room active but no port found.")
                        continue

                    # 1. Send Connect Command to Client
                    client_path = os.path.join("games", user_name, game_name, "client.py")
                    connect_msg = {
                        "op": "connect",
                        "game_path": client_path,
                        "host": constants.PLAY_HOST,
                        "port": game_port
                    }
                    netutils.send_msg(sock, connect_msg)
                    
                    # 2. Monitor Loop (Wait for Game End)
                    # The client is currently running the game. We just wait for the room to close.
                    while True:
                        time.sleep(1)
                        # Check if room is still active
                        chk_req_inner = {"op": "query room", "criteria": {"name": t_name}}
                        chk_resp_inner = send_db_request(chk_req_inner)
                        data_inner = chk_resp_inner.get("data", [])

                        if not data_inner:
                            room_deleted = True # Room deleted entirely
                            break 
                        
                        if data_inner[0].get("status") == "inactive":
                            # Game Over
                            break
                    
                    if room_deleted: break
                    
                    # If we break here, it means status went back to 'inactive'.
                    # Send user back to waiting state (or lobby).
                    client_interaction(sock, "Game finished. Returning to lobby...", "none")
                    # Break the outer loop to return to Lobby Menu? 
                    # Usually, guests stay in the room for the next match unless they leave.
                    # We will stay in the Guest Waiting Loop.
                    continue

            if room_deleted:
                client_interaction(sock, "Host closed the room.", "none")

# -----------------------------------------------------------------------------
# Main Logic: Client Handler
# -----------------------------------------------------------------------------

def handle_client(sock):
    """
    Main state machine for a connected player client.
    """
    print(f"[Server] New connection: {sock.getpeername()}")
    name = None 

    try:
        while True:
            # --- Step 1: Pre-Login Menu ---
            if not name:
                menu_text = "1. Login\n2. Register\n3. Exit"
                response = client_interaction(sock, menu_text, ["1", "2", "3"])
                if not response: break 
                
                choice = response.get("response")

                # --- Step 2: Register ---
                if choice == "2":
                    resp_name = client_interaction(sock, "Enter Name:", ["text", 20])
                    reg_name = resp_name.get("response")
                    
                    resp_pw = client_interaction(sock, "Enter Password:", ["text", 20])
                    reg_password = resp_pw.get("response")

                    db_req = {"op": "create player", "name": reg_name, "password": reg_password}
                    db_resp = send_db_request(db_req)

                    if db_resp.get("status") == "success":
                        client_interaction(sock, "Registration Successful!", "none")
                    else:
                        client_interaction(sock, f"Registration Failed: Username Invalid", "none")

                # --- Step 3: Login ---
                elif choice == "1":
                    resp_name = client_interaction(sock, "Enter Name:", ["text", 20])
                    login_name = resp_name.get("response")
                    
                    resp_pw = client_interaction(sock, "Enter Password:", ["text", 20])
                    login_pass = resp_pw.get("response")

                    db_req = {"op": "query player", "criteria": {"name": login_name}}
                    db_resp = send_db_request(db_req)
                    user_list = db_resp.get("data", [])
                    
                    error_msg = None
                    if not user_list:
                        error_msg = "User does not exist."
                    else:
                        user_data = user_list[0]
                        if user_data.get("password") != login_pass:
                            error_msg = "Incorrect password."
                        elif user_data.get("status") != "offline":
                            error_msg = "User is already logged in."

                    if error_msg:
                        client_interaction(sock, f"Login Failed: {error_msg}", "none")
                    else:
                        name = login_name
                        send_db_request({"op": "update player status", "name": name, "status": "online"})
                        client_interaction(sock, f"Welcome {name}", "none")

                # --- Step 4: Exit ---
                elif choice == "3":
                    break

            # =========================================================
            # PHASE B: SESSION LOOP (User is Logged In)
            # =========================================================
            else:
                games_req = {"op": "query game", "criteria": {}} 
                games_resp = send_db_request(games_req)
                games_list = games_resp.get("data", [])

                store_menu = "--- Game Store ---\n"
                for idx, g in enumerate(games_list):
                    store_menu += f"{idx + 1}. {g['name']} (v{g['version']})\n"
                store_menu += f"{len(games_list) + 1}. Logout"

                valid_store_inputs = [str(i) for i in range(1, len(games_list) + 2)]
                
                resp = client_interaction(sock, store_menu, valid_store_inputs)
                if not resp: break
                
                store_choice = int(resp.get("response"))

                if store_choice == len(games_list) + 1:
                    send_db_request({"op": "update player status", "name": name, "status": "offline"})
                    name = None
                    print(f"[Server] Logged out.")
                    continue 

                selected_game = games_list[store_choice - 1]
                game_name = selected_game['name']
                server_game_version = selected_game['version']
                game_player_limit = selected_game.get('players', 2)

                # --- Inner Loop: Specific Game Actions ---
                while True:
                    p_req = {"op": "query player", "criteria": {"name": name}}
                    p_data = send_db_request(p_req).get("data")[0]
                    g_req = {"op": "query game", "criteria": {"name": game_name}}
                    selected_game = send_db_request(g_req).get("data")[0]
                    
                    library = p_data.get("games", {}) 
                    is_owned = game_name in dict(library)
                    client_game_version = dict(library).get(game_name, 0)

                    sub_text = f"--- {game_name} ---\n1. Details\n2. Play"
                    sub_opts = ["1", "2"]
                    if is_owned:
                        sub_text += "\n3. Review"
                        sub_opts.append("3")
                    
                    back_idx = len(sub_opts) + 1
                    sub_text += f"\n{back_idx}. Back"
                    sub_opts.append(str(back_idx))

                    g_resp = client_interaction(sock, sub_text, sub_opts)
                    if not g_resp: break
                    g_choice = g_resp.get("response")

                    if g_choice == str(back_idx):
                        break 

                    if g_choice == "1":
                        def get_description(data):
                            if not data: return "No description"
                            return "\n====\n" + data + "\n===="
                        def get_feedback(data):
                            if not data: return "No feedback"
                            ret = "\n====\n"
                            for i in data:
                                ret += f"User {i[0]} ({i[1]} stars): {i[2]}\n"
                            return ret + "===="

                        desc = f"Name: {selected_game['name']}\n" \
                               f"Version: {selected_game['version']}\n" \
                               f"Players: {selected_game['players']}\n" \
                               f"Description: {get_description(selected_game.get('description'))}\n" \
                               f"Feedback: {get_feedback(selected_game.get('feedback'))}"
                        client_interaction(sock, desc, "none")

                    elif g_choice == "2": # PLAY
                        need_download = False
                        if not is_owned:
                            client_interaction(sock, "You don't own this game. Downloading...", "none")
                            need_download = True
                        elif client_game_version < server_game_version:
                            client_interaction(sock, f"Update available. Updating...", "none")
                            need_download = True
                        
                        if need_download:
                            code_content = read_game_file(game_name)
                            if not code_content:
                                client_interaction(sock, "Error: Game file missing on server.", "none")
                                continue

                            save_path = os.path.join("games", name, game_name, "client.py")
                            save_msg = {"op": "save", "path": save_path, "file data": code_content}
                            netutils.send_msg(sock, save_msg)

                            action = "add game" if not is_owned else "update version"
                            upd_req = {
                                "op": "update player games",
                                "name": name,
                                "action": action,
                                "payload": [game_name, server_game_version]
                            }
                            send_db_request(upd_req)
                            client_interaction(sock, "Download Complete!", "none")
                        
                        # --- ENTER GAME LOBBY ---
                        handle_game_lobby(sock, name, game_name, game_player_limit)

                    elif g_choice == "3" and is_owned:
                        s_resp = client_interaction(sock, "Rate (1-5):", ["1", "2", "3", "4", "5"])
                        stars = int(s_resp.get("response"))
                        c_resp = client_interaction(sock, "Write a short review:", ["text", 100])
                        comment = c_resp.get("response")
                        fb_req = {
                            "op": "add feedback",
                            "name": game_name,
                            "feedback": [name, stars, comment]
                        }
                        send_db_request(fb_req)
                        client_interaction(sock, "Review submitted.", "none")

    except (ConnectionResetError, BrokenPipeError):
        print(f"[Server] Connection lost with {name if name else 'client'}")
    except Exception as e:
        print(f"[Server] Error handling client: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if name:
            try: send_db_request({"op": "update player status", "name": name, "status": "offline"})
            except: pass
        sock.close()

# -----------------------------------------------------------------------------
# Server Startup
# -----------------------------------------------------------------------------

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    bind_addr = ('0.0.0.0', constants.PLAY_PORT)
    server.bind(bind_addr)
    server.listen(5)
    
    print(f"[Server] Player Server listening on {bind_addr}")

    try:
        while True:
            client_sock, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(client_sock,))
            t.daemon = True
            t.start()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
    finally:
        server.close()

if __name__ == "__main__":
    start_server()