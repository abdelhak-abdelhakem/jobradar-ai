import { useState } from 'react'
import { api, type Settings } from '../../api'
import SettingsCard, { type CardProps } from './SettingsCard'

const LABELS: Record<Settings['schedule'], string> = {
  off: 'Off, I run it by hand',
  daily: 'Every day',
  weekly: 'Every week',
}

export default function ScheduleCard({ options, settings, onSaved }: CardProps) {
  const [schedule, setSchedule] = useState(settings.schedule)
  const [day, setDay] = useState(settings.schedule_day)
  const [time, setTime] = useState(settings.schedule_time)

  async function save() {
    // The API installs the systemd timer first and saves only if that worked.
    const { message, ...saved } = await api.updateSchedule(schedule, day, time)
    onSaved(saved)
    return message
  }

  return (
    <SettingsCard
      title="Schedule"
      description={<>systemd runs the pipeline on this computer, so it must be on. A run missed while it was off
        happens when it’s back on.</>}
      onSave={save}
    >
      {options.schedules.map((name) => (
        <label key={name} className="flex items-center gap-2 text-sm">
          <input type="radio" name="schedule" checked={schedule === name} onChange={() => setSchedule(name)} />
          {LABELS[name]}
        </label>
      ))}
      <div className="flex flex-wrap gap-3">
        <label className="text-sm">
          <span className="label block">Day</span>
          <select value={day} onChange={(e) => setDay(e.target.value)} disabled={schedule !== 'weekly'} className="field">
            {options.weekdays.map((d) => <option key={d}>{d}</option>)}
          </select>
        </label>
        <label className="text-sm">
          <span className="label block">Time</span>
          <input type="time" value={time} onChange={(e) => setTime(e.target.value)} disabled={schedule === 'off'} required className="field" />
        </label>
      </div>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        {settings.next_run ? `Next run: ${settings.next_run}.` : 'Not scheduled.'} Logs:{' '}
        <code>journalctl --user -u jobradar.service</code>
      </p>
    </SettingsCard>
  )
}
