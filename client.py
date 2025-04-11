import pygame
import socket
import pickle
import threading

WIDTH, HEIGHT = 800, 800
ROWS, COLS = 8, 8
SQUARE_SIZE = WIDTH // COLS

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
PLAYER_COLORS = [
    (255, 0, 0),   # Player 0 = Red
    (0, 0, 255),   # Player 1 = Blue
    (0, 200, 0)    # Player 2 = Green
]

HOST = '127.0.0.1'  # or server IP
PORT = 5555

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Deny and Conquer (Real-Time, Partial Scribbles)")
clock = pygame.time.Clock()

# We'll keep a separate surface for partial scribbles so they're not overwritten each frame.
scribble_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
scribble_surface.fill((0,0,0,0))  # fully transparent

# Networking
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((HOST, PORT))

board = None  # 2D array [8][8], storing None or a player ID
player_id = None

# For scribbling logic
scribbling = False
scribble_cells = []  # store (tile-local-x, tile-local-y) for coverage
start_tile = (None, None)

# Helper: get tile coordinates under mouse

def get_tile_under_mouse():
    mx, my = pygame.mouse.get_pos()
    c = mx // SQUARE_SIZE
    r = my // SQUARE_SIZE
    if 0 <= r < ROWS and 0 <= c < COLS:
        return (r, c)
    return (None, None)

# Draw the main board

def draw_board():
    for r in range(ROWS):
        for c in range(COLS):
            owner = board[r][c]
            color = PLAYER_COLORS[owner] if owner is not None else WHITE
            x = c * SQUARE_SIZE
            y = r * SQUARE_SIZE
            pygame.draw.rect(screen, color, (x, y, SQUARE_SIZE, SQUARE_SIZE))
            pygame.draw.rect(screen, BLACK, (x, y, SQUARE_SIZE, SQUARE_SIZE), 1)

# Thread to listen for server updates

def network_listener():
    global board
    while True:
        try:
            data = client_socket.recv(4096)
            if not data:
                break
            msg = pickle.loads(data)
            if msg["type"] == "init":
                # Should only happen once, but safe to ignore.
                pass
            elif msg["type"] == "update":
                board = msg["board"]
        except:
            break


def main():
    global board, player_id, scribbling, start_tile

    # Receive init data from server
    init_data = client_socket.recv(4096)
    init_msg = pickle.loads(init_data)
    if init_msg["type"] == "init":
        player_id = init_msg["player_id"]
        board = init_msg["board"]

    # Start listener thread
    listener_thread = threading.Thread(target=network_listener, daemon=True)
    listener_thread.start()

    running = True
    while running:
        clock.tick(60)

        # 1) Draw the board
        screen.fill(WHITE)
        draw_board()

        # 2) Blit partial scribbles
        screen.blit(scribble_surface, (0, 0))

        # 3) Update the display
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Begin scribbling if tile is unclaimed
                r, c = get_tile_under_mouse()
                if r is not None and board[r][c] is None:
                    scribbling = True
                    scribble_cells.clear()
                    start_tile = (r, c)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if scribbling:
                    tile_r, tile_c = start_tile
                    # Calculate fill percentage
                    tile_area = SQUARE_SIZE * SQUARE_SIZE
                    fill_ratio = len(scribble_cells) / tile_area
                    if fill_ratio >= 0.5:
                        # Send claim to server
                        msg = {
                            "type": "scribble",
                            "row": tile_r,
                            "col": tile_c,
                            "fill": fill_ratio
                        }
                        client_socket.send(pickle.dumps(msg))

                    # Clear scribble surface
                    scribble_surface.fill((0,0,0,0))
                    scribble_cells.clear()

                scribbling = False
                start_tile = (None, None)

            elif event.type == pygame.MOUSEMOTION:
                # If we're scribbling, draw circles to scribble_surface
                if scribbling:
                    mx, my = pygame.mouse.get_pos()
                    tile_r, tile_c = start_tile
                    # Only draw if still inside that tile
                    # Because if we move out of the tile, it's not valid scribble
                    if tile_r is not None and tile_c is not None:
                        tile_x = tile_c * SQUARE_SIZE
                        tile_y = tile_r * SQUARE_SIZE

                        local_x = mx - tile_x
                        local_y = my - tile_y

                        # Check if within tile bounds
                        if 0 <= local_x < SQUARE_SIZE and 0 <= local_y < SQUARE_SIZE:
                            pygame.draw.circle(scribble_surface, PLAYER_COLORS[player_id], (mx, my), 3)
                            scribble_cells.append((local_x, local_y))

    pygame.quit()
    client_socket.close()

if __name__ == '__main__':
    main()

