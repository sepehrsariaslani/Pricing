import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import Icons from 'unplugin-icons/vite'
import { FileSystemIconLoader } from 'unplugin-icons/loaders'

export default defineConfig(async ({ mode }) => {
  const isDev = mode === 'development'

  return {
    base: '/assets/pricing/frontend/',
    plugins: [
      vue(),
      Icons({
        compiler: 'vue3',
        customCollections: {
          lucide: FileSystemIconLoader(
            path.resolve(__dirname, 'node_modules/lucide-static/icons'),
            (svg) => svg.replace(/^<svg /, '<svg fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ')
          ),
        },
      }),
    ],
    server: {
      allowedHosts: true,
      fs: {
        allow: ['..', 'node_modules'],
      },
      proxy: {
        '^/(api|assets|files)': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
        'tailwind.config.js': path.resolve(__dirname, 'tailwind.config.cjs'),
      },
    },
    optimizeDeps: {
      include: ['feather-icons'],
    },
    build: {
      outDir: '../pricing/public/frontend',
      emptyOutDir: true,
      sourcemap: true,
      modulePreload: {
        polyfill: false,
      },
      rollupOptions: {
        output: {
          entryFileNames: 'assets/index.js',
          chunkFileNames: 'assets/[name].js',
          assetFileNames: 'assets/[name].[ext]',
          inlineDynamicImports: true,
        },
      },
    },
  }
})

