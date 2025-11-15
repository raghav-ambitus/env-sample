import asyncio
import copy
import json
from collections.abc import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="Twinominoes API", version="1.0.0")

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

# Pydantic models for API requests
class PuzzleState(BaseModel):
    grid_w: int
    grid_h: int
    dark_pieces: List[List[List[int]]]  # List of pieces, each piece is List[[x, y]]
    stars: List[List[int]]  # List of [x, y] coordinates
    lit_pieces: Optional[List[List[List[int]]]] = None  # Optional solution pieces
    level_id: Optional[str] = "seeded"  # Optional level identifier

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
    # Immediately replay the current puzzle to the new subscriber, if available
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

@app.post("/seed")
async def seed_game(state: PuzzleState):
    """Initialize the game with a starting puzzle configuration"""
    try:
        global current_level_obj, original_level_obj
        
        # Convert the puzzle state to the expected format
        puzzle_data = {
            "grid_w": state.grid_w,
            "grid_h": state.grid_h,
            "dark_pieces": state.dark_pieces,
            "stars": state.stars,
            "lit_pieces": state.lit_pieces if state.lit_pieces else None
        }
        
        level_data = {
            "puzzle": puzzle_data,
            "level_id": state.level_id,
            "user_pieces": [],
            "selected_cells": []
        }
        
        current_level_obj = copy.deepcopy(level_data)
        original_level_obj = copy.deepcopy(level_data)
        
        # Notify frontend via SSE
        _publish("level", level_data)
        
        return {
            "status": "success",
            "message": "Game seeded successfully",
            "puzzle": puzzle_data,
            "level_id": state.level_id
        }
        
    except Exception as e:
        print(f"Error seeding game: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/state")
async def get_state():
    """Get current game state"""
    global current_level_obj
    
    if current_level_obj is None:
        return {
            "seeded": False,
            "state": None
        }
    
    puzzle = current_level_obj.get("puzzle", {})
    user_pieces = current_level_obj.get("user_pieces", [])
    selected_cells = current_level_obj.get("selected_cells", [])
    
    # Calculate summary statistics
    dark_pieces = puzzle.get("dark_pieces", [])
    stars = puzzle.get("stars", [])
    lit_pieces = puzzle.get("lit_pieces")
    
    # Count covered stars
    covered_stars_set = set(tuple(cell) for piece in user_pieces for cell in piece.get("cells", []))
    stars_set = set(tuple(star) for star in stars)
    covered_stars_count = len(covered_stars_set & stars_set)
    
    return {
        "seeded": True,
        "state": current_level_obj,
        "level_id": current_level_obj.get("level_id", "unknown"),
        "summary": {
            "grid_size": {
                "width": puzzle.get("grid_w", 0),
                "height": puzzle.get("grid_h", 0)
            },
            "dark_pieces": {
                "count": len(dark_pieces),
                "total_cells": sum(len(piece) for piece in dark_pieces)
            },
            "stars": {
                "total": len(stars),
                "covered": covered_stars_count,
                "uncovered": len(stars) - covered_stars_count
            },
            "user_pieces": {
                "count": len(user_pieces),
                "total_cells": sum(len(piece.get("cells", [])) for piece in user_pieces),
                "pieces": [
                    {
                        "label": piece.get("label", ""),
                        "cell_count": len(piece.get("cells", []))
                    }
                    for piece in user_pieces
                ]
            },
            "selected_cells": {
                "count": len(selected_cells),
                "cells": selected_cells
            },
            "solution_available": lit_pieces is not None
        }
    }

def normalize_shape(cells):
    """Normalize a shape to its canonical form"""
    if not cells:
        return []
    xs = [x for x, y in cells]
    ys = [y for x, y in cells]
    min_x, min_y = min(xs), min(ys)
    normalized = sorted([(x - min_x, y - min_y) for x, y in cells])
    return normalized

def shapes_match(cells1, cells2):
    """Check if two shapes match (considering rotations and reflections)"""
    if len(cells1) != len(cells2):
        return False
    
    norm1 = normalize_shape(cells1)
    
    # Try all rotations and reflections
    for flip_x in [False, True]:
        for flip_y in [False, True]:
            for rot in range(4):
                transformed = []
                for x, y in cells2:
                    nx, ny = x, y
                    if flip_x:
                        nx = -nx
                    if flip_y:
                        ny = -ny
                    # Rotate
                    for _ in range(rot):
                        nx, ny = -ny, nx
                    transformed.append((nx, ny))
                
                if normalize_shape(transformed) == norm1:
                    return True
    return False

def is_orthogonally_adjacent(cell1, cell2):
    """Check if two cells are orthogonally adjacent (share an edge)"""
    x1, y1 = cell1
    x2, y2 = cell2
    return (abs(x1 - x2) == 1 and y1 == y2) or (abs(y1 - y2) == 1 and x1 == x2)

def check_shape_match(selected_cells, dark_pieces):
    """
    Check if selected cells form a valid shape that matches a dark piece.
    Returns (match_found, dark_piece_index, label) or (False, None, None)
    """
    if not selected_cells:
        return False, None, None
    
    for dark_idx, dark_piece in enumerate(dark_pieces):
        # Check if selection borders this dark piece
        borders = any(
            any(is_orthogonally_adjacent(sel_cell, dark_cell) 
                for dark_cell in dark_piece)
            for sel_cell in selected_cells
        )
        
        if borders and shapes_match(selected_cells, dark_piece):
            label = chr(65 + dark_idx)  # A, B, C, ...
            return True, dark_idx, label
    
    return False, None, None

@app.post("/click")
async def click_cell(request: Request):
    """
    Click a cell to select/deselect it. Automatically places piece if valid shape is formed.
    Body: {x: number, y: number}
    """
    global current_level_obj
    if current_level_obj is None:
        return {"success": False, "message": "No level loaded"}
    
    try:
        request_body = await request.json()
        x = request_body["x"]
        y = request_body["y"]
        
        selected_cells = current_level_obj.get("selected_cells", [])
        user_pieces = current_level_obj.get("user_pieces", [])
        dark_pieces = current_level_obj["puzzle"]["dark_pieces"]
        # Check if clicking on a dark piece cell - not allowed
        for dark_piece in dark_pieces:
            if (x, y) in dark_piece:
                return {"success": False, "message": "Cannot click on dark piece cells"}
        
        # Check if clicking on an existing user piece - if so, erase it
        piece_to_remove = None
        for piece in user_pieces:
            if [x, y] in piece["cells"]:
                piece_to_remove = piece
                break
        
        if piece_to_remove:
            # Erase the piece
            user_pieces.remove(piece_to_remove)
            current_level_obj["user_pieces"] = user_pieces
            
            # Make the cells of the erased piece become selected, EXCEPT the clicked cell
            remaining_cells = [cell for cell in piece_to_remove["cells"] if cell != [x, y]]
            current_level_obj["selected_cells"] = remaining_cells
            
            _publish("level", current_level_obj)
            return {"success": True, "message": f"Piece '{piece_to_remove['label']}' erased, other cells selected"}
        
        # Toggle selection
        cell = [x, y]
        if cell in selected_cells:
            selected_cells.remove(cell)
        else:
            selected_cells.append(cell)
        
        current_level_obj["selected_cells"] = selected_cells
        
        # Check if selected cells form a valid shape
        if selected_cells:
            match_found, dark_idx, label = check_shape_match(selected_cells, dark_pieces)
            
            if match_found:
                # Valid shape! Place the piece
                # Remove any overlapping pieces
                cell_set = set(tuple(c) for c in selected_cells)
                user_pieces = [
                    piece for piece in user_pieces
                    if not any(tuple(c) in cell_set for c in piece["cells"])
                ]
                
                # Add new piece
                user_pieces.append({"cells": selected_cells[:], "label": label})
                current_level_obj["user_pieces"] = user_pieces
                current_level_obj["selected_cells"] = []  # Clear selection after placing
                
                _publish("level", current_level_obj)
                return {"success": True, "message": f"Piece '{label}' placed!", "placed": True}
        
        # Just update selection
        _publish("level", current_level_obj)
        return {"success": True, "message": "Cell selection updated", "placed": False}
        
    except Exception as e:
        print(f"Error clicking cell: {e}")
        return {"success": False, "message": str(e)}

@app.post("/reset")
async def reset_board():
    """Reset the board to original state"""
    global current_level_obj, original_level_obj
    
    if original_level_obj is None:
        return {"success": False, "message": "No original level to reset to"}
    
    # Deep copy the original puzzle
    current_level_obj = copy.deepcopy(original_level_obj)
    current_level_obj["user_pieces"] = []
    current_level_obj["selected_cells"] = []
    
    # Broadcast update
    _publish("level", current_level_obj)
    return {"success": True, "message": "Board reset successfully"}

@app.post("/verify")
async def verify_solution():
    """Verify if the user's solution is correct"""
    global current_level_obj
    
    if current_level_obj is None:
        return {"complete": False, "message": "No level loaded"}
    
    try:
        puzzle = current_level_obj["puzzle"]
        user_pieces = current_level_obj.get("user_pieces", [])
        selected_cells = current_level_obj.get("selected_cells", [])
        
        # Check if there are still selected cells (not placed as pieces)
        if selected_cells:
            return {"complete": False, "message": "❌ You have unplaced selected cells! Complete or deselect them first."}
        
        if len(user_pieces) == 0:
            return {"complete": False, "message": "No pieces placed yet!"}
        
        stars = puzzle["stars"]
        dark_pieces = puzzle["dark_pieces"]
        
        # Check 1: All stars must be covered
        covered_stars = set()
        for piece in user_pieces:
            for cell in piece["cells"]:
                covered_stars.add(tuple(cell))
        
        all_stars_covered = all(tuple(star) in covered_stars for star in stars)
        if not all_stars_covered:
            return {"complete": False, "message": "❌ Not all stars (★) are covered!"}
        
        # Check 2: No two pieces should be orthogonally adjacent
        def is_orthogonal(c1, c2):
            return (abs(c1[0] - c2[0]) == 1 and c1[1] == c2[1]) or \
                   (abs(c1[1] - c2[1]) == 1 and c1[0] == c2[0])
        
        for i in range(len(user_pieces)):
            for j in range(i + 1, len(user_pieces)):
                piece1 = user_pieces[i]
                piece2 = user_pieces[j]
                
                for cell1 in piece1["cells"]:
                    for cell2 in piece2["cells"]:
                        if is_orthogonal(cell1, cell2):
                            return {
                                "complete": False, 
                                "message": f"❌ Pieces {piece1['label']} and {piece2['label']} are touching by edges!"
                            }
        
        # Check 3: All pieces should be corner-connected
        if len(user_pieces) > 1:
            visited = set([0])
            queue = [0]
            
            while queue:
                current = queue.pop(0)
                
                for i in range(len(user_pieces)):
                    if i in visited:
                        continue
                    
                    current_piece = user_pieces[current]
                    other_piece = user_pieces[i]
                    
                    # Check if corner-connected (diagonal)
                    corner_connected = False
                    for c1 in current_piece["cells"]:
                        for c2 in other_piece["cells"]:
                            dx = abs(c1[0] - c2[0])
                            dy = abs(c1[1] - c2[1])
                            if dx == 1 and dy == 1:
                                corner_connected = True
                                break
                        if corner_connected:
                            break
                    
                    if corner_connected:
                        visited.add(i)
                        queue.append(i)
            
            if len(visited) != len(user_pieces):
                return {"complete": False, "message": "❌ All pieces must be connected by corners!"}
        
        # All checks passed!
        return {"complete": True, "message": "✅ Perfect! Your solution is correct! 🎉"}
    except Exception as e:
        print(f"Error verifying solution: {e}")
        return {"complete": False, "message": str(e)}