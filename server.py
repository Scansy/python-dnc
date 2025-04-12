import socket
import threading
import pickle
import time

HOST_IP = '192.75.240.161'
PORT = 5555
MAX_PLAYERS = 3
FILL_THRESHOLD = 0.5

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
                r, c = msg["row"], msg["col"]
                broadcast(msg)

            # 2) Final scribble claims
            elif msg["type"] == "scribble":
                r, c, fill_pct = msg["row"], msg["col"], msg["fill"]
                
                # Get the lock before checking or modifying the tile
                with board_locks[r][c]:
                    # Check tile state INSIDE the lock
                    is_tile_empty = board[r][c] is None
                    is_above_fill_threshold = fill_pct >= FILL_THRESHOLD
                    
                    if is_tile_empty and is_above_fill_threshold:
                        # Claim the tile
                        board[r][c] = player_id
                        update_msg = {"type": "update", "board": board}
                        broadcast(update_msg)
                        print(f"Player {player_id} claimed tile ({r},{c}) with fill {fill_pct:.2f}")
                    else:
                        # Only reset if the tile is empty (don't allow overwriting claimed tiles)
                        if is_tile_empty:
                            reset_msg = {"type": "reset", "row": r, "col": c}
                            broadcast(reset_msg)
                            print(f"Tile ({r},{c}) reset, fill {fill_pct:.2f} below threshold")
                        else:
                            # Tile is already claimed
                            print(f"Tile ({r},{c}) already claimed by player {board[r][c]}")

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
    print(f"Server listening on {HOST_IP}:{PORT}")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((HOST_IP, PORT))
        s.listen()

        while player_count < MAX_PLAYERS:
            conn, addr = s.accept()
            print(f"Player {player_count} connected from {addr}")
            clients.append(conn)
            threading.Thread(target=handle_client, args=(conn, player_count), daemon=True).start()
            player_count += 1

        print("Server is now full. Running game...")

        # Start a 60-second timer, then end the game
        game_timer = threading.Timer(60.0, end_game)
        game_timer.start()

        # Keep the server running here
        while True:
            time.sleep(1)  # Simple idle loop to keep main thread alive
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        # Cleanup
        print("Cleaning up connections...")
        for client in clients:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except:
                pass
            client.close()
        try:
            s.shutdown(socket.SHUT_RDWR)
        except:
            pass
        s.close()
        print("Server shutdown complete.")

if __name__ == '__main__':
    main()

