/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The proxy keeps the browser on one origin, so session cookies stay first-party.
const proxy = { '/api': { target: process.env.API_URL ?? 'http://127.0.0.1:8090', changeOrigin: false } }

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { host: '127.0.0.1', port: 5190, strictPort: true, proxy },
  preview: { host: '127.0.0.1', port: 5190, strictPort: true, proxy },
  build: { target: 'es2023', reportCompressedSize: true },
  test: { include: ['src/**/*.test.ts'] },
})
