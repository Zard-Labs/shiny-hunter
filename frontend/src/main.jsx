import React from 'react'
import ReactDOM from 'react-dom/client'
import { WebSocketProvider } from './hooks/useWebSocket.jsx'
import App from './App.jsx'
import './styles/App.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <WebSocketProvider>
      <App />
    </WebSocketProvider>
  </React.StrictMode>,
)
