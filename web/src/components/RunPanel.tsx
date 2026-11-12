import { useEffect, useRef } from 'react'
import type { RunStatus } from '../api'

export default function RunPanel({
  status,
  error,
  onClose,
}: {
  status: RunStatus | null
  error: string | null
  onClose: () => void
}) {
  const logRef = useRef<HTMLPreElement>(null)

  // Keep the newest line in view, like a terminal.
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [status?.log])

  const running = status?.running ?? false
  let title = 'Run finished'
  if (error) title = 'Couldn’t start the run'
  else if (running) title = 'Running the pipeline…'
  else if (status?.exit_code !== null && status?.exit_code !== 0) title = `Run failed (exit code ${status?.exit_code})`

  const failed = Boolean(error) || (!running && (status?.exit_code ?? 0) !== 0)
  return (
    <section className={`card overflow-hidden ${failed ? 'border-red-300 dark:border-red-900' : ''}`}>
      <div className="flex items-center gap-3 border-b border-slate-200 px-4 py-2.5 dark:border-slate-800">
        {running && <span className="size-3 animate-spin rounded-full border-2 border-final border-t-transparent" />}
        <h2 role="status" className="text-sm font-semibold">{title}</h2>
        <span className="text-xs text-slate-500 dark:text-slate-400">
          {running ? 'Scraping, scoring, and writing letters takes a few minutes. You can keep using the page.' : ''}
        </span>
        {!running && (
          <button onClick={onClose} className="ml-auto text-sm text-slate-500 hover:text-slate-800 dark:hover:text-slate-200" aria-label="Close the run log">
            ✕
          </button>
        )}
      </div>
      {error && <p className="px-4 py-3 text-sm text-red-700 dark:text-red-400">{error}</p>}
      {!error && (
        <pre ref={logRef} className="max-h-64 overflow-y-auto bg-slate-950 px-4 py-3 font-mono text-xs leading-relaxed whitespace-pre-wrap text-slate-200">
          {status?.log || 'Starting…'}
        </pre>
      )}
    </section>
  )
}
