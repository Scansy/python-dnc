import pygame
import socket
import pickle
import threading
from server import HOST_IP, PORT

WIDTH, HEIGHT = 800, 800
ROWS, COLS = 8, 8
SQUARE_SIZE = WIDTH // COLS

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
PLAYER_COLORS = [
    (255, 0, 0),   # P0 = Red
    (0, 0, 255),   # P1 = Blue
    (0, 200, 0)    # P2 = Green
]

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Deny & Conquer - Real-Time Multiplayer")
clock = pygame.time.Clock()

# Surfaces
board = None  # 8×8 array with None or player_id
player_id = None

# For partial scribbles:
# - local_scribble_surface: your own scribbles
# - network_scribble_surface: scribbles from other players
local_scribble_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
local_scribble_surface.fill((0,0,0,0))
network_scribble_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
network_scribble_surface.fill((0,0,0,0))

scribbling = False
scribble_cells = []
start_tile = (None, None)

# Track which tiles other players are currently scribbling on
is_being_claimed = set()

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((HOST_IP, PORT))

def get_tile_under_mouse():
    mx, my = pygame.mouse.get_pos()
    c = mx // SQUARE_SIZE
    r = my // SQUARE_SIZE
    if 0 <= r < ROWS and 0 <= c < COLS:
        return r, c
    return None, None

def draw_board():
    for r in range(ROWS):
        for c in range(COLS):
            owner = board[r][c]
            color = PLAYER_COLORS[owner] if owner is not None else WHITE
            x = c * SQUARE_SIZE
            y = r * SQUARE_SIZE
            pygame.draw.rect(screen, color, (x, y, SQUARE_SIZE, SQUARE_SIZE))
            pygame.draw.rect(screen, BLACK, (x, y, SQUARE_SIZE, SQUARE_SIZE), 1)

def network_listener():
    global board, is_being_claimed
    while True:
        try:
            data = client_socket.recv(4096)
            if not data:
                break
            msg = pickle.loads(data)

            # 1) init message
            if msg["type"] == "init":
                pass

            # 2) update board when tile is definitively claimed
            elif msg["type"] == "update":
                board = msg["board"]
                # The tile is now owned, remove it from is_being_claimed
                # (We don't know exactly which tile(s) changed, 
                # so re-check the entire set)
                still_being_claimed = set()
                for (r_claim, c_claim) in is_being_claimed:
                    # If now owned, remove it from being_claimed
                    if board[r_claim][c_claim] is None:
                        still_being_claimed.add((r_claim, c_claim))
                is_being_claimed = still_being_claimed

                # Clear network scribbles for a cleaner look
                network_scribble_surface.fill((0, 0, 0, 0))

            # 3) partial draws from other players
            elif msg["type"] == "draw":
                other_color = PLAYER_COLORS[msg["player_id"]]
                mx, my = msg["mouse_pos"]
                r, c = msg["row"], msg["col"]

                # Mark that tile as being claimed (if nobody owns it yet)
                if board[r][c] is None:
                    is_being_claimed.add((r, c))

                # Draw on network_scribble_surface
                pygame.draw.circle(network_scribble_surface, other_color, (mx, my), 3)

            # 4) reset a tile
            elif msg["type"] == "reset":
                r, c = msg["row"], msg["col"]
                board[r][c] = None

                # Remove reset tile from is_being_claimed
                if (r, c) in is_being_claimed:
                    print(f"Tile ({r},{c}) reset, removing from is_being_claimed")
                    is_being_claimed.remove((r, c))

                # Clear the network scribbles for this specific tile
                tile_x = c * SQUARE_SIZE
                tile_y = r * SQUARE_SIZE
                tile_rect = pygame.Rect(tile_x, tile_y, SQUARE_SIZE, SQUARE_SIZE)
                network_scribble_surface.fill((0, 0, 0, 0), tile_rect)

        except Exception as e:
            print("Network listener error:", e)
            break

def main():
    global board, player_id, scribbling, start_tile

    # Receive init data from server
    init_data = client_socket.recv(4096)
    init_msg = pickle.loads(init_data)
    if init_msg["type"] == "init":
        player_id = init_msg["player_id"]
        board = init_msg["board"]

    # Start the listener thread
    threading.Thread(target=network_listener, daemon=True).start()

    running = True
    while running:
        clock.tick(60)
        screen.fill(WHITE)
        draw_board()

        # Blit network scribbles first
        screen.blit(network_scribble_surface, (0, 0))
        # Blit local scribbles on top
        screen.blit(local_scribble_surface, (0, 0))

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                r, c = get_tile_under_mouse()
                # 1) Make sure tile is unowned
                # 2) Make sure no one else is claiming it
                #    (but do allow if it's the tile we already started)
                if r is not None and board[r][c] is None:
                    if (r, c) not in is_being_claimed:
                        scribbling = True
                        scribble_cells.clear()
                        start_tile = (r, c)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if scribbling:
                    tile_r, tile_c = start_tile
                    # Calculate fill ratio
                    tile_area = SQUARE_SIZE * SQUARE_SIZE
                    fill_ratio = (len(scribble_cells) / tile_area) * 10

                    # Send scribble message to server
                    claim_msg = {
                        "type": "scribble",
                        "row": tile_r,
                        "col": tile_c,
                        "fill": fill_ratio
                    }
                    client_socket.send(pickle.dumps(claim_msg))

                    local_scribble_surface.fill((0, 0, 0, 0))
                    scribble_cells.clear()
                    
                    # Make sure that current tile is not in is_being_claimed in client-side too
                    if (tile_r, tile_c) in is_being_claimed:
                        is_being_claimed.remove((tile_r, tile_c))

                scribbling = False
                start_tile = (None, None)

            elif event.type == pygame.MOUSEMOTION:
                if scribbling:
                    mx, my = pygame.mouse.get_pos()
                    tile_r, tile_c = start_tile
                    if tile_r is not None and tile_c is not None:
                        is_tile_being_claimed = (tile_r, tile_c) in is_being_claimed
                        is_tile_unclaimed = board[tile_r][tile_c] is None
                        is_not_our_claiming_tile = (tile_r, tile_c) != start_tile

                        if is_tile_being_claimed and is_not_our_claiming_tile and is_tile_unclaimed:
                            continue #stop scribbling

                        tile_x = tile_c * SQUARE_SIZE
                        tile_y = tile_r * SQUARE_SIZE
                        local_x = mx - tile_x
                        local_y = my - tile_y

                        if 0 <= local_x < SQUARE_SIZE and 0 <= local_y < SQUARE_SIZE:
                            # Draw locally
                            pygame.draw.circle(local_scribble_surface, PLAYER_COLORS[player_id], (mx, my), 3)
                            scribble_cells.append((local_x, local_y))

                            # Broadcast partial draw
                            draw_msg = {
                                "type": "draw",
                                "player_id": player_id,
                                "mouse_pos": (mx, my),
                                "row": tile_r,
                                "col": tile_c
                            }
                            client_socket.send(pickle.dumps(draw_msg))

    pygame.quit()
    client_socket.close()

if __name__ == '__main__':
    main()

