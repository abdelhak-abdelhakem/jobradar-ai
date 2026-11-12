import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development, Vite serves the app and forwards /api requests to FastAPI, so both share one origin
// and the API needs no CORS setup (see src/api/main.py for why it has none).
// API_URL points it at an API on another port, such as a second copy for testing.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: { '/api': process.env.API_URL ?? 'http://127.0.0.1:8000' },
  },
})
