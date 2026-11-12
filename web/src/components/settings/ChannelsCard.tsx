import { useState } from 'react'
import { api } from '../../api'
import SettingsCard, { type CardProps } from './SettingsCard'

export default function ChannelsCard({ options, settings, onSaved }: CardProps) {
  const [chosen, setChosen] = useState(settings.channels)
  const label = (name: string) => options.channels.find((c) => c.name === name)?.label ?? name

  function toggle(name: string, on: boolean) {
    // Keep the API's order, not the order the boxes were clicked in.
    setChosen(options.channels.map((c) => c.name).filter((n) => (n === name ? on : chosen.includes(n))))
  }

  async function save() {
    onSaved(await api.updateSettings({ channels: chosen }))
    return `The next run sends to ${chosen.map(label).join(' and ')}.`
  }

  // Ticked channels with nothing in .env: the run would try them and send nothing.
  const missing = chosen.filter((name) => settings.missing_credentials.includes(name))

  return (
    <SettingsCard
      title="Notifications"
      description="Where the digest is sent. A job counts as sent once any chosen channel delivers it. Gmail sends one email per run, to the address in .env."
      onSave={save}
    >
      {options.channels.map((channel) => (
        <label key={channel.name} className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={chosen.includes(channel.name)} onChange={(e) => toggle(channel.name, e.target.checked)} />
          {channel.label}
        </label>
      ))}
      {missing.length > 0 && (
        <p className="rounded-lg border border-amber-300 bg-amber-50 p-2.5 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">
          ⚠ No credentials in .env for: {missing.map(label).join(', ')}. Nothing will be sent there.
        </p>
      )}
    </SettingsCard>
  )
}
