'use client'

import { useEffect, useState } from 'react'

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
  
  // Place dark pieces
  dark_pieces.forEach((piece, idx) => {
    const label = String.fromCharCode(97 + (idx % 26)) // a, b, c, ...
    piece.forEach(([x, y]) => {
      if (y >= 0 && y < grid_h && x >= 0 && x < grid_w) {
        grid[y][x] = { type: 'dark', label }
      }
    })
  })
  
  // Place user pieces (always show these)
  userPieces.forEach((piece) => {
    piece.cells.forEach(([x, y]) => {
      if (y >= 0 && y < grid_h && x >= 0 && x < grid_w) {
        const isStar = starSet.has(`${x},${y}`)
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
          const isStar = starSet.has(`${x},${y}`)
          grid[y][x] ={ type: 'lit', label }
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
      <h1 style={{
        fontSize: '3rem',
        fontWeight: 'bold',
        color: '#fff',
        margin: 0,
        textShadow: '2px 2px 4px rgba(0,0,0,0.5)'
      }}>
        Twinominoes
      </h1>

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
            
            let bgColor = '#f5f5f5' // empty cell background
            let textColor = '#333'
            let content = ''
            let borderColor = '#ddd'
            
            if (cell.type === 'dark') {
              bgColor = '#4a4a4a'
              textColor = '#aaa'
              content = cell.label || ''
            } else if (cell.type === 'user_piece') {
              bgColor = '#9370db' // Purple for user pieces
              textColor = '#fff'
              content = cell.label || ''
            } else if (cell.type === 'lit') {
              bgColor = '#6eb5ff' // Blue for solution pieces
              textColor = '#fff'
              content = cell.label || ''
            } else if (cell.type === 'star') {
              bgColor = '#fff8dc'
              textColor = '#ff6b35'
              content = '★'
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
                  color: textColor,
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  fontSize: `${cellSize * 0.5}px`,
                  fontWeight: 'bold',
                  borderRadius: '2px',
                  boxShadow: cell.type !== 'empty' ? 'inset 0 2px 4px rgba(0,0,0,0.1)' : 'none',
                  border: isSelected ? `3px solid ${borderColor}` : '1px solid #ddd'
                }}
              >
                {content}
              </div>
            )
          })
        ))}
      </div>

      {/* Game Info */}
      <div style={{
        backgroundColor: '#3a3a4a',
        padding: '1.5rem',
        borderRadius: '8px',
        color: '#fff',
        maxWidth: '600px',
        boxShadow: '0 4px 16px rgba(0,0,0,0.3)'
      }}>
        <h2 style={{ margin: '0 0 1rem 0', fontSize: '1.5rem' }}>Game Rules:</h2>
        <ul style={{ margin: 0, paddingLeft: '1.5rem', lineHeight: '1.8' }}>
          <li><strong>Dark pieces</strong> (gray, lowercase) are constraints</li>
          <li><strong>Purple pieces</strong> are user placements (via CLI)</li>
          <li>Goal: Cover all ★ stars with pieces</li>
          <li>Pieces must touch dark pieces by edges</li>
          <li>Pieces must NOT touch each other by edges (corners OK)</li>
          <li>All pieces must be corner-connected</li>
        </ul>
        <div style={{ marginTop: '1rem', fontSize: '0.9rem', color: '#bbb' }}>
          Control this game via CLI commands to the backend API
        </div>
      </div>

      {/* Action button */}
      <div style={{
        display: 'flex',
        gap: '1rem',
        flexWrap: 'wrap',
        justifyContent: 'center'
      }}>
        <button
          onClick={() => setShowSolution(!showSolution)}
          style={{
            padding: '12px 32px',
            backgroundColor: showSolution ? '#4CAF50' : '#2196F3',
            color: 'white',
            fontSize: '1.2rem',
            fontWeight: 'bold',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            transition: 'all 0.2s',
            boxShadow: '0 4px 8px rgba(0,0,0,0.2)'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-2px)'
            e.currentTarget.style.boxShadow = '0 6px 12px rgba(0,0,0,0.3)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)'
            e.currentTarget.style.boxShadow = '0 4px 8px rgba(0,0,0,0.2)'
          }}
        >
          {showSolution ? 'Hide Solution' : 'Show Solution'}
        </button>
      </div>

      {/* Puzzle Stats */}
      <div style={{
        display: 'flex',
        gap: '2rem',
        color: '#aaa',
        fontSize: '0.9rem'
      }}>
        <div>Grid: {grid_w} × {grid_h}</div>
        <div>Dark pieces: {dark_pieces.length}</div>
        <div>Stars: {stars.length}</div>
        <div>Your pieces: {userPieces.length}</div>
      </div>
    </main>
  )
}


