'use client'

import { useEffect, useState } from 'react'

interface GameInfo {
  board: number[][]
  numbers_available: number[]
}

interface LevelData {
  game_info: GameInfo
  level_id: string
}

export default function Home() {
  const [gameData, setGameData] = useState<GameInfo | null>(null)
  const [selectedCell, setSelectedCell] = useState<{row: number, col: number} | null>(null)

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
            const isWhite = cell === -1
            const isPlaced = cell !== -1 && gameData.numbers_available.includes(cell)
            const isSelected = selectedCell?.row === rowIdx && selectedCell?.col === colIdx
            const canSelect = isWhite || isPlaced
            
            return (
              <div
                key={`${rowIdx}-${colIdx}`}
                onClick={() => {
                  // Select cell (for placing numbers or erasing)
                  if (canSelect) {
                    if (isSelected) {
                      setSelectedCell(null)
                    } else {
                      setSelectedCell({row: rowIdx, col: colIdx})
                    }
                  }
                }}
                style={{
                  width: '120px',
                  height: '120px',
                  backgroundColor: isWhite ? 'white' : 'black',
                  color: isWhite ? 'black' : 'white',
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  fontSize: '3rem',
                  fontWeight: 'bold',
                  border: isSelected ? '4px solid #ff8800' : '2px solid #aaa',
                  cursor: canSelect ? 'pointer' : 'default',
                  transition: 'opacity 0.2s, border 0.2s',
                }}
                onMouseEnter={(e) => {
                  if (canSelect && !isSelected) {
                    e.currentTarget.style.backgroundColor = isWhite ? '#f0f0f0' : '#333'
                  }
                }}
                onMouseLeave={(e) => {
                  if (canSelect && !isSelected) {
                    e.currentTarget.style.backgroundColor = isWhite ? 'white' : 'black'
                  }
                }}
              >
                {cell !== -1 ? cell : ''}
              </div>
            )
          })
        ))}
      </div>

      {/* Number buttons */}
      <div style={{
        display: 'flex',
        gap: '1rem'
      }}>
        {gameData.numbers_available.map((num) => (
          <button
            key={num}
            onClick={async () => {
              if (selectedCell !== null) {
                // Place number in selected cell
                try {
                  const response = await fetch('http://localhost:8000/place', {
                    method: 'POST',
                    headers: {
                      'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                      row: selectedCell.row,
                      col: selectedCell.col,
                      number: num
                    })
                  })
                  const result = await response.json()
                  if (!result.success) {
                    console.error('Failed to place number:', result.message)
                  } else {
                    setSelectedCell(null)
                  }
                } catch (error) {
                  console.error('Error placing number:', error)
                }
              }
            }}
            style={{
              width: '80px',
              height: '80px',
              backgroundColor: '#555',
              color: 'white',
              fontSize: '2rem',
              fontWeight: 'bold',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
              transition: 'background-color 0.2s'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#666'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = '#555'
            }}
          >
            {num}
          </button>
        ))}
      </div>

      {/* Action buttons */}
      <div style={{
        display: 'flex',
        gap: '1rem'
      }}>
        <button
          onClick={async () => {
            if (selectedCell !== null) {
              try {
                const response = await fetch('http://localhost:8000/erase', {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                  },
                  body: JSON.stringify({
                    row: selectedCell.row,
                    col: selectedCell.col
                  })
                })
                const result = await response.json()
                if (!result.success) {
                  console.error('Failed to erase:', result.message)
                } else {
                  setSelectedCell(null)
                }
              } catch (error) {
                console.error('Error erasing cell:', error)
              }
            }
          }}
          style={{
            padding: '12px 24px',
            backgroundColor: '#888',
            color: 'white',
            fontSize: '1.2rem',
            fontWeight: 'bold',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            transition: 'background-color 0.2s'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = '#999'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = '#888'
          }}
        >
          Erase
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
              setSelectedCell(null)
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


