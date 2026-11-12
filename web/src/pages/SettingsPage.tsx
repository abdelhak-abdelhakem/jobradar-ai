import type { Options, Settings } from '../api'
import ChannelsCard from '../components/settings/ChannelsCard'
import ContractCard from '../components/settings/ContractCard'
import HistoryCard from '../components/settings/HistoryCard'
import KeywordsCard from '../components/settings/KeywordsCard'
import LettersCard from '../components/settings/LettersCard'
import ScheduleCard from '../components/settings/ScheduleCard'
import SourcesCard from '../components/settings/SourcesCard'

export default function SettingsPage({
  options,
  settings,
  jobCount,
  onSaved,
  onCleared,
}: {
  options: Options
  settings: Settings
  jobCount: number
  onSaved: (settings: Settings) => void
  onCleared: () => void
}) {
  const card = { options, settings, onSaved }
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500 dark:text-slate-400">
        These settings apply from the next run. Each card saves on its own.
      </p>
      <div className="grid items-start gap-4 md:grid-cols-2">
        <ContractCard {...card} />
        <SourcesCard {...card} />
        <KeywordsCard {...card} />
        <LettersCard {...card} />
        <ChannelsCard {...card} />
        <ScheduleCard {...card} />
        <HistoryCard count={jobCount} onCleared={onCleared} />
      </div>
    </div>
  )
}
