import pygame
import sys

# Constants
WIDTH, HEIGHT = 800, 800
ROWS, COLS = 8, 8
SQUARE_SIZE = WIDTH // COLS

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
PLAYER_COLORS = [(255, 0, 0), (0, 0, 255)]  # Red, Blue

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Deny and Conquer")
clock = pygame.time.Clock()

# Grid to store ownership and surface
grid = [[{"owner": None, "surface": pygame.Surface((SQUARE_SIZE, SQUARE_SIZE)), "drawn": 0} for _ in range(COLS)] for _ in range(ROWS)]

for row in grid:
    for cell in row:
        cell["surface"].fill(WHITE)

def draw_board():
    for i in range(ROWS):
        for j in range(COLS):
            screen.blit(grid[i][j]["surface"], (j * SQUARE_SIZE, i * SQUARE_SIZE))
            pygame.draw.rect(screen, BLACK, (j * SQUARE_SIZE, i * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE), 1)

def count_colored_pixels(surface, player_color):
    arr = pygame.surfarray.pixels3d(surface)
    count = ((arr == player_color).all(axis=2)).sum()
    return count

def get_square_under_mouse():
    mx, my = pygame.mouse.get_pos()
    col, row = mx // SQUARE_SIZE, my // SQUARE_SIZE
    if row < ROWS and col < COLS:
        return row, col
    return None, None

current_player = 0
scribbling = False
row, col = None, None
running = True

while running:
    clock.tick(60)
    screen.fill(WHITE)
    draw_board()
    pygame.display.flip()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            r, c = get_square_under_mouse()
            if r is not None and grid[r][c]["owner"] is None:
                scribbling = True
                row, col = r, c

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and scribbling:
            if row is not None and col is not None:
                surface = grid[row][col]["surface"]
                player_color = PLAYER_COLORS[current_player]
                count = count_colored_pixels(surface, player_color)
                if count >= (SQUARE_SIZE * SQUARE_SIZE) // 2:
                    grid[row][col]["owner"] = current_player
                else:
                    surface.fill(WHITE)  # reset if failed
                current_player = (current_player + 1) % len(PLAYER_COLORS)
            scribbling = False
            row, col = None, None

    if scribbling and row is not None and col is not None:
        mx, my = pygame.mouse.get_pos()
        lx, ly = mx - col * SQUARE_SIZE, my - row * SQUARE_SIZE
        if 0 <= lx < SQUARE_SIZE and 0 <= ly < SQUARE_SIZE:
            pygame.draw.circle(grid[row][col]["surface"], PLAYER_COLORS[current_player], (lx, ly), 3)

pygame.quit()
sys.exit()

