import type { Job, Options } from '../api'
import { isStrong } from '../labels'

export default function StatTiles({ jobs, options }: { jobs: Job[]; options: Options }) {
  const tiles = [
    { label: 'Jobs scored', value: jobs.length },
    { label: 'Strong matches', value: jobs.filter((job) => isStrong(options, job)).length },
    { label: 'Lowered by the caps', value: jobs.filter((job) => job.llm_score > job.score).length },
    { label: 'Letters to check', value: jobs.filter((job) => job.issues.length > 0).length },
  ]
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {tiles.map((tile) => (
        <div key={tile.label} className="card p-4">
          <div className="text-sm text-slate-500 dark:text-slate-400">{tile.label}</div>
          <div className="mt-1 text-3xl font-semibold tabular-nums">{tile.value}</div>
        </div>
      ))}
    </div>
  )
}
