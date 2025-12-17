import socket
import threading
import sys
import os

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

# --- Game Logic Helpers ---
def check_win(board, player):
    wins = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8), # Rows
        (0, 3, 6), (1, 4, 7), (2, 5, 8), # Cols
        (0, 4, 8), (2, 4, 6)             # Diagonals
    ]
    return any(all(board[i] == player for i in combo) for combo in wins)

def check_draw(board):
    return "" not in board

# --- Threaded Server Class ---
class TicTacToeServer:
    def __init__(self, host, port):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((host, int(port)))
        self.server_socket.listen(2)
        
        self.players = {}  # Format: {'X': socket_obj, 'O': socket_obj}
        self.board = [""] * 9
        self.turn = "X"
        self.game_over = False
        self.lock = threading.Lock() 

    def broadcast(self, message):
        """Helper to send a message to ALL players."""
        for conn in self.players.values():
            try:
                netutils.send_msg(conn, message)
            except Exception as e:
                print(f"[!] Broadcast error: {e}")

    def handle_client(self, conn, symbol):
        """Thread function for each player."""
        print(f"[*] Listening thread started for Player {symbol}")
        
        try:
            while not self.game_over:
                msg = netutils.recv_msg(conn)
                
                if not msg:
                    print(f"[-] Player {symbol} disconnected.")
                    break
                
                if msg.get("action") == "MOVE":
                    index = msg["index"]
                    
                    with self.lock:
                        if self.game_over: break

                        if self.turn != symbol:
                            continue # Ignore moves out of turn

                        if 0 <= index < 9 and self.board[index] == "":
                            self.board[index] = symbol
                            
                            if check_win(self.board, symbol):
                                self.game_over = True
                                self.broadcast({
                                    "action": "GAME_OVER", 
                                    "result": "WIN", 
                                    "winner": symbol, 
                                    "board": self.board
                                })
                            elif check_draw(self.board):
                                self.game_over = True
                                self.broadcast({
                                    "action": "GAME_OVER", 
                                    "result": "DRAW", 
                                    "board": self.board
                                })
                            else:
                                self.turn = "O" if self.turn == "X" else "X"
                                self.broadcast({
                                    "action": "UPDATE",
                                    "board": self.board,
                                    "turn": self.turn
                                })

        except Exception as e:
            print(f"[!] Error in thread {symbol}: {e}")
        finally:
            # If one player disconnects mid-game, the other wins
            with self.lock:
                if not self.game_over:
                    self.game_over = True
                    winner = "O" if symbol == "X" else "X"
                    print(f"[*] Player {symbol} left. Declaring {winner} winner.")
                    self.broadcast({
                        "action": "GAME_OVER", 
                        "result": "WIN", 
                        "winner": winner, 
                        "board": self.board
                    })
            conn.close()

    def start(self):
        print(f"[*] Server listening on {self.server_socket.getsockname()}")

        # 1. Accept Player X
        conn1, addr1 = self.server_socket.accept()
        print(f"[*] Player X connected from {addr1}. Waiting for opponent...")
        self.players["X"] = conn1
        # We DO NOT send START yet. Player X's client will remain in "WAITING" state.

        # 2. Accept Player O
        conn2, addr2 = self.server_socket.accept()
        print(f"[*] Player O connected from {addr2}. Both players ready.")
        self.players["O"] = conn2

        # 3. Both Connected -> Send START to both
        netutils.send_msg(conn1, {"action": "START", "symbol": "X"})
        netutils.send_msg(conn2, {"action": "START", "symbol": "O"})

        # 4. Launch Threads
        t1 = threading.Thread(target=self.handle_client, args=(conn1, "X"))
        t2 = threading.Thread(target=self.handle_client, args=(conn2, "O"))
        t1.start()
        t2.start()

        t1.join()
        t2.join()
        
        print("[*] Game finished. Shutting down server.")
        self.server_socket.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 server.py <host> <port>")
        sys.exit(1)
    
    server = TicTacToeServer(sys.argv[1], sys.argv[2])
    server.start()