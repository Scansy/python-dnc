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
    global board, scribbling
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
                # Clear both local and network scribbles to immediately show the claim
                network_scribble_surface.fill((0,0,0,0))
                local_scribble_surface.fill((0,0,0,0))
                scribble_cells.clear()

            # 3) partial draws from other players
            elif msg["type"] == "draw":
                other_color = PLAYER_COLORS[msg["player_id"]]
                mx, my = msg["mouse_pos"]
                # draw on network_scribble_surface
                pygame.draw.circle(network_scribble_surface, other_color, (mx, my), 3)

            # 4) reset a tile
            elif msg["type"] == "reset":
                r, c = msg["row"], msg["col"]
                # If we were scribbling on this tile, stop
                if scribbling and start_tile == (r, c):
                    scribbling = False
                    start_tile = (None, None)
                
                # Clear both local and network scribbles for this tile
                tile_rect = pygame.Rect(c * SQUARE_SIZE, r * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE)
                local_scribble_surface.fill((0,0,0,0), tile_rect)
                network_scribble_surface.fill((0,0,0,0), tile_rect)
                scribble_cells.clear()
                
                # Update board state
                board[r][c] = None

            # 5) Add victory message handling
            elif msg["type"] == "victory":
                winner = msg["winner"]
                tile_count = msg["tile_count"]
                
                # Create victory screen
                screen.fill((0, 0, 0))
                font = pygame.font.SysFont(None, 64)
                
                if winner is not None:
                    color = PLAYER_COLORS[winner]
                    text = font.render(f"Player {winner} Wins!", True, color)
                else:
                    text = font.render("Game Over - Tie!", True, WHITE)
                    
                screen.blit(text, (WIDTH//2 - text.get_width()//2, HEIGHT//3))
                
                # Show score
                y_pos = HEIGHT//2
                for player, score in tile_count.items():
                    score_text = font.render(f"Player {player}: {score} tiles", True, PLAYER_COLORS[player])
                    screen.blit(score_text, (WIDTH//2 - score_text.get_width()//2, y_pos))
                    y_pos += 60
                
                pygame.display.flip()
                
                # Wait for 5 seconds then quit
                pygame.time.wait(5000)
                global running
                running = False

        except Exception as e:
            print("Network listener error:", e)
            break

def main():
    global board, player_id, scribbling, start_tile, running
    running = True

    # 1) Receive init data
    init_data = client_socket.recv(4096)
    init_msg = pickle.loads(init_data)
    if init_msg["type"] == "init":
        player_id = init_msg["player_id"]
        board = init_msg["board"]

    # 2) Start listener thread
    threading.Thread(target=network_listener, daemon=True).start()

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
                if r is not None and board[r][c] is None:
                    scribbling = True
                    scribble_cells.clear()
                    start_tile = (r, c)
                    
                    # Clear any previous scribbles on this tile
                    tile_rect = pygame.Rect(c * SQUARE_SIZE, r * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE)
                    local_scribble_surface.fill((0,0,0,0), tile_rect)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if scribbling:
                    tile_r, tile_c = start_tile
                    # Calculate fill ratio
                    tile_area = SQUARE_SIZE * SQUARE_SIZE
                    fill_ratio = (len(scribble_cells) / tile_area) * 10
                    
                    # Always send scribble message to server
                    claim_msg = {
                        "type": "scribble",
                        "row": tile_r,
                        "col": tile_c,
                        "fill": fill_ratio
                    }
                    client_socket.send(pickle.dumps(claim_msg))
                    
                    # Don't clear scribbles yet - wait for server confirmation
                    # This helps players understand the server is processing their claim
                    # The server will send either "update" or "reset" which will clear scribbles
                
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

