import { useState } from 'react'
import type { Job, Options } from '../api'
import { domainLabel } from '../labels'

const TICKS = [0, 20, 40, 60, 80, 100]

// A dumbbell per job: the LLM's score, the final score after the caps, and a line between them.
// It's plain HTML positioned in percent, since a score is already a percentage of 100.
export default function ScoreChart({
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
  const [hovered, setHovered] = useState<string | null>(null)
  const cutoff = options.match_threshold

  return (
    <div className="card p-4">
      <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-slate-600 dark:text-slate-300">
        <h2 className="mr-auto font-semibold text-slate-800 dark:text-slate-100">Scores</h2>
        <span className="flex items-center gap-1.5"><Dot className="bg-llm" /> LLM score</span>
        <span className="flex items-center gap-1.5"><Dot className="bg-final" /> Final score</span>
        <span className="flex items-center gap-1.5">
          <span className="h-3.5 border-l-2 border-dashed border-slate-400" /> Letter cutoff ({cutoff})
        </span>
      </div>

      <div className="space-y-0.5">
        {jobs.map((job) => {
          const low = Math.min(job.score, job.llm_score)
          const high = Math.max(job.score, job.llm_score)
          const active = hovered === job.key || selected === job.key
          return (
            <button
              key={job.key}
              onClick={() => onSelect(job.key)}
              onMouseEnter={() => setHovered(job.key)}
              onMouseLeave={() => setHovered(null)}
              className={`grid w-full grid-cols-[minmax(0,11rem)_1fr] items-center gap-3 rounded-md px-2 py-1 text-left sm:grid-cols-[minmax(0,18rem)_1fr] ${
                active ? 'bg-slate-100 dark:bg-slate-800' : ''
              }`}
            >
              <span className="truncate text-sm" title={job.title}>{job.title}</span>
              <span className="relative h-6">
                <span className="absolute inset-y-0 border-l-2 border-dashed border-slate-300 dark:border-slate-600"
                      style={{ left: `${cutoff}%` }} />
                <span className="absolute top-1/2 h-0.5 -translate-y-1/2 bg-slate-400 dark:bg-slate-500"
                      style={{ left: `${low}%`, width: `${high - low}%` }} />
                {/* The final score is drawn last, so it sits on top when both scores are equal. */}
                <Dot className="bg-llm absolute top-1/2 -translate-x-1/2 -translate-y-1/2" left={job.llm_score} />
                <Dot className="bg-final absolute top-1/2 -translate-x-1/2 -translate-y-1/2" left={job.score} />
                {hovered === job.key && (
                  <span className="absolute bottom-full z-10 mb-1 -translate-x-1/2 whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-xs text-white shadow-lg dark:bg-slate-100 dark:text-slate-900"
                        style={{ left: `${Math.min(Math.max(high, 15), 85)}%` }}>
                    LLM {job.llm_score} → final {job.score} · domain: {domainLabel(job)}
                  </span>
                )}
              </span>
            </button>
          )
        })}
      </div>

      {/* The axis, under the tracks only. */}
      <div className="grid grid-cols-[minmax(0,11rem)_1fr] gap-3 px-2 sm:grid-cols-[minmax(0,18rem)_1fr]">
        <span />
        <div className="relative mt-1 h-4 text-xs text-slate-500 tabular-nums dark:text-slate-400">
          {TICKS.map((tick) => (
            <span key={tick} className="absolute -translate-x-1/2" style={{ left: `${tick}%` }}>{tick}</span>
          ))}
        </div>
      </div>
    </div>
  )
}

function Dot({ className, left }: { className: string; left?: number }) {
  // The ring in the card's colour keeps two overlapping dots apart.
  return (
    <span
      className={`inline-block size-3 rounded-full ring-2 ring-white dark:ring-slate-900 ${className}`}
      style={left === undefined ? undefined : { left: `${left}%` }}
    />
  )
}
