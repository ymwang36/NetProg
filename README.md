# NetProg
Introduction to Network Programming, NYCU 2025 Fall

## Homework 3

### file structure
```bash
hw3/
├── developer
│   ├── dev_client.py
│   └── games
│       ├── guess
│       │   ├── client.py
│       │   ├── description.txt
│       │   └── server.py
│       ├── hand
│       │   ├── client.py
│       │   ├── description.txt
│       │   └── server.py
│       └── ooxx
│           ├── client.py
│           ├── description.txt
│           └── server.py
├── player
│   ├── games
│   └── player_client.py
├── server
│   ├── database.py
│   ├── dev_server.py
│   ├── games
│   └── player_server.py
└── tools
    ├── constants.py
    └── netutils.py
```

### Tools
#### `constants.py`
Holds the host address and port number.

#### `netutils.py`
Handle length prefix framing protocol.
* `send_msg(sock, msg)` - send a python dict
* `recv_msg(sock)` - receive a python dict

### Server
Please run `database.py`, `dev_server.py`, `player_server.py` (in that order) on a suitable server, make sure to change the host in `tools/constants.py` to match.

#### `database.py`
Stores the data, including user and game information.

#### `dev_server.py`
Handle interaction with developer users.

#### `player_server.py`
Handle interaction with player users.

#### `games`
A directory for storing game files. Avoid making changes unless absolutely necessary.

### Developer
#### `dev_client.py`
Handle interation with server.

#### `games`
A directory for storing and testing games.
This system supports CLI and GUI games with 2 to 5 players.

If a developer wishes to upload a game, please make sure the game follows the following file structure
```bash
games/
└── [game_name]
    ├── client.py
    ├── description.txt
    └── server.py
```
The game must have `client.py`, `description.txt`, and `server.py`
`description.txt` should have the description of the game.

`client.py` should be able to run using `python client.py <host> <port>` where `<host>` and `<port>` is the host and port the client should connect to.
`server.py` should be able to run using `python server.py <host> <port>` where `<host>` and `<port>` is the host and port the server should connect to. `server.py` should be able to accept exactly the amount of player the game needs. After the game, please terminate all players at the same time gracefully. 
`server.py` and `client.py` may use `tools/netutils.py`, but they should pay attention to how the file is imported in the example games, if the file is not imported the same way, it may not work once it's uploaded to the system.

Example games
1. guess - guess the number, a 3-player CLI game
2. hand - rock paper scissors, a 2-player CLI game
3. ooxx - tic tac toe, a 2-player GUI game

### Player
#### `player_client.py`
Handle interaction with server.
Players should run this file on their computer.

#### `games`
A directory for storing player's game files. **DO NOT** make changes to these files.
