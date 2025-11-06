#!/usr/bin/env python3
"""
CLI script to control the Twinominoes game via API calls.
All commands update the backend state, which broadcasts to the frontend via SSE.
"""

import requests
import sys

BASE_URL = "http://localhost:8000"

def generate_puzzle(grid_w=6, grid_h=6, pieces_range=(3, 4), star_density=0.3):
    """Generate a new random puzzle"""
    print(f"Generating puzzle {grid_w}x{grid_h}...")
    response = requests.post(f"{BASE_URL}/generate", json={
        "grid_w": grid_w,
        "grid_h": grid_h,
        "pieces_range": list(pieces_range),
        "star_density": star_density
    })
    result = response.json()
    if result["success"]:
        print("✓ Puzzle generated successfully!")
        print(f"  Grid: {result['puzzle']['grid_w']}x{result['puzzle']['grid_h']}")
        print(f"  Dark pieces: {len(result['puzzle']['dark_pieces'])}")
        print(f"  Stars: {len(result['puzzle']['stars'])}")
    else:
        print(f"✗ Error: {result['message']}")
    return result

def load_puzzle(puzzle_data, level_id="custom"):
    """Load a custom puzzle"""
    print(f"Loading puzzle '{level_id}'...")
    response = requests.post(f"{BASE_URL}/load", json={
        "puzzle": puzzle_data,
        "level_id": level_id
    })
    result = response.json()
    if result["success"]:
        print("✓ Puzzle loaded successfully!")
    else:
        print(f"✗ Error: {result['message']}")
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
    
    python game_control.py generate [grid_w] [grid_h]
        Generate a new puzzle
        Example: python game_control.py generate 6 6
    
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
    - Click cells to select them (shown with orange border)
    - When selected cells form a valid shape that:
      1. Matches a dark piece's shape (any rotation/reflection)
      2. Borders that dark piece by an edge
      → The piece is automatically placed!
    - Click a placed piece to erase it
    - Click a selected cell again to deselect it

Examples:
    # Generate a new puzzle
    python game_control.py generate
    
    # Click cells to build a domino shape
    python game_control.py click 0 1  # Select first cell
    python game_control.py click 1 1  # Select second cell → auto-places if valid!
    
    # Click cells to build an L-tromino
    python game_control.py click 2 0
    python game_control.py click 2 1
    python game_control.py click 3 1  # Third cell → auto-places if valid!
    
    # Erase a piece by clicking on it
    python game_control.py click 0 1  # If there's a piece here, it's erased
    
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
        if command == "generate":
            grid_w = int(sys.argv[2]) if len(sys.argv) > 2 else 6
            grid_h = int(sys.argv[3]) if len(sys.argv) > 3 else 6
            generate_puzzle(grid_w, grid_h)
        
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
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

