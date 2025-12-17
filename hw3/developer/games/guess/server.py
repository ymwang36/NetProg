import socket, sys, threading, random, time, os

current_dir = os.path.dirname(os.path.abspath(__file__))
while True:
    if os.path.exists(os.path.join(current_dir, 'tools')):
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        break
    parent_dir = os.path.dirname(current_dir)
    if parent_dir == current_dir:
        break
    current_dir = parent_dir
from tools import netutils, constants

# Game State
players = []       # List of sockets
player_threads = []
target_number = 0
current_turn = 0   # Index of the player whose turn it is (0, 1, or 2)
game_over = False

# Synchronization
game_state_lock = threading.Condition() # Locks the game state and notifies threads

def broadcast(message, exclude_id=None):
    """Sends a message to all connected players."""
    for idx, sock in enumerate(players):
        if exclude_id is not None and idx == exclude_id:
            continue
        try:
            netutils.send_msg(sock, {"type": "print", "content": message})
        except:
            pass

def handle_player(sock, player_id):
    global current_turn, game_over

    # 1. Wait for Game Start
    # We cheat slightly: The main thread won't start these threads until all 3 connect.
    # So we can just send the welcome message immediately.
    try:
        netutils.send_msg(sock, {
            "type": "print", 
            "content": f"Game Started! You are Player {player_id + 1}."
        })
    except:
        return

    # 2. Main Turn Loop
    while not game_over:
        with game_state_lock:
            # WAIT phase: Wait until it is my turn or the game ends
            while (current_turn != player_id) and not game_over:
                game_state_lock.wait()
            
            # Check if we woke up because the game ended
            if game_over:
                netutils.send_msg(sock, {"type": "end", "content": "Game Over."})
                return

            # ACTION phase: It is my turn
            try:
                # Notify others
                broadcast(f"Player {player_id + 1} is guessing...", exclude_id=player_id)

                # Ask for input
                netutils.send_msg(sock, {
                    "type": "input", 
                    "content": "Your turn! Guess (1-100): "
                })
                
                # Receive input (Blocking)
                response = netutils.recv_msg(sock)
                if not response or 'data' not in response:
                    guess = -1 # Treat bad data as invalid
                else:
                    try:
                        guess = int(response['data'])
                    except ValueError:
                        guess = -1

                # Logic Check
                if guess == target_number:
                    broadcast(f"CORRECT! Player {player_id + 1} wins with {guess}!", exclude_id=None)
                    game_over = True
                    game_state_lock.notify_all() # Wake up everyone to exit
                    return
                elif guess == -1:
                    netutils.send_msg(sock, {"type": "print", "content": "Invalid input."})
                elif guess < target_number:
                    netutils.send_msg(sock, {"type": "print", "content": "Too Low!"})
                    broadcast(f"Player {player_id + 1} guessed {guess} (Too Low).", exclude_id=player_id)
                else:
                    netutils.send_msg(sock, {"type": "print", "content": "Too High!"})
                    broadcast(f"Player {player_id + 1} guessed {guess} (Too High).", exclude_id=player_id)

                # End of turn: Pass baton to next player
                if not game_over:
                    current_turn = (current_turn + 1) % 3
                    game_state_lock.notify_all() # Wake up all threads to check whose turn it is

            except Exception as e:
                print(f"Error in Player {player_id + 1} thread: {e}")
                game_over = True
                game_state_lock.notify_all()
                return

def main():
    global target_number, players

    if len(sys.argv) != 3:
        print("Usage: python3 server.py <host> <port>")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((host, port))
        server_socket.listen(3)
    except Exception as e:
        print(f"Server start failed: {e}")
        sys.exit(1)

    print(f"Threaded Server running on {host}:{port}")
    print("Waiting for 3 players...")

    # 1. Accept connections (Main Thread)
    while len(players) < 3:
        client_sock, addr = server_socket.accept()
        print(f"Connection from {addr}")
        players.append(client_sock)
        
        # Send a temp message so they know they are connected
        netutils.send_msg(client_sock, {
            "type": "print", 
            "content": f"Connected. Waiting for {3 - len(players)} more player(s)..."
        })

    # 2. Setup Game
    target_number = random.randint(1, 100)
    print(f"All players connected. Target is {target_number}. Starting threads...")

    # 3. Start a thread for each player
    for i in range(3):
        t = threading.Thread(target=handle_player, args=(players[i], i))
        t.start()
        player_threads.append(t)

    # 4. Wait for threads to finish
    for t in player_threads:
        t.join()

    print("Game finished. Closing sockets.")
    for s in players:
        s.close()
    server_socket.close()

if __name__ == "__main__":
    main()