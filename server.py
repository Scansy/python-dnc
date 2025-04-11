import socket
import threading
import pickle

HOST = '127.0.0.1'
PORT = 5555
MAX_PLAYERS = 3

# 8×8 board. None means unclaimed.
board = [[None for _ in range(8)] for _ in range(8)]
# A lock for each tile, so multiple threads can't claim it simultaneously.
board_locks = [[threading.Lock() for _ in range(8)] for _ in range(8)]

clients = []

def handle_client(conn, player_id):
    """
    Listens for 'scribble' messages from this client.
    If >= 50% fill is reported on an unclaimed tile, claim it for this player.
    Broadcast updates to everyone.
    """
    # Send initial board + assigned player ID
    conn.send(pickle.dumps({"type": "init", "player_id": player_id, "board": board}))

    while True:
        try:
            data = conn.recv(4096)
            if not data:
                break

            msg = pickle.loads(data)
            if msg["type"] == "scribble":
                r, c, fill_pct = msg["row"], msg["col"], msg["fill"]
                # Lock the specific tile to prevent race conditions
                with board_locks[r][c]:
                    # If tile unclaimed and fill >= 0.5, claim for this player
                    if board[r][c] is None and fill_pct >= 0.5:
                        board[r][c] = player_id
                        # Broadcast update to all clients
                        update_msg = {"type": "update", "board": board}
                        broadcast(update_msg)
        except Exception as e:
            print(f"Error with client {player_id}: {e}")
            break

    conn.close()

def broadcast(message):
    """
    Send pickled messages to all connected clients.
    """
    data = pickle.dumps(message)
    for c in clients:
        c.send(data)

def main():
    print("Server starting on", (HOST, PORT))
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen()

    # Accept exactly 3 players (or you can accept unlimited if desired).
    player_id = 0
    while player_id < MAX_PLAYERS:
        conn, addr = s.accept()
        print(f"Player {player_id} connected from {addr}")
        clients.append(conn)
        threading.Thread(target=handle_client, args=(conn, player_id), daemon=True).start()
        player_id += 1

    print("Server is now full — 3 players connected.")
    # Server keeps running. You could add logic to end the game when board is full.

if __name__ == '__main__':
    main()

