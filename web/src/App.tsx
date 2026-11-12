import { useEffect, useState } from 'react'
import { api, type Job, type Options, type Settings } from './api'

type Tab = 'jobs' | 'settings'

export default function App() {
  const [tab, setTab] = useState<Tab>('jobs')
  const [options, setOptions] = useState<Options | null>(null)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [jobs, setJobs] = useState<Job[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Load everything once when the page opens. The three requests run at the same time.
  useEffect(() => {
    Promise.all([api.options(), api.settings(), api.jobs()])
      .then(([options, settings, jobs]) => {
        setOptions(options)
        setSettings(settings)
        setJobs(jobs)
      })
      .catch(() => setError('Can’t reach the API. Start it with: uvicorn src.api.main:app --reload'))
  }, [])

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-2">
            <img src="/favicon.svg" alt="" className="size-7" />
            <span className="text-lg font-semibold tracking-tight">JobRadar</span>
          </div>
          <nav className="flex gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-800">
            {(['jobs', 'settings'] as const).map((name) => (
              <button
                key={name}
                onClick={() => setTab(name)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium capitalize transition ${
                  tab === name
                    ? 'bg-white shadow-sm dark:bg-slate-950'
                    : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100'
                }`}
              >
                {name}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        {error && (
          <p className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
            {error}
          </p>
        )}
        {!error && (!options || !settings || !jobs) && <p className="text-slate-500">Loading…</p>}
        {options && settings && jobs && (
          <p className="text-slate-500">
            Connected: {jobs.length} jobs saved, looking for {settings.contract_type}. The {tab} page comes next.
          </p>
        )}
      </main>
    </div>
  )
}
