import { createContext, useContext, useState, useCallback } from 'react'

const PANEL_LEFT = 420
const PANEL_RIGHT = 400
const PANEL_TOP = 480
const PANEL_BOTTOM = 520

const PanelSpaceContext = createContext(null)

export function PanelSpaceProvider({ children }) {
  const [visibleDirections, setVisibleDirections] = useState(new Set())

  const registerPanel = useCallback((direction) => {
    setVisibleDirections(prev => new Set([...prev, direction]))
  }, [])

  const unregisterPanel = useCallback((direction) => {
    setVisibleDirections(prev => {
      const next = new Set(prev)
      next.delete(direction)
      return next
    })
  }, [])

  const getOffset = useCallback((direction) => {
    let offsetX = 0
    let offsetY = 0
    const vw = window.innerWidth
    // 768 must match the .slide-panel-bottom sheet breakpoint in main.css: below it
    // panels span the full viewport, so a horizontal nudge would push them offscreen.
    if (direction === 'top') {
      if (visibleDirections.has('right')) {
        offsetX = vw < 768 ? 0 : -(PANEL_RIGHT + 40)
      } else {
        offsetX = vw < 768 ? 0 : vw < 800 ? 80 : vw < 1024 ? 120 : 160
      }
    }
    if (direction === 'bottom') {
      if (visibleDirections.has('left')) {
        offsetX = vw < 768 ? 0 : PANEL_LEFT + 40
      } else {
        offsetX = vw < 768 ? 0 : vw < 800 ? 80 : vw < 1024 ? 140 : 200
      }
    }
    return { offsetX, offsetY }
  }, [visibleDirections])

  return (
    <PanelSpaceContext.Provider value={{ registerPanel, unregisterPanel, getOffset }}>
      {children}
    </PanelSpaceContext.Provider>
  )
}

export function usePanelSpace() {
  const ctx = useContext(PanelSpaceContext)
  if (!ctx) return { registerPanel: () => {}, unregisterPanel: () => {}, getOffset: () => ({ offsetX: 0, offsetY: 0 }) }
  return ctx
}
