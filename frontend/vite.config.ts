import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// When GITHUB_PAGES=true, build a standalone bundle for GitHub Pages hosting.
// The base path must match the repository name so asset URLs resolve correctly.
const isGitHubPages = process.env.GITHUB_PAGES === 'true'

export default defineConfig({
  plugins: [react()],

  // GitHub Pages: /Wildlife_PTZ_Camera_Tracker/  •  local: /
  base: isGitHubPages ? '/Wildlife_PTZ_Camera_Tracker/' : '/',

  server: {
    port: 5173,
    // Proxy only applies during local dev (not used on GitHub Pages).
    // Override with: BACKEND_PORT=8090 npm run dev
    proxy: {
      '/api': `http://localhost:${process.env.BACKEND_PORT ?? 8080}`,
      '/ws':  { target: `ws://localhost:${process.env.BACKEND_PORT ?? 8080}`, ws: true },
    },
  },

  build: {
    // GitHub Pages: standalone bundle in <repo-root>/dist/pages/
    // Local server: lands in backend/static/ so FastAPI serves it
    outDir:     isGitHubPages ? '../dist/pages' : '../backend/static',
    emptyOutDir: true,
  },
})
