import { io } from 'socket.io-client'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || window.location.origin

const socket = io(BACKEND_URL, {
  autoConnect: false,
  transports: ['polling', 'websocket'],
  reconnection: true,
  reconnectionDelay: 500,
  reconnectionDelayMax: 3000,
  reconnectionAttempts: Infinity,
  timeout: 10000
})

// Expose for console debugging
if (typeof window !== 'undefined') {
  window.__sodaSocket = socket
}

export default socket
