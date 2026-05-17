import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/status/',
  server: {
    host: '0.0.0.0',
    port: 5173,
    open: '/status/',
    proxy: {
      '/api': {
        target: 'http://host.docker.internal:5050',
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
