/**
 * WebSocket Context Provider - shares a single WebSocket connection
 * across all components that need it.
 * 
 * Handles two message types:
 * - Binary messages: raw JPEG video frames (sent as Blob)
 * - Text messages: JSON for state updates, encounters, annotations, etc.
 * 
 * Features:
 * - Fast reconnect with exponential backoff (500ms → 10s max)
 * - Client-side ping/keepalive every 5 seconds
 * - Visibility API handling (pauses on tab hide)
 */
import { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'

// Reconnect settings
const RECONNECT_MIN_MS = 500
const RECONNECT_MAX_MS = 10000
const PING_INTERVAL_MS = 5000

// Context for sharing WebSocket state
const WebSocketContext = createContext(null)

/**
 * Provider component - wraps the app and manages a single WebSocket connection.
 */
export function WebSocketProvider({ children }) {
  const [connected, setConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState(null)
  // videoFrame is now a Blob (binary JPEG), not a base64 object
  const [videoFrame, setVideoFrame] = useState(null)
  const [annotations, setAnnotations] = useState(null)
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const reconnectDelayRef = useRef(RECONNECT_MIN_MS)
  const pingIntervalRef = useRef(null)
  const mountedRef = useRef(true)
  const visibleRef = useRef(true)

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
      // Accept binary data as Blob (default), not ArrayBuffer
      ws.binaryType = 'blob'
      
      ws.onopen = () => {
        if (!mountedRef.current) return
        console.log('WebSocket connected')
        setConnected(true)
        reconnectDelayRef.current = RECONNECT_MIN_MS // Reset backoff
        
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current)
          reconnectTimeoutRef.current = null
        }
        
        // Start ping keepalive
        startPing(ws)
      }

      ws.onmessage = (event) => {
        if (!mountedRef.current) return
        
        // Binary message = raw JPEG video frame
        if (event.data instanceof Blob) {
          setVideoFrame(event.data)
          return
        }
        
        // Text message = JSON (state updates, annotations, etc.)
        try {
          const message = JSON.parse(event.data)
          
          if (message.type === 'annotations') {
            setAnnotations(message.data)
          } else if (message.type === 'pong') {
            // Keepalive response — connection is healthy
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
        stopPing()
        
        // Exponential backoff reconnect
        const delay = reconnectDelayRef.current
        reconnectDelayRef.current = Math.min(delay * 2, RECONNECT_MAX_MS)
        
        reconnectTimeoutRef.current = setTimeout(() => {
          if (mountedRef.current) {
            console.log(`Reconnecting in ${delay}ms...`)
            connect()
          }
        }, delay)
      }

      wsRef.current = ws
    } catch (error) {
      console.error('Error creating WebSocket:', error)
    }
  }, [])

  const startPing = useCallback((ws) => {
    stopPing()
    pingIntervalRef.current = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, PING_INTERVAL_MS)
  }, [])

  const stopPing = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current)
      pingIntervalRef.current = null
    }
  }, [])

  const sendMessage = useCallback((message) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  // Handle tab visibility changes
  useEffect(() => {
    const handleVisibility = () => {
      visibleRef.current = !document.hidden
      if (document.hidden) {
        // Tab hidden — stop ping to reduce overhead
        stopPing()
      } else {
        // Tab visible — restart ping and reconnect if needed
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          startPing(wsRef.current)
        } else if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED) {
          connect()
        }
      }
    }

    document.addEventListener('visibilitychange', handleVisibility)
    return () => document.removeEventListener('visibilitychange', handleVisibility)
  }, [connect, startPing, stopPing])

  useEffect(() => {
    mountedRef.current = true
    connect()

    return () => {
      mountedRef.current = false
      stopPing()
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect, stopPing])

  const value = {
    connected,
    lastMessage,
    videoFrame,     // Now a Blob (binary JPEG)
    annotations,    // Separate state for zone annotations
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
