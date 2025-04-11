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

is_being_claimed = []

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

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((HOST_IP, PORT))

def get_tile_under_mouse():
    mx, my = pygame.mouse.get_pos()
    c = mx // SQUARE_SIZE
    r = my // SQUARE_SIZE
    if 0 <= r < ROWS and 0 <= c < COLS:
        return r, c
    return None, None

def is_tile_being_claimed(r, c, exclude_own=False):
    # Check if any points in is_being_claimed are within this tile
    tile_x = c * SQUARE_SIZE
    tile_y = r * SQUARE_SIZE
    
    for point in is_being_claimed:
        point_r = point[1] // SQUARE_SIZE
        point_c = point[0] // SQUARE_SIZE
        
        # If excluding own tile and this is the tile we're working on, skip it
        if exclude_own and (r, c) == start_tile:
            continue
            
        # If this point is in the specified tile, it's being claimed
        if point_r == r and point_c == c:
            return True
            
    return False

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

            # 1) init message (only once)
            if msg["type"] == "init":
                pass

            # 2) update board when tile is claimed
            elif msg["type"] == "update":
                board = msg["board"]
                # Clear network scribbles
                network_scribble_surface.fill((0,0,0,0))
                
                # Clear is_being_claimed for the updated tiles
                # Since they're now owned and not being claimed anymore
                is_being_claimed = [p for p in is_being_claimed if
                                   board[p[1] // SQUARE_SIZE][p[0] // SQUARE_SIZE] is None]

            # 3) partial draws from other players
            elif msg["type"] == "draw":
                other_player = msg["player_id"]
                if other_player != player_id:  # Only process draws from other players
                    mx, my = msg["mouse_pos"]
                    r, c = msg["row"], msg["col"]
                    
                    # draw on network_scribble_surface
                    other_color = PLAYER_COLORS[other_player]
                    pygame.draw.circle(network_scribble_surface, other_color, (mx, my), 3)
                    
                    # Add to is_being_claimed
                    is_being_claimed.append((mx, my))

            # 4) reset a tile
            elif msg["type"] == "reset":
                r, c = msg["row"], msg["col"]
                board[r][c] = None
                
                # Clear the network scribbles for this specific tile
                tile_rect = pygame.Rect(c * SQUARE_SIZE, r * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE)
                network_scribble_surface.fill((0,0,0,0), tile_rect)
                
                # Remove all points in this tile from is_being_claimed
                tile_x = c * SQUARE_SIZE
                tile_y = r * SQUARE_SIZE
                is_being_claimed = [p for p in is_being_claimed if
                                   not (tile_y <= p[1] < tile_y + SQUARE_SIZE and
                                        tile_x <= p[0] < tile_x + SQUARE_SIZE)]

        except Exception as e:
            print("Network listener error:", e)
            break

def main():
    global board, player_id, scribbling, start_tile

    # 1) Receive init data
    init_data = client_socket.recv(4096)
    init_msg = pickle.loads(init_data)
    if init_msg["type"] == "init":
        player_id = init_msg["player_id"]
        board = init_msg["board"]

    # 2) Start listener thread
    threading.Thread(target=network_listener, daemon=True).start()

    running = True
    while running:
        clock.tick(60)

        # Draw board
        screen.fill(WHITE)
        draw_board()

        # Blit network scribbles first
        screen.blit(network_scribble_surface, (0,0))
        # Then your local scribbles on top
        screen.blit(local_scribble_surface, (0,0))

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                r, c = get_tile_under_mouse()
                
                # Check if this tile is allowed to be claimed
                # A tile can be claimed if:
                # 1. It's not already owned by a player
                # 2. No other player is currently trying to claim it
                # 3. OR this is the tile the player is already working on
                allowed_to_claim = (
                    r is not None and 
                    board[r][c] is None and 
                    not is_tile_being_claimed(r, c, exclude_own=True)
                )
                
                if allowed_to_claim:
                    scribbling = True
                    scribble_cells.clear()
                    start_tile = (r, c)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if scribbling:
                    tile_r, tile_c = start_tile
                    # Calculate fill ratio
                    tile_area = SQUARE_SIZE * SQUARE_SIZE
                    fill_ratio = (len(scribble_cells) / tile_area) * 10
                    
                    # Always send scribble message to server, regardless of fill ratio
                    claim_msg = {
                        "type": "scribble",
                        "row": tile_r,
                        "col": tile_c,
                        "fill": fill_ratio
                    }
                    client_socket.send(pickle.dumps(claim_msg))

                    # Clear local scribbles
                    local_scribble_surface.fill((0,0,0,0))
                    scribble_cells.clear()

                scribbling = False
                start_tile = (None, None)

            elif event.type == pygame.MOUSEMOTION:
                if scribbling:
                    mx, my = pygame.mouse.get_pos()
                    tile_r, tile_c = start_tile
                    if tile_r is not None and tile_c is not None:
                        tile_x = tile_c * SQUARE_SIZE
                        tile_y = tile_r * SQUARE_SIZE
                        local_x = mx - tile_x
                        local_y = my - tile_y

                        if 0 <= local_x < SQUARE_SIZE and 0 <= local_y < SQUARE_SIZE:
                            # Draw locally
                            pygame.draw.circle(local_scribble_surface, PLAYER_COLORS[player_id], (mx, my), 3)
                            scribble_cells.append((local_x, local_y))

                            # Also broadcast partial draw so others see
                            draw_msg = {
                                "type": "draw",
                                "player_id": player_id,
                                "mouse_pos": (mx, my),
                                "row": tile_r,
                                "col": tile_c
                            }
                            # Could limit frequency here if you want
                            client_socket.send(pickle.dumps(draw_msg))

    pygame.quit()
    client_socket.close()

if __name__ == '__main__':
    main()

