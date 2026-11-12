import { useEffect, useRef, useState } from 'react'
import { api, ApiError, type RunStatus } from './api'

const POLL_MS = 2000

// Starts a pipeline run and follows it. A run takes minutes, so the API only starts it; this hook then
// asks for its status every 2 seconds while it runs, and calls onFinished once when it ends.
export function useRun(onFinished: () => void) {
  const [status, setStatus] = useState<RunStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [visible, setVisible] = useState(false)   // whether the log panel is open

  // Refs keep values between renders without causing one: the last running state, and the latest callback.
  const wasRunning = useRef(false)
  const finished = useRef(onFinished)
  useEffect(() => {
    finished.current = onFinished
  })

  function update(next: RunStatus) {
    setStatus(next)
    if (next.running) setVisible(true)
    if (wasRunning.current && !next.running) finished.current()
    wasRunning.current = next.running
  }

  // On load, a run may already be going, such as one started by the timer.
  useEffect(() => {
    api.runStatus().then(update, () => {})
  }, [])

  // Poll only while a run is going. The cleanup stops the timer when it ends or the page closes.
  const running = status?.running ?? false
  useEffect(() => {
    if (!running) return
    const timer = setInterval(() => api.runStatus().then(update, () => {}), POLL_MS)
    return () => clearInterval(timer)
  }, [running])

  async function start() {
    setError(null)
    setVisible(true)
    try {
      update(await api.startRun())
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Can’t reach the API.')
    }
  }

  return { status, running, error, visible, start, hide: () => setVisible(false) }
}
