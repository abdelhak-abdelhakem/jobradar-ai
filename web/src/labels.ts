import type { Job, Options } from './api'

// Turns the API's names (such as "phd" or "adjacent") into the words shown on the page.

export const DOMAIN_LABELS: Record<string, string> = { direct: 'Direct', adjacent: 'Adjacent', none: 'None' }

export function domainLabel(job: Job): string {
  return job.domain_fit ? DOMAIN_LABELS[job.domain_fit] : 'Not recorded'
}

export function contractLabel(options: Options, name: string | null): string {
  if (name === null) return 'Not recorded'
  if (name === 'other') return 'Other'
  return options.contracts.find((c) => c.name === name)?.label ?? name
}

export function sourceLabel(options: Options, name: string): string {
  return options.sources.find((s) => s.name === name)?.label ?? name
}

export function isStrong(options: Options, job: Job): boolean {
  return job.score >= options.match_threshold
}
