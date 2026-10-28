import { useEffect, useRef } from 'react'

const MOOD_COLORS = {
  neutral: {
    primary: '#00fbfb', secondary: '#0064ff', accent: '#34d1ea',
    glow: 'rgba(0,251,251,0.3)',
    coronaInner: 'rgba(0,251,251,0.4)', coronaOuter: 'rgba(0,100,255,0.2)',
    gasInner: 'rgba(0,251,251,0.25)', gasOuter: 'rgba(0,100,255,0.08)',
    flow015: 'rgba(56,189,248,0.9)', flow04: 'rgba(0,100,255,0.55)', flow085: 'rgba(13,148,136,0.12)',
    halo0: 'rgba(0,100,255,0.05)', halo085: 'rgba(34,211,238,0.82)',
    core055: 'rgba(34,211,238,0.75)', core085: 'rgba(0,100,255,0.3)',
    linePrimary: 'rgba(0,251,251,0.25)', lineDash: 'rgba(0,100,255,0.15)',
    primaryGlow: 'rgba(0,251,251,0.8)',
    dropShadow: 'drop-shadow(0 0 40px rgba(0,251,251,0.3))',
  },
  playful: {
    primary: '#f59e0b', secondary: '#d97706', accent: '#fbbf24',
    glow: 'rgba(245,158,11,0.3)',
    coronaInner: 'rgba(245,158,11,0.4)', coronaOuter: 'rgba(217,119,6,0.2)',
    gasInner: 'rgba(245,158,11,0.25)', gasOuter: 'rgba(217,119,6,0.08)',
    flow015: 'rgba(251,191,36,0.9)', flow04: 'rgba(217,119,6,0.55)', flow085: 'rgba(146,64,14,0.12)',
    halo0: 'rgba(217,119,6,0.05)', halo085: 'rgba(251,191,36,0.82)',
    core055: 'rgba(251,191,36,0.75)', core085: 'rgba(217,119,6,0.3)',
    linePrimary: 'rgba(245,158,11,0.25)', lineDash: 'rgba(217,119,6,0.15)',
    primaryGlow: 'rgba(245,158,11,0.8)',
    dropShadow: 'drop-shadow(0 0 40px rgba(245,158,11,0.3))',
  },
  tired: {
    primary: '#5b7c8c', secondary: '#3d5a6b', accent: '#7a9baa',
    glow: 'rgba(91,124,140,0.2)',
    coronaInner: 'rgba(91,124,140,0.35)', coronaOuter: 'rgba(61,90,107,0.15)',
    gasInner: 'rgba(91,124,140,0.2)', gasOuter: 'rgba(61,90,107,0.06)',
    flow015: 'rgba(122,155,170,0.75)', flow04: 'rgba(61,90,107,0.45)', flow085: 'rgba(30,50,60,0.12)',
    halo0: 'rgba(61,90,107,0.04)', halo085: 'rgba(122,155,170,0.7)',
    core055: 'rgba(122,155,170,0.65)', core085: 'rgba(61,90,107,0.25)',
    linePrimary: 'rgba(91,124,140,0.2)', lineDash: 'rgba(61,90,107,0.12)',
    primaryGlow: 'rgba(91,124,140,0.7)',
    dropShadow: 'drop-shadow(0 0 30px rgba(91,124,140,0.2))',
  },
  curious: {
    primary: '#3b82f6', secondary: '#1d4ed8', accent: '#60a5fa',
    glow: 'rgba(59,130,246,0.3)',
    coronaInner: 'rgba(59,130,246,0.4)', coronaOuter: 'rgba(29,78,216,0.2)',
    gasInner: 'rgba(59,130,246,0.25)', gasOuter: 'rgba(29,78,216,0.08)',
    flow015: 'rgba(96,165,250,0.9)', flow04: 'rgba(29,78,216,0.55)', flow085: 'rgba(15,50,150,0.12)',
    halo0: 'rgba(29,78,216,0.05)', halo085: 'rgba(96,165,250,0.82)',
    core055: 'rgba(96,165,250,0.75)', core085: 'rgba(29,78,216,0.3)',
    linePrimary: 'rgba(59,130,246,0.25)', lineDash: 'rgba(29,78,216,0.15)',
    primaryGlow: 'rgba(59,130,246,0.8)',
    dropShadow: 'drop-shadow(0 0 40px rgba(59,130,246,0.3))',
  },
  smug: {
    primary: '#fbbf24', secondary: '#b8860b', accent: '#fde68a',
    glow: 'rgba(251,191,36,0.3)',
    coronaInner: 'rgba(251,191,36,0.4)', coronaOuter: 'rgba(184,134,11,0.2)',
    gasInner: 'rgba(251,191,36,0.25)', gasOuter: 'rgba(184,134,11,0.08)',
    flow015: 'rgba(253,230,138,0.9)', flow04: 'rgba(184,134,11,0.55)', flow085: 'rgba(120,80,0,0.12)',
    halo0: 'rgba(184,134,11,0.05)', halo085: 'rgba(253,230,138,0.82)',
    core055: 'rgba(253,230,138,0.75)', core085: 'rgba(184,134,11,0.3)',
    linePrimary: 'rgba(251,191,36,0.25)', lineDash: 'rgba(184,134,11,0.15)',
    primaryGlow: 'rgba(251,191,36,0.8)',
    dropShadow: 'drop-shadow(0 0 40px rgba(251,191,36,0.3))',
  },
  serious: {
    primary: '#94a3b8', secondary: '#475569', accent: '#cbd5e1',
    glow: 'rgba(148,163,184,0.3)',
    coronaInner: 'rgba(148,163,184,0.35)', coronaOuter: 'rgba(71,85,105,0.15)',
    gasInner: 'rgba(148,163,184,0.2)', gasOuter: 'rgba(71,85,105,0.06)',
    flow015: 'rgba(203,213,225,0.85)', flow04: 'rgba(71,85,105,0.45)', flow085: 'rgba(30,41,59,0.12)',
    halo0: 'rgba(71,85,105,0.04)', halo085: 'rgba(203,213,225,0.75)',
    core055: 'rgba(203,213,225,0.7)', core085: 'rgba(71,85,105,0.25)',
    linePrimary: 'rgba(148,163,184,0.2)', lineDash: 'rgba(71,85,105,0.12)',
    primaryGlow: 'rgba(148,163,184,0.7)',
    dropShadow: 'drop-shadow(0 0 35px rgba(148,163,184,0.25))',
  },
  excited: {
    primary: '#a855f7', secondary: '#7c3aed', accent: '#c084fc',
    glow: 'rgba(168,85,247,0.4)',
    coronaInner: 'rgba(168,85,247,0.45)', coronaOuter: 'rgba(124,58,237,0.22)',
    gasInner: 'rgba(168,85,247,0.28)', gasOuter: 'rgba(124,58,237,0.1)',
    flow015: 'rgba(192,132,252,0.92)', flow04: 'rgba(124,58,237,0.6)', flow085: 'rgba(80,30,150,0.14)',
    halo0: 'rgba(124,58,237,0.06)', halo085: 'rgba(192,132,252,0.85)',
    core055: 'rgba(192,132,252,0.8)', core085: 'rgba(124,58,237,0.35)',
    linePrimary: 'rgba(168,85,247,0.28)', lineDash: 'rgba(124,58,237,0.17)',
    primaryGlow: 'rgba(168,85,247,0.8)',
    dropShadow: 'drop-shadow(0 0 50px rgba(168,85,247,0.4))',
  },
  empathetic: {
    primary: '#f472b6', secondary: '#db2777', accent: '#f9a8d4',
    glow: 'rgba(244,114,182,0.3)',
    coronaInner: 'rgba(244,114,182,0.4)', coronaOuter: 'rgba(219,39,119,0.2)',
    gasInner: 'rgba(244,114,182,0.25)', gasOuter: 'rgba(219,39,119,0.08)',
    flow015: 'rgba(249,168,212,0.9)', flow04: 'rgba(219,39,119,0.55)', flow085: 'rgba(150,20,80,0.12)',
    halo0: 'rgba(219,39,119,0.05)', halo085: 'rgba(249,168,212,0.82)',
    core055: 'rgba(249,168,212,0.75)', core085: 'rgba(219,39,119,0.3)',
    linePrimary: 'rgba(244,114,182,0.25)', lineDash: 'rgba(219,39,119,0.15)',
    primaryGlow: 'rgba(244,114,182,0.8)',
    dropShadow: 'drop-shadow(0 0 40px rgba(244,114,182,0.3))',
  },
  gentle: {
    primary: '#a78bfa', secondary: '#7c3aed', accent: '#c4b5fd',
    glow: 'rgba(167,139,250,0.3)',
    coronaInner: 'rgba(167,139,250,0.4)', coronaOuter: 'rgba(124,58,237,0.2)',
    gasInner: 'rgba(167,139,250,0.25)', gasOuter: 'rgba(124,58,237,0.08)',
    flow015: 'rgba(196,181,253,0.9)', flow04: 'rgba(124,58,237,0.55)', flow085: 'rgba(80,30,150,0.12)',
    halo0: 'rgba(124,58,237,0.05)', halo085: 'rgba(196,181,253,0.82)',
    core055: 'rgba(196,181,253,0.75)', core085: 'rgba(124,58,237,0.3)',
    linePrimary: 'rgba(167,139,250,0.25)', lineDash: 'rgba(124,58,237,0.15)',
    primaryGlow: 'rgba(167,139,250,0.8)',
    dropShadow: 'drop-shadow(0 0 40px rgba(167,139,250,0.3))',
  },
  somber: {
    primary: '#64748b', secondary: '#334155', accent: '#94a3b8',
    glow: 'rgba(100,116,139,0.2)',
    coronaInner: 'rgba(100,116,139,0.3)', coronaOuter: 'rgba(51,65,85,0.12)',
    gasInner: 'rgba(100,116,139,0.18)', gasOuter: 'rgba(51,65,85,0.05)',
    flow015: 'rgba(148,163,184,0.7)', flow04: 'rgba(51,65,85,0.4)', flow085: 'rgba(20,30,50,0.1)',
    halo0: 'rgba(51,65,85,0.04)', halo085: 'rgba(148,163,184,0.65)',
    core055: 'rgba(148,163,184,0.6)', core085: 'rgba(51,65,85,0.2)',
    linePrimary: 'rgba(100,116,139,0.18)', lineDash: 'rgba(51,65,85,0.1)',
    primaryGlow: 'rgba(100,116,139,0.6)',
    dropShadow: 'drop-shadow(0 0 30px rgba(100,116,139,0.15))',
  },
}

const SPEAKING_PALETTE = {
  coronaInner: 'rgba(124, 58, 237, 0.45)', coronaOuter: 'rgba(109, 40, 217, 0.2)',
  gasInner: 'rgba(168, 85, 247, 0.25)', gasOuter: 'rgba(109, 40, 217, 0.08)',
  flow015: 'rgba(168,85,247,0.8)', flow04: 'rgba(139,92,246,0.45)', flow085: 'rgba(0,0,0,0)',
  halo0: 'rgba(168, 85, 247, 0.1)', halo085: 'rgba(147, 51, 234, 0.7)',
  core055: 'rgba(168,85,247,0.75)', core085: 'rgba(79,70,229,0.3)',
  linePrimary: 'rgba(168, 85, 247, 0.28)', lineDash: 'rgba(168, 85, 247, 0.15)',
  primaryGlow: 'rgba(168,85,247,0.3)',
  dropShadow: 'drop-shadow(0 0 40px rgba(168,85,247,0.3))',
}

export default function HolographicOrb({
  size = 400,
  micLevel = 0,
  isSpeaking = false,
  isListening = false,
  lang = 'en',
  mood = 'neutral',
  idle = false,
  waking = false,
}) {
  const canvasRef = useRef(null)

  const stateRef = useRef({
    timer: 0,
    swirlAngle1: 0,
    swirlAngle2: 0,
    pulseFactor: 0,
    inwardFlows: [],
    currentMicLevel: 0,
    lastTime: 0,
  })

  const propsRef = useRef({ size, micLevel, isSpeaking, isListening, lang, mood, idle, waking })

  useEffect(() => {
    propsRef.current = { size, micLevel, isSpeaking, isListening, lang, mood, idle, waking }
  }, [size, micLevel, isSpeaking, isListening, lang, mood, idle, waking])

  useEffect(() => {
    const inwardFlows = []
    for (let i = 0; i < 8; i++) {
      inwardFlows.push({
        radiusScale: (i / 8) * 0.9 + 0.3,
        angleOffset: (i * Math.PI * 2) / 8 + Math.random() * 0.5,
        rotationSpeed: 0.6 + Math.random() * 0.8,
        opacity: 0.15 + Math.random() * 0.45,
      })
    }
    stateRef.current.inwardFlows = inwardFlows
  }, [size])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animId

    const draw = (currentTime) => {
      const state = stateRef.current
      const props = propsRef.current

      if (state.lastTime === 0) state.lastTime = currentTime
      const dt = Math.min(currentTime - state.lastTime, 50)
      state.lastTime = currentTime
      const delta = dt / 1000

      state.currentMicLevel += (props.micLevel - state.currentMicLevel) * 0.06

      const speedMultiplier = (props.isSpeaking ? 0.4 : 1.0) * (1.0 + state.currentMicLevel * 1.5)

      state.timer += delta * (0.8 + state.currentMicLevel * 1.0)
      state.swirlAngle1 += 0.85 * speedMultiplier * delta
      state.swirlAngle2 -= 1.65 * speedMultiplier * delta

      const dpr = window.devicePixelRatio || 1
      const targetSize = props.size
      if (canvas.width !== targetSize * dpr || canvas.height !== targetSize * dpr) {
        canvas.width = targetSize * dpr
        canvas.height = targetSize * dpr
        canvas.style.width = `${targetSize}px`
        canvas.style.height = `${targetSize}px`
      }

      ctx.setTransform(1, 0, 0, 1, 0, 0)
      ctx.scale(dpr, dpr)
      ctx.clearRect(0, 0, targetSize, targetSize)

      const cx = targetSize / 2
      const cy = targetSize / 2
      const baseRadius = targetSize * 0.35

      const bounceIntensity = 1.0 + state.currentMicLevel * 0.12 + 0.03 * Math.sin(state.timer * 3)
      const activeRadius = baseRadius * bounceIntensity

      const mc = MOOD_COLORS[props.mood] || MOOD_COLORS.neutral
      const p = props.isSpeaking ? SPEAKING_PALETTE : mc

      if (props.idle) {
        state.currentMicLevel = 0
      }

      // 1. DEEP RADIAL CORONA BACKDROP
      ctx.save()
      const corona = ctx.createRadialGradient(cx, cy, activeRadius * 0.1, cx, cy, activeRadius * 1.7)
      corona.addColorStop(0, p.coronaInner)
      corona.addColorStop(0.3, p.coronaOuter)
      corona.addColorStop(1, 'rgba(0, 0, 0, 0)')
      ctx.fillStyle = corona
      ctx.fillRect(0, 0, targetSize, targetSize)
      ctx.restore()

      // 2. STITCH-STYLE INNER GAS LAYER
      ctx.save()
      ctx.globalCompositeOperation = 'screen'
      const gasFlares = 8
      for (let i = 0; i < gasFlares; i++) {
        const angle = state.swirlAngle1 + (i * Math.PI * 2) / gasFlares
        const outerX = cx + Math.cos(angle) * activeRadius
        const outerY = cy + Math.sin(angle) * activeRadius
        const gasGrad = ctx.createRadialGradient(outerX, outerY, 4, outerX, outerY, activeRadius * 0.9)
        gasGrad.addColorStop(0, p.gasInner)
        gasGrad.addColorStop(0.5, p.gasOuter)
        gasGrad.addColorStop(1, 'rgba(0,0,0,0)')
        ctx.fillStyle = gasGrad
        ctx.beginPath()
        ctx.arc(cx, cy, activeRadius * 1.1, 0, Math.PI * 2)
        ctx.fill()
      }
      ctx.restore()

      // 3. INWARD FLOWING STREAM FIBERS
      ctx.save()
      ctx.globalCompositeOperation = 'screen'
      state.inwardFlows.forEach((flow) => {
        flow.radiusScale -= 0.12 * (1.0 + state.currentMicLevel * 1.5) * delta
        if (flow.radiusScale <= 0.15) {
          flow.radiusScale = 1.15
          flow.angleOffset = Math.random() * Math.PI * 2
        }

        const radiusNow = activeRadius * flow.radiusScale
        const armAngle = state.swirlAngle2 * 1.2 + flow.angleOffset

        ctx.beginPath()
        const flowGradient = ctx.createRadialGradient(cx, cy, radiusNow * 0.1, cx, cy, radiusNow)
        if (props.isSpeaking) {
          flowGradient.addColorStop(0, 'rgba(255, 255, 255, 0.9)')
          flowGradient.addColorStop(0.2, 'rgba(168, 85, 247, 0.8)')
          flowGradient.addColorStop(0.5, 'rgba(139, 92, 246, 0.45)')
          flowGradient.addColorStop(1, 'rgba(0,0,0,0)')
        } else {
          flowGradient.addColorStop(0, 'rgba(255, 255, 255, 0.95)')
          flowGradient.addColorStop(0.15, p.flow015)
          flowGradient.addColorStop(0.4, p.flow04)
          flowGradient.addColorStop(0.85, p.flow085)
          flowGradient.addColorStop(1, 'rgba(0,0,0,0)')
        }

        ctx.strokeStyle = flowGradient
        ctx.lineWidth = (3.5 + state.currentMicLevel * 6.5) * flow.radiusScale

        const spiralRotations = Math.PI * 1.5
        let p_initialized = false
        for (let rad = 0; rad <= spiralRotations; rad += 0.08) {
          const proportion = rad / spiralRotations
          const currentFilamentRad = radiusNow * Math.pow(1.0 - proportion, 0.85)
          const theta = armAngle - rad * 1.6
          const sx = cx + Math.cos(theta) * currentFilamentRad
          const sy = cy + Math.sin(theta) * currentFilamentRad
          if (!p_initialized) {
            ctx.moveTo(sx, sy)
            p_initialized = true
          } else {
            ctx.lineTo(sx, sy)
          }
        }
        ctx.stroke()
      })
      ctx.restore()

      // 4. PLASMATIC FLAME HALO EDGE
      ctx.save()
      ctx.globalCompositeOperation = 'screen'
      ctx.beginPath()
      const steps = 90
      for (let i = 0; i <= steps; i++) {
        const phi = (i / steps) * Math.PI * 2
        let rExtra = 0
        if (props.isSpeaking) {
          const wave1 = Math.sin(phi * 4 + state.timer * 3.5) * 11
          const wave2 = Math.cos(phi * 6 - state.timer * 5.0) * 7
          const voiceSwell = Math.sin(phi * 2 + state.timer * 7.0) * (state.currentMicLevel * 18)
          rExtra = wave1 + wave2 + voiceSwell
        } else {
          const wave1 = Math.sin(phi * 5 + state.timer * 4.0) * 7
          const wave2 = Math.cos(phi * 8 - state.timer * 6.0) * 4
          const soundRippler = Math.sin(phi * 6 + state.timer * 11.0) * (state.currentMicLevel * 11)
          rExtra = wave1 + wave2 + soundRippler
        }

        const dynamicRadius = activeRadius * 1.02 + rExtra
        const ex = cx + Math.cos(phi) * dynamicRadius
        const ey = cy + Math.sin(phi) * dynamicRadius
        if (i === 0) ctx.moveTo(ex, ey)
        else ctx.lineTo(ex, ey)
      }
      ctx.closePath()

      const outerFlareGrad = ctx.createRadialGradient(cx, cy, activeRadius * 0.7, cx, cy, activeRadius * 1.15)
      if (props.isSpeaking) {
        outerFlareGrad.addColorStop(0, 'rgba(168, 85, 247, 0.1)')
        outerFlareGrad.addColorStop(0.85, 'rgba(147, 51, 234, 0.7)')
        outerFlareGrad.addColorStop(1, 'rgba(255, 255, 255, 1.0)')
      } else {
        outerFlareGrad.addColorStop(0, p.halo0)
        outerFlareGrad.addColorStop(0.82, p.halo085)
        outerFlareGrad.addColorStop(1, 'rgba(255, 255, 255, 1.0)')
      }
      ctx.strokeStyle = outerFlareGrad
      ctx.lineWidth = 3.5 + state.currentMicLevel * 6.0
      ctx.shadowBlur = 15
      ctx.shadowColor = p.primaryGlow
      ctx.stroke()
      ctx.restore()

      // 5. INTENSE PULSATING CORES
      ctx.save()
      ctx.globalCompositeOperation = 'screen'
      const corePulse = (props.isSpeaking ? 0.06 : 0.045) * Math.sin(state.timer * 4.5)
      const coreRadius = activeRadius * (0.33 + corePulse + state.currentMicLevel * 0.35)
      const centerCore = ctx.createRadialGradient(cx, cy, coreRadius * 0.05, cx, cy, coreRadius)
      centerCore.addColorStop(0, 'rgba(255,255,255,1.0)')
      centerCore.addColorStop(0.2, 'rgba(255,255,255,0.95)')
      centerCore.addColorStop(0.55, p.core055)
      centerCore.addColorStop(0.85, p.core085)
      centerCore.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.fillStyle = centerCore
      ctx.beginPath()
      ctx.arc(cx, cy, coreRadius, 0, Math.PI * 2)
      ctx.fill()
      ctx.restore()

      // 6. DETAILED HOLOGRAPHIC OVERLAY LINES
      ctx.save()
      ctx.strokeStyle = p.linePrimary
      ctx.lineWidth = 0.85
      ctx.beginPath()
      ctx.arc(cx, cy, activeRadius * 0.98, 0, Math.PI * 2)
      ctx.stroke()
      ctx.beginPath()
      ctx.arc(cx, cy, activeRadius * 1.05 + 6, 0, Math.PI * 2)
      ctx.setLineDash([3, 24])
      ctx.lineWidth = 1.5
      ctx.strokeStyle = p.lineDash
      ctx.stroke()
      ctx.restore()

      // 7. REFLECTED CRITICAL CURVE HIGH-SHINE
      ctx.save()
      ctx.beginPath()
      const shine = ctx.createLinearGradient(cx * 0.6, cy * 0.5, cx * 1.4, cy * 1.45)
      shine.addColorStop(0, 'rgba(255, 255, 255, 0.35)')
      shine.addColorStop(0.4, 'rgba(255, 255, 255, 0.08)')
      shine.addColorStop(1, 'rgba(255, 255, 255, 0)')
      ctx.arc(cx - 6, cy - 6, activeRadius * 0.93, Math.PI * 1.0, Math.PI * 1.8)
      ctx.lineTo(cx, cy)
      ctx.closePath()
      ctx.fillStyle = shine
      ctx.fill()
      ctx.restore()

      animId = requestAnimationFrame(draw)
    }

    animId = requestAnimationFrame(draw)

    return () => {
      cancelAnimationFrame(animId)
    }
  }, [])

  return (
    <div className="flex flex-col items-center justify-center select-none">
      <div
        className="relative flex items-center justify-center"
        style={{
          width: `${size}px`,
          height: `${size}px`,
          transition: 'filter 0.8s ease',
          filter: waking
            ? (MOOD_COLORS[mood] || MOOD_COLORS.neutral).dropShadow
            : idle
              ? 'grayscale(100%) drop-shadow(0 0 15px rgba(128,128,128,0.2))'
              : (isSpeaking
                ? SPEAKING_PALETTE.dropShadow
                : (MOOD_COLORS[mood] || MOOD_COLORS.neutral).dropShadow),
        }}
      >
        <canvas ref={canvasRef} className="block z-10" style={{ pointerEvents: 'none' }} />
        <div className="absolute inset-0 border border-slate-900/40 rounded-full scale-[1.06] pointer-events-none" />
      </div>
    </div>
  )
}
