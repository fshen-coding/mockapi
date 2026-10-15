import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: '../web/static',
    emptyOutDir: true,
    // main.js 全量注册 Element Plus，它单独一个 chunk 就有压缩后约 960 kB，阈值按它设置；要再降需改成按需引入。
    chunkSizeWarningLimit: 1024,
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            { name: 'vendor-element-plus', test: /node_modules[\\/](element-plus|@element-plus|dayjs|lodash-es|@floating-ui|async-validator)/ },
            { name: 'vendor-vue', test: /node_modules[\\/](@vue|vue)[\\/]/ },
            { name: 'vendor-motion', test: /node_modules[\\/](gsap|ogl)[\\/]/ },
          ],
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
    },
  },
})
