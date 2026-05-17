import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/collections/',
  server: {
    open: '/collections/',
    proxy: {
      '/capi': {
        target: 'http://localhost:5060',
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
