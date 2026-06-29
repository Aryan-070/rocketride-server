import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

// Repo root — so we can import pipelines/var-review.pipe directly.
const repoRoot = fileURLToPath(new URL('../..', import.meta.url))

export default defineConfig({
  plugins: [react()],
  server: { port: 5174, open: true, fs: { allow: [repoRoot] } },
})
