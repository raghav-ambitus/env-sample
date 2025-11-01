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
  const [selectedNumber, setSelectedNumber] = useState<number | null>(null)
  const [isEraseMode, setIsEraseMode] = useState<boolean>(false)

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
            const canPlace = (isWhite || isPlaced) && selectedNumber !== null && !isEraseMode
            const canErase = isPlaced && isEraseMode
            
            return (
              <div
                key={`${rowIdx}-${colIdx}`}
                onClick={async () => {
                  if (isEraseMode && canErase) {
                    try {
                      const response = await fetch('http://localhost:8000/erase', {
                        method: 'POST',
                        headers: {
                          'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                          row: rowIdx,
                          col: colIdx
                        })
                      })
                      const result = await response.json()
                      if (!result.success) {
                        console.error('Failed to erase:', result.message)
                      }
                    } catch (error) {
                      console.error('Error erasing cell:', error)
                    }
                  } else if (canPlace) {
                    try {
                      const response = await fetch('http://localhost:8000/place', {
                        method: 'POST',
                        headers: {
                          'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                          row: rowIdx,
                          col: colIdx,
                          number: selectedNumber
                        })
                      })
                      const result = await response.json()
                      if (!result.success) {
                        console.error('Failed to place number:', result.message)
                      }
                    } catch (error) {
                      console.error('Error placing number:', error)
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
                  border: '2px solid #aaa',
                  cursor: (canPlace || canErase) ? 'pointer' : 'default',
                  opacity: (canPlace || canErase) ? 0.8 : 1,
                  transition: 'opacity 0.2s',
                }}
                onMouseEnter={(e) => {
                  if (canPlace && isWhite) {
                    e.currentTarget.style.backgroundColor = '#f0f0f0'
                  } else if (canErase) {
                    e.currentTarget.style.backgroundColor = '#ffebee'
                  }
                }}
                onMouseLeave={(e) => {
                  if (canPlace && isWhite) {
                    e.currentTarget.style.backgroundColor = 'white'
                  } else if (canErase) {
                    e.currentTarget.style.backgroundColor = 'white'
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
            onClick={() => {
              setSelectedNumber(selectedNumber === num ? null : num)
              setIsEraseMode(false)
            }}
            style={{
              width: '80px',
              height: '80px',
              backgroundColor: selectedNumber === num ? '#4CAF50' : '#555',
              color: 'white',
              fontSize: '2rem',
              fontWeight: 'bold',
              border: selectedNumber === num ? '3px solid #fff' : 'none',
              borderRadius: '8px',
              cursor: 'pointer',
              transition: 'background-color 0.2s, border 0.2s'
            }}
            onMouseEnter={(e) => {
              if (selectedNumber !== num) {
                e.currentTarget.style.backgroundColor = '#666'
              }
            }}
            onMouseLeave={(e) => {
              if (selectedNumber !== num) {
                e.currentTarget.style.backgroundColor = '#555'
              }
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
          onClick={() => {
            setIsEraseMode(!isEraseMode)
            setSelectedNumber(null)
          }}
          style={{
            padding: '12px 24px',
            backgroundColor: isEraseMode ? '#ff8800' : '#888',
            color: 'white',
            fontSize: '1.2rem',
            fontWeight: 'bold',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            transition: 'background-color 0.2s'
          }}
          onMouseEnter={(e) => {
            if (!isEraseMode) {
              e.currentTarget.style.backgroundColor = '#999'
            }
          }}
          onMouseLeave={(e) => {
            if (!isEraseMode) {
              e.currentTarget.style.backgroundColor = '#888'
            }
          }}
        >
          {isEraseMode ? 'Erase Mode ON' : 'Erase'}
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
              setSelectedNumber(null)
              setIsEraseMode(false)
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


