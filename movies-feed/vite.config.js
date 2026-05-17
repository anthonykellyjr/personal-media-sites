import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/recently-added/',
  server: {
    open: '/recently-added/',
    proxy: {
      '/api': {
        target: 'http://localhost:5050',
        changeOrigin: true
      }
    }
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
