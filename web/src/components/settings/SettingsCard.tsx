import { useState, type FormEvent, type ReactNode } from 'react'
import { ApiError, type Options, type Settings } from '../../api'

// What every settings card receives from the page.
export type CardProps = {
  options: Options
  settings: Settings
  onSaved: (settings: Settings) => void   // tells the page the new settings, so every card shows them
}

// A form with a title, its fields, and a Save button. onSave sends the change and returns the sentence to
// show; if it throws, the error is shown instead. Each card only has to describe its own fields.
export default function SettingsCard({
  title,
  description,
  onSave,
  saveLabel = 'Save',
  saveDisabled = false,
  danger = false,
  children,
}: {
  title: string
  description?: ReactNode
  onSave: () => Promise<string>
  saveLabel?: string
  saveDisabled?: boolean
  danger?: boolean
  children: ReactNode
}) {
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState<{ ok: boolean; text: string } | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()   // a form's default is to reload the page
    setSaving(true)
    setStatus(null)
    try {
      setStatus({ ok: true, text: await onSave() })
    } catch (error) {
      setStatus({ ok: false, text: error instanceof ApiError ? error.message : 'Can’t reach the API.' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} className="card flex flex-col p-5">
      <h2 className="font-semibold">{title}</h2>
      {description && <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{description}</p>}
      <div className="mt-4 flex-1 space-y-3">{children}</div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={saving || saveDisabled}
          className={danger ? 'button border-red-300 text-red-700 dark:border-red-800 dark:text-red-300' : 'button-primary'}
        >
          {saving ? 'Saving…' : saveLabel}
        </button>
        {status && (
          <p role="status" className={`text-sm ${status.ok ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-700 dark:text-red-400'}`}>
            {status.ok ? '✓ ' : '✕ '}
            {status.text}
          </p>
        )}
      </div>
    </form>
  )
}
