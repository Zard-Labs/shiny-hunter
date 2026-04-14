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
 * - Video frames & annotations bypass React state (ref + callback)
 *   to avoid 30fps re-renders of the entire component tree
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
 *
 * Video frames and annotations are delivered via ref-based callbacks
 * instead of React state, so only subscribing components (LiveFeed)
 * update — the rest of the tree is untouched.
 */
export function WebSocketProvider({ children }) {
  const [connected, setConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState(null)

  // --- Ref-based subscribers for high-frequency data ---
  // Subscribers are Sets of callbacks; adding/removing is O(1).
  const frameSubscribers = useRef(new Set())
  const annotationSubscribers = useRef(new Set())

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
        // Deliver directly to subscribers — NO React state update
        if (event.data instanceof Blob) {
          for (const cb of frameSubscribers.current) {
            try { cb(event.data) } catch (_) { /* subscriber error */ }
          }
          return
        }
        
        // Text message = JSON (state updates, annotations, etc.)
        try {
          const message = JSON.parse(event.data)
          
          if (message.type === 'annotations') {
            // Deliver directly to subscribers — NO React state update
            for (const cb of annotationSubscribers.current) {
              try { cb(message.data) } catch (_) { /* subscriber error */ }
            }
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

  // --- Subscription helpers (stable refs, never change identity) ---
  const subscribeToFrames = useCallback((callback) => {
    frameSubscribers.current.add(callback)
    return () => frameSubscribers.current.delete(callback)
  }, [])

  const subscribeToAnnotations = useCallback((callback) => {
    annotationSubscribers.current.add(callback)
    return () => annotationSubscribers.current.delete(callback)
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
    sendMessage,
    // Subscription-based APIs — no React state for high-frequency data
    subscribeToFrames,
    subscribeToAnnotations,
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
