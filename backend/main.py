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
_subscribers: set[asyncio.Queue[tuple[str, dict]]] = set()


# game_info = {
#     "board": [
#         [-1, -1, 9, -1, -1],
#         [40, -1, -1, -1, 20],
#         [-1, 40, -1, 16, -1],
#         [40, -1, -1, -1, 24],
#         [-1, -1, 20, -1, -1],
#     ],
#     "numbers_available": [1, 2, 3, 4, 5]
# }

def _publish(event: str, data: dict) -> None:
    for queue in list(_subscribers):
        try:
            queue.put_nowait((event, data))
        except Exception:
            # Best-effort; drop if enqueue fails
            pass

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


@app.post("/place")
async def place_number(request: Request):
    request_body = await request.json()
    row = request_body["row"]
    col = request_body["col"]
    number = request_body["number"]

    global current_level_obj
    if current_level_obj is None:
        return {"success": False, "message": "No level loaded"}

    game_info = current_level_obj["game_info"]
    board = game_info["board"]
    numbers_available = game_info.get("numbers_available", [])

    # Validate position
    if row < 0 or row >= len(board) or col < 0 or col >= len(board[0]):
        return {"success": False, "message": "Invalid position"}

    current_value = board[row][col]
    
    # Allow placing in white squares (value -1) or replacing previously placed numbers
    # Original numbers (not in numbers_available) cannot be replaced
    if current_value != -1 and current_value not in numbers_available:
        return {"success": False, "message": "Cannot place number in this square"}

    # Place the number
    board[row][col] = number

    # Publish update
    _publish("level", current_level_obj)
    return {"success": True, "message": "Number placed successfully"}


@app.post("/erase")
async def erase_number(request: Request):
    request_body = await request.json()
    row = request_body["row"]
    col = request_body["col"]

    global current_level_obj
    if current_level_obj is None:
        return {"success": False, "message": "No level loaded"}

    game_info = current_level_obj["game_info"]
    board = game_info["board"]
    numbers_available = game_info.get("numbers_available", [])

    # Validate position
    if row < 0 or row >= len(board) or col < 0 or col >= len(board[0]):
        return {"success": False, "message": "Invalid position"}

    current_value = board[row][col]
    
    # Can only erase placed numbers (values in numbers_available) or already empty cells
    # Cannot erase original numbers (not in numbers_available and not -1)
    if current_value != -1 and current_value not in numbers_available:
        return {"success": False, "message": "Cannot erase original numbers"}

    # Erase the cell (set to -1)
    board[row][col] = -1

    # Publish update
    _publish("level", current_level_obj)
    return {"success": True, "message": "Cell erased successfully"}


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


@app.post("/verify/{level_id}")
async def verify(level_id: str, request: Request):
    pass