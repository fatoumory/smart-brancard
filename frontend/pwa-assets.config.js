import { defineConfig, minimal2023Preset } from '@vite-pwa/assets-generator/config'

// Génère les icônes de la PWA à partir de public/logo.svg
// Commande : npm run generate-pwa-assets (à relancer seulement si le logo change)
export default defineConfig({
  headLinkOptions: { preset: '2023' },
  preset: {
    ...minimal2023Preset,
    // Fond de l'icône Apple et de l'icône "maskable" : même bleu que le logo
    apple: { ...minimal2023Preset.apple, resizeOptions: { background: '#1565c0' } },
    maskable: { ...minimal2023Preset.maskable, resizeOptions: { background: '#1565c0' } },
  },
  images: ['public/logo.svg'],
})
