import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev server is pinned to :3000 because the backend's default CORS allowlist
// (backend/core/config.py -> cors_origins) only contains http://localhost:3000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    strictPort: true,
  },
  build: {
    rollupOptions: {
      output: {
        // maplibre-gl dwarfs everything else; isolating it (and recharts,
        // which only loads with the lazy detail panel) keeps re-deploys
        // cacheable.
        manualChunks: {
          maplibre: ['maplibre-gl'],
          charts: ['recharts'],
        },
      },
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.js'],
  },
});
