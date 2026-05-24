import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import electron from 'vite-plugin-electron/simple'

export default defineConfig({
  plugins: [
    react(),
    electron({
      main: {
        // Compiles electron/main.ts → dist-electron/main.js
        entry: 'electron/main.ts',
      },
      preload: {
        // Compiles electron/preload.ts → dist-electron/preload.js
        input: 'electron/preload.ts',
      },
      // Renderer process uses React — no need for polyfills
      renderer: {},
    }),
  ],
  server: { port: 5173 },
  base: './',
})
