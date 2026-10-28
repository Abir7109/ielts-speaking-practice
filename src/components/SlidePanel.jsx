import { useEffect, useRef } from 'react'
import { usePanelSpace } from '../contexts/PanelSpaceContext'

const DIRECTION_STYLES = {
  left: {
    hidden: 'translateX(-110%)',
    shown: 'translateX(0)',
    panelClass: 'slide-panel-left',
  },
  right: {
    hidden: 'translateX(110%)',
    shown: 'translateX(0)',
    panelClass: 'slide-panel-right',
  },
  top: {
    hidden: 'translateY(-110%)',
    shown: 'translateY(0)',
    panelClass: 'slide-panel-top',
  },
  bottom: {
    hidden: 'translateY(110%)',
    shown: 'translateY(0)',
    panelClass: 'slide-panel-bottom',
  },
}

export default function SlidePanel({
  visible = false,
  direction = 'left',
  title = 'OUTPUT',
  icon = null,
  onClose,
  autoDismissMs = 0,
  scrollToTop = false,
  accentColor,
  children,
}) {
  const scrollRef = useRef(null)
  const timerRef = useRef(null)
  const scrollPhaseRef = useRef(0)
  const scrollTimerRef = useRef(null)
  const dir = DIRECTION_STYLES[direction] || DIRECTION_STYLES.left
  const { registerPanel, unregisterPanel, getOffset } = usePanelSpace()

  useEffect(() => {
    if (!visible) {
      scrollPhaseRef.current = 0
      if (scrollTimerRef.current) clearTimeout(scrollTimerRef.current)
      return
    }
    if (scrollRef.current && scrollPhaseRef.current === 0) {
      scrollPhaseRef.current = 1
      scrollRef.current.scrollTo({
        top: scrollToTop ? 0 : scrollRef.current.scrollHeight,
        behavior: 'smooth',
      })
      if (!scrollToTop) {
        scrollTimerRef.current = setTimeout(() => {
          if (scrollRef.current && scrollPhaseRef.current === 1) {
            scrollRef.current.scrollTo({ top: 0, behavior: 'smooth' })
            scrollPhaseRef.current = 2
          }
        }, 600)
      } else {
        scrollPhaseRef.current = 2
      }
    }
  }, [visible, scrollToTop])

  useEffect(() => {
    if (autoDismissMs > 0 && visible) {
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => {
        if (onClose) onClose()
      }, autoDismissMs)
    }
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [visible, autoDismissMs])

  useEffect(() => {
    if (visible) {
      registerPanel(direction)
    } else {
      unregisterPanel(direction)
    }
  }, [visible, direction, registerPanel, unregisterPanel])

  const autoOffset = getOffset(direction)
  const baseTransform = visible ? dir.shown : dir.hidden
  const offsetTransform = (autoOffset.offsetX || autoOffset.offsetY)
    ? `translate(${autoOffset.offsetX}px, ${autoOffset.offsetY}px)`
    : ''
  const transform = offsetTransform
    ? `${baseTransform} ${offsetTransform}`
    : baseTransform

  return (
    <div
      className={`slide-panel ${dir.panelClass}`}
      style={{
        transform,
        opacity: visible ? 1 : 0,
        pointerEvents: visible ? 'auto' : 'none',
      }}
    >
      <div className="hud-corner hud-corner-tl" />
      <div className="hud-corner hud-corner-tr" />
      <div className="hud-corner hud-corner-bl" />
      <div className="hud-corner hud-corner-br" />
      <div className="slide-panel-header">
        <div className="slide-panel-header-left">
          <span className="terminal-dot" style={{ background: '#ef4444' }} />
          <span className="terminal-dot" style={{ background: '#f59e0b' }} />
          <span className="terminal-dot" style={{ background: '#22c55e' }} />
        </div>
        <span className="slide-panel-title">
          {icon && <span style={{ marginRight: 4 }}>{icon}</span>}
          {title}
        </span>
        <button className="slide-panel-close" onClick={onClose}>✕</button>
      </div>

      <div className="slide-panel-body" ref={scrollRef}>
        {children}
      </div>
    </div>
  )
}
