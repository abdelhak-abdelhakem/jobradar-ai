import { useState } from 'react'
import { api } from '../../api'
import SettingsCard from './SettingsCard'

export default function HistoryCard({ count, onCleared }: { count: number; onCleared: () => void }) {
  const [confirmed, setConfirmed] = useState(false)

  async function clear() {
    const { deleted, backup } = await api.clearHistory()
    onCleared()
    setConfirmed(false)
    return deleted ? `Cleared ${deleted} jobs. A backup was saved to ${backup}.` : 'The history was already empty.'
  }

  return (
    <SettingsCard
      title="History"
      description={<>{count} jobs are saved. Runs skip them, so new settings only apply to new jobs. Clearing
        removes these results, and the next run scores every listed job again, which costs OpenAI credit.</>}
      onSave={clear}
      saveLabel="Clear history"
      saveDisabled={count === 0 || !confirmed}
      danger
    >
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
        I understand the next run costs more
      </label>
    </SettingsCard>
  )
}
