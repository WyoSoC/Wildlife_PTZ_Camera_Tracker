import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Forward REST calls to the FastAPI backend during development
      '/api': 'http://localhost:8080',
      // Forward WebSocket upgrade to FastAPI
      '/ws': {
        target: 'ws://localhost:8080',
        ws: true,
      },
    },
  },
  build: {
    // Output lands directly in backend/static/ so FastAPI serves it
    outDir: '../backend/static',
    emptyOutDir: true,
  },
})
