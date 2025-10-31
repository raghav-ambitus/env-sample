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
          row.map((cell, colIdx) => (
            <div
              key={`${rowIdx}-${colIdx}`}
              style={{
                width: '120px',
                height: '120px',
                backgroundColor: cell === -1 ? 'white' : 'black',
                color: cell === -1 ? 'black' : 'white',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                fontSize: '3rem',
                fontWeight: 'bold',
                border: '2px solid #aaa'
              }}
            >
              {cell !== -1 ? cell : ''}
            </div>
          ))
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
    </main>
  )
}


