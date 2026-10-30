import React from 'react'

const label = (text) => ({
  fontFamily: 'Space Grotesk, sans-serif',
  fontSize: 10,
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
  color: 'var(--soda-muted)',
})

const bandColor = (band) => {
  if (band >= 7.5) return 'var(--soda-success)'
  if (band >= 6.5) return 'var(--soda-accent)'
  if (band >= 5.5) return 'var(--soda-warning)'
  return 'var(--soda-error)'
}

const CRITERIA = [
  ['Fluency & Coherence', 'fluency_coherence'],
  ['Lexical Resource', 'lexical_resource'],
  ['Grammatical Range', 'grammatical_range'],
  ['Pronunciation', 'pronunciation'],
]

export default function IELTSReportPanel({ report, onRestart }) {
  if (!report) {
    return (
      <div style={{ padding: 20 }}>
        <div style={{ ...label(), marginBottom: 8 }}>No report yet</div>
        <div style={{
          fontFamily: 'Space Grotesk, sans-serif',
          fontSize: 13,
          color: 'var(--soda-text)',
        }}>
          Finish a practice test to see your band report.
        </div>
      </div>
    )
  }

  const crit = report.band_scores || {}
  const parts = report.part_scores || {}
  const corrections = report.corrections || []
  const strengths = report.strengths || []
  const tips = report.top_tips || []
  const critFeedback = report.criterion_feedback || {}

  return (
    <div style={{ padding: 20 }}>
      <div style={{
        background: 'rgba(0, 240, 255, 0.04)',
        border: '1px solid rgba(0, 240, 255, 0.2)',
        padding: 20,
        marginBottom: 16,
      }}>
        <div style={{ ...label(), color: 'var(--soda-accent)', marginBottom: 6 }}>
          Final Result
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
          <span style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 52,
            fontWeight: 700,
            color: bandColor(report.overall_band),
          }}>
            {Number(report.overall_band || 0).toFixed(1)}
          </span>
          <span style={{ ...label(), fontSize: 11 }}>Overall Band</span>
        </div>
        <div style={{
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 10,
          color: 'var(--soda-muted)',
          marginTop: 6,
        }}>
          {report.mode === 'part' ? 'SINGLE PART' : 'FULL MOCK TEST'} / {report.answer_count || 0} ANSWERS
        </div>
      </div>

      {report.scoring_mode === 'estimate' && (
        <div style={{
          padding: 10,
          marginBottom: 14,
          background: 'rgba(255, 170, 0, 0.08)',
          border: '1px solid rgba(255, 170, 0, 0.25)',
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 10,
          color: 'var(--soda-warning)',
          lineHeight: 1.6,
        }}>
          AUTOMATED SCORING UNAVAILABLE — these bands are rough local estimates,
          not examiner-level scores.
        </div>
      )}

      <div style={{ ...label(), marginBottom: 8 }}>Criteria</div>
      {CRITERIA.map(([name, key]) => {
        const fb = critFeedback[key] || {}
        return (
          <div key={key} style={{ marginBottom: 8 }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '8px 12px',
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.07)',
            }}>
              <span style={{
                fontFamily: 'Space Grotesk, sans-serif',
                fontSize: 12,
                color: 'var(--soda-text)',
              }}>
                {name}
              </span>
              <span style={{
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: crit[key] == null ? 11 : 16,
                fontWeight: 700,
                color: crit[key] == null ? 'var(--soda-muted)' : bandColor(crit[key]),
              }}>
                {crit[key] == null ? 'NOT ASSESSED' : Number(crit[key]).toFixed(1)}
              </span>
            </div>
            {(fb.reasons?.length > 0 || fb.next_step) && (
              <div style={{
                padding: '8px 12px',
                background: 'rgba(255,255,255,0.02)',
                border: '1px solid rgba(255,255,255,0.06)',
                borderTop: 'none',
              }}>
                {(fb.reasons || []).map((r, i) => (
                  <div key={i} style={{
                    fontFamily: 'Space Grotesk, sans-serif',
                    fontSize: 11,
                    color: 'var(--soda-muted)',
                    lineHeight: 1.5,
                    marginBottom: 3,
                  }}>
                    {r}
                  </div>
                ))}
                {fb.why_not_higher && (
                  <div style={{
                    fontFamily: 'Space Grotesk, sans-serif',
                    fontSize: 11,
                    color: 'var(--soda-warning)',
                    lineHeight: 1.5,
                    marginTop: 3,
                  }}>
                    BLOCKING THE NEXT HALF-BAND: {fb.why_not_higher}
                  </div>
                )}
                {fb.next_step && (
                  <div style={{
                    fontFamily: 'Space Grotesk, sans-serif',
                    fontSize: 11,
                    color: 'var(--soda-accent)',
                    lineHeight: 1.5,
                    marginTop: 3,
                  }}>
                    NEXT: {fb.next_step}
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}

      <div style={{ display: 'flex', gap: 8, margin: '14px 0' }}>
        {['1', '2', '3'].map(p => parts[p] !== undefined && (
          <div key={p} style={{
            flex: 1,
            padding: 10,
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.07)',
            textAlign: 'center',
          }}>
            <div style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 18,
              fontWeight: 700,
              color: 'var(--soda-accent)',
            }}>
              {Number(parts[p] || 0).toFixed(1)}
            </div>
            <div style={label()}>Part {p}</div>
          </div>
        ))}
      </div>

      {report.strongest_criterion && (
        <div style={{
          fontFamily: 'Space Grotesk, sans-serif',
          fontSize: 12,
          color: 'var(--soda-muted)',
          marginBottom: 14,
        }}>
          Strongest: <span style={{ color: 'var(--soda-success)' }}>{report.strongest_criterion}</span>
          {report.weakest_criterion && (
            <> / Focus next: <span style={{ color: 'var(--soda-warning)' }}>{report.weakest_criterion}</span></>
          )}
        </div>
      )}

      {(report.question_notes || []).length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ ...label(), marginBottom: 6 }}>Examiner notes, question by question</div>
          {(report.question_notes || []).map((n, i) => (
            <div key={i} style={{
              display: 'flex',
              gap: 8,
              marginBottom: 5,
              fontFamily: 'Space Grotesk, sans-serif',
              fontSize: 11,
              color: 'var(--soda-muted)',
              lineHeight: 1.5,
            }}>
              <span style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--soda-accent)' }}>
                P{n.part} Q{n.index}
              </span>
              <span style={{ color: 'var(--soda-text)' }}>{n.note}</span>
            </div>
          ))}
        </div>
      )}

      {report.weakest_reason && (
        <div style={{
          padding: 10,
          marginBottom: 14,
          background: 'rgba(255, 170, 0, 0.06)',
          border: '1px solid rgba(255, 170, 0, 0.2)',
        }}>
          <div style={{ ...label(), color: 'var(--soda-warning)', marginBottom: 5 }}>
            Why you lost marks
          </div>
          <div style={{
            fontFamily: 'Space Grotesk, sans-serif',
            fontSize: 12,
            color: 'var(--soda-text)',
            lineHeight: 1.55,
          }}>
            {report.weakest_reason}
          </div>
        </div>
      )}

      {corrections.length > 0 && (
        <>
          <div style={{ ...label(), marginBottom: 8 }}>Grammar Corrections</div>
          {corrections.map((c, i) => (
            <div key={i} style={{
              padding: 10,
              marginBottom: 6,
              background: 'rgba(255, 51, 85, 0.05)',
              border: '1px solid rgba(255, 51, 85, 0.2)',
            }}>
              <div style={{
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: 11,
                color: 'var(--soda-error)',
                textDecoration: 'line-through',
              }}>
                {c.error}
              </div>
              <div style={{
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: 11,
                color: 'var(--soda-success)',
                marginTop: 3,
              }}>
                {c.correction}
              </div>
              {c.type && (
                <div style={{ ...label(), marginTop: 5 }}>{c.type}</div>
              )}
            </div>
          ))}
        </>
      )}

      {strengths.length > 0 && (
        <>
          <div style={{ ...label(), color: 'var(--soda-success)', margin: '14px 0 8px' }}>
            Strengths
          </div>
          {strengths.map((s, i) => (
            <div key={i} style={{
              fontFamily: 'Space Grotesk, sans-serif',
              fontSize: 12,
              color: 'var(--soda-text)',
              padding: '4px 0',
            }}>
              + {s}
            </div>
          ))}
        </>
      )}

      {tips.length > 0 && (
        <>
          <div style={{ ...label(), color: 'var(--soda-warning)', margin: '14px 0 8px' }}>
            Next Steps
          </div>
          {tips.map((t, i) => (
            <div key={i} style={{
              fontFamily: 'Space Grotesk, sans-serif',
              fontSize: 12,
              color: 'var(--soda-text)',
              padding: '4px 0',
            }}>
              &gt; {t}
            </div>
          ))}
        </>
      )}

      <div style={{
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: 9,
        color: 'var(--soda-muted)',
        marginTop: 16,
      }}>
        {report.disclaimer}
      </div>

      {onRestart && (
        <button
          onClick={onRestart}
          style={{
            width: '100%',
            marginTop: 14,
            padding: '12px 16px',
            background: 'rgba(0, 240, 255, 0.08)',
            border: '1px solid var(--soda-accent)',
            color: 'var(--soda-accent)',
            fontFamily: 'Space Grotesk, sans-serif',
            fontSize: 12,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            cursor: 'pointer',
          }}
        >
          Practice Again
        </button>
      )}
    </div>
  )
}
