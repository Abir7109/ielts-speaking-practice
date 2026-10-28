import { useRef, useCallback } from 'react'

export default function useAudioPlayback() {
  const audioCtxRef = useRef(null)
  const audioNextTime = useRef(0)
  const audioReadyRef = useRef(false)

  const stopAudio = useCallback(() => {
    audioNextTime.current = 0
    if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
      audioCtxRef.current.close().catch(() => {})
      audioCtxRef.current = null
    }
  }, [])

  const initAudioCtx = useCallback(() => {
    if (!audioCtxRef.current) {
      const AC = window.AudioContext || window.webkitAudioContext
      if (!AC) return null
      audioCtxRef.current = new AC()
      console.log('[Audio] Created AudioContext, sampleRate:', audioCtxRef.current.sampleRate)
    }
    if (audioCtxRef.current.state === 'suspended') {
      audioCtxRef.current.resume().catch(e => console.warn('[Audio] resume failed:', e))
    }
    return audioCtxRef.current
  }, [])

  const playPcmBytes = useCallback((data) => {
    if (!data) return
    const ctx = initAudioCtx()
    if (!ctx) return

    let bytes
    if (typeof data === 'string') {
      const bin = atob(data)
      bytes = new Uint8Array(bin.length)
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
    } else {
      bytes = data
    }

    const len = Math.floor(bytes.length / 2)
    if (len === 0) return
    const float32 = new Float32Array(len)
    for (let i = 0; i < len; i++) {
      const val = bytes[i * 2] | (bytes[i * 2 + 1] << 8)
      float32[i] = (val << 16 >> 16) / 32768.0
    }

    try {
      const buffer = ctx.createBuffer(1, float32.length, 24000)
      buffer.copyToChannel(float32, 0)
      const source = ctx.createBufferSource()
      source.buffer = buffer
      source.connect(ctx.destination)
      let startTime = audioNextTime.current
      if (startTime < ctx.currentTime) {
        startTime = ctx.currentTime
      }
      source.start(startTime)
      audioNextTime.current = startTime + buffer.duration
    } catch (e) {
      console.warn('[Audio] Playback error:', e)
    }
  }, [initAudioCtx])

  const playConnectionBeep = useCallback(() => {
    if (audioReadyRef.current) return
    audioReadyRef.current = true
    setTimeout(() => {
      const ctx = initAudioCtx()
      if (ctx) {
        try {
          const t = ctx.currentTime
          const osc = ctx.createOscillator()
          const gain = ctx.createGain()
          osc.type = 'sine'
          osc.frequency.value = 660
          gain.gain.setValueAtTime(0.04, t)
          gain.gain.exponentialRampToValueAtTime(0.001, t + 0.08)
          osc.connect(gain).connect(ctx.destination)
          osc.start(t)
          osc.stop(t + 0.08)
        } catch (e) {}
      }
    }, 500)
  }, [initAudioCtx])

  return { initAudioCtx, playPcmBytes, playConnectionBeep, stopAudio }
}
