import { useRef, useCallback, useEffect, useState } from 'react'

const SAMPLE_RATE = 16000
const CHUNK_SIZE = 512
// ponytail: fixed software boost so far/quiet speech arrives loud enough to detect
const MIC_GAIN = 3.0

let audioCtx = null
let scriptNode = null
let stream = null

export function resumeMicAudio() {
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume().catch(() => {})
  }
}

export default function useBrowserMic(socket) {
  const [micActive, setMicActive] = useState(false)
  const [micError, setMicError] = useState(null)
  const activeRef = useRef(false)
  const socketRef = useRef(socket)
  socketRef.current = socket

  const start = useCallback(async () => {
    if (activeRef.current) return
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: { ideal: SAMPLE_RATE },
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }
      })

      const AC = window.AudioContext || window.webkitAudioContext
      audioCtx = new AC({ sampleRate: SAMPLE_RATE })
      if (audioCtx.state === 'suspended') {
        await audioCtx.resume()
      }
      const source = audioCtx.createMediaStreamSource(stream)

      scriptNode = audioCtx.createScriptProcessor(CHUNK_SIZE, 1, 1)
      scriptNode.onaudioprocess = (event) => {
        if (!activeRef.current) return
        const input = event.inputBuffer.getChannelData(0)
        const pcm = new Int16Array(input.length)
        for (let i = 0; i < input.length; i++) {
          const s = Math.max(-1, Math.min(1, input[i] * MIC_GAIN))
          pcm[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
        }
        const bytes = new Uint8Array(pcm.buffer)
        const arr = Array.from(bytes)
        if (socketRef.current?.connected) {
          socketRef.current.emit('browser_audio', { audio: arr })
        }
      }

      source.connect(scriptNode)
      scriptNode.connect(audioCtx.destination)
      activeRef.current = true
      setMicActive(true)
      setMicError(null)
    } catch (err) {
      setMicError(err.message)
      setMicActive(false)
    }
  }, [])

  const stop = useCallback(() => {
    activeRef.current = false
    if (scriptNode) {
      scriptNode.disconnect()
      scriptNode = null
    }
    if (audioCtx) {
      audioCtx.close().catch(() => {})
      audioCtx = null
    }
    if (stream) {
      stream.getTracks().forEach(t => t.stop())
      stream = null
    }
    setMicActive(false)
  }, [])

  useEffect(() => {
    return () => stop()
  }, [stop])

  return { micActive, micError, start, stop }
}
