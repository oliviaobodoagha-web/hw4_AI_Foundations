import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// FastAPI backend (run from backend/: uvicorn main:app --reload --port 8000).
// Override with BACKEND_URL=http://localhost:<port> if 8000 is busy.
const backend = process.env.BACKEND_URL ?? 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true,
    // Send API and image requests to the FastAPI backend during development.
    proxy: {
      '/api': backend,
      '/images': backend,
    },
  },
})
