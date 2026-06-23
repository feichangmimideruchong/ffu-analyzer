import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '..', '')
  if (!env.OPENAI_API_KEY) throw new Error('Missing OPENAI_API_KEY in ../.env')
  return {
    server: {
      proxy: {
        // Backend now serves routes under /api, so forward the prefix as-is.
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
