import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    headers: {
      'Cross-Origin-Embedder-Policy': 'unsafe-none',
      'Cross-Origin-Opener-Policy': 'unsafe-none',
    },
    proxy: {
      '/api': {
        // Overridable so a second backend (a branch, a live check on another
        // port) can be pointed at without editing this file -- 8000 is taken
        // by another project on at least one machine here.
        target: process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
        // FastAPI answers a path with no trailing slash with a 307 to the
        // canonical one, and the Location header carries the *backend's*
        // origin. Without this rewrite the browser follows that redirect
        // cross-origin, drops the auth cookie and Authorization header with
        // it, and a request that should be a 200 lands as a 401 -- which is
        // exactly what `/api/v1/accounts` did.
        autoRewrite: true,
      },
    },
  },
})
