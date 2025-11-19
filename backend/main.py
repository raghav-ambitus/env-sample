import asyncio
import copy
import json
from collections.abc import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

app = FastAPI(title="Cross Product API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

current_level_obj = None
original_level_obj = None
pentonimo_letters = ["F", "I", "L", "P", "N", "T", "U", "V", "W", "X", "Y", "Z"]
_subscribers: set[asyncio.Queue[tuple[str, dict]]] = set()

EMPTY_TILE = "-"
SELECTED_TILE = "*"
BLOCKED_TILE = "|"

def _publish(event: str, data: dict) -> None:
    for queue in list(_subscribers):
        try:
            queue.put_nowait((event, data))
        except Exception:
            # Best-effort; drop if enqueue fails
            pass


def _is_selection_valid(board: list[list[str]], coords: list[tuple[int, int]]) -> bool:
    if len(coords) != 5:
        return False

    coords_set = set(coords)
    if len(coords_set) != 5:
        return False

    rows = len(board)
    cols = len(board[0]) if rows else 0

    for row, col in coords_set:
        if row < 0 or row >= rows or col < 0 or col >= cols:
            return False
        if board[row][col] != SELECTED_TILE:
            return False

    stack: list[tuple[int, int]] = [next(iter(coords_set))]
    visited: set[tuple[int, int]] = set()
    directions = ((1, 0), (-1, 0), (0, 1), (0, -1))

    while stack:
        r, c = stack.pop()
        if (r, c) in visited:
            continue
        visited.add((r, c))
        for dr, dc in directions:
            neighbor = (r + dr, c + dc)
            if neighbor in coords_set and neighbor not in visited:
                stack.append(neighbor)

    return len(visited) == len(coords_set)


def _transformations(coords: list[tuple[int, int]]) -> set[tuple[tuple[int, int], ...]]:
    """Generate all rotations/reflections of a coordinate set."""
    results: set[tuple[tuple[int, int], ...]] = set()

    for rotate_amount in range(4):  # 0°, 90°, 180°, 270°
        for mirror in (False, True):
            transformed: list[tuple[int, int]] = []
            for row, col in coords:
                r, c = row, col

                for _ in range(rotate_amount):
                    r, c = -c, r

                if mirror:
                    c = -c

                transformed.append((r, c))

            min_row = min(r for r, _ in transformed)
            min_col = min(c for _, c in transformed)
            normalized = tuple(sorted((r - min_row, c - min_col) for r, c in transformed))
            results.add(normalized)

    return results


def _canonical(coords: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    """Return the canonical (lexicographically smallest) representation."""
    return min(_transformations(coords))


def _clear_pentomino_cluster(board: list[list[str]], start_row: int, start_col: int) -> bool:
    """Remove the contiguous cluster of the letter at (start_row, start_col)."""
    rows = len(board)
    cols = len(board[0]) if rows else 0
    if start_row < 0 or start_row >= rows or start_col < 0 or start_col >= cols:
        return False

    letter = board[start_row][start_col]
    if letter not in pentonimo_letters:
        return False

    stack = [(start_row, start_col)]
    visited: set[tuple[int, int]] = set()
    directions = ((1, 0), (-1, 0), (0, 1), (0, -1))

    cleared_positions: list[tuple[int, int]] = []

    while stack:
        r, c = stack.pop()
        if (r, c) in visited:
            continue
        if board[r][c] != letter:
            continue
        visited.add((r, c))
        board[r][c] = EMPTY_TILE
        cleared_positions.append((r, c))

        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in visited:
                if board[nr][nc] == letter:
                    stack.append((nr, nc))

    if len(visited) == 5:
        return True

    # Restore the tiles if we didn't clear exactly one pentomino
    for r, c in cleared_positions:
        board[r][c] = letter
    return False


_PENTOMINO_BASE_SHAPES = {
    "F": [(0, 1), (1, 0), (1, 1), (1, 2), (2, 2)],
    "I": [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)],
    "L": [(0, 0), (1, 0), (2, 0), (3, 0), (3, 1)],
    "N": [(0, 0), (1, 0), (1, 1), (2, 1), (3, 1)],
    "P": [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0)],
    "T": [(0, 0), (1, 0), (2, 0), (1, 1), (1, 2)],
    "U": [(0, 0), (0, 1), (1, 1), (2, 0), (2, 1)],
    "V": [(0, 0), (0, 1), (0, 2), (1, 2), (2, 2)],
    "W": [(0, 0), (0, 1), (1, 1), (1, 2), (2, 2)],
    "X": [(1, 0), (0, 1), (1, 1), (2, 1), (1, 2)],
    "Y": [(0, 0), (1, 0), (2, 0), (3, 0), (2, 1)],
    "Z": [(0, 0), (0, 1), (1, 1), (2, 1), (2, 2)],
}

# Build dictionary mapping all transformations of each pentomino to its letter
_CANONICAL_TO_LETTER: dict[tuple[tuple[int, int], ...], str] = {}
for letter, shape in _PENTOMINO_BASE_SHAPES.items():
    # Add all transformations of this shape to the dictionary
    for transform in _transformations(shape):
        _CANONICAL_TO_LETTER[transform] = letter

@app.get("/events")
async def sse_stream() -> StreamingResponse:
    queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()
    _subscribers.add(queue)
    # Immediately replay the current grid to the new subscriber, if available
    try:
        if current_level_obj is not None:
            queue.put_nowait(("level", current_level_obj))
    except Exception:
        pass

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # Initial comment to open the stream
            yield ": connected\n\n"
            while True:
                event, data = await queue.get()
                yield f"event: {event}\ndata: {json.dumps(data)}\n\n"
        finally:
            _subscribers.discard(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "API is running successfully"}

@app.post("/levels/{level_id}")
async def get_level(level_id: str, request: Request):
    request_body = await request.json()
    game_info = request_body["game_info"]

    global current_level_obj, original_level_obj
    # Deep copy the board for original state
    original_game_info = copy.deepcopy(game_info)
    level_data = {"game_info": game_info, "level_id": level_id}
    original_level_data = {"game_info": original_game_info, "level_id": level_id}
    
    current_level_obj = level_data
    original_level_obj = original_level_data

    _publish("level", level_data)
    return {"success": True, "message": "Level fetched successfully"}


@app.post("/select")
async def select_tile(request: Request):
    request_body = await request.json()
    row = request_body["row"]
    col = request_body["col"]

    global current_level_obj
    if current_level_obj is None:
        return {"success": False, "message": "No level loaded"}

    game_info = current_level_obj["game_info"]
    board = game_info["board"]

    # Validate position
    if row < 0 or row >= len(board) or col < 0 or col >= len(board[0]):
        return {"success": False, "message": "Invalid position"}

    current_value = board[row][col]

    # Selecting an empty tile
    if current_value == EMPTY_TILE:
        # Count currently selected tiles on the board
        selected_count = sum(1 for row_data in board for cell in row_data if cell == SELECTED_TILE)
        if selected_count >= 5:
            return {
                "success": False,
                "message": "Cannot select more than 5 tiles at once",
            }
        board[row][col] = SELECTED_TILE
        _publish("level", current_level_obj)
        return {"success": True, "message": "Tile selected"}

    # Unselecting an already selected tile
    if current_value == SELECTED_TILE:
        board[row][col] = EMPTY_TILE
        _publish("level", current_level_obj)
        return {"success": True, "message": "Tile unselected"}

    # Blocked tiles cannot be selected
    if current_value == BLOCKED_TILE:
        return {"success": False, "message": "Cannot select blocked tiles"}

    # Locked tiles (pentomino letters) are no-ops for selection
    if current_value in pentonimo_letters:
        return {"success": True, "message": "Locked tile unchanged"}

    # Unexpected value
    return {
        "success": False,
        "message": f"Unsupported tile value '{current_value}' at ({row}, {col})",
    }


@app.post("/lock")
async def lock_pentomino():
    global current_level_obj
    if current_level_obj is None:
        return {"success": False, "message": "No level loaded"}

    game_info = current_level_obj["game_info"]
    board = game_info["board"]

    # Build selection from board state
    current_selection = []
    for row_idx, row in enumerate(board):
        for col_idx, cell in enumerate(row):
            if cell == SELECTED_TILE:
                # Ensure coordinates are integers
                current_selection.append((int(row_idx), int(col_idx)))

    if not _is_selection_valid(board, current_selection):
        return {
            "success": False,
            "message": "Exactly 5 connected tiles must be selected to lock",
        }

    canonical_form = _canonical(current_selection)
    letter = _CANONICAL_TO_LETTER.get(canonical_form)
    if letter is None:
        # Debug: log what we got
        print(f"DEBUG: Selection: {current_selection}")
        print(f"DEBUG: Canonical: {canonical_form}")
        print(f"DEBUG: In dict: {canonical_form in _CANONICAL_TO_LETTER}")
        print(f"DEBUG: Dict size: {len(_CANONICAL_TO_LETTER)}")
        # Check if it's a type issue
        if isinstance(canonical_form, tuple):
            print(f"DEBUG: Canonical is tuple, checking if any similar keys exist...")
            for key in list(_CANONICAL_TO_LETTER.keys())[:3]:
                print(f"DEBUG: Sample key: {key}, type: {type(key)}")
        return {"success": False, "message": "Selected tiles do not form a valid pentomino"}

    for row, col in current_selection:
        board[row][col] = letter

    _publish("level", current_level_obj)
    return {"success": True, "message": f"Locked pentomino {letter}"}


@app.post("/unlock")
async def unlock_pentomino(request: Request):
    request_body = await request.json()
    row = request_body["row"]
    col = request_body["col"]

    global current_level_obj
    if current_level_obj is None:
        return {"success": False, "message": "No level loaded"}

    game_info = current_level_obj["game_info"]
    board = game_info["board"]

    # Validate position
    if row < 0 or row >= len(board) or col < 0 or col >= len(board[0]):
        return {"success": False, "message": "Invalid position"}

    cell_value = board[row][col]
    if cell_value == EMPTY_TILE or cell_value == "*":
        return {"success": True, "message": "Tile unchanged"}

    if cell_value not in pentonimo_letters:
        return {"success": False, "message": "Invalid tile state"}

    if not _clear_pentomino_cluster(board, row, col):
        return {"success": False, "message": "Failed to unlock pentomino"}

    # Publish update
    _publish("level", current_level_obj)
    return {"success": True, "message": "Pentomino unlocked"}

@app.post("/reset")
async def reset_board():
    global current_level_obj, original_level_obj
    
    if original_level_obj is None:
        return {"success": False, "message": "No original level to reset to"}

    # Deep copy the original board
    reset_game_info = copy.deepcopy(original_level_obj["game_info"])
    current_level_obj = {
        "game_info": reset_game_info,
        "level_id": original_level_obj["level_id"]
    }

    # Publish update
    _publish("level", current_level_obj)
    return {"success": True, "message": "Board reset successfully"}


@app.get("/verify/")
async def verify(request: Request):
    global current_level_obj
    if current_level_obj is None:
        return {"success": False, "message": "No level loaded"}
    
    game_info = current_level_obj["game_info"]
    board = game_info["board"]

    for row in board:
        for val in row:
            if val == EMPTY_TILE or val == SELECTED_TILE:
                return {"success": False, "message": "Board contains unplaced cells"}

    return {"success": True, "message": "Level verified successfully"}