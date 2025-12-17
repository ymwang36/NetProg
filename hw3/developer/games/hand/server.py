import socket, sys, threading, os

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

def get_player_move(conn, player_id, moves):
	"""
	Notifies player to start and waits for their JSON response.
	"""
	try:
		# 4. Ask player to choose
		netutils.send_msg(conn, {
			"status": "start", 
			"message": "Game Started! Please enter your move."
		})
		
		# Receive dictionary from client using netutils
		data = netutils.recv_msg(conn)
		
		# We expect a dictionary like {'move': 'rock'}
		move = data.get('move')
		
		print(f"Player {player_id} selected: {move}")
		moves[player_id] = move
		
	except Exception as e:
		print(f"Error with Player {player_id}: {e}")
		moves[player_id] = None

def determine_winner(m1, m2):
	if not m1 or not m2:
		return -1 # Error/Disconnect

	if m1 == m2:
		return 0

	if (m1 == 'rock' and m2 == 'scissors') or \
		(m1 == 'scissors' and m2 == 'paper') or \
		(m1 == 'paper' and m2 == 'rock'):
		return 1

	return 2

def main():
	if len(sys.argv) != 3:
		print("Usage: python3 server.py <host> <port>")
		sys.exit(1)

	host = sys.argv[1]
	port = int(sys.argv[2])

	server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	try:
		server_socket.bind((host, port))
	except socket.error as e:
		print(f"Bind failed: {e}")
		sys.exit(1)

	server_socket.listen(2)
	print(f"Server listening on {host}:{port}...")

	clients = []

	# 2. Accept two player connections
	while len(clients) < 2:
		conn, addr = server_socket.accept()
		clients.append(conn)
		print(f"Player {len(clients)} connected from {addr}")
		
		# Send a waiting message using netutils
		netutils.send_msg(conn, {
			"status": "info", 
			"message": f"Connected as Player {len(clients)}. Waiting for opponent..."
		})

	# 3. Start the game
	print("Both players connected. Starting game.")

	moves = {}
	threads = []

	# Threading to handle simultaneous input
	for i, conn in enumerate(clients):
		player_id = i + 1
		t = threading.Thread(target=get_player_move, args=(conn, player_id, moves))
		threads.append(t)
		t.start()

	for t in threads:
		t.join()

	# 5. Determine winner
	m1 = moves.get(1)
	m2 = moves.get(2)
	result = determine_winner(m1, m2)

	p1_res = {"status": "end", "message": "", "winner": False}
	p2_res = {"status": "end", "message": "", "winner": False}

	if result == -1:
		p1_res["message"] = p2_res["message"] = "Game Void: Player disconnected or error."
	elif result == 0:
		p1_res["message"] = p2_res["message"] = f"It's a Draw! Both chose {m1}."
	elif result == 1:
		p1_res["message"] = f"You Won! {m1} beats {m2}."
		p1_res["winner"] = True
		p2_res["message"] = f"You Lost! {m1} beats {m2}."
	else: # result == 2
		p1_res["message"] = f"You Lost! {m2} beats {m1}."
		p2_res["message"] = f"You Won! {m2} beats {m1}."
		p2_res["winner"] = True

	# Send results via netutils
	try:
		netutils.send_msg(clients[0], p1_res)
		netutils.send_msg(clients[1], p2_res)
	except:
		pass

	# 6. Game End
	print("Game Over. Closing connections.")
	for conn in clients:
		conn.close()
	server_socket.close()

if __name__ == "__main__":
    main()