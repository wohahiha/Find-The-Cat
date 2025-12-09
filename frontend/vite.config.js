import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

const backendTarget = process.env.VITE_BACKEND_URL || 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      // proxy /api to backend (Django)
      '/api': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      // proxy captcha endpoints
      '/captcha': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      // serve media/static files during local dev
      '/media': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      '/static': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
    },
  },
})
