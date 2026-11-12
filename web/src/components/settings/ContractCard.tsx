import { useState } from 'react'
import { api } from '../../api'
import { sourceLabel } from '../../labels'
import SettingsCard, { type CardProps } from './SettingsCard'

export default function ContractCard({ options, settings, onSaved }: CardProps) {
  const [chosen, setChosen] = useState(settings.contract_type)
  const label = (name: string) => options.contracts.find((c) => c.name === name)!.label

  async function save() {
    onSaved(await api.updateSettings({ contract_type: chosen }))
    return `The next run looks for ${label(chosen)} offers.`
  }

  return (
    <SettingsCard title="Contract type" description="What the next run looks for." onSave={save}>
      {options.contracts.map((contract) => (
        <label key={contract.name} className="flex items-start gap-2 text-sm">
          <input
            type="radio"
            name="contract"
            className="mt-0.5"
            checked={chosen === contract.name}
            onChange={() => setChosen(contract.name)}
          />
          <span>
            {contract.label}
            {contract.skipped_sources.length > 0 && (
              <span className="block text-xs text-slate-500 dark:text-slate-400">
                Skips {contract.skipped_sources.map((s) => sourceLabel(options, s)).join(', ')}, which has no
                such offers on its job site.
              </span>
            )}
          </span>
        </label>
      ))}
    </SettingsCard>
  )
}
