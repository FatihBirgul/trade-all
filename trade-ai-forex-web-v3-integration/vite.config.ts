
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  server: {
    allowedHosts: process.env.TRADE_TAILSCALE_HOST ? [process.env.TRADE_TAILSCALE_HOST] : [],
    proxy: {
      '/news': {
        target: 'http://127.0.0.1:8007',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/news/, ''),
      },
      '/mt5': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/mt5/, ''),
      },
      '/engine': {
        target: process.env.V3_ANALYSIS_PROXY_TARGET ?? 'http://127.0.0.1:8008',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/engine/, ''),
      },
    },
  },
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Trade AI Forex',
        short_name: 'Trade AI',
        description: 'Forex ve XAUUSD analiz platformu',
        theme_color: '#0b1020',
        background_color: '#0b1020',
        display: 'standalone',
        start_url: '/',
        scope: '/',
        lang: 'tr',
        icons: [
          {
            src: '/icon-192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
          },
        ],
      },
    }),
  ],
})
