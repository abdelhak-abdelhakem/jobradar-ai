import { useState } from 'react'
import type { Job, Options } from '../api'
import { contractLabel, isStrong, sourceLabel } from '../labels'

export default function JobsTable({
  jobs,
  options,
  selected,
  onSelect,
}: {
  jobs: Job[]
  options: Options
  selected: string | null
  onSelect: (key: string) => void
}) {
  const [search, setSearch] = useState('')
  const [source, setSource] = useState('all')
  const [lettersOnly, setLettersOnly] = useState(false)

  // Filtering runs on every render. With a few hundred jobs that's instant, so nothing needs caching.
  const words = search.toLowerCase().trim()
  const shown = jobs.filter(
    (job) =>
      (source === 'all' || job.source === source) &&
      (!lettersOnly || job.letter !== null) &&
      (!words || `${job.title} ${job.company ?? ''}`.toLowerCase().includes(words)),
  )

  return (
    <div className="card overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 p-3 dark:border-slate-800">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search titles"
          className="field min-w-0 flex-1"
        />
        <select value={source} onChange={(e) => setSource(e.target.value)} className="field">
          <option value="all">All sources</option>
          {options.sources.map((s) => <option key={s.name} value={s.name}>{s.label}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={lettersOnly} onChange={(e) => setLettersOnly(e.target.checked)} />
          With a letter
        </label>
      </div>

      {shown.length === 0 && <p className="p-4 text-sm text-slate-500">No jobs match these filters.</p>}
      <ul className="max-h-[32rem] divide-y divide-slate-100 overflow-y-auto dark:divide-slate-800">
        {shown.map((job) => (
          <li key={job.key}>
            <button
              onClick={() => onSelect(job.key)}
              className={`flex w-full items-center gap-3 px-3 py-2.5 text-left transition hover:bg-slate-50 dark:hover:bg-slate-800/60 ${
                selected === job.key ? 'bg-blue-50 dark:bg-blue-950/50' : ''
              }`}
            >
              <ScoreBadge score={job.score} strong={isStrong(options, job)} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">{job.title}</span>
                <span className="block text-xs text-slate-500 dark:text-slate-400">
                  {sourceLabel(options, job.source)} · {contractLabel(options, job.contract_type)}
                  {job.letter && ' · Letter written'}
                  {job.issues.length > 0 && ' · ⚠ To check'}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function ScoreBadge({ score, strong }: { score: number; strong: boolean }) {
  return (
    <span
      className={`w-11 shrink-0 rounded-md py-1 text-center text-sm font-semibold tabular-nums ${
        strong
          ? 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200'
          : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
      }`}
    >
      {score}
    </span>
  )
}
