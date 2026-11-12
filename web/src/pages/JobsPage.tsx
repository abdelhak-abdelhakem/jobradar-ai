import { useState } from 'react'
import type { Job, Options } from '../api'
import JobDetails from '../components/JobDetails'
import JobsTable from '../components/JobsTable'
import ScoreChart from '../components/ScoreChart'
import StatTiles from '../components/StatTiles'

export default function JobsPage({ jobs, options }: { jobs: Job[]; options: Options }) {
  // The selected job is kept by key, and the best job is shown until the user picks one.
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const selected = jobs.find((job) => job.key === selectedKey) ?? jobs[0]

  if (jobs.length === 0) {
    return (
      <div className="card p-8 text-center">
        <p className="font-medium">No results yet.</p>
        <p className="mt-1 text-sm text-slate-500">
          Run the pipeline with <code className="rounded bg-slate-100 px-1.5 py-0.5 dark:bg-slate-800">python -m scheduler.run_daily</code>
        </p>
      </div>
    )
  }

  const lastRun = jobs.map((job) => job.seen_at).sort().at(-1)!.slice(0, 16).replace('T', ' ')
  const hasOldRows = jobs.some((job) => job.rationale === null)

  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-500 dark:text-slate-400">
        Last saved: {lastRun} UTC. Scores are LLM estimates and can change between runs.
      </p>
      {hasOldRows && (
        <p className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">
          ⚠ Some jobs were saved by an older version, so their details are missing. To fill them in, clear the
          history in Settings and run the pipeline again.
        </p>
      )}
      <StatTiles jobs={jobs} options={options} />
      <ScoreChart jobs={jobs} options={options} selected={selected.key} onSelect={setSelectedKey} />
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <JobsTable jobs={jobs} options={options} selected={selected.key} onSelect={setSelectedKey} />
        <div className="lg:sticky lg:top-4">
          <JobDetails job={selected} options={options} />
        </div>
      </div>
    </div>
  )
}
