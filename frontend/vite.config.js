import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),

    // PWA : rend l'application installable sur smartphone et PC, sans passer par un store
    VitePWA({
      // Le service worker se met à jour tout seul dès qu'une nouvelle version est déployée
      registerType: 'autoUpdate',

      // Icônes générées par "npm run generate-pwa-assets" (voir pwa-assets.config.js)
      includeAssets: ['favicon.ico', 'logo.svg', 'apple-touch-icon-180x180.png'],

      // Fichier manifest.webmanifest : décrit l'application installée
      manifest: {
        name: 'Smart-Brancard · Cardio-Connect',
        short_name: 'Smart-Brancard',
        description: 'Système intelligent de brancardage hospitalier',
        lang: 'fr',
        start_url: '/',
        scope: '/',
        display: 'standalone',   // s'ouvre en plein écran, sans la barre du navigateur
        theme_color: '#1565c0',
        background_color: '#f1f5f9',
        icons: [
          { src: 'pwa-64x64.png', sizes: '64x64', type: 'image/png' },
          { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: 'maskable-icon-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },

      workbox: {
        // Seuls les fichiers de l'application (JS, CSS, HTML, icônes) sont mis en cache.
        // Les réponses de l'API ne le sont pas : aucune donnée patient ne reste sur le
        // téléphone (CDC §7.2), et le mode hors ligne complet est un bonus.
        globPatterns: ['**/*.{js,css,html,ico,png,svg,webmanifest}'],
        // Un rechargement sur /regulateur ou /brancardier renvoie l'application (routes React)
        navigateFallback: '/index.html',
        cleanupOutdatedCaches: true,
      },
    }),
  ],
})
