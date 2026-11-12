import { useState } from 'react'
import { api } from '../../api'
import SettingsCard, { type CardProps } from './SettingsCard'

export default function SourcesCard({ options, settings, onSaved }: CardProps) {
  const [chosen, setChosen] = useState(settings.sources)

  function toggle(name: string, on: boolean) {
    // Keep the API's order, not the order the boxes were clicked in.
    setChosen(options.sources.map((s) => s.name).filter((n) => (n === name ? on : chosen.includes(n))))
  }

  async function save() {
    onSaved(await api.updateSettings({ sources: chosen }))
    return 'The next run uses these sources.'
  }

  return (
    <SettingsCard title="Job sources" description="Which job boards the next run scrapes." onSave={save}>
      {options.sources.map((source) => (
        <label key={source.name} className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={chosen.includes(source.name)} onChange={(e) => toggle(source.name, e.target.checked)} />
          {source.label}
        </label>
      ))}
    </SettingsCard>
  )
}
