// Talks to the FastAPI backend (src/api/main.py). The types mirror what each route returns, so TypeScript
// catches a misspelled field here instead of showing "undefined" on the page.

export type Choice = { name: string; label: string }

export type Options = {
  contracts: (Choice & { skipped_sources: string[] })[]
  sources: Choice[]
  channels: Choice[]
  delivery_modes: ('all' | 'top_k')[]
  schedules: ('off' | 'daily' | 'weekly')[]
  weekdays: string[]
  max_top_k: number
  match_threshold: number
}

export type Settings = {
  sources: string[]
  channels: string[]
  contract_type: string
  domain_keywords: string[]
  delivery: 'all' | 'top_k'
  top_k: number
  schedule: 'off' | 'daily' | 'weekly'
  schedule_day: string
  schedule_time: string
  missing_credentials: string[]   // channels with no credentials in .env
  next_run: string | null         // when systemd runs the pipeline next, or null if it's not scheduled
}

// Only the settings PATCH /api/settings accepts. The schedule has its own route, because it installs a timer.
export type SettingsUpdate = Partial<
  Pick<Settings, 'sources' | 'channels' | 'domain_keywords' | 'contract_type' | 'delivery' | 'top_k'>
>

export type Issue = { quote: string; reason: string }

export type Job = {
  key: string
  source: string
  title: string
  url: string
  company: string | null
  score: number                                   // the final score, after the caps
  llm_score: number                               // the LLM's score, before the caps
  domain_fit: 'direct' | 'adjacent' | 'none' | null
  contract_type: string | null
  rationale: string | null
  matched_skills: string[]
  missing_skills: string[]
  letter: string | null
  issues: Issue[]
  seen_at: string
}

// An error the API explained, such as "Select at least one source.", so the page can show its message.
export class ApiError extends Error {}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    const detail = await response.json().then((data) => data.detail, () => null)
    // FastAPI's own validation errors give a list; our routes give one sentence.
    throw new ApiError(typeof detail === 'string' ? detail : `The server answered ${response.status}.`)
  }
  return response.json()
}

export const api = {
  options: () => request<Options>('GET', '/api/options'),
  settings: () => request<Settings>('GET', '/api/settings'),
  updateSettings: (update: SettingsUpdate) => request<Settings>('PATCH', '/api/settings', update),
  updateSchedule: (schedule: Settings['schedule'], day: string, time: string) =>
    request<Settings & { message: string }>('PUT', '/api/schedule', { schedule, day, time }),
  jobs: () => request<Job[]>('GET', '/api/jobs'),
  clearHistory: () => request<{ deleted: number; backup: string | null }>('DELETE', '/api/history'),
}
