import React, { useEffect, useState } from 'react'

function useCountdown(target) {
  const [left, setLeft] = useState(() => secondsLeft(target))
  useEffect(() => {
    setLeft(secondsLeft(target))
    if (!target) return undefined
    const id = setInterval(() => setLeft(secondsLeft(target)), 500)
    return () => clearInterval(id)
  }, [target])
  return left
}

function secondsLeft(target) {
  if (!target) return null
  const ms = new Date(target).getTime() - Date.now()
  return Math.max(0, Math.ceil(ms / 1000))
}

function QuestionView({ data }) {
  const payload = data.payload || data
  const part = payload.part || data.part
  const isPrep = payload.kind === 'cue_card'
  const prepLeft = useCountdown(isPrep && !data.prep_over ? data.prep_ends_at : null)

  return (
    <div style={{ padding: 20, height: '100%', overflowY: 'auto' }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        marginBottom: 8,
      }}>
        <span style={{
          fontFamily: 'Space Grotesk, sans-serif',
          fontSize: 11, color: 'var(--soda-accent)',
          letterSpacing: '0.15em',
        }}>
          SPEAKING PART {part || '—'}
        </span>
        {data.question_index != null && data.question_total ? (
          <span style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 10, color: 'var(--soda-muted)',
          }}>
            Q{data.question_index + 1}/{data.question_total}
          </span>
        ) : null}
      </div>

      {data.phase === 'evaluating' && (
        <div style={{
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 10,
          color: 'var(--soda-warning)',
          marginBottom: 12,
          letterSpacing: '0.1em',
        }}>
          SCORING THIS PART...
        </div>
      )}

      {isPrep ? (
        <div style={{
          background: 'rgba(0, 240, 255, 0.04)',
          border: '1px solid rgba(0, 240, 255, 0.2)',
          padding: 20, marginBottom: 16,
        }}>
          <div style={{
            fontFamily: 'Space Grotesk, sans-serif',
            fontSize: 16, fontWeight: 600,
            color: 'var(--soda-text)', marginBottom: 16,
          }}>
            {payload.topic || 'Cue Card'}
          </div>
          <div style={{
            fontFamily: 'Space Grotesk, sans-serif',
            fontSize: 12, color: 'var(--soda-muted)',
            marginBottom: 6, textTransform: 'uppercase',
            letterSpacing: '0.08em',
          }}>
            You should say:
          </div>
          {(payload.bullet_points || payload.points || []).map((point, i) => (
            <div key={i} style={{ display: 'flex', gap: 10, padding: '5px 0' }}>
              <span style={{ color: 'var(--soda-accent)' }}>•</span>
              <span style={{
                fontFamily: 'Space Grotesk, sans-serif',
                fontSize: 13, color: 'var(--soda-text)',
              }}>
                {point}
              </span>
            </div>
          ))}
        </div>
      ) : payload.question ? (
        <div style={{
          background: 'rgba(0, 240, 255, 0.04)',
          border: '1px solid rgba(0, 240, 255, 0.2)',
          padding: 20, marginBottom: 16,
        }}>
          <div style={{
            fontFamily: 'Space Grotesk, sans-serif',
            fontSize: 15,
            color: 'var(--soda-text)',
            lineHeight: 1.5,
          }}>
            {payload.question}
          </div>
        </div>
      ) : null}

      {isPrep && (
        <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
          <div style={{
            flex: 1,
            background: prepLeft > 0 ? 'rgba(255, 170, 0, 0.08)' : 'rgba(255,255,255,0.03)',
            border: `1px solid ${prepLeft > 0 ? 'rgba(255, 170, 0, 0.4)' : 'rgba(255,255,255,0.08)'}`,
            padding: 12,
          }}>
            <div style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 22,
              color: prepLeft > 0 ? 'var(--soda-warning)' : 'var(--soda-muted)',
            }}>
              {prepLeft != null ? `${prepLeft}s` : '—'}
            </div>
            <div style={{
              fontFamily: 'Space Grotesk, sans-serif',
              fontSize: 10, color: 'var(--soda-muted)',
            }}>
              {prepLeft > 0 ? 'PREP TIME LEFT' : 'PREP COMPLETE'}
            </div>
          </div>
          <div style={{
            flex: 1,
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.08)',
            padding: 12,
          }}>
            <div style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 22, color: 'var(--soda-accent)',
            }}>
              {payload.speak_time_seconds || 120}s
            </div>
            <div style={{
              fontFamily: 'Space Grotesk, sans-serif',
              fontSize: 10, color: 'var(--soda-muted)',
            }}>
              SPEAK TIME
            </div>
          </div>
        </div>
      )}

      {payload.follow_up_part3?.length > 0 && (
        <div>
          <div style={{
            fontFamily: 'Space Grotesk, sans-serif',
            fontSize: 11, color: 'var(--soda-muted)',
            letterSpacing: '0.1em', textTransform: 'uppercase',
            marginBottom: 10,
          }}>
            Follow-up Questions
          </div>
          {payload.follow_up_part3.map((q, i) => (
            <div key={i} style={{
              background: 'rgba(0, 240, 255, 0.03)',
              border: '1px solid rgba(0, 240, 255, 0.1)',
              padding: 10, marginBottom: 8,
            }}>
              <span style={{
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: 11, color: 'var(--soda-accent)',
              }}>
                Q{i + 1}:{' '}
              </span>
              <span style={{
                fontFamily: 'Space Grotesk, sans-serif',
                fontSize: 13, color: 'var(--soda-text)',
              }}>
                {q}
              </span>
            </div>
          ))}
        </div>
      )}

      {data.phase === 'idle' && (
        <div style={{
          fontFamily: 'Space Grotesk, sans-serif',
          fontSize: 12,
          color: 'var(--soda-muted)',
          marginTop: 18,
        }}>
          Listen to the examiner, then answer out loud.
        </div>
      )}
    </div>
  )
}

export default function IELTSSpeakingPanel({ data }) {
  const [tab, setTab] = useState('scores')

  if (!data) return null

  const isTestState = Boolean(data.payload) || Boolean(data.phase)

  if (isTestState) return <QuestionView data={data} />

  const { band_scores, overall_band, part, strengths, improvements,
          vocabulary_feedback, grammar_errors, corrected_transcript,
          pronunciation_detail, band7_tip, filler_words_count,
          criterion_feedback, why_band_summary, degraded, evaluator } = data

  const estimated = evaluator === 'heuristic'
    || (Array.isArray(degraded) && degraded.includes('text-evaluator-unavailable'))
  const critFeedback = criterion_feedback || {}

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{
        padding: '16px 20px',
        borderBottom: '1px solid rgba(255,255,255,0.06)'
      }}>
        <div style={{
          fontFamily: 'Space Grotesk, sans-serif',
          fontSize: 11, color: 'var(--soda-accent)',
          letterSpacing: '0.15em', marginBottom: 4
        }}>
          SPEAKING EVALUATION{part ? ` — PART ${part}` : ''}
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
          <span style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 40, fontWeight: 700,
            color: overall_band >= 7
              ? 'var(--soda-success)' : 'var(--soda-warning)'
          }}>
            {overall_band}
          </span>
          <span style={{
            fontFamily: 'Space Grotesk, sans-serif',
            fontSize: 14, color: 'var(--soda-muted)'
          }}>
            {part ? `Part ${part} Band` : 'Overall Band'}
          </span>
          {filler_words_count > 0 && (
            <span style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 11, color: 'var(--soda-error)',
              background: 'rgba(255,51,85,0.1)',
              padding: '2px 8px'
            }}>
              {filler_words_count} filler words
            </span>
          )}
        </div>
        <div style={{
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 9,
          color: estimated ? 'var(--soda-warning)' : 'var(--soda-success)',
          letterSpacing: '0.08em',
          marginTop: 6,
          textAlign: 'right',
        }}>
          {estimated
            ? 'LOCAL ESTIMATE — AI SCORER OFFLINE'
            : `SCORED BY ${String(evaluator || 'gemini').toUpperCase()}`}
        </div>
      </div>

      {estimated && (
        <div style={{
          padding: '8px 20px',
          background: 'rgba(255, 170, 0, 0.08)',
          borderBottom: '1px solid rgba(255, 170, 0, 0.25)',
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 10, color: 'var(--soda-warning)',
          lineHeight: 1.6, letterSpacing: '0.04em'
        }}>
          AUTOMATED SCORING UNAVAILABLE — these bands are rough local estimates.
          Configure GEMINI_API_KEY on the server for real examiner scoring.
        </div>
      )}

      <div style={{ display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        {['scores', 'feedback', 'grammar', 'vocab'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            flex: 1, padding: '8px 4px',
            background: tab === t ? 'rgba(0, 240, 255, 0.08)' : 'transparent',
            border: 'none',
            borderBottom: tab === t
              ? '2px solid var(--soda-accent)' : '2px solid transparent',
            color: tab === t ? 'var(--soda-accent)' : 'var(--soda-muted)',
            fontFamily: 'Space Grotesk, sans-serif',
            fontSize: 10, letterSpacing: '0.08em',
            textTransform: 'uppercase', cursor: 'pointer'
          }}>
            {t}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        {tab === 'scores' && band_scores && (
          <div>
            {[
              ['Fluency & Coherence', band_scores.fluency_coherence, 'fluency_coherence'],
              ['Lexical Resource', band_scores.lexical_resource, 'lexical_resource'],
              ['Grammatical Range', band_scores.grammatical_range, 'grammatical_range'],
              ['Pronunciation', band_scores.pronunciation, 'pronunciation']
            ].map(([label, score, key]) => {
              const color = score >= 7 ? 'var(--soda-success)' :
                           score >= 6 ? 'var(--soda-accent)' :
                           score >= 5 ? 'var(--soda-warning)' : 'var(--soda-error)'
              const fb = critFeedback[key] || {}
              return (
                <div key={key} style={{ marginBottom: 10 }}>
                  <div style={{
                    display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center', padding: '10px 12px',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.07)'
                  }}>
                    <span style={{
                      fontFamily: 'Space Grotesk, sans-serif',
                      fontSize: 12, color: 'var(--soda-muted)'
                    }}>
                      {label}
                    </span>
                    <span style={{
                      fontFamily: 'JetBrains Mono, monospace',
                      fontSize: 18, fontWeight: 700, color
                    }}>
                      {score}
                    </span>
                  </div>
                  {(fb.reason || fb.next_step) && (
                    <div style={{
                      padding: '8px 12px',
                      background: 'rgba(255,255,255,0.02)',
                      border: '1px solid rgba(255,255,255,0.06)',
                      borderTop: 'none'
                    }}>
                      {fb.reason && (
                        <div style={{
                          fontFamily: 'Space Grotesk, sans-serif',
                          fontSize: 11, color: 'var(--soda-text)',
                          lineHeight: 1.5, marginBottom: 4
                        }}>
                          <span style={{ color: 'var(--soda-warning)' }}>WHY: </span>
                          {fb.reason}
                        </div>
                      )}
                      {fb.evidence && (
                        <div style={{
                          fontFamily: 'JetBrains Mono, monospace',
                          fontSize: 10, color: 'var(--soda-muted)',
                          fontStyle: 'italic', marginBottom: 4
                        }}>
                          "{fb.evidence}"
                        </div>
                      )}
                      {fb.next_step && (
                        <div style={{
                          fontFamily: 'Space Grotesk, sans-serif',
                          fontSize: 11, color: 'var(--soda-accent)',
                          lineHeight: 1.5
                        }}>
                          <span style={{ letterSpacing: '0.08em' }}>NEXT: </span>
                          {fb.next_step}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}

            {pronunciation_detail && (
              <div style={{
                marginTop: 12,
                background: 'rgba(0, 240, 255, 0.03)',
                border: '1px solid rgba(0, 240, 255, 0.15)',
                padding: 12
              }}>
                <div style={{
                  fontFamily: 'Space Grotesk, sans-serif',
                  fontSize: 10, color: 'var(--soda-accent)',
                  letterSpacing: '0.1em', textTransform: 'uppercase',
                  marginBottom: 6
                }}>
                  Pronunciation Notes
                </div>
                <div style={{
                  fontFamily: 'Space Grotesk, sans-serif',
                  fontSize: 12, color: 'var(--soda-text)', lineHeight: 1.5
                }}>
                  {typeof pronunciation_detail === 'string'
                    ? pronunciation_detail
                    : pronunciation_detail.notes ||
                      pronunciation_detail.feedback ||
                      JSON.stringify(pronunciation_detail)}
                </div>
                {Array.isArray(pronunciation_detail.problem_words) &&
                  pronunciation_detail.problem_words.length > 0 && (
                  <div style={{
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: 11, color: 'var(--soda-warning)', marginTop: 8
                  }}>
                    Watch: {pronunciation_detail.problem_words.join(', ')}
                  </div>
                )}
              </div>
            )}

            {band7_tip && (
              <div style={{
                marginTop: 12,
                background: 'rgba(0, 255, 136, 0.05)',
                border: '1px solid rgba(0, 255, 136, 0.2)',
                padding: 12
              }}>
                <div style={{
                  fontFamily: 'Space Grotesk, sans-serif',
                  fontSize: 10, color: 'var(--soda-success)',
                  letterSpacing: '0.1em', textTransform: 'uppercase',
                  marginBottom: 6
                }}>
                  Top Tip to Reach Band 7
                </div>
                <div style={{
                  fontFamily: 'Space Grotesk, sans-serif',
                  fontSize: 13, color: 'var(--soda-text)'
                }}>
                  {band7_tip}
                </div>
              </div>
            )}
          </div>
        )}

        {tab === 'feedback' && (
          <div>
            {why_band_summary && (
              <div style={{
                background: 'rgba(0, 240, 255, 0.04)',
                border: '1px solid rgba(0, 240, 255, 0.18)',
                padding: 10, marginBottom: 14
              }}>
                <div style={{
                  fontFamily: 'Space Grotesk, sans-serif',
                  fontSize: 10, color: 'var(--soda-accent)',
                  letterSpacing: '0.1em', textTransform: 'uppercase',
                  marginBottom: 5
                }}>
                  Why this band
                </div>
                <div style={{
                  fontFamily: 'Space Grotesk, sans-serif',
                  fontSize: 12, color: 'var(--soda-text)',
                  lineHeight: 1.55
                }}>
                  {why_band_summary}
                </div>
              </div>
            )}
            {strengths?.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{
                  fontFamily: 'Space Grotesk, sans-serif',
                  fontSize: 11, color: 'var(--soda-success)',
                  letterSpacing: '0.1em', textTransform: 'uppercase',
                  marginBottom: 8
                }}>
                  Strengths
                </div>
                {strengths.map((s, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, padding: '5px 0' }}>
                    <span style={{ color: 'var(--soda-success)' }}>✓</span>
                    <span style={{
                      fontFamily: 'Space Grotesk, sans-serif',
                      fontSize: 12, color: 'var(--soda-text)'
                    }}>
                      {s}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {improvements?.length > 0 && (
              <div>
                <div style={{
                  fontFamily: 'Space Grotesk, sans-serif',
                  fontSize: 11, color: 'var(--soda-warning)',
                  letterSpacing: '0.1em', textTransform: 'uppercase',
                  marginBottom: 8
                }}>
                  Improvements
                </div>
                {improvements.map((imp, i) => (
                  <div key={i} style={{
                    background: 'rgba(255, 170, 0, 0.05)',
                    border: '1px solid rgba(255, 170, 0, 0.15)',
                    padding: 10, marginBottom: 8
                  }}>
                    <div style={{
                      fontFamily: 'Space Grotesk, sans-serif',
                      fontSize: 12, color: 'var(--soda-warning)',
                      marginBottom: 6
                    }}>
                      {imp.issue}
                    </div>
                    {imp.example_from_response && (
                      <div style={{
                        fontFamily: 'JetBrains Mono, monospace',
                        fontSize: 11, color: 'var(--soda-error)',
                        textDecoration: 'line-through', fontStyle: 'italic',
                        marginBottom: 3
                      }}>
                        "{imp.example_from_response}"
                      </div>
                    )}
                    {imp.better_version && (
                      <div style={{
                        fontFamily: 'JetBrains Mono, monospace',
                        fontSize: 11, color: 'var(--soda-success)',
                        fontStyle: 'italic', marginBottom: 4
                      }}>
                        ✓ "{imp.better_version}"
                      </div>
                    )}
                    {imp.band_impact && (
                      <div style={{
                        fontFamily: 'Space Grotesk, sans-serif',
                        fontSize: 10, color: 'var(--soda-accent)'
                      }}>
                        {imp.band_impact}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'grammar' && (
          <div>
            {grammar_errors?.length === 0 ? (
              <div style={{
                fontFamily: 'Space Grotesk, sans-serif',
                fontSize: 13, color: 'var(--soda-success)',
                textAlign: 'center', padding: 20
              }}>
                No grammar errors detected!
              </div>
            ) : (
              (grammar_errors || []).map((err, i) => (
                <div key={i} style={{
                  background: 'rgba(255, 51, 85, 0.05)',
                  border: '1px solid rgba(255, 51, 85, 0.2)',
                  padding: 10, marginBottom: 8
                }}>
                  <div style={{
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: 11, color: 'var(--soda-error)',
                    textDecoration: 'line-through', marginBottom: 4
                  }}>
                    {err.error}
                  </div>
                  <div style={{
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: 11, color: 'var(--soda-success)', marginBottom: 4
                  }}>
                    ✓ {err.correction}
                  </div>
                  <div style={{
                    fontFamily: 'Space Grotesk, sans-serif',
                    fontSize: 10, color: 'var(--soda-muted)',
                    textTransform: 'uppercase'
                  }}>
                    {err.type}
                  </div>
                </div>
              ))
            )}

            {corrected_transcript && (
              <div style={{
                marginTop: 12,
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.08)',
                padding: 12
              }}>
                <div style={{
                  fontFamily: 'Space Grotesk, sans-serif',
                  fontSize: 10, color: 'var(--soda-muted)',
                  letterSpacing: '0.1em', textTransform: 'uppercase',
                  marginBottom: 6
                }}>
                  Corrected Transcript
                </div>
                <div style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: 11, color: 'var(--soda-text)',
                  lineHeight: 1.6
                }}>
                  {corrected_transcript}
                </div>
              </div>
            )}
          </div>
        )}

        {tab === 'vocab' && vocabulary_feedback && (
          <div>
            {(vocabulary_feedback.suggested_upgrades || []).map((s, i) => (
              <div key={i} style={{
                display: 'flex', gap: 8, padding: '7px 0',
                borderBottom: '1px solid rgba(255,255,255,0.04)',
                alignItems: 'center', flexWrap: 'wrap'
              }}>
                <span style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: 12, color: 'var(--soda-error)'
                }}>
                  {s.used}
                </span>
                <span style={{ color: 'var(--soda-muted)' }}>→</span>
                <span style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: 12, color: 'var(--soda-warning)'
                }}>
                  {s.better}
                </span>
                <span style={{ color: 'var(--soda-muted)' }}>→</span>
                <span style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: 12, color: 'var(--soda-success)'
                }}>
                  {s.best}
                </span>
              </div>
            ))}
            {vocabulary_feedback.summary && (
              <div style={{
                fontFamily: 'Space Grotesk, sans-serif',
                fontSize: 12, color: 'var(--soda-muted)',
                marginTop: 10, lineHeight: 1.5
              }}>
                {vocabulary_feedback.summary}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
