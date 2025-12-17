import socket, sys, os

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

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 client.py <host> <port>")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        client_socket.connect((host, port))
    except socket.error as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    # 1. Receive initial "Connected/Waiting" message
    initial_msg = netutils.recv_msg(client_socket)
    print(f"[Server]: {initial_msg.get('message')}")

    # 2. Receive "Game Started" signal
    start_msg = netutils.recv_msg(client_socket)
    print(f"[Server]: {start_msg.get('message')}")

    # 3. Prompt user input with Client-Side Validation
    valid_moves = ['rock', 'paper', 'scissors']
    user_move = ""

    while True:
        user_move = input("Enter 'rock', 'paper', or 'scissors': ").strip().lower()
        if user_move in valid_moves:
            break
        print("Invalid move. Please try again.")

    # 4. Send valid move using netutils
    netutils.send_msg(client_socket, {"move": user_move})
    print("Move sent! Waiting for result...")

    # 5. Receive Winner/Loser result
    result_msg = netutils.recv_msg(client_socket)
    
    print("\n--- RESULT ---")
    print(result_msg.get('message'))
    print("--------------")

    client_socket.close()

if __name__ == "__main__":
    main()