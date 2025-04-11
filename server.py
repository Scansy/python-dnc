import socket
import threading
import pickle

HOST = '127.0.0.1'
PORT = 5555
MAX_PLAYERS = 3

# 8×8 board. None means unclaimed
board = [[None for _ in range(8)] for _ in range(8)]
# Per-tile locks to prevent race conditions
board_locks = [[threading.Lock() for _ in range(8)] for _ in range(8)]

clients = []
player_count = 0

def broadcast(message):
    data = pickle.dumps(message)
    for c in clients:
        c.send(data)

def handle_client(conn, player_id):
    # Send init message with board + player_id
    init_msg = {"type": "init", "player_id": player_id, "board": board}
    conn.send(pickle.dumps(init_msg))

    while True:
        try:
            data = conn.recv(4096)
            if not data:
                break
            msg = pickle.loads(data)

            # 1) Partial draws
            if msg["type"] == "draw":
                # Just broadcast to all, so other clients see the scribble
                broadcast(msg)

            # 2) Final scribble claims
            elif msg["type"] == "scribble":
                r, c, fill_pct = msg["row"], msg["col"], msg["fill"]
                # Lock the tile to prevent race conditions
                with board_locks[r][c]:
                    if board[r][c] is None and fill_pct >= 0.5:
                        board[r][c] = player_id
                        update_msg = {"type": "update", "board": board}
                        broadcast(update_msg)

        except Exception as e:
            print(f"Server error with player {player_id}: {e}")
            break

    conn.close()

def main():
    global player_count
    print(f"Server listening on {HOST}:{PORT}")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen()

    while player_count < MAX_PLAYERS:
        conn, addr = s.accept()
        print(f"Player {player_count} connected from {addr}")
        clients.append(conn)
        threading.Thread(target=handle_client, args=(conn, player_count), daemon=True).start()
        player_count += 1

    print("Server is now full. Running game...")

if __name__ == '__main__':
    main()

