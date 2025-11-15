'use client'

import { useEffect, useMemo, useState } from 'react'

type Cell = [number, number] // [x, y]

interface PuzzleData {
  grid_w: number
  grid_h: number
  dark_pieces: Cell[][]
  lit_pieces?: Cell[][] // Optional - only shown in solution view
  stars: Cell[]
}

interface LevelData {
  puzzle: PuzzleData
  level_id: string
  user_pieces: {cells: Cell[], label: string}[]
  selected_cells: Cell[]
}

// Color palette for pieces - maps labels to colors
const COLOR_PALETTE = [
  '#FFE066', // Light yellow
  '#FFA07A', // Light orange/salmon
  '#87CEEB', // Sky blue
  '#98D8C8', // Mint green
  '#F0A3FF', // Light purple
  '#FFB6C1', // Light pink
  '#FFD700', // Gold
  '#90EE90', // Light green
  '#FFE4B5', // Moccasin
  '#DDA0DD', // Plum
  '#B0E0E6', // Powder blue
  '#F5DEB3', // Wheat
  '#FFE4E1', // Misty rose
  '#E0E0E0', // Light gray
  '#FFCCCB', // Light red
  '#B19CD9', // Light purple-blue
]

// Color mapping function - creates a consistent mapping from labels to colors
function createColorMap(labels: string[]): Map<string, string> {
  const map = new Map<string, string>()
  const uniqueLabels = Array.from(new Set(labels)).sort()
  
  uniqueLabels.forEach((label, index) => {
    map.set(label, COLOR_PALETTE[index % COLOR_PALETTE.length])
  })
  
  return map
}

// Normalize a shape to its canonical form
function normalizeShape(cells: Cell[]): Cell[] {
  if (cells.length === 0) return []
  const xs = cells.map(([x]) => x)
  const ys = cells.map(([, y]) => y)
  const minX = Math.min(...xs)
  const minY = Math.min(...ys)
  return cells.map(([x, y]) => [x - minX, y - minY] as Cell).sort((a, b) => {
    if (a[1] !== b[1]) return a[1] - b[1]
    return a[0] - b[0]
  })
}

// Check if two shapes match (considering rotations and reflections)
function shapesMatch(cells1: Cell[], cells2: Cell[]): boolean {
  if (cells1.length !== cells2.length) return false
  
  const norm1 = normalizeShape(cells1)
  
  // Try all rotations and reflections
  for (const flipX of [false, true]) {
    for (const flipY of [false, true]) {
      for (let rot = 0; rot < 4; rot++) {
        const transformed: Cell[] = cells2.map(([x, y]) => {
          let nx = flipX ? -x : x
          let ny = flipY ? -y : y
          // Rotate
          for (let r = 0; r < rot; r++) {
            const temp = nx
            nx = -ny
            ny = temp
          }
          return [nx, ny] as Cell
        })
        
        if (JSON.stringify(normalizeShape(transformed)) === JSON.stringify(norm1)) {
          return true
        }
      }
    }
  }
  return false
}

export default function Home() {
  const [puzzleData, setPuzzleData] = useState<PuzzleData | null>(null)
  const [showSolution, setShowSolution] = useState(false)
  const [userPieces, setUserPieces] = useState<{cells: Cell[], label: string}[]>([])
  const [selectedCells, setSelectedCells] = useState<Cell[]>([])

  useEffect(() => {
    const eventSource = new EventSource('http://localhost:8000/events')

    eventSource.addEventListener('level', (event) => {
      const data: LevelData = JSON.parse(event.data)
      if (data.puzzle) {
        setPuzzleData(data.puzzle)
        setUserPieces(data.user_pieces || [])
        setSelectedCells(data.selected_cells || [])
      }
    })

    eventSource.onerror = () => {
      eventSource.close()
    }

    return () => {
      eventSource.close()
    }
  }, [])

  // All hooks must be called before any conditional returns
  // Create a master color map for all possible labels (A, B, C, etc.)
  // This ensures dark pieces and user pieces with the same label get the same color
  const masterColorMap = useMemo(() => {
    if (!puzzleData) return new Map<string, string>()
    // Create labels for all dark pieces (A, B, C, etc.)
    const labels = puzzleData.dark_pieces.map((_, idx) => String.fromCharCode(65 + idx))
    return createColorMap(labels)
  }, [puzzleData?.dark_pieces])

  // Create color maps
  const userPieceColorMap = useMemo(() => {
    // Use the master color map to ensure consistency with dark pieces
    return masterColorMap
  }, [masterColorMap])
  
  const litPieceColorMap = useMemo(() => {
    if (!puzzleData || !showSolution || !puzzleData.lit_pieces) return new Map<string, string>()
    const labels = puzzleData.lit_pieces.map((_, idx) => String.fromCharCode(65 + (idx % 26)))
    return createColorMap(labels)
  }, [puzzleData?.lit_pieces, showSolution])

  // Create color map for dark pieces based on their index (A, B, C, etc.)
  // This is independent of user pieces - each dark piece always has a color
  const darkPieceColorMap = useMemo(() => {
    if (!puzzleData) return new Map<number, string>()
    const map = new Map<number, string>()
    puzzleData.dark_pieces.forEach((_, darkIdx) => {
      const label = String.fromCharCode(65 + darkIdx) // A, B, C, etc.
      // Use the master color map to get the color for this label
      map.set(darkIdx, masterColorMap.get(label) || COLOR_PALETTE[darkIdx % COLOR_PALETTE.length])
    })
    return map
  }, [puzzleData?.dark_pieces, masterColorMap])

  // Determine which dark pieces have matching user pieces placed
  const darkPieceComplete = useMemo(() => {
    if (!puzzleData) return new Map<number, boolean>()
    const complete = new Map<number, boolean>()
    puzzleData.dark_pieces.forEach((darkPiece, darkIdx) => {
      // Expected label for this dark piece (A=0, B=1, etc.)
      const expectedLabel = String.fromCharCode(65 + darkIdx)
      
      // Find user piece with this label
      const matchingUserPiece = userPieces.find(p => p.label === expectedLabel)
      
      if (matchingUserPiece) {
        // Check if shapes match
        const userCells = matchingUserPiece.cells.map(([x, y]) => [x, y] as Cell)
        const darkCells = darkPiece.map(([x, y]) => [x, y] as Cell)
        complete.set(darkIdx, shapesMatch(userCells, darkCells))
      } else {
        complete.set(darkIdx, false)
      }
    })
    return complete
  }, [puzzleData?.dark_pieces, userPieces])
  
  // Determine which cell in each dark piece should show the circle (first cell)
  // Always show the circle, even when no user pieces are placed
  const darkPieceIndicatorCells = useMemo(() => {
    if (!puzzleData) return new Map<string, { filled: boolean; color: string }>()
    const indicators = new Map<string, { filled: boolean; color: string }>()
    puzzleData.dark_pieces.forEach((darkPiece, darkIdx) => {
      if (darkPiece.length > 0) {
        const [x, y] = darkPiece[0] // First cell of the dark piece
        const key = `${x},${y}`
        // Get the color assigned to this dark piece
        const color = darkPieceColorMap.get(darkIdx) || COLOR_PALETTE[darkIdx % COLOR_PALETTE.length]
        indicators.set(key, { 
          filled: darkPieceComplete.get(darkIdx) || false,
          color: color
        })
      }
    })
    return indicators
  }, [puzzleData?.dark_pieces, darkPieceComplete, darkPieceColorMap])

  if (!puzzleData) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: '#2a2a3a'
      }}>
        <div style={{
          width: '60px',
          height: '60px',
          border: '6px solid #555',
          borderTop: '6px solid #fff',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite'
        }} />
        <style jsx>{`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    )
  }

  // Create a grid representation
  const { grid_w, grid_h, dark_pieces, lit_pieces, stars } = puzzleData
  
  // Initialize grid with empty cells
  const grid: { type: 'empty' | 'dark' | 'lit' | 'star' | 'user_piece', label?: string }[][] = 
    Array(grid_h).fill(null).map(() => Array(grid_w).fill(null).map(() => ({ type: 'empty' })))
  
  // Mark star positions
  const starSet = new Set(stars.map(([x, y]) => `${x},${y}`))
  
  // Place dark pieces (no labels needed, just mark as dark)
  dark_pieces.forEach((piece) => {
    piece.forEach(([x, y]) => {
      if (y >= 0 && y < grid_h && x >= 0 && x < grid_w) {
        grid[y][x] = { type: 'dark' }
      }
    })
  })
  
  // Place user pieces (always show these)
  userPieces.forEach((piece) => {
    piece.cells.forEach(([x, y]) => {
      if (y >= 0 && y < grid_h && x >= 0 && x < grid_w) {
        grid[y][x] = { type: 'user_piece', label: piece.label }
      }
    })
  })
  
  // Place lit pieces if showing solution
  if (showSolution && lit_pieces) {
    lit_pieces.forEach((piece, idx) => {
      const label = String.fromCharCode(65 + (idx % 26)) // A, B, C, ...
      piece.forEach(([x, y]) => {
        if (y >= 0 && y < grid_h && x >= 0 && x < grid_w) {
          // Only place if not already covered by user piece
          if (grid[y][x].type !== 'user_piece') {
            grid[y][x] = { type: 'lit', label }
          }
        }
      })
    })
  } else {
    // In puzzle mode, show stars in empty cells (not covered by user pieces)
    stars.forEach(([x, y]) => {
      if (y >= 0 && y < grid_h && x >= 0 && x < grid_w) {
        if (grid[y][x].type === 'empty') {
          grid[y][x] = { type: 'star' }
        }
      }
    })
  }

  const cellSize = Math.min(80, Math.max(40, 480 / Math.max(grid_w, grid_h)))

  return (
    <main style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'center',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      backgroundColor: '#2a2a3a',
      padding: '2rem',
      gap: '2rem'
    }}>
      {/* Board */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${grid_w}, ${cellSize}px)`,
        gridTemplateRows: `repeat(${grid_h}, ${cellSize}px)`,
        gap: '2px',
        backgroundColor: '#555',
        padding: '4px',
        borderRadius: '8px',
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)'
      }}>
        {grid.map((row, rowIdx) => (
          row.map((cell, colIdx) => {
            // Check if this cell is selected
            const isSelected = selectedCells.some(([x, y]) => x === colIdx && y === rowIdx)
            const isStar = starSet.has(`${colIdx},${rowIdx}`)
            
            let bgColor = '#e0e0e0' // empty cell background (light grey)
            let borderColor = '#ccc'
            let showStar = false
            
            // Check if this dark cell should show a circle indicator
            const darkIndicatorKey = `${colIdx},${rowIdx}`
            const darkIndicator = darkPieceIndicatorCells.get(darkIndicatorKey)
            
            if (cell.type === 'dark') {
              bgColor = '#1a1a1a' // Very dark/black for dark pieces
              borderColor = '#333'
            } else if (cell.type === 'user_piece') {
              // Use color from map, default to light yellow
              bgColor = cell.label ? (userPieceColorMap.get(cell.label) || '#FFE066') : '#FFE066'
              borderColor = '#d4a017'
            } else if (cell.type === 'lit') {
              // Use color from map, default to light orange
              bgColor = cell.label ? (litPieceColorMap.get(cell.label) || '#FFA07A') : '#FFA07A'
              borderColor = '#ff7f50'
            } else if (cell.type === 'star') {
              bgColor = '#e0e0e0' // Use empty cell background
              borderColor = '#ccc'
              showStar = true
            }
            
            // Show star if this cell has a star (even if covered by a piece)
            if (isStar && cell.type !== 'empty' && cell.type !== 'star') {
              showStar = true
            }
            
            // Selected cells get orange border
            if (isSelected) {
              borderColor = '#ffa500'
            }
            
            return (
              <div
                key={`${rowIdx}-${colIdx}`}
                style={{
                  width: `${cellSize}px`,
                  height: `${cellSize}px`,
                  backgroundColor: bgColor,
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  borderRadius: '2px',
                  boxShadow: cell.type !== 'empty' ? 'inset 0 2px 4px rgba(0,0,0,0.1)' : 'none',
                  border: isSelected ? `3px solid ${borderColor}` : `2px solid ${borderColor}`,
                  position: 'relative'
                }}
              >
                {showStar && (
                  <span style={{
                    fontSize: `${cellSize * 0.6}px`,
                    color: '#1a1a1a',
                    fontWeight: 'bold',
                    textShadow: '0 0 2px rgba(255,255,255,0.8)'
                  }}>
                    ★
                  </span>
                )}
                {darkIndicator && (
                  <div style={{
                    position: 'absolute',
                    width: `${cellSize * 0.3}px`,
                    height: `${cellSize * 0.3}px`,
                    borderRadius: '50%',
                    border: `2px solid ${darkIndicator.color}`,
                    backgroundColor: darkIndicator.filled ? darkIndicator.color : 'transparent', // Transparent when hollow (shows black background)
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    boxShadow: '0 0 2px rgba(0,0,0,0.5)'
                  }} />
                )}
              </div>
            )
          })
        ))}
      </div>
    </main>
  )
}


