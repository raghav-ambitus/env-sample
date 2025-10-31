import asyncio
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

    global current_level_obj
    level_data = {"game_info": game_info, "level_id": level_id}
    current_level_obj = level_data

    _publish("level", level_data)
    return {"success": True, "message": "Level fetched successfully"}


@app.post("/verify/{level_id}")
async def verify(level_id: str, request: Request):
    pass