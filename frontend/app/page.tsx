'use client'

import { useEffect, useState } from 'react'

interface GameInfo {
  board: string[][]
}

interface LevelData {
  game_info: GameInfo
  level_id: string
}

// Color mapping for pentomino letters (at 50% opacity)
const PENTOMINO_COLORS: Record<string, string> = {
  'F': 'rgba(255, 0, 0, 0.5)',      // Red
  'I': 'rgba(0, 255, 0, 0.5)',      // Green
  'L': 'rgba(0, 0, 255, 0.5)',      // Blue
  'P': 'rgba(255, 255, 0, 0.5)',   // Yellow
  'N': 'rgba(255, 0, 255, 0.5)',   // Magenta
  'T': 'rgba(0, 255, 255, 0.5)',   // Cyan
  'U': 'rgba(255, 165, 0, 0.5)',  // Orange
  'V': 'rgba(128, 0, 128, 0.5)',  // Purple
  'W': 'rgba(255, 192, 203, 0.5)', // Pink
  'X': 'rgba(165, 42, 42, 0.5)',  // Brown
  'Y': 'rgba(0, 128, 128, 0.5)',  // Teal
  'Z': 'rgba(255, 20, 147, 0.5)', // Deep Pink
}

export default function Home() {
  const [gameData, setGameData] = useState<GameInfo | null>(null)

  useEffect(() => {
    const eventSource = new EventSource('http://localhost:8000/events')

    eventSource.addEventListener('level', (event) => {
      const data: LevelData = JSON.parse(event.data)
      if (data.game_info) {
        setGameData(data.game_info)
      }
    })

    eventSource.onerror = () => {
      eventSource.close()
    }

    return () => {
      eventSource.close()
    }
  }, [])

  const handleCellClick = async (row: number, col: number) => {
    if (!gameData) return

    const cellValue = gameData.board[row][col]

    if (cellValue === '|') {
      return
    }

    // If cell is empty ("-") or selected ("*"), call /select
    if (cellValue === '-' || cellValue === '*') {
      try {
        const response = await fetch('http://localhost:8000/select', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            row,
            col,
          })
        })
        const result = await response.json()
        if (!result.success) {
          console.error('Failed to select/unselect tile:', result.message)
        }
      } catch (error) {
        console.error('Error selecting tile:', error)
      }
    }
    // If cell is a locked pentomino (letter), call /unlock
    else if (cellValue in PENTOMINO_COLORS) {
      try {
        const response = await fetch('http://localhost:8000/unlock', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            row,
            col,
          })
        })
        const result = await response.json()
        if (!result.success) {
          console.error('Failed to unlock pentomino:', result.message)
        }
      } catch (error) {
        console.error('Error unlocking pentomino:', error)
      }
    }
  }

  const handleLock = async () => {
    try {
      const response = await fetch('http://localhost:8000/lock', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({})
      })
      const result = await response.json()
      if (!result.success) {
        console.error('Failed to lock:', result.message)
      }
    } catch (error) {
      console.error('Error locking pentomino:', error)
    }
  }

  const hasSelectedTiles = () => {
    if (!gameData) return false
    return gameData.board.some(row => row.some(cell => cell === '*'))
  }

  if (!gameData) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: '#3a3a3a'
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

  return (
    <main style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'center',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      backgroundColor: '#3a3a3a',
      padding: '2rem',
      gap: '2rem'
    }}>
      {/* Board */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${gameData.board[0]?.length || 5}, 1fr)`,
        gap: '0',
        border: '8px solid white',
        borderRadius: '12px',
        overflow: 'hidden',
        backgroundColor: 'white',
        padding: '8px'
      }}>
        {gameData.board.map((row, rowIdx) => (
          row.map((cell, colIdx) => {
            const isEmpty = cell === '-'
            const isSelected = cell === '*'
            const isLocked = cell in PENTOMINO_COLORS
            const isBlocked = cell === '|'
            
            // Determine background color
            let backgroundColor = 'white' // default for empty
            if (isSelected) {
              backgroundColor = '#808080' // grey for selected
            } else if (isLocked) {
              backgroundColor = PENTOMINO_COLORS[cell] || 'white'
            } else if (isBlocked) {
              backgroundColor = '#000000'
            }

            const textColor = isBlocked ? '#ffffff' : '#000000'
            
            return (
              <div
                key={`${rowIdx}-${colIdx}`}
                onClick={() => handleCellClick(rowIdx, colIdx)}
                style={{
                  width: '120px',
                  height: '120px',
                  backgroundColor,
                  color: textColor,
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  fontSize: '2rem',
                  fontWeight: 'bold',
                  border: '2px solid #aaa',
                  cursor: isBlocked ? 'default' : 'pointer',
                  transition: 'opacity 0.2s, border 0.2s',
                }}
                onMouseEnter={(e) => {
                  if ((isEmpty || isSelected) && !isBlocked) {
                    e.currentTarget.style.backgroundColor = isSelected ? '#999' : '#f0f0f0'
                  }
                }}
                onMouseLeave={(e) => {
                  if ((isEmpty || isSelected) && !isBlocked) {
                    e.currentTarget.style.backgroundColor = isSelected ? '#808080' : 'white'
                  }
                }}
              >
                {isLocked ? cell : isBlocked ? '|' : ''}
              </div>
            )
          })
        ))}
      </div>

      {/* Action buttons */}
      <div style={{
        display: 'flex',
        gap: '1rem'
      }}>
        <button
          onClick={handleLock}
          disabled={!hasSelectedTiles()}
          style={{
            padding: '12px 24px',
            backgroundColor: hasSelectedTiles() ? '#D4AF37' : '#B8860B',
            color: 'white',
            fontSize: '1.2rem',
            fontWeight: 'bold',
            border: 'none',
            borderRadius: '8px',
            cursor: hasSelectedTiles() ? 'pointer' : 'not-allowed',
            transition: 'background-color 0.2s',
            opacity: hasSelectedTiles() ? 1 : 0.6
          }}
          onMouseEnter={(e) => {
            if (hasSelectedTiles()) {
              e.currentTarget.style.backgroundColor = '#F4D03F'
            }
          }}
          onMouseLeave={(e) => {
            if (hasSelectedTiles()) {
              e.currentTarget.style.backgroundColor = '#D4AF37'
            }
          }}
        >
          Lock
        </button>
        <button
          onClick={async () => {
            try {
              const response = await fetch('http://localhost:8000/reset', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                }
              })
              const result = await response.json()
              if (!result.success) {
                console.error('Failed to reset:', result.message)
              }
            } catch (error) {
              console.error('Error resetting board:', error)
            }
          }}
          style={{
            padding: '12px 24px',
            backgroundColor: '#ff4444',
            color: 'white',
            fontSize: '1.2rem',
            fontWeight: 'bold',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            transition: 'background-color 0.2s'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = '#ff6666'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = '#ff4444'
          }}
        >
          Reset
        </button>
      </div>
    </main>
  )
}
