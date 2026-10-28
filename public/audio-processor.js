// AudioWorklet processor for streaming PCM audio playback
// Reads from a shared ring buffer fed by the main thread

class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this.ring = new Float32Array(24000 * 3) // 3 seconds at 24kHz
    this.writePos = 0
    this.readPos = 0
    this.port.onmessage = (e) => {
      if (e.data.type === 'write') {
        const samples = e.data.samples
        const len = this.ring.length
        for (let i = 0; i < samples.length; i++) {
          this.ring[this.writePos] = samples[i]
          this.writePos = (this.writePos + 1) % len
        }
      } else if (e.data.type === 'reset') {
        this.readPos = 0
        this.writePos = 0
      }
    }
  }

  process(outputs) {
    const out = outputs[0][0]
    if (!out) return true
    const len = this.ring.length
    let rp = this.readPos
    let wp = this.writePos
    const available = (wp - rp + len) % len

    if (available < out.length) {
      // Not enough data — output silence for what we have, then zeros
      for (let i = 0; i < out.length; i++) {
        if (rp !== wp) {
          out[i] = this.ring[rp]
          rp = (rp + 1) % len
        } else {
          out[i] = 0
        }
      }
    } else {
      for (let i = 0; i < out.length; i++) {
        out[i] = this.ring[rp]
        rp = (rp + 1) % len
      }
    }
    this.readPos = rp
    return true
  }
}

registerProcessor('audio-processor', AudioProcessor)
