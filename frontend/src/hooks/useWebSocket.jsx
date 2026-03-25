/**
 * WebSocket Context Provider - shares a single WebSocket connection
 * across all components that need it.
 * 
 * Instead of each component creating its own WebSocket connection,
 * this provides a shared context that all consumers read from.
 */
import { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'

// Context for sharing WebSocket state
const WebSocketContext = createContext(null)

/**
 * Provider component - wraps the app and manages a single WebSocket connection.
 */
export function WebSocketProvider({ children }) {
  const [connected, setConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState(null)
  const [videoFrame, setVideoFrame] = useState(null)
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    // Don't connect if already connected or connecting
    if (wsRef.current && (
      wsRef.current.readyState === WebSocket.OPEN ||
      wsRef.current.readyState === WebSocket.CONNECTING
    )) {
      return
    }

    try {
      const ws = new WebSocket(WS_URL)
      
      ws.onopen = () => {
        if (!mountedRef.current) return
        console.log('WebSocket connected')
        setConnected(true)
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current)
          reconnectTimeoutRef.current = null
        }
      }

      ws.onmessage = (event) => {
        if (!mountedRef.current) return
        try {
          const message = JSON.parse(event.data)
          
          if (message.type === 'video_frame') {
            setVideoFrame(message.data)
          } else {
            setLastMessage(message)
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error)
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
      }

      ws.onclose = () => {
        if (!mountedRef.current) return
        console.log('WebSocket disconnected')
        setConnected(false)
        wsRef.current = null
        
        // Attempt to reconnect after 3 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          if (mountedRef.current) {
            console.log('Attempting WebSocket reconnect...')
            connect()
          }
        }, 3000)
      }

      wsRef.current = ws
    } catch (error) {
      console.error('Error creating WebSocket:', error)
    }
  }, [])

  const sendMessage = useCallback((message) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    connect()

    return () => {
      mountedRef.current = false
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect])

  const value = {
    connected,
    lastMessage,
    videoFrame,
    sendMessage,
  }

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  )
}

/**
 * Hook to consume the shared WebSocket context.
 * Must be used within a <WebSocketProvider>.
 */
export default function useWebSocket() {
  const context = useContext(WebSocketContext)
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider')
  }
  return context
}
