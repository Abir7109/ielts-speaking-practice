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

function useViewport() {
  const read = () => ({ w: window.innerWidth, h: window.innerHeight })
  const [vp, setVp] = useState(read)
  useEffect(() => {
    const onResize = () => setVp(read())
    window.addEventListener('resize', onResize)
    window.addEventListener('orientationchange', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      window.removeEventListener('orientationchange', onResize)
    }
  }, [])
  return vp
}

// Constrained by width AND height: a phone held in landscape has ~360px of vertical
// space, and a 220px orb there pushes Start/Stop off the screen.
function orbSizeFor(w, h, isPhone) {
  return Math.round(Math.max(
    150,
    Math.min(isPhone ? 400 : 420, Math.min(w * (isPhone ? 0.46 : 0.36), h * 0.32)),
  ))
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
  const { w: viewportW, h: viewportH } = useViewport()
  const isPhone = viewportW <= 768
  const orbSize = orbSizeFor(viewportW, viewportH, isPhone)

  const {
    connected, active, phase, test, latestEvaluation, report, progress,
    transcript, micLevel, speaking, activeTool, error,
    rightOpen, rightTab, transcriptOpen, micActive, micError,
    start, stop, setRightOpen, setRightTab, setTranscriptOpen,
    showProgress, endTest, clearError,
  } = session

  const sheetOpen = rightOpen || transcriptOpen

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
        ? (isPhone ? 'SPEAKING' : 'EXAMINER SPEAKING')
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

  const actionBtn = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: isPhone ? 6 : 8,
    minHeight: 48,
    flex: isPhone ? '1 1 auto' : undefined,
    padding: isPhone ? '0 14px' : '12px 18px',
    fontFamily: GROTESK,
    fontSize: isPhone ? 10 : 11,
    letterSpacing: '0.12em',
    textTransform: 'uppercase',
    cursor: 'pointer',
  }

  const headerBtn = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    minWidth: isPhone ? 44 : undefined,
    minHeight: isPhone ? 44 : 32,
    padding: isPhone ? '0 12px' : '6px 10px',
    border: '1px solid rgba(255,255,255,0.1)',
    fontFamily: GROTESK,
    fontSize: 10,
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
    cursor: 'pointer',
  }

  const restart = () => {
    stop()
    start()
  }

  return (
    <div className="app-shell" style={{
      background: '#04080B',
      color: 'var(--soda-text)',
      display: 'flex',
      flexDirection: 'column',
      position: 'relative',
    }}>
      <header style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: isPhone ? 8 : 12,
        padding: isPhone ? '8px 12px' : '12px 20px',
        paddingTop: `max(${isPhone ? 8 : 12}px, env(safe-area-inset-top))`,
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        background: 'rgba(4, 8, 11, 0.85)',
        zIndex: 30,
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
          <span style={{
            fontFamily: MONO,
            fontSize: isPhone ? 11 : 12,
            letterSpacing: '0.18em',
            color: 'var(--soda-accent)',
          }}>
            IELTS // SPEAKING
          </span>
          {!isPhone && (
            <span style={{
              fontFamily: GROTESK,
              fontSize: 10,
              letterSpacing: '0.1em',
              color: 'var(--soda-muted)',
            }}>
              AI EXAMINER
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: isPhone ? 6 : 10 }}>
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
            aria-label="Transcript"
            style={{
              ...headerBtn,
              background: transcriptOpen ? 'rgba(0, 240, 255, 0.08)' : 'transparent',
              color: transcriptOpen ? 'var(--soda-accent)' : 'var(--soda-muted)',
            }}
          >
            <FileText size={isPhone ? 16 : 12} />
            {!isPhone && 'Log'}
          </button>

          <button
            onClick={() => { setRightTab('progress'); setRightOpen(true); if (active) showProgress() }}
            title="Progress"
            aria-label="Progress dashboard"
            style={{
              ...headerBtn,
              background: rightOpen && rightTab === 'progress'
                ? 'rgba(0, 240, 255, 0.08)' : 'transparent',
              color: rightOpen && rightTab === 'progress'
                ? 'var(--soda-accent)' : 'var(--soda-muted)',
            }}
          >
            <BarChart3 size={isPhone ? 16 : 12} />
            {!isPhone && 'Progress'}
          </button>
        </div>
      </header>

      <main style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: isPhone && sheetOpen ? 'flex-start' : 'center',
        gap: isPhone ? 14 : 20,
        padding: isPhone ? '16px 14px 20px' : '32px 20px 40px',
        position: 'relative',
        zIndex: 1,
      }}>
        <div style={{
          display: 'flex',
          gap: 8,
          alignItems: 'center',
          flexWrap: 'wrap',
          justifyContent: 'center',
          minHeight: 30,
        }}>
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

        {!isPhone || !sheetOpen ? (
          <div style={{
            fontFamily: GROTESK,
            fontSize: isPhone ? 12 : 13,
            letterSpacing: '0.06em',
            color: 'var(--soda-muted)',
            textAlign: 'center',
            maxWidth: isPhone ? '100%' : 520,
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
        ) : null}

        <div style={{
          display: 'flex',
          gap: isPhone ? 8 : 10,
          flexWrap: 'wrap',
          justifyContent: 'center',
          width: '100%',
          maxWidth: isPhone ? 420 : undefined,
        }}>
          {!active ? (
            <button
              onClick={start}
              disabled={!connected}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 10,
                minHeight: 52,
                padding: isPhone ? '0 24px' : '14px 30px',
                margin: '0 auto',
                background: connected ? 'rgba(0, 240, 255, 0.1)' : 'rgba(255,255,255,0.03)',
                border: `1px solid ${connected ? 'var(--soda-accent)' : 'rgba(255,255,255,0.12)'}`,
                color: connected ? 'var(--soda-accent)' : 'var(--soda-muted)',
                fontFamily: GROTESK,
                fontSize: isPhone ? 12 : 13,
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
                  ...actionBtn,
                  padding: isPhone ? '0 14px' : '12px 22px',
                  background: 'rgba(0, 240, 255, 0.08)',
                  border: '1px solid var(--soda-accent)',
                  color: 'var(--soda-accent)',
                }}
              >
                <BarChart3 size={14} />
                End Test
              </button>
              <button
                onClick={showProgress}
                style={{
                  ...actionBtn,
                  background: 'transparent',
                  border: '1px solid rgba(255,255,255,0.12)',
                  color: 'var(--soda-muted)',
                }}
              >
                <BarChart3 size={14} />
                Dashboard
              </button>
              <button
                onClick={stop}
                style={{
                  ...actionBtn,
                  background: 'transparent',
                  border: '1px solid rgba(255, 76, 102, 0.4)',
                  color: 'var(--soda-error)',
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
        padding: isPhone ? '8px 12px' : '10px 20px',
        paddingBottom: `max(${isPhone ? 8 : 10}px, env(safe-area-inset-bottom))`,
        borderTop: '1px solid rgba(255,255,255,0.06)',
        fontFamily: MONO,
        fontSize: isPhone ? 8 : 9,
        letterSpacing: '0.08em',
        color: 'var(--soda-muted)',
        textAlign: 'center',
      }}>
        AI-ESTIMATED PRACTICE BANDS / NOT AN OFFICIAL IELTS RESULT / SPEAK CLEARLY AND WAIT FOR THE EXAMINER
      </footer>

      <SlidePanel
        visible={transcriptOpen}
        direction={isPhone ? 'bottom' : 'left'}
        title="TRANSCRIPT"
        icon={<FileText size={12} />}
        onClose={() => setTranscriptOpen(false)}
      >
        <TranscriptView transcript={transcript} />
      </SlidePanel>

      <SlidePanel
        visible={rightOpen}
        direction={isPhone ? 'bottom' : 'right'}
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
                minHeight: isPhone ? 44 : undefined,
                padding: isPhone ? '12px 2px' : '9px 4px',
                background: rightTab === id ? 'rgba(0, 240, 255, 0.08)' : 'transparent',
                border: 'none',
                borderBottom: rightTab === id
                  ? '2px solid var(--soda-accent)' : '2px solid transparent',
                color: rightTab === id ? 'var(--soda-accent)' : 'var(--soda-muted)',
                fontFamily: GROTESK,
                fontSize: isPhone ? 10 : 9,
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
                      minHeight: 44,
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
          bottom: `calc(${isPhone ? 12 : 24}px + env(safe-area-inset-bottom))`,
          transform: 'translateX(-50%)',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '10px 14px',
          background: '#0a1218',
          border: '1px solid rgba(255, 68, 102, 0.5)',
          boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
          zIndex: 60,
          maxWidth: 'calc(100vw - 24px)',
        }}>
          <span style={{
            fontFamily: GROTESK,
            fontSize: isPhone ? 11 : 12,
            color: 'var(--soda-error)',
          }}>
            {error}
          </span>
          <button
            onClick={clearError}
            aria-label="Dismiss error"
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--soda-muted)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              minWidth: 44,
              minHeight: 44,
            }}
          >
            <X size={16} />
          </button>
        </div>
      )}
    </div>
  )
}
