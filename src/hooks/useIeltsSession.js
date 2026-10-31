import { useCallback, useEffect, useRef, useState } from 'react'
import socket from '../services/SocketService'
import useBrowserMic from '../services/useBrowserMic'
import useAudioPlayback from './useAudioPlayback'

const CLIENT_ID_KEY = 'ielts_client_id'

const TAB_BY_PANEL = {
  IELTSSpeaking: 'question',
  IELTSDashboard: 'progress',
  IELTSReport: 'report',
}

// Below this width both panels render as full-width bottom sheets, so only one of
// them can be visible at a time — opening the other must dismiss the first.
const SHEET_WIDTH = 768
const isSheetLayout = () => window.innerWidth <= SHEET_WIDTH

function getClientId() {
  try {
    let id = window.localStorage.getItem(CLIENT_ID_KEY)
    if (!id) {
      id = window.crypto?.randomUUID
        ? window.crypto.randomUUID()
        : `c_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`
      window.localStorage.setItem(CLIENT_ID_KEY, id)
    }
    return id
  } catch {
    return null
  }
}

export default function useIeltsSession() {
  const [connected, setConnected] = useState(socket.connected)
  const [active, setActive] = useState(false)
  const [phase, setPhase] = useState('idle')
  const [test, setTest] = useState(null)
  const [evaluations, setEvaluations] = useState([])
  const [report, setReport] = useState(null)
  const [progress, setProgress] = useState(null)
  const [transcript, setTranscript] = useState([])
  const [micLevel, setMicLevel] = useState(0)
  const [speaking, setSpeaking] = useState('idle')
  const [activeTool, setActiveTool] = useState(null)
  const [error, setError] = useState(null)
  const [rightOpen, setRightOpen] = useState(false)
  const [rightTab, setRightTab] = useState('question')
  const [transcriptOpen, setTranscriptOpen] = useState(false)

  const pendingStart = useRef(false)
  const activeRef = useRef(false)
  activeRef.current = active

  const onPlaybackDrained = useCallback(() => {
    if (socket.connected) socket.emit('playback_drained')
    setSpeaking(prev => (prev === 'model' ? 'idle' : prev))
  }, [])

  const { initAudioCtx, playPcmBytes, playConnectionBeep, stopAudio } = useAudioPlayback({ onDrained: onPlaybackDrained })
  const mic = useBrowserMic(socket)

  // On phones both panels are the same full-width sheet, so they cannot share the
  // screen. The question/feedback panel wins; the transcript steps aside.
  useEffect(() => {
    if (isSheetLayout() && transcriptOpen && rightOpen) setTranscriptOpen(false)
  }, [transcriptOpen, rightOpen])

  useEffect(() => {
    const pushTranscript = (sender, text, final = false) => {
      if (!text) return
      setTranscript(prev => {
        const last = prev[prev.length - 1]
        if (!final && last && last.sender === sender && !last.final) {
          const merged = prev.slice()
          merged[merged.length - 1] = { ...last, text: last.text + text }
          return merged
        }
        const next = [...prev, {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          sender,
          text,
          final,
        }]
        return next.length > 300 ? next.slice(next.length - 300) : next
      })
    }

    const onConnect = () => {
      setConnected(true)
      if (pendingStart.current) {
        pendingStart.current = false
        socket.emit('start_audio', { client_id: getClientId() })
      } else if (activeRef.current) {
        socket.emit('start_audio', { client_id: getClientId() })
      }
    }

    const onDisconnect = () => {
      setConnected(false)
      setSpeaking('idle')
    }

    const onConnectError = () => {
      setConnected(false)
      setError('Cannot reach the examiner server. Check VITE_BACKEND_URL.')
    }

    const onAudio = (data) => {
      if (data?.data) playPcmBytes(data.data)
    }

    const onMicLevel = (data) => {
      setMicLevel(Number(data?.level) || 0)
    }

    const onSpeaking = (data) => {
      setSpeaking(data?.state || 'idle')
    }

    const onTranscription = (data) => {
      pushTranscript(data?.sender || 'Candidate', data?.text || '', Boolean(data?.final))
    }

    const onTestState = (data) => {
      if (!data) return
      setTest(data)
      if (data.phase) setPhase(data.phase)
      if (data.report) setReport(data.report)
      if (data.phase === 'finished' && data.report) {
        setRightTab('report')
        setRightOpen(true)
      } else if (data.payload && data.phase !== 'idle') {
        setRightTab('question')
      }
    }

    const onEvaluation = (data) => {
      const ev = data?.evaluation
      if (!ev) return
      setEvaluations(prev => [ev, ...prev].slice(0, 30))
      setRightTab('feedback')
      setRightOpen(true)
    }

    const onReport = (data) => {
      if (!data?.report) return
      setReport(data.report)
      setRightTab('report')
      setRightOpen(true)
    }

    const onProgress = (data) => {
      if (data?.progress) setProgress(data.progress)
    }

    const onToolStatus = (data) => {
      if (!data?.tool) return
      setActiveTool(data.status === 'start' ? data.tool : null)
    }

    const onPanelOpen = (data) => {
      const tab = TAB_BY_PANEL[data?.panelType]
      if (!tab) return
      setRightTab(tab)
      setRightOpen(true)
    }

    const onClosePanel = () => {
      setRightOpen(false)
      setTranscriptOpen(false)
    }

    const onError = (data) => {
      setError(data?.msg || data?.message || 'Something went wrong.')
      setActiveTool(null)
    }

    const onConnectionState = (data) => {
      if (data?.connected === false && data?.reason) {
        setError(`Examiner connection closed (${data.reason}).`)
      }
    }

    socket.on('connect', onConnect)
    socket.on('disconnect', onDisconnect)
    socket.on('connect_error', onConnectError)
    socket.on('audio_data', onAudio)
    socket.on('mic_level', onMicLevel)
    socket.on('speaking_state', onSpeaking)
    socket.on('transcription', onTranscription)
    socket.on('test_state', onTestState)
    socket.on('answer_evaluated', onEvaluation)
    socket.on('report_ready', onReport)
    socket.on('client_progress', onProgress)
    socket.on('tool_status', onToolStatus)
    socket.on('panel_open', onPanelOpen)
    socket.on('close_panel', onClosePanel)
    socket.on('error', onError)
    socket.on('connection_state', onConnectionState)

    if (!socket.connected) socket.connect()

    return () => {
      socket.off('connect', onConnect)
      socket.off('disconnect', onDisconnect)
      socket.off('connect_error', onConnectError)
      socket.off('audio_data', onAudio)
      socket.off('mic_level', onMicLevel)
      socket.off('speaking_state', onSpeaking)
      socket.off('transcription', onTranscription)
      socket.off('test_state', onTestState)
      socket.off('answer_evaluated', onEvaluation)
      socket.off('report_ready', onReport)
      socket.off('client_progress', onProgress)
      socket.off('tool_status', onToolStatus)
      socket.off('panel_open', onPanelOpen)
      socket.off('close_panel', onClosePanel)
      socket.off('error', onError)
      socket.off('connection_state', onConnectionState)
    }
  }, [playPcmBytes])

  const start = useCallback(async () => {
    if (activeRef.current) return
    setError(null)
    setReport(null)
    setProgress(null)
    setEvaluations([])
    setTranscript([])
    setTest(null)
    setPhase('idle')
    setActiveTool(null)
    setRightTab('question')
    initAudioCtx()
    playConnectionBeep()
    await mic.start()
    setActive(true)
    // The transcript is a convenience surface; on a phone it would cover the orb
    // and the Stop button at the exact moment the candidate needs to speak.
    setTranscriptOpen(!isSheetLayout())
    if (socket.connected) {
      socket.emit('start_audio', { client_id: getClientId() })
    } else {
      pendingStart.current = true
      socket.connect()
    }
  }, [initAudioCtx, playConnectionBeep, mic])

  const stop = useCallback(() => {
    pendingStart.current = false
    mic.stop()
    stopAudio()
    if (socket.connected) socket.emit('stop_audio')
    setActive(false)
    setSpeaking('idle')
    setPhase('idle')
    setActiveTool(null)
  }, [mic, stopAudio])

  const runTool = useCallback((tool, args = {}) => {
    if (!socket.connected) return
    socket.emit('run_ielts_tool', { tool, args })
  }, [])

  const showProgress = useCallback(() => runTool('get_progress'), [runTool])
  const endTest = useCallback(() => runTool('finish_test'), [runTool])
  const setGoal = useCallback((targetBand) => {
    runTool('set_goal', { target_band: Number(targetBand) })
  }, [runTool])

  return {
    connected,
    active,
    phase,
    test,
    latestEvaluation: evaluations[0] || null,
    evaluations,
    report,
    progress,
    transcript,
    micLevel,
    speaking,
    activeTool,
    error,
    rightOpen,
    rightTab,
    transcriptOpen,
    micActive: mic.micActive,
    micError: mic.micError,
    start,
    stop,
    setRightOpen,
    setRightTab,
    setTranscriptOpen,
    showProgress,
    endTest,
    setGoal,
    clearError: () => setError(null),
  }
}
