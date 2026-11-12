import { useState } from 'react'
import type { Job, Options } from '../api'
import { contractLabel, domainLabel, sourceLabel } from '../labels'

export default function JobDetails({ job, options }: { job: Job; options: Options }) {
  return (
    <article className="card space-y-5 p-5">
      <header>
        <h2 className="text-lg font-semibold leading-snug">{job.title}</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          {sourceLabel(options, job.source)} · {contractLabel(options, job.contract_type)}
        </p>
        <a href={job.url} target="_blank" rel="noreferrer" className="button mt-3 inline-block">
          View job posting ↗
        </a>
      </header>

      <dl className="grid grid-cols-3 gap-3 text-center">
        <Metric label="Final score" value={`${job.score}/100`} />
        <Metric label="LLM score" value={`${job.llm_score}/100`} />
        <Metric label="Domain fit" value={domainLabel(job)} />
      </dl>

      {job.rationale && (
        <section>
          <h3 className="label">Why this score</h3>
          <p className="text-sm leading-relaxed">{job.rationale}</p>
        </section>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <Skills title="Matched skills" skills={job.matched_skills} tone="bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200" />
        <Skills title="Missing skills" skills={job.missing_skills} tone="bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300" />
      </div>

      {job.issues.length > 0 && (
        <section className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">
          <p className="font-semibold">⚠ Unverified letter. Check these points before using it:</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {job.issues.map((issue, i) => (
              <li key={i}>{issue.quote && <q className="italic">{issue.quote}</q>} {issue.reason}</li>
            ))}
          </ul>
        </section>
      )}

      {job.letter ? (
        <Letter text={job.letter} />
      ) : (
        <p className="rounded-lg bg-slate-100 p-3 text-sm text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          No letter, because the final score is below {options.match_threshold}.
        </p>
      )}
    </article>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-2 dark:bg-slate-800/60">
      <dt className="text-xs text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="mt-0.5 font-semibold tabular-nums">{value}</dd>
    </div>
  )
}

function Skills({ title, skills, tone }: { title: string; skills: string[]; tone: string }) {
  return (
    <section>
      <h3 className="label">{title}</h3>
      {skills.length === 0 ? (
        <p className="text-sm text-slate-500">None recorded</p>
      ) : (
        <ul className="flex flex-wrap gap-1.5">
          {skills.map((skill) => <li key={skill} className={`rounded-full px-2.5 py-0.5 text-xs ${tone}`}>{skill}</li>)}
        </ul>
      )}
    </section>
  )
}

function Letter({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  function copy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <section>
      <div className="mb-1 flex items-center justify-between">
        <h3 className="label mb-0">Cover letter draft</h3>
        <button onClick={copy} className="button text-xs">{copied ? 'Copied ✓' : 'Copy'}</button>
      </div>
      <pre className="max-h-96 overflow-y-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 font-sans text-sm leading-relaxed dark:bg-slate-800/60">
        {text}
      </pre>
    </section>
  )
}
