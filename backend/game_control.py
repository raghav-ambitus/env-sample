#!/usr/bin/env python3
"""
CLI script to control the Twinominoes game via API calls.
All commands update the backend state, which broadcasts to the frontend via SSE.
"""

import json
import requests
import sys
import os

BASE_URL = "http://localhost:8000"
DEFAULT_PUZZLES_FILE = "puzzles.json"

def seed_puzzle_from_file(json_path, problem_id):
    """Seed the game with a puzzle from a JSON file"""
    try:
        with open(json_path, 'r') as f:
            puzzles = json.load(f)
    except FileNotFoundError:
        print(f"✗ Error: Puzzle file '{json_path}' not found")
        return {"status": "error", "message": f"File not found: {json_path}"}
    except json.JSONDecodeError as e:
        print(f"✗ Error: Invalid JSON in puzzle file: {e}")
        return {"status": "error", "message": f"Invalid JSON: {e}"}
    except Exception as e:
        print(f"✗ Failed to load puzzle JSON file: {e}")
        return {"status": "error", "message": str(e)}
    
    # Convert problem_id to string to match JSON keys
    problem_id_str = str(problem_id)
    
    if problem_id_str not in puzzles:
        print(f"✗ Error: Puzzle with problem_id '{problem_id}' not found in file")
        print(f"  Available problem IDs: {', '.join(sorted(puzzles.keys(), key=int))}")
        return {"status": "error", "message": f"Puzzle {problem_id} not found"}
    
    puzzle_data = puzzles[problem_id_str]
    
    # Extract level_id from puzzle if available, otherwise use problem_id
    level_id = puzzle_data.get("level_id", problem_id_str)
    
    print(f"Seeding puzzle '{problem_id}' (level_id: {level_id}) from file '{json_path}'...")
    print(f"  Grid: {puzzle_data['grid_w']}x{puzzle_data['grid_h']}")
    print(f"  Dark pieces: {len(puzzle_data['dark_pieces'])}")
    print(f"  Stars: {len(puzzle_data['stars'])}")
    
    # Prepare seed request
    seed_request = {
        "grid_w": puzzle_data["grid_w"],
        "grid_h": puzzle_data["grid_h"],
        "dark_pieces": puzzle_data["dark_pieces"],
        "stars": puzzle_data["stars"],
        "level_id": level_id
    }
    
    # Add lit_pieces if available
    if "lit_pieces" in puzzle_data:
        seed_request["lit_pieces"] = puzzle_data["lit_pieces"]
    
    response = requests.post(f"{BASE_URL}/seed", json=seed_request)
    
    try:
        result = response.json()
    except Exception as e:
        print(f"✗ Error parsing response JSON: {e}")
        return {"status": "error", "message": str(e)}
    
    if result.get("status") == "success":
        print("✓ Puzzle seeded successfully!")
    else:
        print(f"✗ Error: {result.get('message', 'Unknown error')}")
    
    return result

def click_cell(x, y):
    """
    Click a cell to select/deselect it.
    Automatically places piece if valid shape is formed.
    
    Args:
        x: X coordinate (column)
        y: Y coordinate (row)
    """
    print(f"Clicking cell ({x}, {y})...")
    response = requests.post(f"{BASE_URL}/click", json={
        "x": x,
        "y": y
    })
    result = response.json()
    if result["success"]:
        print(f"✓ {result['message']}")
        if result.get("placed"):
            print("  🎉 Piece automatically placed!")
    else:
        print(f"✗ Error: {result['message']}")
    return result

def reset_board():
    """Reset the board to original state"""
    print("Resetting board...")
    response = requests.post(f"{BASE_URL}/reset")
    result = response.json()
    if result["success"]:
        print("✓ Board reset!")
    else:
        print(f"✗ Error: {result['message']}")
    return result

def get_state():
    """Get the current game state"""
    print("Fetching current game state...")
    response = requests.get(f"{BASE_URL}/state")
    result = response.json()
    
    if not result.get("seeded"):
        print("✗ No puzzle is currently seeded")
        return result
    
    print("✓ Current game state:")
    summary = result.get("summary", {})
    print(f"  Level ID: {result.get('level_id', 'unknown')}")
    
    grid_size = summary.get("grid_size", {})
    print(f"  Grid: {grid_size.get('width', 0)}x{grid_size.get('height', 0)}")
    
    dark_pieces = summary.get("dark_pieces", {})
    print(f"  Dark pieces: {dark_pieces.get('count', 0)} ({dark_pieces.get('total_cells', 0)} cells)")
    
    stars = summary.get("stars", {})
    print(f"  Stars: {stars.get('covered', 0)}/{stars.get('total', 0)} covered")
    
    user_pieces = summary.get("user_pieces", {})
    print(f"  User pieces: {user_pieces.get('count', 0)} ({user_pieces.get('total_cells', 0)} cells)")
    
    selected = summary.get("selected_cells", {})
    if selected.get("count", 0) > 0:
        print(f"  Selected cells: {selected.get('count', 0)}")
    
    return result

def verify_solution():
    """Verify if the current solution is correct"""
    print("Verifying solution...")
    response = requests.post(f"{BASE_URL}/verify")
    result = response.json()
    print(f"\n{result['message']}\n")
    return result

def show_help():
    """Show available commands"""
    help_text = """
Twinominoes Game Control CLI
============================

Available commands:
    
    python game_control.py seed [problem_id] [puzzles_file]
        Seed the game with a puzzle from a JSON file
        Example: python game_control.py seed 1
        Example: python game_control.py seed 5 puzzles.json
    
    python game_control.py state
        Get the current game state
    
    python game_control.py click x y
        Click a cell to select/deselect it
        Automatically places piece if valid shape is formed
        Example: python game_control.py click 0 1
    
    python game_control.py reset
        Reset board to original state
    
    python game_control.py verify
        Check if solution is correct
    
View the game at: http://localhost:3000

How it works:
    - Seed a puzzle from puzzles.json file
    - Click cells to select them (shown with orange border)
    - When selected cells form a valid shape that:
      1. Matches a dark piece's shape (any rotation/reflection)
      2. Borders that dark piece by an edge
      → The piece is automatically placed!
    - Click a placed piece to erase it
    - Click a selected cell again to deselect it

Examples:
    # Seed puzzle with problem_id 1 from puzzles.json
    python game_control.py seed 1
    
    # Seed puzzle with problem_id 5 from custom file
    python game_control.py seed 5 my_puzzles.json
    
    # Check current state
    python game_control.py state
    
    # Click cells to build a domino shape
    python game_control.py click 0 1  # Select first cell
    python game_control.py click 1 1  # Select second cell → auto-places if valid!
    
    # Check solution
    python game_control.py verify
    
    # Reset the board
    python game_control.py reset
"""
    print(help_text)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_help()
        sys.exit(0)
    
    command = sys.argv[1].lower()
    
    try:
        if command == "seed":
            if len(sys.argv) < 3:
                print("Error: seed command requires a problem_id")
                print("Example: python game_control.py seed 1")
                print("Example: python game_control.py seed 5 puzzles.json")
                sys.exit(1)
            
            problem_id = int(sys.argv[2])
            puzzles_file = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_PUZZLES_FILE
            
            # Check if file exists
            if not os.path.exists(puzzles_file):
                print(f"✗ Error: Puzzle file '{puzzles_file}' not found")
                print(f"  Looking for: {os.path.abspath(puzzles_file)}")
                sys.exit(1)
            
            seed_puzzle_from_file(puzzles_file, problem_id)
        
        elif command == "state":
            get_state()
        
        elif command == "click":
            if len(sys.argv) < 4:
                print("Error: click command requires x and y coordinates")
                print("Example: python game_control.py click 0 1")
                sys.exit(1)
            x = int(sys.argv[2])
            y = int(sys.argv[3])
            click_cell(x, y)
        
        elif command == "reset":
            reset_board()
        
        elif command == "verify":
            verify_solution()
        
        elif command == "help":
            show_help()
        
        else:
            print(f"Unknown command: {command}")
            print("Run 'python game_control.py help' for usage")
            sys.exit(1)
    
    except requests.exceptions.ConnectionError:
        print("✗ Error: Could not connect to backend server")
        print("Make sure the backend is running on http://localhost:8000")
        sys.exit(1)
    except ValueError as e:
        print(f"✗ Error: Invalid argument - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

