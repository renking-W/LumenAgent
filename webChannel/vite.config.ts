import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      // HTTP、SSE 和 WebSocket 在开发环境统一转发到 FastAPI。
      '/v1': {
        target: 'http://127.0.0.1:21675',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
