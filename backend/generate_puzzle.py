#!/usr/bin/env python3
"""
Twinominoes Puzzle Generator

Generates solvable puzzle configurations with 5 difficulty levels.
"""

import argparse
import json
import random
import sys
import time
from typing import Dict, List

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
    dark_cells = set()  # Track all dark piece cells separately
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
                                # Check if this dark piece would be orthogonally adjacent to any existing dark piece
                                # Dark pieces can only touch corner-to-corner, not edge-to-edge
                                orth_adjacent_to_dark = False
                                for cand_cell in s:
                                    for orth_nbr in orthogonal_neighbors(cand_cell):
                                        if orth_nbr in dark_cells:
                                            orth_adjacent_to_dark = True
                                            break
                                    if orth_adjacent_to_dark:
                                        break
                                if orth_adjacent_to_dark:
                                    continue
                                # Valid placement - no orthogonal adjacency to other dark pieces
                                darks.append(cand)
                                occupied |= s
                                dark_cells |= s
                                placed = True
                                break
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

# Default configuration for 5 difficulty levels
DEFAULT_CONFIG = {
    1: {
        "grid_w": 5,
        "grid_h": 5,
        "min_pieces": 2,
        "max_pieces": 3,
        "min_star_density": 0.15,
        "max_star_density": 0.25,
        "max_tries": 100,
        "max_attempts": 100
    },
    2: {
        "grid_w": 6,
        "grid_h": 6,
        "min_pieces": 3,
        "max_pieces": 4,
        "min_star_density": 0.20,
        "max_star_density": 0.30,
        "max_tries": 150,
        "max_attempts": 150
    },
    3: {
        "grid_w": 7,
        "grid_h": 7,
        "min_pieces": 4,
        "max_pieces": 5,
        "min_star_density": 0.25,
        "max_star_density": 0.35,
        "max_tries": 200,
        "max_attempts": 200
    },
    4: {
        "grid_w": 8,
        "grid_h": 8,
        "min_pieces": 5,
        "max_pieces": 6,
        "min_star_density": 0.30,
        "max_star_density": 0.40,
        "max_tries": 300,
        "max_attempts": 250
    },
    5: {
        "grid_w": 9,
        "grid_h": 9,
        "min_pieces": 6,
        "max_pieces": 8,
        "min_star_density": 0.35,
        "max_star_density": 0.45,
        "max_tries": 400,
        "max_attempts": 300
    }
}

def sample_params(difficulty_config: Dict) -> Dict:
    """Sample parameters from the ranges specified in difficulty config"""
    return {
        'grid_w': difficulty_config['grid_w'],
        'grid_h': difficulty_config['grid_h'],
        'pieces_range': (
            difficulty_config['min_pieces'],
            difficulty_config['max_pieces']
        ),
        'star_density': random.uniform(
            difficulty_config['min_star_density'],
            difficulty_config['max_star_density']
        ),
        'max_tries': difficulty_config['max_tries'],
        'max_attempts': difficulty_config['max_attempts']
    }

def generate_puzzles(count=1, grid_w=6, grid_h=6, pieces_range=(3,4), star_density=0.25, max_tries=200, max_attempts=200, verbose=False):
    """Generate puzzles with given parameters"""
    puzzles=[]; tries=0
    shape_pool = list(PRESET_SHAPES.keys())
    while len(puzzles)<count and tries<max_tries:
        tries+=1
        num = random.randint(*pieces_range)
        lit = place_solution(grid_w, grid_h, num, shape_pool, max_attempts=max_attempts)
        if not lit: continue
        dark = place_darks_for_solution(lit, grid_w, grid_h)
        if not dark: continue
        all_lit = list(set().union(*lit))
        k = max(1, int(len(all_lit)*star_density))
        stars = set(random.sample(all_lit, k))
        sol_count, sols = solve_puzzle_fast(grid_w, grid_h, dark, stars, max_solutions=2, max_nodes=20000)
        if sol_count == 1:
            puzzles.append({'grid_w':grid_w,'grid_h':grid_h,'lit_pieces':lit,'dark_pieces':dark,'stars':list(stars)})
            if verbose:
                print(f"Generated puzzle #{len(puzzles)} after {tries} tries (pieces={num}, stars={len(stars)})")
    return puzzles

def generate_puzzle(params: Dict, problem_id: int, verbose: bool = False) -> Dict:
    """Generate a single puzzle configuration with sampled parameters"""
    if verbose:
        print(f"\nGenerating puzzle {problem_id}:")
        print(f"  Grid: {params['grid_w']}x{params['grid_h']}, Pieces: {params['pieces_range']}, "
              f"Star density: {params['star_density']:.2f}")
        print(f"  Max tries: {params['max_tries']}, Max attempts: {params['max_attempts']}")
    
    puzzles = generate_puzzles(
        count=1,
        grid_w=params['grid_w'],
        grid_h=params['grid_h'],
        pieces_range=params['pieces_range'],
        star_density=params['star_density'],
        max_tries=params['max_tries'],
        max_attempts=params['max_attempts'],
        verbose=verbose
    )
    
    if not puzzles:
        return None
    
    puzzle = puzzles[0]
    return {
        "grid_w": puzzle['grid_w'],
        "grid_h": puzzle['grid_h'],
        "dark_pieces": [list(piece) for piece in puzzle['dark_pieces']],
        "lit_pieces": [list(piece) for piece in puzzle['lit_pieces']],
        "stars": [list(star) for star in puzzle['stars']],
        "problem_id": problem_id
    }

def generate_difficulty_set(
    difficulty_config: Dict,
    n_puzzles: int,
    start_id: int,
    difficulty_level: int,
    verbose: bool = False
) -> List[Dict]:
    """Generate a set of puzzles for a specific difficulty"""
    puzzles = []
    
    print(f"\nGenerating {n_puzzles} puzzles for difficulty {difficulty_level}...")
    
    for i in range(n_puzzles):
        problem_id = start_id + i
        
        # Sample parameters from ranges for this puzzle
        params = sample_params(difficulty_config)
        
        puzzle = generate_puzzle(
            params=params,
            problem_id=problem_id,
            verbose=verbose
        )
        
        if puzzle:
            puzzles.append(puzzle)
        else:
            if verbose:
                print(f"  Warning: Failed to generate puzzle {problem_id}")
    
    return puzzles

def convert_to_legacy_format(puzzles: List[Dict]) -> Dict[str, Dict]:
    """Convert list of puzzles to legacy dict format (problem_id: puzzle_dict)"""
    legacy = {}
    for puzzle in puzzles:
        problem_id = str(puzzle['problem_id'])
        legacy[problem_id] = puzzle
    return legacy

def main():
    parser = argparse.ArgumentParser(
        description="Generate Twinominoes puzzles in JSON format",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument("--difficulties", type=str, required=True,
                        help="Dictionary mapping difficulty to number of puzzles. Must be quoted! (e.g., '{1:5, 2:5, 3:5}')")
    parser.add_argument("--config-file", type=str, default=None,
                        help="Path to custom JSON config file with difficulty configurations")
    parser.add_argument("--start-id", type=int, default=1,
                        help="Starting problem ID")
    parser.add_argument("--output-file", type=str, default="puzzles.json",
                        help="Output JSON file path")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducibility")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print detailed generation progress")
    
    args = parser.parse_args()
    
    # Parse difficulties dictionary
    try:
        difficulties_dict = eval(args.difficulties)
        if not isinstance(difficulties_dict, dict):
            raise ValueError("--difficulties must be a dictionary")
    except Exception as e:
        print(f"Error parsing --difficulties: {e}")
        print("Example: --difficulties '{1:5, 2:5, 3:5, 4:5, 5:5}'")
        print("Note: Make sure to wrap the dictionary in quotes!")
        return
    
    # Load config
    if args.config_file:
        with open(args.config_file, 'r') as f:
            config = json.load(f)
        # Convert string keys to int if necessary
        config = {int(k): v for k, v in config.items()}
    else:
        config = DEFAULT_CONFIG
    
    # Set random seed
    if args.seed is not None:
        final_seed = args.seed
    else:
        final_seed = random.randint(0, 2**32 - 1)
    
    random.seed(final_seed)
    print(f"Random seed: {final_seed}")
    
    # Generate puzzles
    all_puzzles = []
    current_id = args.start_id
    
    for difficulty_level, n_puzzles in sorted(difficulties_dict.items()):
        if n_puzzles > 0:
            if difficulty_level not in config:
                print(f"Warning: Difficulty {difficulty_level} not found in config, skipping")
                continue
            
            puzzles = generate_difficulty_set(
                difficulty_config=config[difficulty_level],
                n_puzzles=n_puzzles,
                start_id=current_id,
                difficulty_level=difficulty_level,
                verbose=args.verbose
            )
            
            all_puzzles.extend(puzzles)
            current_id += len(puzzles)
    
    if not all_puzzles:
        print("Error: No puzzles were generated")
        return
    
    # Convert to legacy JSON format
    output_data = convert_to_legacy_format(all_puzzles)
    
    # Save to file
    with open(args.output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n✓ Successfully generated {len(all_puzzles)} total puzzles")
    print(f"✓ Saved to: {args.output_file}")
    print(f"✓ Problem IDs: {args.start_id} to {current_id - 1}")
    
    # Print breakdown by difficulty
    print("\nBreakdown by difficulty:")
    for difficulty_level, n_puzzles in sorted(difficulties_dict.items()):
        if n_puzzles > 0:
            print(f"  Difficulty {difficulty_level}: {n_puzzles} puzzles")

if __name__ == "__main__":
    main()

