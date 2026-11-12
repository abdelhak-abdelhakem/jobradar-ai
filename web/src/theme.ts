// Light or dark mode. Until the user picks one, the page follows the system setting, even if it changes.
// The first choice is made in index.html, before the page draws.

export type Theme = 'light' | 'dark'

const query = matchMedia('(prefers-color-scheme: dark)')

function savedTheme(): Theme | null {
  try {
    const saved = localStorage.getItem('theme')
    return saved === 'light' || saved === 'dark' ? saved : null
  } catch {
    return null   // storage can be blocked, such as in a private window
  }
}

export function currentTheme(): Theme {
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light'
}

export function setTheme(theme: Theme): void {
  document.documentElement.classList.toggle('dark', theme === 'dark')
  try {
    localStorage.setItem('theme', theme)
  } catch {
    // The theme still changes; it just isn't remembered.
  }
}

// Calls onChange when the system setting changes, unless the user picked a theme. Returns a function to stop.
export function followSystem(onChange: (theme: Theme) => void): () => void {
  function update() {
    if (savedTheme()) return
    document.documentElement.classList.toggle('dark', query.matches)
    onChange(currentTheme())
  }
  query.addEventListener('change', update)
  return () => query.removeEventListener('change', update)
}
