import sqlite3
import threading
import socket
import json
import sys
import os

# Ensure we can import from the parent/tools directory if running from server/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import netutils
from tools.constants import *

# Configuration
DB_PATH = 'game_store.db'

def get_db_connection():
    """Establishes a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    """Initializes the database tables if they do not exist."""
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Table: Players
    # Identical structure to original Users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Players (
            name TEXT PRIMARY KEY,
            password TEXT,
            games TEXT DEFAULT '[]',
            status TEXT DEFAULT 'offline'
        )
    ''')

    # Table: Devs
    # Identical structure to original Users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Devs (
            name TEXT PRIMARY KEY,
            password TEXT,
            games TEXT DEFAULT '[]',
            status TEXT DEFAULT 'offline'
        )
    ''')

    # Table: Rooms
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Rooms (
            name TEXT PRIMARY KEY,
            game TEXT,
            host TEXT,
            guests TEXT DEFAULT '[]',
			status TEXT DEFAULT 'inactive',
            port INTEGER DEFAULT 0,
            player_limit INTEGER
        )
    ''')

    # Table: Games
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Games (
            name TEXT PRIMARY KEY,
            dev TEXT,
            version INTEGER DEFAULT 1,
            status TEXT DEFAULT 'up',
            type TEXT,
            players INTEGER,
            description TEXT,
            feedback TEXT DEFAULT '[]'
        )
    ''')

    conn.commit()
    conn.close()
    print(f"[*] Database initialized at {DB_PATH}")

def row_to_dict(row):
    return dict(row) if row else None

def process_request(conn, request):
    """
    Dispatches the request to the appropriate handler logic.
    """
    op = request.get('op')
    cursor = conn.cursor()
    response = {"status": "error", "message": "Unknown operation"}

    try:
        # Helper function to handle 'update games' logic to avoid code duplication
        # This works for both tables since they are identical
        def handle_update_games(table_name, name, action, payload):
            cursor.execute(f"SELECT games FROM {table_name} WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                games_list = json.loads(row['games'])
                
                if action == 'add game':
                    # payload: [game_name, version]
                    if not any(g[0] == payload[0] for g in games_list):
                        games_list.append(payload)
                
                elif action == 'update version':
                    # payload: [game_name, new_version]
                    target_game, new_ver = payload
                    for i, (g_name, g_ver) in enumerate(games_list):
                        if g_name == target_game:
                            games_list[i] = [g_name, new_ver]
                            break
                            
                elif action == 'remove game':
                    # payload: game_name
                    target_game = payload
                    games_list = [g for g in games_list if g[0] != target_game]

                cursor.execute(
                    f"UPDATE {table_name} SET games = ? WHERE name = ?",
                    (json.dumps(games_list), name)
                )
                conn.commit()
                return {"status": "success"}
            else:
                return {"status": "error", "message": f"User not found in {table_name}"}

        # ---------------------------------------------------------------------
        # 1. Player Operations
        # ---------------------------------------------------------------------
        if op == 'create player':
            cursor.execute(
                "INSERT INTO Players (name, password) VALUES (?, ?)",
                (request['name'], request['password'])
            )
            conn.commit()
            response = {"status": "success"}

        elif op == 'query player':
            criteria = request.get('criteria', {})
            query = "SELECT * FROM Players"
            params = []
            if criteria:
                conditions = [f"{k} = ?" for k in criteria.keys()]
                query += " WHERE " + " AND ".join(conditions)
                params = list(criteria.values())
            
            cursor.execute(query, params)
            users = []
            for row in cursor.fetchall():
                u = row_to_dict(row)
                u['games'] = json.loads(u['games'])
                users.append(u)
            response = {"status": "success", "data": users}

        elif op == 'update player status':
            cursor.execute(
                "UPDATE Players SET status = ? WHERE name = ?",
                (request['status'], request['name'])
            )
            conn.commit()
            response = {"status": "success"}

        elif op == 'update player games':
            response = handle_update_games('Players', request['name'], request['action'], request['payload'])

        # ---------------------------------------------------------------------
        # 2. Dev Operations (Exact Mirror of Player Ops)
        # ---------------------------------------------------------------------
        elif op == 'create dev':
            cursor.execute(
                "INSERT INTO Devs (name, password) VALUES (?, ?)",
                (request['name'], request['password'])
            )
            conn.commit()
            response = {"status": "success"}

        elif op == 'query dev':
            criteria = request.get('criteria', {})
            query = "SELECT * FROM Devs"
            params = []
            if criteria:
                conditions = [f"{k} = ?" for k in criteria.keys()]
                query += " WHERE " + " AND ".join(conditions)
                params = list(criteria.values())
            
            cursor.execute(query, params)
            users = []
            for row in cursor.fetchall():
                u = row_to_dict(row)
                u['games'] = json.loads(u['games'])
                users.append(u)
            response = {"status": "success", "data": users}

        elif op == 'update dev status':
            cursor.execute(
                "UPDATE Devs SET status = ? WHERE name = ?",
                (request['status'], request['name'])
            )
            conn.commit()
            response = {"status": "success"}

        elif op == 'update dev games':
            response = handle_update_games('Devs', request['name'], request['action'], request['payload'])

        # ---------------------------------------------------------------------
        # 3. Room Operations
        # ---------------------------------------------------------------------
        elif op == 'create room':
            cursor.execute(
                "INSERT INTO Rooms (name, game, host, player_limit) VALUES (?, ?, ?, ?)",
                (request['name'], request['game'], request['host'], request['player_limit'])
            )
            conn.commit()
            response = {"status": "success"}
        
        elif op == 'update room status':
            cursor.execute(
                "UPDATE Rooms SET status = ? WHERE name = ?",
                (request['status'], request['name'])
            )
            conn.commit()
            
            # Check if a row was actually modified (optional but good for debugging)
            if cursor.rowcount > 0:
                response = {"status": "success"}
            else:
                response = {"status": "error", "message": "Room not found"}

        elif op == 'update room port':
            cursor.execute(
                "UPDATE Rooms SET port = ? WHERE name = ?",
                (request['port'], request['name'])
            )
            conn.commit()
            
            # Check if the room actually existed
            if cursor.rowcount > 0:
                response = {"status": "success"}
            else:
                response = {"status": "error", "message": "Room not found"}

        elif op == 'query room':
            criteria = request.get('criteria', {})
            query = "SELECT * FROM Rooms"
            params = []
            if criteria:
                conditions = [f"{k} = ?" for k in criteria.keys()]
                query += " WHERE " + " AND ".join(conditions)
                params = list(criteria.values())
                
            cursor.execute(query, params)
            rooms = []
            for row in cursor.fetchall():
                r = row_to_dict(row)
                r['guests'] = json.loads(r['guests'])
                rooms.append(r)
            response = {"status": "success", "data": rooms}

        elif op == 'update room guests':
            cursor.execute("SELECT guests FROM Rooms WHERE name = ?", (request['name'],))
            row = cursor.fetchone()
            if row:
                guests_list = json.loads(row['guests'])
                action = request['action']
                guest = request['guest_name']

                if action == 'add guest':
                    if guest not in guests_list:
                        guests_list.append(guest)
                elif action == 'remove guest':
                    if guest in guests_list:
                        guests_list.remove(guest)

                cursor.execute(
                    "UPDATE Rooms SET guests = ? WHERE name = ?",
                    (json.dumps(guests_list), request['name'])
                )
                conn.commit()
                response = {"status": "success"}
            else:
                response = {"status": "error", "message": "Room not found"}

        elif op == 'remove room':
            cursor.execute("DELETE FROM Rooms WHERE name = ?", (request['name'],))
            conn.commit()
            response = {"status": "success"}

        # ---------------------------------------------------------------------
        # 4. Game Operations
        # ---------------------------------------------------------------------
        elif op == 'create game':
            cursor.execute(
                "INSERT INTO Games (name, dev, type, players, description) VALUES (?, ?, ?, ?, ?)",
                (request['name'], request['dev'], request['type'], request['players'], request['description'])
            )
            conn.commit()
            response = {"status": "success"}

        elif op == 'query game':
            criteria = request.get('criteria', {})
            query = "SELECT * FROM Games"
            params = []
            if criteria:
                conditions = [f"{k} = ?" for k in criteria.keys()]
                query += " WHERE " + " AND ".join(conditions)
                params = list(criteria.values())

            cursor.execute(query, params)
            games = []
            for row in cursor.fetchall():
                g = row_to_dict(row)
                g['feedback'] = json.loads(g['feedback'])
                games.append(g)
            response = {"status": "success", "data": games}

        elif op == 'update game':
            updates = request.get('updates', {})
            if updates:
                set_clause = [f"{k} = ?" for k in updates.keys()]
                params = list(updates.values())
                params.append(request['name'])
                
                sql = f"UPDATE Games SET {', '.join(set_clause)} WHERE name = ?"
                cursor.execute(sql, params)
                conn.commit()
                response = {"status": "success"}

        elif op == 'add feedback':
            cursor.execute("SELECT feedback FROM Games WHERE name = ?", (request['name'],))
            row = cursor.fetchone()

            if row:
                fb_list = json.loads(row['feedback'])
                fb_list.append(request['feedback'])
                
                cursor.execute(
                    "UPDATE Games SET feedback = ? WHERE name = ?",
                    (json.dumps(fb_list), request['name'])
                )
                conn.commit()
                response = {"status": "success"}
            else:
                response = {"status": "error", "message": "Game not found"}

    except sqlite3.Error as e:
        response = {"status": "error", "message": f"Database error: {str(e)}"}
    except Exception as e:
        response = {"status": "error", "message": f"Server error: {str(e)}"}

    return response

def client_handler(sock):
    """
    Thread target. Handles the connection lifecycle for a single client.
    """
    conn = get_db_connection()
    try:
        while True:
            request = netutils.recv_msg(sock)
            if not request:
                break
            response = process_request(conn, request)
            netutils.send_msg(sock, response)
    except Exception as e:
        print(f"[!] Error handling client: {e}")
    finally:
        conn.close()
        sock.close()

def start_server():
    init_db()
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_sock.bind((DB_HOST, DB_PORT))
        server_sock.listen(5)
        print(f"[*] Database Server listening on {DB_HOST}:{DB_PORT}")
        
        while True:
            client_sock, addr = server_sock.accept()
            t = threading.Thread(target=client_handler, args=(client_sock,))
            t.daemon = True 
            t.start()
            
    except KeyboardInterrupt:
        print("\n[*] Stopping server...")
    finally:
        server_sock.close()

if __name__ == "__main__":
    start_server()