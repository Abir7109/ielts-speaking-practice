import { useEffect, useMemo, useRef, useState } from 'react'
import { BarChart3, FileText, Mic, Play, Square, X } from 'lucide-react'
import HolographicOrb from './components/HolographicOrb'
import SlidePanel from './components/SlidePanel'
import IELTSSpeakingPanel from './components/panels/IELTSSpeakingPanel'
import IELTSDashboardPanel from './components/panels/IELTSDashboardPanel'
import IELTSReportPanel from './components/panels/IELTSReportPanel'
import useIeltsSession from './hooks/useIeltsSession'

const MONO = 'JetBrains Mono, monospace'
const GROTESK = 'Space Grotesk, sans-serif'

const TABS = [
  ['question', 'Question'],
  ['feedback', 'Feedback'],
  ['progress', 'Progress'],
  ['report', 'Report'],
]

function useOrbSize() {
  const compute = () => Math.min(420, Math.max(220, Math.round(window.innerWidth * 0.36)))
  const [size, setSize] = useState(compute)
  useEffect(() => {
    const onResize = () => setSize(compute())
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  return size
}

function PrepChip({ prepEndsAt }) {
  const [left, setLeft] = useState(null)

  useEffect(() => {
    if (!prepEndsAt) {
      setLeft(null)
      return undefined
    }
    const tick = () => {
      const ms = new Date(prepEndsAt).getTime() - Date.now()
      setLeft(Math.max(0, Math.ceil(ms / 1000)))
    }
    tick()
    const id = setInterval(tick, 500)
    return () => clearInterval(id)
  }, [prepEndsAt])

  if (left == null) return null

  return (
    <div style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 8,
      padding: '6px 12px',
      border: `1px solid ${left > 0 ? 'rgba(255, 170, 0, 0.4)' : 'rgba(255,255,255,0.12)'}`,
      background: left > 0 ? 'rgba(255, 170, 0, 0.08)' : 'rgba(255,255,255,0.03)',
    }}>
      <span style={{
        fontFamily: GROTESK,
        fontSize: 10,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        color: 'var(--soda-muted)',
      }}>
        Prep
      </span>
      <span style={{
        fontFamily: MONO,
        fontSize: 14,
        fontWeight: 700,
        color: left > 0 ? 'var(--soda-warning)' : 'var(--soda-muted)',
      }}>
        {left > 0 ? `${left}s` : 'go'}
      </span>
    </div>
  )
}

function EmptyState({ title, hint, action }) {
  return (
    <div style={{ padding: 24 }}>
      <div style={{
        fontFamily: GROTESK,
        fontSize: 11,
        letterSpacing: '0.15em',
        textTransform: 'uppercase',
        color: 'var(--soda-muted)',
        marginBottom: 8,
      }}>
        {title}
      </div>
      <div style={{
        fontFamily: GROTESK,
        fontSize: 13,
        color: 'var(--soda-text)',
        lineHeight: 1.6,
        marginBottom: action ? 16 : 0,
      }}>
        {hint}
      </div>
      {action}
    </div>
  )
}

function TranscriptView({ transcript }) {
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [transcript])

  if (!transcript.length) {
    return (
      <div style={{ padding: 20 }}>
        <div style={{
          fontFamily: GROTESK,
          fontSize: 12,
          color: 'var(--soda-muted)',
        }}>
          Conversation appears here once the examiner starts talking.
        </div>
      </div>
    )
  }

  return (
    <div style={{ padding: '12px 16px' }}>
      {transcript.map(line => {
        const isExaminer = line.sender === 'Examiner'
        return (
          <div key={line.id} style={{ marginBottom: 10 }}>
            <div style={{
              fontFamily: MONO,
              fontSize: 9,
              letterSpacing: '0.1em',
              color: isExaminer ? 'var(--soda-accent)' : 'var(--soda-success)',
              marginBottom: 3,
            }}>
              {isExaminer ? 'EXAMINER' : 'YOU'}
            </div>
            <div style={{
              fontFamily: GROTESK,
              fontSize: 13,
              lineHeight: 1.5,
              color: isExaminer ? 'var(--soda-text)' : 'rgba(224, 240, 255, 0.85)',
              borderLeft: `2px solid ${isExaminer ? 'var(--soda-accent)' : 'var(--soda-success)'}`,
              paddingLeft: 10,
            }}>
              {line.text}
            </div>
          </div>
        )
      })}
      <div ref={endRef} />
    </div>
  )
}

export default function App() {
  const session = useIeltsSession()
  const orbSize = useOrbSize()

  const {
    connected, active, phase, test, latestEvaluation, report, progress,
    transcript, micLevel, speaking, activeTool, error,
    rightOpen, rightTab, transcriptOpen, micActive, micError,
    start, stop, setRightOpen, setRightTab, setTranscriptOpen,
    showProgress, endTest, clearError,
  } = session

  const dashboardData = useMemo(() => {
    if (!progress) return null
    let days = null
    const raw = String(progress.exam_date || '').slice(0, 10)
    if (raw) {
      const target = new Date(`${raw}T00:00:00`)
      if (!Number.isNaN(target.getTime())) {
        const today = new Date()
        today.setHours(0, 0, 0, 0)
        days = Math.max(0, Math.round((target.getTime() - today.getTime()) / 86400000))
      }
    }
    return {
      progress,
      target_band: progress.target_band,
      days_until_exam: days,
    }
  }, [progress])

  const prepEndsAt = test?.payload?.kind === 'cue_card' && !test?.prep_over
    ? test?.prep_ends_at
    : null

  const statusText = !connected
    ? 'OFFLINE'
    : !active
      ? 'STANDBY'
      : speaking === 'model'
        ? 'EXAMINER SPEAKING'
        : phase === 'evaluating' || activeTool
          ? 'SCORING'
          : micActive && speaking === 'user'
            ? 'LISTENING'
            : 'MIC LIVE'

  const statusColor = !connected
    ? 'var(--soda-error)'
    : speaking === 'model'
      ? 'var(--soda-accent)'
      : phase === 'evaluating' || activeTool
        ? 'var(--soda-warning)'
        : micActive
          ? 'var(--soda-success)'
          : 'var(--soda-muted)'

  const restart = () => {
    stop()
    start()
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: '#04080B',
      color: 'var(--soda-text)',
      display: 'flex',
      flexDirection: 'column',
      position: 'relative',
      overflow: 'hidden',
    }}>
      <header style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        padding: '12px 20px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        background: 'rgba(4, 8, 11, 0.85)',
        zIndex: 30,
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
          <span style={{
            fontFamily: MONO,
            fontSize: 12,
            letterSpacing: '0.18em',
            color: 'var(--soda-accent)',
          }}>
            IELTS // SPEAKING
          </span>
          <span style={{
            fontFamily: GROTESK,
            fontSize: 10,
            letterSpacing: '0.1em',
            color: 'var(--soda-muted)',
          }}>
            AI EXAMINER
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 10px',
            border: '1px solid rgba(255,255,255,0.08)',
          }}>
            <span style={{
              width: 6,
              height: 6,
              background: statusColor,
              boxShadow: active ? `0 0 8px ${statusColor}` : 'none',
            }} />
            <span style={{
              fontFamily: MONO,
              fontSize: 9,
              letterSpacing: '0.1em',
              color: 'var(--soda-muted)',
            }}>
              {statusText}
            </span>
          </div>

          <button
            onClick={() => setTranscriptOpen(v => !v)}
            title="Transcript"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 10px',
              background: transcriptOpen ? 'rgba(0, 240, 255, 0.08)' : 'transparent',
              border: '1px solid rgba(255,255,255,0.1)',
              color: transcriptOpen ? 'var(--soda-accent)' : 'var(--soda-muted)',
              fontFamily: GROTESK,
              fontSize: 10,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              cursor: 'pointer',
            }}
          >
            <FileText size={12} />
            Log
          </button>

          <button
            onClick={() => { setRightTab('progress'); setRightOpen(true); if (active) showProgress() }}
            title="Progress"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 10px',
              background: rightOpen && rightTab === 'progress'
                ? 'rgba(0, 240, 255, 0.08)' : 'transparent',
              border: '1px solid rgba(255,255,255,0.1)',
              color: rightOpen && rightTab === 'progress'
                ? 'var(--soda-accent)' : 'var(--soda-muted)',
              fontFamily: GROTESK,
              fontSize: 10,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              cursor: 'pointer',
            }}
          >
            <BarChart3 size={12} />
            Progress
          </button>
        </div>
      </header>

      <main style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 20,
        padding: '32px 20px 40px',
        position: 'relative',
        zIndex: 1,
      }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', minHeight: 30 }}>
          {active && test?.part && (
            <div style={{
              padding: '5px 12px',
              border: '1px solid rgba(0, 240, 255, 0.25)',
              background: 'rgba(0, 240, 255, 0.05)',
              fontFamily: MONO,
              fontSize: 10,
              letterSpacing: '0.12em',
              color: 'var(--soda-accent)',
            }}>
              PART {test.part}
            </div>
          )}
          {active && test?.question_total ? (
            <div style={{
              padding: '5px 12px',
              border: '1px solid rgba(255,255,255,0.1)',
              fontFamily: MONO,
              fontSize: 10,
              letterSpacing: '0.12em',
              color: 'var(--soda-muted)',
            }}>
              Q{(test.question_index ?? 0) + 1}/{test.question_total}
            </div>
          ) : null}
          <PrepChip prepEndsAt={prepEndsAt} />
        </div>

        <HolographicOrb
          size={orbSize}
          micLevel={micLevel}
          isSpeaking={speaking === 'model'}
          isListening={active && micActive && speaking === 'user'}
          idle={!active}
        />

        <div style={{
          fontFamily: GROTESK,
          fontSize: 13,
          letterSpacing: '0.06em',
          color: 'var(--soda-muted)',
          textAlign: 'center',
          maxWidth: 520,
          minHeight: 20,
        }}>
          {!connected
            ? 'Connecting to the examiner server...'
            : !active
              ? 'Start a voice session and the examiner will greet you, then run a full IELTS speaking test.'
              : speaking === 'model'
                ? 'The examiner is speaking.'
                : phase === 'evaluating' || activeTool
                  ? 'Scoring your answer against the four IELTS criteria...'
                  : 'Answer out loud. The examiner will ask the next question automatically.'}
        </div>

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
          {!active ? (
            <button
              onClick={start}
              disabled={!connected}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '14px 30px',
                background: connected ? 'rgba(0, 240, 255, 0.1)' : 'rgba(255,255,255,0.03)',
                border: `1px solid ${connected ? 'var(--soda-accent)' : 'rgba(255,255,255,0.12)'}`,
                color: connected ? 'var(--soda-accent)' : 'var(--soda-muted)',
                fontFamily: GROTESK,
                fontSize: 13,
                fontWeight: 600,
                letterSpacing: '0.16em',
                textTransform: 'uppercase',
                cursor: connected ? 'pointer' : 'not-allowed',
                boxShadow: connected ? '0 0 24px rgba(0, 240, 255, 0.15)' : 'none',
              }}
            >
              <Play size={16} />
              Start Practice
            </button>
          ) : (
            <>
              <button
                onClick={endTest}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '12px 22px',
                  background: 'rgba(0, 240, 255, 0.08)',
                  border: '1px solid var(--soda-accent)',
                  color: 'var(--soda-accent)',
                  fontFamily: GROTESK,
                  fontSize: 11,
                  letterSpacing: '0.12em',
                  textTransform: 'uppercase',
                  cursor: 'pointer',
                }}
              >
                <BarChart3 size={14} />
                End Test
              </button>
              <button
                onClick={showProgress}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '12px 18px',
                  background: 'transparent',
                  border: '1px solid rgba(255,255,255,0.12)',
                  color: 'var(--soda-muted)',
                  fontFamily: GROTESK,
                  fontSize: 11,
                  letterSpacing: '0.12em',
                  textTransform: 'uppercase',
                  cursor: 'pointer',
                }}
              >
                <BarChart3 size={14} />
                Dashboard
              </button>
              <button
                onClick={stop}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '12px 18px',
                  background: 'transparent',
                  border: '1px solid rgba(255, 76, 102, 0.4)',
                  color: 'var(--soda-error)',
                  fontFamily: GROTESK,
                  fontSize: 11,
                  letterSpacing: '0.12em',
                  textTransform: 'uppercase',
                  cursor: 'pointer',
                }}
              >
                <Square size={13} />
                Stop
              </button>
            </>
          )}
        </div>

        {micError && (
          <div style={{
            fontFamily: MONO,
            fontSize: 10,
            color: 'var(--soda-error)',
          }}>
            Microphone error: {micError}
          </div>
        )}
      </main>

      <footer style={{
        padding: '10px 20px',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        fontFamily: MONO,
        fontSize: 9,
        letterSpacing: '0.08em',
        color: 'var(--soda-muted)',
        textAlign: 'center',
      }}>
        AI-ESTIMATED PRACTICE BANDS / NOT AN OFFICIAL IELTS RESULT / SPEAK CLEARLY AND WAIT FOR THE EXAMINER
      </footer>

      <SlidePanel
        visible={transcriptOpen}
        direction="left"
        title="TRANSCRIPT"
        icon={<FileText size={12} />}
        onClose={() => setTranscriptOpen(false)}
      >
        <TranscriptView transcript={transcript} />
      </SlidePanel>

      <SlidePanel
        visible={rightOpen}
        direction="right"
        title={rightTab.toUpperCase()}
        icon={<Mic size={12} />}
        onClose={() => setRightOpen(false)}
        scrollToTop
      >
        <div style={{
          display: 'flex',
          position: 'sticky',
          top: 0,
          background: '#04080B',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          zIndex: 2,
        }}>
          {TABS.map(([id, label]) => (
            <button
              key={id}
              onClick={() => setRightTab(id)}
              style={{
                flex: 1,
                padding: '9px 4px',
                background: rightTab === id ? 'rgba(0, 240, 255, 0.08)' : 'transparent',
                border: 'none',
                borderBottom: rightTab === id
                  ? '2px solid var(--soda-accent)' : '2px solid transparent',
                color: rightTab === id ? 'var(--soda-accent)' : 'var(--soda-muted)',
                fontFamily: GROTESK,
                fontSize: 9,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                cursor: 'pointer',
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {rightTab === 'question' && (
          test?.payload
            ? <IELTSSpeakingPanel data={test} />
            : (
              <EmptyState
                title="No active question"
                hint="Start a practice session. The examiner will open Part 1 and the current question will appear here."
              />
            )
        )}

        {rightTab === 'feedback' && (
          latestEvaluation
            ? <IELTSSpeakingPanel data={latestEvaluation} />
            : (
              <EmptyState
                title="No feedback yet"
                hint="After each spoken answer the examiner scores fluency, vocabulary, grammar and pronunciation. Your latest evaluation appears here."
              />
            )
        )}

        {rightTab === 'progress' && (
          dashboardData
            ? <IELTSDashboardPanel data={dashboardData} />
            : (
              <EmptyState
                title="No history yet"
                hint="Finish a practice test to build your band history and track weak areas over time."
                action={active ? (
                  <button
                    onClick={showProgress}
                    style={{
                      padding: '10px 16px',
                      background: 'rgba(0, 240, 255, 0.08)',
                      border: '1px solid var(--soda-accent)',
                      color: 'var(--soda-accent)',
                      fontFamily: GROTESK,
                      fontSize: 10,
                      letterSpacing: '0.12em',
                      textTransform: 'uppercase',
                      cursor: 'pointer',
                    }}
                  >
                    Load Progress
                  </button>
                ) : null}
              />
            )
        )}

        {rightTab === 'report' && (
          <IELTSReportPanel report={report} onRestart={restart} />
        )}
      </SlidePanel>

      {error && (
        <div style={{
          position: 'fixed',
          left: '50%',
          bottom: 24,
          transform: 'translateX(-50%)',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '10px 14px',
          background: '#0a1218',
          border: '1px solid rgba(255, 68, 102, 0.5)',
          boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
          zIndex: 60,
          maxWidth: 'calc(100vw - 40px)',
        }}>
          <span style={{
            fontFamily: GROTESK,
            fontSize: 12,
            color: 'var(--soda-error)',
          }}>
            {error}
          </span>
          <button
            onClick={clearError}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--soda-muted)',
              cursor: 'pointer',
              display: 'flex',
            }}
          >
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  )
}
