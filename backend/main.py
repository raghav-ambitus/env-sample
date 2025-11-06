import asyncio
import copy
import json
import random
import time
from collections import defaultdict
from collections.abc import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

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

# ===== Twinominoes Puzzle Generator Code =====

def normalize(cells):
    xs = [x for x,y in cells]
    ys = [y for x,y in cells]
    minx, miny = min(xs), min(ys)
    return tuple(sorted(((x-minx, y-miny) for x,y in cells)))

def rotations_and_reflections(shape):
    cells = list(shape)
    variants = set()
    for flip_x in (False, True):
        for flip_y in (False, True):
            for rot in range(4):
                pts = []
                for x,y in cells:
                    nx, ny = x, y
                    if flip_x: nx = -nx
                    if flip_y: ny = -ny
                    rx, ry = nx, ny
                    for _ in range(rot):
                        rx, ry = -ry, rx
                    pts.append((rx, ry))
                variants.add(normalize(pts))
    return variants

PRESET_SHAPES = {
    'monomino': normalize([(0,0)]),
    'domino': normalize([(0,0),(1,0)]),
    'tromino_I': normalize([(0,0),(1,0),(2,0)]),
    'tromino_L': normalize([(0,0),(0,1),(1,0)]),
    'tetromino_O': normalize([(0,0),(1,0),(0,1),(1,1)]),
}

SHAPE_VARIANTS = {name: list(rotations_and_reflections(shape)) for name, shape in PRESET_SHAPES.items()}

def inside(grid_w, grid_h, cells):
    return all(0 <= x < grid_w and 0 <= y < grid_h for x,y in cells)

def translate(shape, tx, ty):
    return tuple(sorted(((x+tx, y+ty) for x,y in shape)))

def orthogonal_neighbors(cell):
    x,y = cell
    return [(x-1,y),(x+1,y),(x,y-1),(x,y+1)]

def corner_neighbors(cell):
    x,y = cell
    return [(x-1,y-1),(x-1,y+1),(x+1,y-1),(x+1,y+1)]

def place_solution(grid_w, grid_h, num_pieces, shape_pool, max_attempts=1000):
    for _ in range(max_attempts):
        lit_pieces = []
        occupied = set()
        # pick first
        first_name = random.choice(shape_pool)
        first_var = random.choice(SHAPE_VARIANTS[first_name])
        max_tx = grid_w - max(x for x,y in first_var) - 1
        max_ty = grid_h - max(y for x,y in first_var) - 1
        if max_tx < 0 or max_ty < 0: continue
        tx = random.randint(0, max_tx); ty = random.randint(0, max_ty)
        first = translate(first_var, tx, ty)
        lit_pieces.append(first); occupied |= set(first)
        ok = True
        for _ in range(num_pieces-1):
            placed = False
            variants = []
            for name in shape_pool:
                variants.extend(SHAPE_VARIANTS[name])
            random.shuffle(variants)
            for var in variants:
                max_tx = grid_w - max(x for x,y in var) - 1
                max_ty = grid_h - max(y for x,y in var) - 1
                if max_tx < 0 or max_ty < 0: continue
                # try few random translations to limit runtime
                trials = 12
                for _ in range(trials):
                    tx = random.randint(0, max_tx); ty = random.randint(0, max_ty)
                    cand = translate(var, tx, ty)
                    s = set(cand)
                    if s & occupied: continue
                    # no orthogonal adjacency
                    bad = False
                    for cell in s:
                        for nbr in orthogonal_neighbors(cell):
                            if nbr in occupied:
                                bad = True; break
                        if bad: break
                    if bad: continue
                    # must corner-touch existing cluster
                    corner_touch = False
                    for cell in s:
                        for nbr in corner_neighbors(cell):
                            if nbr in occupied:
                                corner_touch = True; break
                        if corner_touch: break
                    if not corner_touch: continue
                    lit_pieces.append(cand); occupied |= s; placed = True; break
                if placed: break
            if not placed: ok = False; break
        if ok and len(lit_pieces)==num_pieces:
            return lit_pieces
    return None

def place_darks_for_solution(lit_pieces, grid_w, grid_h):
    darks = []
    occupied = set().union(*lit_pieces)
    for lit in lit_pieces:
        # Dark piece should have THE SAME SHAPE as the lit piece (not just size)
        # Normalize the lit piece shape
        lit_normalized = normalize(lit)
        
        # Find which preset shape this matches
        matching_shapes = []
        for name, preset_shape in PRESET_SHAPES.items():
            for variant in SHAPE_VARIANTS[name]:
                if normalize(variant) == lit_normalized:
                    matching_shapes.append(name)
                    break
        
        # If no exact match, use any shape with same size
        if not matching_shapes:
            size = len(lit)
            matching_shapes = [n for n, s in PRESET_SHAPES.items() if len(s) == size]
        
        random.shuffle(matching_shapes)
        placed = False
        
        for name in matching_shapes:
            variants = SHAPE_VARIANTS[name][:]
            random.shuffle(variants)
            for var in variants:
                max_tx = grid_w - max(x for x,y in var) - 1
                max_ty = grid_h - max(y for x,y in var) - 1
                if max_tx < 0 or max_ty < 0: continue
                # try attaching near each lit cell
                for cell in lit:
                    for nbr in orthogonal_neighbors(cell):
                        # try to place so one of var's cells is at nbr
                        for tx in range(max_tx+1):
                            for ty in range(max_ty+1):
                                cand = translate(var, tx, ty)
                                if nbr not in cand: continue
                                s = set(cand)
                                if s & occupied: continue
                                darks.append(cand); occupied |= s; placed = True; break
                            if placed: break
                        if placed: break
                    if placed: break
                if placed: break
            if placed: break
        if not placed:
            return None
    return darks

def enumerate_candidates_for_dark_fast(dark, shape_name, grid_w, grid_h, dark_cells_union):
    cands = []
    for var in SHAPE_VARIANTS[shape_name]:
        max_tx = grid_w - max(x for x,y in var) - 1
        max_ty = grid_h - max(y for x,y in var) - 1
        if max_tx < 0 or max_ty < 0: continue
        for tx in range(max_tx+1):
            for ty in range(max_ty+1):
                p = translate(var, tx, ty)
                if set(p) & dark_cells_union:
                    continue
                touch=False
                for cell in p:
                    for nbr in orthogonal_neighbors(cell):
                        if nbr in dark:
                            touch=True; break
                    if touch: break
                if not touch: continue
                s = frozenset(p)
                orth_adj = set()
                for cell in p:
                    for nbr in orthogonal_neighbors(cell):
                        orth_adj.add(nbr)
                cands.append({'cells': s, 'orth_adj': frozenset(orth_adj)})
    return cands

def solve_puzzle_fast(grid_w, grid_h, dark_pieces, stars, max_solutions=2, max_nodes=200000):
    n = len(dark_pieces)
    dark_union = set().union(*dark_pieces)
    names_per_piece = [[name for name,shape in PRESET_SHAPES.items() if len(shape)==len(d)] for d in dark_pieces]
    all_candidates = []
    for i,d in enumerate(dark_pieces):
        cands = []
        for name in names_per_piece[i]:
            cands.extend(enumerate_candidates_for_dark_fast(d, name, grid_w, grid_h, dark_union))
        uniq = {}
        for c in cands:
            uniq[c['cells']] = c
        cands = list(uniq.values())
        if not cands:
            return 0, []
        all_candidates.append(cands)
    order = sorted(range(n), key=lambda i: len(all_candidates[i]))
    placed = [None]*n
    used_cells = set()
    used_orth_adj = set()
    solutions = []
    nodes = 0

    def backtrack(idx):
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes:
            return
        if len(solutions) >= max_solutions:
            return
        if idx == n:
            covered = set().union(*(p['cells'] for p in placed))
            if not stars.issubset(covered): return
            sets = [set(p['cells']) for p in placed]
            comps = corner_connected_components(sets)
            if len(comps) != 1: return
            solutions.append([tuple(sorted(p['cells'])) for p in placed])
            return
        i = order[idx]
        for c in all_candidates[i]:
            if c['cells'] & used_cells: continue
            if any(cell in used_orth_adj for cell in c['cells']):
                continue
            placed[i] = c
            prev_used = set(used_cells)
            prev_orth = set(used_orth_adj)
            used_cells.update(c['cells'])
            used_orth_adj.update(c['orth_adj'])
            backtrack(idx+1)
            used_cells.clear(); used_cells.update(prev_used)
            used_orth_adj.clear(); used_orth_adj.update(prev_orth)
            placed[i] = None
            if len(solutions) >= max_solutions: return
            if nodes > max_nodes: return

    backtrack(0)
    return len(solutions), solutions

def corner_connected_components(placed_sets):
    n = len(placed_sets)
    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i+1,n):
            connected = False
            for a in placed_sets[i]:
                for nbr in corner_neighbors(a):
                    if nbr in placed_sets[j]:
                        connected=True; break
                if connected: break
            if connected:
                adj[i].append(j); adj[j].append(i)
    visited=[False]*n; comps=[]
    for i in range(n):
        if visited[i]: continue
        q=[i]; comp=set([i]); visited[i]=True
        while q:
            u=q.pop()
            for v in adj[u]:
                if not visited[v]:
                    visited[v]=True; q.append(v); comp.add(v)
        comps.append(comp)
    return comps

def generate_puzzles(count=1, grid_w=6, grid_h=6, pieces_range=(3,4), star_density=0.25, max_tries=200):
    puzzles=[]; tries=0
    shape_pool = list(PRESET_SHAPES.keys())
    while len(puzzles)<count and tries<max_tries:
        tries+=1
        num = random.randint(*pieces_range)
        lit = place_solution(grid_w, grid_h, num, shape_pool, max_attempts=200)
        if not lit: continue
        dark = place_darks_for_solution(lit, grid_w, grid_h)
        if not dark: continue
        all_lit = list(set().union(*lit))
        k = max(1, int(len(all_lit)*star_density))
        stars = set(random.sample(all_lit, k))
        sol_count, sols = solve_puzzle_fast(grid_w, grid_h, dark, stars, max_solutions=2, max_nodes=20000)
        if sol_count == 1:
            puzzles.append({'grid_w':grid_w,'grid_h':grid_h,'lit_pieces':lit,'dark_pieces':dark,'stars':list(stars)})
            print(f"Generated puzzle #{len(puzzles)} after {tries} tries (pieces={num})")
    return puzzles

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

@app.post("/generate")
async def generate_puzzle(request: Request):
    """Generate a new Twinominoes puzzle"""
    try:
        params = await request.json()
        grid_w = params.get("grid_w", 6)
        grid_h = params.get("grid_h", 6)
        pieces_range = tuple(params.get("pieces_range", [3, 4]))
        star_density = params.get("star_density", 0.3)
        
        random.seed(int(time.time()))
        puzzles = generate_puzzles(
            count=1, 
            grid_w=grid_w, 
            grid_h=grid_h, 
            pieces_range=pieces_range, 
            star_density=star_density, 
            max_tries=300
        )
        
        if not puzzles:
            return {"success": False, "message": "Failed to generate puzzle"}
        
        puzzle = puzzles[0]
        # Convert tuples to lists for JSON serialization
        puzzle_data = {
            "grid_w": puzzle["grid_w"],
            "grid_h": puzzle["grid_h"],
            "dark_pieces": [list(piece) for piece in puzzle["dark_pieces"]],
            "lit_pieces": [list(piece) for piece in puzzle["lit_pieces"]],
            "stars": list(puzzle["stars"])
        }
        
        global current_level_obj, original_level_obj
        level_data = {"puzzle": puzzle_data, "level_id": "generated", "user_pieces": [], "selected_cells": []}
        current_level_obj = copy.deepcopy(level_data)
        original_level_obj = copy.deepcopy(level_data)
        
        _publish("level", level_data)
        return {"success": True, "message": "Puzzle generated successfully", "puzzle": puzzle_data}
        
    except Exception as e:
        print(f"Error generating puzzle: {e}")
        return {"success": False, "message": str(e)}

@app.post("/load")
async def load_puzzle(request: Request):
    """Load a pre-defined puzzle"""
    try:
        request_body = await request.json()
        puzzle_data = request_body["puzzle"]
        
        global current_level_obj, original_level_obj
        level_data = {
            "puzzle": puzzle_data, 
            "level_id": request_body.get("level_id", "custom"),
            "user_pieces": [],  # Track user-placed pieces
            "selected_cells": []  # Track currently selected cells for click interface
        }
        current_level_obj = copy.deepcopy(level_data)
        original_level_obj = copy.deepcopy(level_data)
        
        _publish("level", level_data)
        return {"success": True, "message": "Puzzle loaded successfully"}
    except Exception as e:
        print(f"Error loading puzzle: {e}")
        return {"success": False, "message": str(e)}

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

@app.post("/place")
async def place_piece(request: Request):
    """Place a user piece on the board"""
    global current_level_obj
    if current_level_obj is None:
        return {"success": False, "message": "No level loaded"}
    
    try:
        request_body = await request.json()
        cells = request_body["cells"]  # List of [x, y] coordinates
        label = request_body["label"]  # Piece label (e.g., "A", "B")
        
        # Remove any existing pieces that overlap with these cells
        user_pieces = current_level_obj.get("user_pieces", [])
        cell_set = set(tuple(c) for c in cells)
        
        filtered_pieces = [
            piece for piece in user_pieces
            if not any(tuple(c) in cell_set for c in piece["cells"])
        ]
        
        # Add the new piece
        filtered_pieces.append({"cells": cells, "label": label})
        current_level_obj["user_pieces"] = filtered_pieces
        
        # Broadcast update
        _publish("level", current_level_obj)
        return {"success": True, "message": "Piece placed successfully"}
    except Exception as e:
        print(f"Error placing piece: {e}")
        return {"success": False, "message": str(e)}

@app.post("/erase")
async def erase_piece(request: Request):
    """Erase a user piece at the given position"""
    global current_level_obj
    if current_level_obj is None:
        return {"success": False, "message": "No level loaded"}
    
    try:
        request_body = await request.json()
        x = request_body["x"]
        y = request_body["y"]
        
        # Remove any piece that contains this cell
        user_pieces = current_level_obj.get("user_pieces", [])
        filtered_pieces = [
            piece for piece in user_pieces
            if not any(c[0] == x and c[1] == y for c in piece["cells"])
        ]
        
        current_level_obj["user_pieces"] = filtered_pieces
        
        # Broadcast update
        _publish("level", current_level_obj)
        return {"success": True, "message": "Piece erased successfully"}
    except Exception as e:
        print(f"Error erasing piece: {e}")
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
        return {"success": False, "message": "No level loaded"}
    
    try:
        puzzle = current_level_obj["puzzle"]
        user_pieces = current_level_obj.get("user_pieces", [])
        selected_cells = current_level_obj.get("selected_cells", [])
        
        # Check if there are still selected cells (not placed as pieces)
        if selected_cells:
            return {"success": False, "message": "❌ You have unplaced selected cells! Complete or deselect them first."}
        
        if len(user_pieces) == 0:
            return {"success": False, "message": "No pieces placed yet!"}
        
        stars = puzzle["stars"]
        dark_pieces = puzzle["dark_pieces"]
        
        # Check 1: All stars must be covered
        covered_stars = set()
        for piece in user_pieces:
            for cell in piece["cells"]:
                covered_stars.add(tuple(cell))
        
        all_stars_covered = all(tuple(star) in covered_stars for star in stars)
        if not all_stars_covered:
            return {"success": False, "message": "❌ Not all stars (★) are covered!"}
        
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
                                "success": False, 
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
                return {"success": False, "message": "❌ All pieces must be connected by corners!"}
        
        # All checks passed!
        return {"success": True, "message": "✅ Perfect! Your solution is correct! 🎉"}
    except Exception as e:
        print(f"Error verifying solution: {e}")
        return {"success": False, "message": str(e)}