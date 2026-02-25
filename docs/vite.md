# Vite — Performance & Deployment

## Performance (Build & Dev)

- Set `build.target` to match your browser support — don't transpile for ancient browsers if you don't need to:
  ```js
  build: { target: 'es2020' }
  ```
- Enable CSS code splitting (default) — don't disable it unless you have a specific reason.
- Configure manual chunk splitting to isolate vendor dependencies from app code:
  ```js
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
        }
      }
    }
  }
  ```
- Minimize dependency pre-bundling issues — add problematic deps to `optimizeDeps.include` for faster cold starts.
- Use `build.cssMinify: 'lightningcss'` for faster CSS minification.
- Set `build.sourcemap = false` in production unless you need source maps for error tracking — they increase build size.
- Use `build.reportCompressedSize: false` to speed up builds (disables gzip size reporting).
- For large projects, use `build.minify: 'esbuild'` (default and fastest) unless you specifically need Terser's advanced optimizations.
- Leverage `import.meta.glob` for dynamic imports instead of manual boilerplate.
- Use the `vite-plugin-compression` plugin to pre-generate gzip/brotli compressed assets — serve directly from Nginx with `gzip_static on;` or `brotli_static on;`.
- Configure `server.warmup` to pre-transform frequently used modules during dev:
  ```js
  server: {
    warmup: { clientFiles: ['./src/App.vue', './src/router/index.ts'] }
  }
  ```

## Deployment

- Output goes to `dist/` by default. Serve with Nginx as static files — no Node.js process needed for SPA.
- Set long cache headers on hashed assets (`/assets/*`) and no-cache on `index.html`:
  ```
  location /assets/ {
    expires 1y;
    add_header Cache-Control "public, immutable";
  }
  location = /index.html {
    add_header Cache-Control "no-cache";
  }
  ```
- For SSR (Nuxt, Quasar SSR), a Node.js process is required — use PM2 or Supervisor to manage it, and Nginx as a reverse proxy in front.
