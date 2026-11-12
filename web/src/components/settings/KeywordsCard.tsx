import { useState } from 'react'
import { api } from '../../api'
import SettingsCard, { type CardProps } from './SettingsCard'

export default function KeywordsCard({ settings, onSaved }: CardProps) {
  const [text, setText] = useState(settings.domain_keywords.join('\n'))

  async function save() {
    // The API trims, drops empty lines, and removes duplicates, so the box shows what was really saved.
    const saved = await api.updateSettings({ domain_keywords: text.split('\n') })
    onSaved(saved)
    setText(saved.domain_keywords.join('\n'))
    return 'The next run uses these keywords. Jobs already handled aren’t scored again.'
  }

  return (
    <SettingsCard
      title="Search keywords"
      description={<>A job’s title or description must contain one of these. One per line, matched as whole words.
        Keywords in capitals, such as AI, match only in capitals, so AI doesn’t match the French “j’ai”.</>}
      onSave={save}
    >
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={8} className="field w-full font-mono" />
    </SettingsCard>
  )
}
