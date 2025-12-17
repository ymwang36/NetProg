import socket
import threading
import sys
import os

# -----------------------------------------------------------------------------
# Path Setup
# -----------------------------------------------------------------------------
# Append parent directory to path to import 'tools'
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
    1. Sends display instruction to client.
    2. Waits for and returns client response.
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

# -----------------------------------------------------------------------------
# Main Logic: Client Handler
# -----------------------------------------------------------------------------

def handle_client(sock):
    """
    Main state machine for a connected developer client.
    Handles Menu -> Login/Register -> Session Loop (CRUD Operations).
    """
    print(f"[Server] New connection: {sock.getpeername()}")
    name = None # Track the logged-in user

    try:
        while True:
            # --- Step 1: Pre-Login Menu ---
            menu_text = "1. Login\n2. Register\n3. Exit"
            response = client_interaction(sock, menu_text, ["1", "2", "3"])
            if not response: break # Client disconnected
            
            choice = response.get("response")

            # --- Step 2: Register ---
            if choice == "2":
                resp_name = client_interaction(sock, "Enter Name:", ["text", 20])
                reg_name = resp_name.get("response")
                
                resp_pw = client_interaction(sock, "Enter Password:", ["text", 20])
                reg_password = resp_pw.get("response")

                db_req = {"op": "create dev", "name": reg_name, "password": reg_password}
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

                # Query DB
                db_req = {"op": "query dev", "criteria": {"name": login_name}}
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
                    # =========================================================
                    # PHASE B: SESSION LOOP (CRUD)
                    # =========================================================
                    
                    # 1. Update status to online
                    name = login_name # Store for session usage
                    send_db_request({"op": "update dev status", "name": name, "status": "online"})
                    client_interaction(sock, f"Welcome {name}", "none")

                    # 2. Enter Session Loop
                    while True:
                        session_menu = "1. Upload Game\n2. Read Game\n3. Update Game\n4. Remove Game\n5. Logout"
                        sess_resp = client_interaction(sock, session_menu, ["1", "2", "3", "4", "5"])
                        if not sess_resp: break
                        
                        sess_choice = sess_resp.get("response")

                        # --- Option 1: Upload Game (Create) ---
                        if sess_choice == "1":
                            # A. Metadata Collection & Validation
                            g_name_resp = client_interaction(sock, "Enter Game Name:", ["text", 30])
                            if not g_name_resp: break 
                            g_name = g_name_resp.get("response")

                            # Check DB if name is taken
                            db_check = send_db_request({"op": "query game", "criteria": {"name": g_name}})
                            if db_check.get("data"): 
                                client_interaction(sock, f"Error: The name '{g_name}' is already taken.", "none")
                                continue 

                            # Game Type
                            type_menu = "Select Game Type:\n1. CLI\n2. GUI"
                            g_type_resp = client_interaction(sock, type_menu, ["1", "2"])
                            if not g_type_resp: break
                            
                            raw_type = g_type_resp.get("response")
                            g_type = "CLI" if raw_type == "1" else "GUI"
                            
                            g_players = 2
                            player_menu = "Select Players:\n[2] [3] [4] [5]"
                            g_player_resp = client_interaction(sock, player_menu, ["2", "3", "4", "5"])
                            if not g_player_resp: break
                            g_players = int(g_player_resp.get("response"))

                            # B. File Transfer Loop
                            required_files = ["server.py", "client.py", "description.txt"]
                            file_data_buffer = {} 
                            upload_aborted = False

                            for filename in required_files:
                                client_rel_path = os.path.join("games", g_name, filename)
                                netutils.send_msg(sock, {"op": "upload", "path": client_rel_path})
                                file_resp = netutils.recv_msg(sock)
                                if not file_resp or file_resp.get("response") != "success":
                                    client_interaction(sock, f"Error uploading {filename}. Aborting.", "none")
                                    upload_aborted = True
                                    break
                                file_data_buffer[filename] = file_resp.get("file data", "")

                            if upload_aborted: continue 

                            # C. Persist Data
                            try:
                                save_dir = os.path.join("games", g_name)
                                os.makedirs(save_dir, exist_ok=True)
                                for fname, content in file_data_buffer.items():
                                    with open(os.path.join(save_dir, fname), "w") as f:
                                        f.write(content)

                                create_game_req = {
                                    "op": "create game",
                                    "name": g_name,
                                    "dev": name,
                                    "type": g_type, 
                                    "players": g_players,
                                    "description": file_data_buffer.get("description.txt", "")
                                }
                                
                                db_create_resp = send_db_request(create_game_req)
                                if db_create_resp.get("status") == "success":
                                    client_interaction(sock, "Game uploaded successfully!", "none")
                                else:
                                    client_interaction(sock, f"DB Error: {db_create_resp.get('message')}", "none")

                            except Exception as e:
                                print(f"[Server] Upload Error: {e}")
                                client_interaction(sock, "Server internal error during save.", "none")

                        # --- Option 2: Read Game (Read) ---
                        elif sess_choice == "2":
                            # 1. Query DB (All games, even those 'down')
                            query_req = {"op": "query game", "criteria": {"dev": name}}
                            query_resp = send_db_request(query_req)
                            user_games = query_resp.get("data", [])

                            if not user_games:
                                client_interaction(sock, "You have not uploaded any games.", "none")
                                continue

                            # 2. Build Menu
                            game_list_str = "Select Game to Read:\n"
                            valid_choices = []
                            for idx, game in enumerate(user_games, 1):
                                # Show status so they know if it's down
                                status_tag = "[DOWN]" if game.get("status") == "down" else "[UP]"
                                game_list_str += f"{idx}. {game['name']} {status_tag}\n"
                                valid_choices.append(str(idx))

                            # 3. Selection
                            sel_resp = client_interaction(sock, game_list_str, valid_choices)
                            if not sel_resp: break
                            
                            target_game = user_games[int(sel_resp.get("response")) - 1]

                            # 4. Display Info
                            # Format columns: name, dev, version, status, type, players, description, feedback
                            def get_description(data):
                                if not data: return "No description"
                                return "\n====\n" + data + "\n===="
                            def get_feedback(data):
                                if not data: return "No feedback"
                                ret = "\n====\n"
                                for i in data:
                                    ret += f"User {i[0]} ({i[1]} stars): {i[2]}\n"
                                return ret + "===="

                            info_text = (
                                f"--- Game Info: {target_game['name']} ---\n"
                                f"Developer:   {target_game['dev']}\n"
                                f"Version:     {target_game.get('version', 1)}\n"
                                f"Status:      {target_game.get('status', 'unknown')}\n"
                                f"Type:        {target_game['type']}\n"
                                f"Players:     {target_game['players']}\n"
                                f"Description: {get_description(target_game['description'])}\n"
                                f"Feedback:    {get_feedback(target_game.get('feedback', []))}\n"
                                f"---------------------------------\n"
                            )

                            client_interaction(sock, info_text, "none")

                        # --- Option 3: Update Game (Update) ---
                        elif sess_choice == "3":
                            # 1. Query Active Games
                            query_req = {"op": "query game", "criteria": {"dev": name}}
                            query_resp = send_db_request(query_req)
                            all_games = query_resp.get("data", [])
                            
                            # Filter: Only 'up'
                            active_games = [g for g in all_games if g.get("status", "up") == "up"]

                            if not active_games:
                                client_interaction(sock, "No active games found to update.", "none")
                                continue

                            # 2. Build Menu
                            game_list_str = "Select Game to Update:\n"
                            valid_choices = []
                            for idx, game in enumerate(active_games, 1):
                                v_num = game.get("version", 1)
                                game_list_str += f"{idx}. {game['name']} (v{v_num})\n"
                                valid_choices.append(str(idx))

                            sel_resp = client_interaction(sock, game_list_str, valid_choices)
                            if not sel_resp: break
                            
                            target_game = active_games[int(sel_resp.get("response")) - 1]
                            target_name = target_game["name"]
                            current_version = target_game.get("version", 1)

                            # 3. File Transfer
                            required_files = ["server.py", "client.py", "description.txt"]
                            file_data_buffer = {}
                            upload_aborted = False

                            for filename in required_files:
                                client_rel_path = os.path.join("games", target_name, filename)
                                netutils.send_msg(sock, {"op": "upload", "path": client_rel_path})
                                file_resp = netutils.recv_msg(sock)
                                if not file_resp or file_resp.get("response") != "success":
                                    client_interaction(sock, f"Error uploading {filename}. Aborting.", "none")
                                    upload_aborted = True
                                    break
                                file_data_buffer[filename] = file_resp.get("file data", "")

                            if upload_aborted: continue

                            # 4. Save & Update DB
                            try:
                                save_dir = os.path.join("games", target_name)
                                os.makedirs(save_dir, exist_ok=True)
                                for fname, content in file_data_buffer.items():
                                    with open(os.path.join(save_dir, fname), "w") as f:
                                        f.write(content)

                                new_version = current_version + 1
                                update_req = {
                                    "op": "update game", 
                                    "name": target_name,
                                    "updates": {
                                        "description": file_data_buffer.get("description.txt", ""),
                                        "version": new_version
                                    }
                                }
                                db_upd_resp = send_db_request(update_req)

                                if db_upd_resp.get("status") == "success":
                                    client_interaction(sock, f"Updated '{target_name}' to v{new_version}!", "none")
                                else:
                                    err = db_upd_resp.get("message") or db_upd_resp.get("error")
                                    client_interaction(sock, f"DB Error: {err}", "none")

                            except Exception as e:
                                print(f"[Server] Update Error: {e}")
                                client_interaction(sock, "Server error during update.", "none")

                        # --- Option 4: Remove Game (Delete) ---
                        elif sess_choice == "4":
                            # 1. Query Active Games
                            query_req = {"op": "query game", "criteria": {"dev": name}}
                            query_resp = send_db_request(query_req)
                            all_games = query_resp.get("data", [])

                            # Filter: Only 'up'
                            active_games = [g for g in all_games if g.get("status", "up") == "up"]

                            if not active_games:
                                client_interaction(sock, "No active games found to remove.", "none")
                                continue

                            # 2. Build Menu
                            game_list_str = "Select Game to Remove (Shutdown):\n"
                            valid_choices = []
                            for idx, game in enumerate(active_games, 1):
                                game_list_str += f"{idx}. {game['name']}\n"
                                valid_choices.append(str(idx))

                            sel_resp = client_interaction(sock, game_list_str, valid_choices)
                            if not sel_resp: break
                            
                            target_game = active_games[int(sel_resp.get("response")) - 1]
                            target_name = target_game["name"]

                            # 3. Update Status to 'down'
                            update_req = {
                                "op": "update game",
                                "name": target_name,
                                "updates": {"status": "down"}
                            }
                            db_resp = send_db_request(update_req)
                            
                            if db_resp.get("status") == "success":
                                client_interaction(sock, f"Game '{target_name}' is now down.", "none")
                            else:
                                err = db_resp.get("message") or db_resp.get("error")
                                client_interaction(sock, f"Error removing game: {err}", "none")

                        # --- Option 5: Logout ---
                        elif sess_choice == "5":
                            send_db_request({"op": "update dev status", "name": name, "status": "offline"})
                            print(f"[Server] {name} logged out.")
                            return 

            # --- Step 5: Exit (Pre-login) ---
            elif choice == "3":
                print("[Server] Client requested exit.")
                break

    except (ConnectionResetError, BrokenPipeError):
        print(f"[Server] Connection lost with {name if name else 'client'}")
    except Exception as e:
        print(f"[Server] Error handling client: {e}")
    finally:
        if name:
             try: send_db_request({"op": "update dev status", "name": name, "status": "offline"})
             except: pass
        sock.close()

# -----------------------------------------------------------------------------
# Server Startup
# -----------------------------------------------------------------------------

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    bind_addr = ('0.0.0.0', constants.DEV_PORT)
    server.bind(bind_addr)
    server.listen(5)
    
    print(f"[Server] Developer Server listening on {bind_addr}")

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