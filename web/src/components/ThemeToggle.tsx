import { useEffect, useState } from 'react'
import { currentTheme, followSystem, setTheme } from '../theme'

export default function ThemeToggle() {
  const [theme, setState] = useState(currentTheme)

  useEffect(() => followSystem(setState), [])   // the returned function stops listening when it unmounts

  const next = theme === 'dark' ? 'light' : 'dark'
  return (
    <button
      onClick={() => {
        setTheme(next)
        setState(next)
      }}
      className="button px-2.5"
      aria-label={`Switch to ${next} mode`}
      title={`Switch to ${next} mode`}
    >
      {theme === 'dark' ? '☀️' : '🌙'}
    </button>
  )
}
