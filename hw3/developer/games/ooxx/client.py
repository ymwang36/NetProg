import pygame
import socket
import sys
import threading
import os
import time  # Needed for the delay

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

os.environ['SDL_AUDIODRIVER'] = 'dummy'

# --- Constants ---
WIDTH, HEIGHT = 600, 600
LINE_WIDTH = 10
BOARD_ROWS = 3
BOARD_COLS = 3
SQUARE_SIZE = WIDTH // BOARD_COLS
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GRAY = (200, 200, 200)

# --- Global State ---
game_state = {
    "board": [""] * 9,
    "my_symbol": None,
    "turn": "X",
    "status": "WAITING", 
    "winner": None
}
state_lock = threading.Lock()
sock = None
running = True

def draw_lines(screen):
    pygame.draw.line(screen, BLACK, (0, SQUARE_SIZE), (WIDTH, SQUARE_SIZE), LINE_WIDTH)
    pygame.draw.line(screen, BLACK, (0, 2 * SQUARE_SIZE), (WIDTH, 2 * SQUARE_SIZE), LINE_WIDTH)
    pygame.draw.line(screen, BLACK, (SQUARE_SIZE, 0), (SQUARE_SIZE, HEIGHT), LINE_WIDTH)
    pygame.draw.line(screen, BLACK, (2 * SQUARE_SIZE, 0), (2 * SQUARE_SIZE, HEIGHT), LINE_WIDTH)

def draw_figures(screen):
    with state_lock:
        board = game_state["board"]
        
    for row in range(BOARD_ROWS):
        for col in range(BOARD_COLS):
            index = row * 3 + col
            mark = board[index]
            
            center_x = int(col * SQUARE_SIZE + SQUARE_SIZE / 2)
            center_y = int(row * SQUARE_SIZE + SQUARE_SIZE / 2)

            if mark == "X":
                start_desc = (col * SQUARE_SIZE + 50, row * SQUARE_SIZE + 50)
                end_desc = (col * SQUARE_SIZE + SQUARE_SIZE - 50, row * SQUARE_SIZE + SQUARE_SIZE - 50)
                pygame.draw.line(screen, RED, start_desc, end_desc, 20)
                start_asc = (col * SQUARE_SIZE + 50, row * SQUARE_SIZE + SQUARE_SIZE - 50)
                end_asc = (col * SQUARE_SIZE + SQUARE_SIZE - 50, row * SQUARE_SIZE + 50)
                pygame.draw.line(screen, RED, start_asc, end_asc, 20)
            elif mark == "O":
                pygame.draw.circle(screen, BLUE, (center_x, center_y), 60, 15)

def network_listener():
    global running
    try:
        while running:
            msg = netutils.recv_msg(sock)
            if not msg:
                break
            
            action = msg.get("action")
            
            if action == "START":
                with state_lock:
                    game_state["my_symbol"] = msg["symbol"]
                    game_state["status"] = "PLAYING"
                print(f"[*] Game Started. You are {msg['symbol']}")

            elif action == "UPDATE":
                with state_lock:
                    game_state["board"] = msg["board"]
                    game_state["turn"] = msg["turn"]

            elif action == "GAME_OVER":
                # 1. Update the state so the user sees the result
                with state_lock:
                    game_state["board"] = msg["board"]
                    result = msg["result"]
                    winner = msg.get("winner")
                    
                    if result == "DRAW":
                        game_state["status"] = "DRAW"
                    elif winner == game_state["my_symbol"]:
                        game_state["status"] = "WIN"
                    else:
                        game_state["status"] = "LOSE"
                
                # 2. Wait 3 seconds so the user can actually read "YOU WON"
                print("[*] Game Over. Closing in 3 seconds...")
                time.sleep(3)
                
                # 3. Signal the main loop to stop
                running = False
                break

    except Exception as e:
        print(f"[!] Network error: {e}")
    finally:
        print("[*] Network thread ending.")

def main(host, port):
    global sock, running

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, int(port)))
    except Exception as e:
        print(f"[!] Connection failed: {e}")
        return

    thread = threading.Thread(target=network_listener, daemon=True)
    thread.start()

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Tic Tac Toe")
    font = pygame.font.SysFont(None, 40)
    clock = pygame.time.Clock()

    # Changed from 'while True' to 'while running' so the network thread can stop this loop
    while running:
        clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                with state_lock:
                    # Check if game is active AND it's my turn
                    if game_state["status"] == "PLAYING" and game_state["turn"] == game_state["my_symbol"]:
                        mouseX = event.pos[0]
                        mouseY = event.pos[1]
                        clicked_row = int(mouseY // SQUARE_SIZE)
                        clicked_col = int(mouseX // SQUARE_SIZE)
                        index = clicked_row * 3 + clicked_col

                        if game_state["board"][index] == "":
                            netutils.send_msg(sock, {"action": "MOVE", "index": index})

        # --- Rendering ---
        screen.fill(WHITE)
        draw_lines(screen)
        draw_figures(screen)

        # UI Text
        with state_lock:
            status = game_state["status"]
            my_symbol = game_state["my_symbol"]
            turn = game_state["turn"]

        if status == "WAITING":
            text = "Waiting for opponent..."
        elif status == "PLAYING":
            if turn == my_symbol:
                text = f"Your Turn ({my_symbol})"
            else:
                text = f"Opponent's Turn ({'O' if my_symbol=='X' else 'X'})"
        elif status == "WIN":
            text = "YOU WON!"
        elif status == "LOSE":
            text = "YOU LOST!"
        elif status == "DRAW":
            text = "DRAW!"
        else:
            text = ""

        if text:
            text_surf = font.render(text, True, BLACK)
            pygame.draw.rect(screen, GRAY, (5, 5, text_surf.get_width()+10, text_surf.get_height()+10))
            screen.blit(text_surf, (10, 10))

        pygame.display.update()

    # Cleanup
    if sock:
        sock.close()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 client.py <host> <port>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])