import struct
import socket
import json

def send_msg(sock, message):
    """
    1. Serializes a Python object (message) to a JSON string.
    2. Encodes it to bytes (UTF-8).
    3. Prefixes it with a 4-byte (32-bit) length (network byte order).
    4. Sends it.
    """
    # Convert dict/list -> json string -> binary bytes
    json_str = json.dumps(message)
    message_bytes = json_str.encode('utf-8')

    MAX_MSG_SIZE = 64 * 1024  # 65536 bytes
    length = len(message_bytes)
    
    if length > MAX_MSG_SIZE:
        raise ValueError(f"Message too large: {length} bytes (max {MAX_MSG_SIZE})")
    
    prefix = struct.pack('!I', length)
    
    try:
        sock.sendall(prefix)
        sock.sendall(message_bytes)
    except Exception as e:
        print(f"Message cannot be sent. Error: {e}")
        # We re-raise the exception so the caller knows the connection failed
        raise e

def recv_msg(sock):
    """
    Reads a message prefixed with a 4-byte (32-bit) length.
    Throws ValueError if the message length exceeds MAX_MSG_SIZE.
    Returns the decoded Python object (from JSON), or None if the connection is closed.
    """
    # Read the 4-byte length prefix
    prefix = recvall(sock, 4)
    if not prefix:
        return None  # Connection closed

    length = struct.unpack('!I', prefix)[0]
    MAX_MSG_SIZE = 64 * 1024  # 65536 bytes
    
    if length > MAX_MSG_SIZE:
        raise ValueError(f"Message too large: {length} bytes (max {MAX_MSG_SIZE})")

    message_bytes = recvall(sock, length)
    if not message_bytes:
        return None  # Connection closed unexpectedly
    
    # binary bytes -> json string -> dict/list
    json_str = message_bytes.decode('utf-8')
    return json.loads(json_str)

def recvall(sock, n):
    """
    Helper function to receive 'n' bytes or return None if EOF is hit.
    """
    data = b''
    while len(data) < n:
        try:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
        except socket.error as e:
            print(f"Socket error in recvall: {e}")
            return None
        data += packet
    return data