import { useState } from 'react'
import { api } from '../../api'
import SettingsCard, { type CardProps } from './SettingsCard'

export default function LettersCard({ options, settings, onSaved }: CardProps) {
  const [delivery, setDelivery] = useState(settings.delivery)
  const [topK, setTopK] = useState(settings.top_k)

  async function save() {
    onSaved(await api.updateSettings({ delivery, top_k: topK }))
    return delivery === 'top_k'
      ? `The next run writes letters for the best ${topK} strong matches.`
      : 'The next run writes a letter for every strong match.'
  }

  return (
    <SettingsCard
      title="Letters"
      description={<>A strong match scores {options.match_threshold} or more, and each letter costs several LLM
        calls. With the best K, the other strong matches aren’t recorded, so the next run scores them again.</>}
      onSave={save}
    >
      <label className="flex items-center gap-2 text-sm">
        <input type="radio" name="delivery" checked={delivery === 'all'} onChange={() => setDelivery('all')} />
        Every strong match
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input type="radio" name="delivery" checked={delivery === 'top_k'} onChange={() => setDelivery('top_k')} />
        Only the best
        <input
          type="number"
          min={1}
          max={options.max_top_k}
          value={topK}
          onChange={(e) => setTopK(Number(e.target.value))}
          disabled={delivery !== 'top_k'}
          className="field w-20"
          aria-label="K"
        />
      </label>
    </SettingsCard>
  )
}
