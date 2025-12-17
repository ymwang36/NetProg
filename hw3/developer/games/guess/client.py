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

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.connect((host, port))
        print(f"Connected to game server at {host}:{port}")
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    try:
        while True:
            # Wait for instruction from server
            msg = netutils.recv_msg(sock)
            
            if not msg:
                print("Disconnected from server.")
                break

            msg_type = msg.get('type')
            content = msg.get('content', '')

            if msg_type == 'print':
                # Just display text
                print(content)

            elif msg_type == 'input':
                # Prompt user and send back result
                user_input = input(content)
                netutils.send_msg(sock, {'data': user_input})

            elif msg_type == 'end':
                # Game over
                print(content)
                break
            
            else:
                print(f"Unknown message type: {msg}")

    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    main()