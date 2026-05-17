import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/tutorials/',
  server: {
    open: '/tutorials/'
  },
  build: {
    outDir: 'dist',
    emptyDirOnBuild: true,
    minify: 'esbuild',
    rollupOptions: {
      output: {
        manualChunks: {
          'vue': ['vue']
        }
      }
    }
  }
})
