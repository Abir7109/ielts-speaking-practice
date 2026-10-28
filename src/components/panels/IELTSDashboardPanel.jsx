import React from 'react'

const BandMeter = ({ label, band, target }) => {
  const percentage = band ? (band / 9) * 100 : 0
  const gap = band && target ? (target - band).toFixed(1) : null

  const getColor = (band) => {
    if (!band) return 'var(--soda-muted)'
    if (band >= 7.5) return 'var(--soda-success)'
    if (band >= 6.5) return 'var(--soda-accent)'
    if (band >= 5.5) return 'var(--soda-warning)'
    return 'var(--soda-error)'
  }

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        marginBottom: 6, alignItems: 'center'
      }}>
        <span style={{
          fontFamily: 'Space Grotesk, sans-serif',
          fontSize: 13, letterSpacing: '0.08em',
          color: 'var(--soda-muted)', textTransform: 'uppercase'
        }}>
          {label}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 20, fontWeight: 700,
            color: getColor(band)
          }}>
            {band || '—'}
          </span>
          {gap && gap > 0 && (
            <span style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 11, color: 'var(--soda-warning)'
            }}>
              +{gap} needed
            </span>
          )}
        </div>
      </div>
      <div style={{
        height: 4, background: 'rgba(255,255,255,0.06)',
        position: 'relative', overflow: 'hidden'
      }}>
        {target && (
          <div style={{
            position: 'absolute',
            left: `${(target / 9) * 100}%`,
            top: 0, height: '100%', width: 2,
            background: 'rgba(255,255,255,0.3)',
            zIndex: 2
          }} />
        )}
        <div style={{
          width: `${percentage}%`, height: '100%',
          background: getColor(band),
          transition: 'width 0.8s cubic-bezier(0.16,1,0.3,1)',
          opacity: band ? 1 : 0
        }} />
      </div>
      <div style={{
        display: 'flex', justifyContent: 'space-between', marginTop: 3
      }}>
        {[1, 3, 5, 7, 9].map(n => (
          <span key={n} style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 9, color: 'rgba(255,255,255,0.2)'
          }}>{n}</span>
        ))}
      </div>
    </div>
  )
}

export default function IELTSDashboardPanel({ data }) {
  const { progress, days_until_exam, target_band } = data || {}
  const avg = progress?.average_bands || {}

  return (
    <div style={{ padding: 20, height: '100%', overflowY: 'auto' }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{
          fontFamily: 'Space Grotesk, sans-serif',
          fontSize: 11, letterSpacing: '0.15em',
          color: 'var(--soda-accent)', marginBottom: 4
        }}>
          IELTS PREPARATION
        </div>
        <div style={{
          fontFamily: 'Space Grotesk, sans-serif',
          fontSize: 22, fontWeight: 700,
          color: 'var(--soda-text)'
        }}>
          Progress Dashboard
        </div>
      </div>

      {days_until_exam !== null && days_until_exam !== undefined && (
        <div style={{
          background: days_until_exam < 14
            ? 'rgba(255, 51, 85, 0.08)'
            : 'rgba(0, 240, 255, 0.04)',
          border: `1px solid ${days_until_exam < 14
            ? 'rgba(255, 51, 85, 0.3)'
            : 'rgba(0, 240, 255, 0.15)'}`,
          padding: '12px 16px', marginBottom: 20
        }}>
          <div style={{
            fontFamily: 'Space Grotesk, sans-serif',
            fontSize: 11, color: 'var(--soda-muted)',
            letterSpacing: '0.1em', textTransform: 'uppercase'
          }}>
            Exam Countdown
          </div>
          <div style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 32, fontWeight: 700,
            color: days_until_exam < 14
              ? 'var(--soda-error)'
              : 'var(--soda-accent)'
          }}>
            {days_until_exam} <span style={{ fontSize: 14, fontWeight: 400 }}>days</span>
          </div>
        </div>
      )}

      <div style={{
        background: 'rgba(0, 240, 255, 0.03)',
        border: '1px solid rgba(0, 240, 255, 0.12)',
        padding: '16px', marginBottom: 20
      }}>
        <div style={{
          fontFamily: 'Space Grotesk, sans-serif',
          fontSize: 11, color: 'var(--soda-muted)',
          letterSpacing: '0.1em', textTransform: 'uppercase',
          marginBottom: 8
        }}>
          Current Overall Band
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
          <span style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 48, fontWeight: 700,
            color: 'var(--soda-accent)'
          }}>
            {avg.overall || '—'}
          </span>
          <span style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 20, color: 'var(--soda-muted)'
          }}>
            / {target_band || 7.0} target
          </span>
        </div>
      </div>

      <div style={{ marginBottom: 20 }}>
        <div style={{
          fontFamily: 'Space Grotesk, sans-serif',
          fontSize: 11, color: 'var(--soda-muted)',
          letterSpacing: '0.1em', textTransform: 'uppercase',
          marginBottom: 12
        }}>
          Speaking Score
        </div>
        <BandMeter label="Speaking" band={avg.speaking} target={target_band} />
      </div>

      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr 1fr',
        gap: 8, marginBottom: 20
      }}>
        {[
          { label: 'Streak', value: `${progress?.streak_days || 0}d`, color: 'var(--soda-success)' },
          { label: 'Sessions', value: progress?.total_sessions || 0, color: 'var(--soda-accent)' },
          { label: 'Target', value: target_band || 7.0, color: 'var(--soda-warning)' }
        ].map(({ label, value, color }) => (
          <div key={label} style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.06)',
            padding: '12px 8px', textAlign: 'center'
          }}>
            <div style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 22, fontWeight: 700, color
            }}>
              {value}
            </div>
            <div style={{
              fontFamily: 'Space Grotesk, sans-serif',
              fontSize: 10, color: 'var(--soda-muted)',
              textTransform: 'uppercase', letterSpacing: '0.08em'
            }}>
              {label}
            </div>
          </div>
        ))}
      </div>

      {progress?.weak_areas?.length > 0 && (
        <div style={{
          background: 'rgba(255, 170, 0, 0.05)',
          border: '1px solid rgba(255, 170, 0, 0.2)',
          padding: 12
        }}>
          <div style={{
            fontFamily: 'Space Grotesk, sans-serif',
            fontSize: 11, color: 'var(--soda-warning)',
            letterSpacing: '0.1em', textTransform: 'uppercase',
            marginBottom: 8
          }}>
            Focus Areas
          </div>
          {progress.weak_areas.map((area, i) => (
            <div key={i} style={{
              fontFamily: 'Space Grotesk, sans-serif',
              fontSize: 13, color: 'var(--soda-text)',
              padding: '3px 0'
            }}>
              → {area}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
