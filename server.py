import socket
import threading
import pickle
import time

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
                broadcast(msg)

            # 2) Final scribble claims
            elif msg["type"] == "scribble":
                r, c, fill_pct = msg["row"], msg["col"], msg["fill"]
                # Lock the tile to prevent race conditions
                with board_locks[r][c]:
                    if board[r][c] is None and fill_pct >= 0.05:
                        board[r][c] = player_id
                        update_msg = {"type": "update", "board": board}
                        broadcast(update_msg)
                        print("board claimed")
                    else:
                        # Clear tile if fill percentage < 50%
                        board[r][c] = None
                        reset_msg = {"type": "reset", "row": r, "col": c}
                        broadcast(reset_msg)
                        print("board reset, fill_pct: ", fill_pct)
                        print("is board none: ", board[r][c] is None)

        except Exception as e:
            print(f"Server error with player {player_id}: {e}")
            break

    conn.close()

def end_game():
    # Count tiles for each player
    tile_count = {}
    for r in range(8):
        for c in range(8):
            owner = board[r][c]
            if owner is not None:
                tile_count[owner] = tile_count.get(owner, 0) + 1

    # Determine winner
    winner = max(tile_count, key=tile_count.get) if tile_count else None
    result_msg = {"type": "victory", "winner": winner, "tile_count": tile_count}
    broadcast(result_msg)

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

    # Start a 60-second timer, then end the game
    threading.Timer(60.0, end_game).start()

    # Keep the server running here
    while True:
        time.sleep(1)  # Simple idle loop to keep main thread alive

if __name__ == '__main__':
    main()

