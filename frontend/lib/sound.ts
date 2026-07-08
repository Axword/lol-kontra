'use client'

let audioCtx: AudioContext | null = null
let enabled = true
if (typeof window !== 'undefined') {
  const saved = localStorage.getItem('lolrc_sound')
  if (saved !== null) enabled = saved === '1'
}

function ctx(): AudioContext | null {
  if (typeof window === 'undefined') return null
  if (!audioCtx) {
    const AC = (window as any).AudioContext || (window as any).webkitAudioContext
    if (AC) audioCtx = new AC()
  }
  return audioCtx
}

export function isSoundEnabled() { return enabled }
export function setSoundEnabled(v: boolean) {
  enabled = v
  if (typeof window !== 'undefined') localStorage.setItem('lolrc_sound', v ? '1' : '0')
}
export function toggleSound() { setSoundEnabled(!enabled); return enabled }

function beep(freq: number, durationMs: number, type: OscillatorType = 'sine', vol = 0.12, slideTo?: number) {
  if (!enabled) return
  const c = ctx()
  if (!c) return
  if (c.state === 'suspended') c.resume()
  const osc = c.createOscillator()
  const gain = c.createGain()
  osc.connect(gain); gain.connect(c.destination)
  osc.type = type
  osc.frequency.setValueAtTime(freq, c.currentTime)
  if (slideTo) osc.frequency.exponentialRampToValueAtTime(slideTo, c.currentTime + durationMs/1000)
  gain.gain.setValueAtTime(0, c.currentTime)
  gain.gain.linearRampToValueAtTime(vol, c.currentTime + 0.015)
  gain.gain.exponentialRampToValueAtTime(0.001, c.currentTime + durationMs/1000)
  osc.start()
  osc.stop(c.currentTime + durationMs/1000 + 0.02)
}

export const sound = {
  click() { beep(620, 90, 'square', 0.07) },
  open()  { beep(480, 110, 'sine', 0.1, 720) },
  close() { beep(520, 90, 'sine', 0.08, 340) },
  pick()  { beep(660, 120, 'triangle', 0.13); setTimeout(()=>beep(880,100,'triangle',0.1),70) },
  success() { [523,659,784,1046].forEach((f,i)=>setTimeout(()=>beep(f,140,'sine',0.11), i*90)) },
  error() { beep(220, 220, 'sawtooth', 0.09, 160) },
  diamond() {
    // sparkle
    [880,1175,1568,1760].forEach((f,i)=>setTimeout(()=>beep(f,160,'triangle',0.12), i*70))
  },
  submit() { beep(440,130,'square',0.1,660) }
}
