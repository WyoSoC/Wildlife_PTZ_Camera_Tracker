import { useCallback, useEffect, useRef, useState } from 'react'

export interface GamepadState {
  connected: boolean
  name: string
  pan: number     // left stick X  ([-1..1], positive = right)
  tilt: number    // left stick Y  ([-1..1], positive = up)
  zoom: number    // right stick Y ([-1..1], positive = zoom in)
  btnStop: boolean    // button 0  (✕ on DualSense / A on Xbox)
  btnFocus: boolean   // button 3  (△ on DualSense / Y on Xbox)
}

const DEADZONE = 0.1

function dz(v: number): number {
  return Math.abs(v) < DEADZONE ? 0 : v
}

export function useGamepad(
  onAxes?: (pan: number, tilt: number, zoom: number) => void,
): GamepadState {
  const [state, setState] = useState<GamepadState>({
    connected: false,
    name: '',
    pan: 0, tilt: 0, zoom: 0,
    btnStop: false, btnFocus: false,
  })

  // Keep the callback in a ref so the rAF loop always calls the latest version
  // without needing to re-register the loop when the callback changes.
  const onAxesRef = useRef(onAxes)
  useEffect(() => { onAxesRef.current = onAxes }, [onAxes])

  const rafRef = useRef<number>(0)

  const poll = useCallback(() => {
    const gps = navigator.getGamepads()
    const gp = Array.from(gps).find(Boolean) ?? null

    if (gp) {
      const pan  = dz(-gp.axes[0])    // invert X: push right → positive pan
      const tilt = dz(-gp.axes[1])    // invert Y: push up   → positive tilt
      const zoom = dz(-gp.axes[3])    // right stick Y: pull toward you = zoom in
      const btnStop  = gp.buttons[0]?.pressed ?? false
      const btnFocus = gp.buttons[3]?.pressed ?? false

      setState({ connected: true, name: gp.id, pan, tilt, zoom, btnStop, btnFocus })
      onAxesRef.current?.(pan, tilt, zoom)
    }

    rafRef.current = requestAnimationFrame(poll)
  }, [])

  useEffect(() => {
    const onConnect = (e: GamepadEvent) =>
      setState(s => ({ ...s, connected: true, name: e.gamepad.id }))
    const onDisconnect = () =>
      setState(s => ({ ...s, connected: false, name: '', pan: 0, tilt: 0, zoom: 0 }))

    window.addEventListener('gamepadconnected', onConnect)
    window.addEventListener('gamepaddisconnected', onDisconnect)
    rafRef.current = requestAnimationFrame(poll)

    return () => {
      window.removeEventListener('gamepadconnected', onConnect)
      window.removeEventListener('gamepaddisconnected', onDisconnect)
      cancelAnimationFrame(rafRef.current)
    }
  }, [poll])

  return state
}
