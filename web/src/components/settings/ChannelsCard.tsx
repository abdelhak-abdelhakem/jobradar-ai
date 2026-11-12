import SettingsCard, { type CardProps } from './SettingsCard'

// YOUR TURN: build this card. It chooses where the digest is sent (Telegram, Gmail, or both).
// SourcesCard.tsx is almost the same card, so start by reading it. Then:
//   1. Keep the chosen channels in state, starting from settings.channels.
//   2. Show one checkbox per item in options.channels (each has a name and a label).
//   3. In save(), send { channels: chosen } with api.updateSettings, pass the result to onSaved,
//      and return a sentence such as "The next run sends to Telegram and Gmail."
//   4. Bonus: settings.missing_credentials lists the channels with nothing in .env. Show a warning
//      when a chosen channel is in that list, like the Streamlit sidebar did.
// Try saving with no box ticked: the API answers "Select at least one channel.", and the card shows it.
export default function ChannelsCard(_props: CardProps) {
  return (
    <SettingsCard title="Notifications" onSave={async () => 'Not built yet.'} saveDisabled>
      <p className="text-sm text-slate-500">To build: see web/src/components/settings/ChannelsCard.tsx</p>
    </SettingsCard>
  )
}
