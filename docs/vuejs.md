# Vue.js — Security & Performance

## Security

- Never use `v-html` with user-supplied data — it renders raw HTML and enables XSS.
- Sanitize any dynamic content rendered from APIs or user input before display.
- Don't store secrets or API keys in frontend code — anything in the bundle is public. Use a backend proxy for sensitive API calls.
- Set proper CSP (Content Security Policy) headers to restrict script sources.
- Use `rel="noopener noreferrer"` on external links opened with `target="_blank"`.

## Performance

- Enable route-based code splitting with dynamic imports — every route should be lazy-loaded:
  ```js
  const Dashboard = () => import('./views/Dashboard.vue')
  ```
- Use `defineAsyncComponent` for heavy components not needed at first render.
- Use `v-once` for content that never changes after initial render.
- Use `v-memo` to skip re-rendering of list items that haven't changed.
- Use `shallowRef` and `shallowReactive` for large data structures that don't need deep reactivity.
- Use `computed` over methods in templates — computed values are cached until dependencies change.
- Avoid large reactive objects — only make reactive what the template actually uses.
- Use `keep-alive` with `include`/`exclude` to cache component instances on route switches (e.g., list/detail patterns).
- Virtualize long lists with a virtual scroll library instead of rendering all items.
- Use `watchEffect` with `onCleanup` and avoid setting up watchers that outlive their purpose.
- Audit bundle size with `npx vite-bundle-visualizer` — identify and eliminate large unused dependencies.
- Use tree-shakable icon libraries (e.g., `@iconify/vue` with per-icon imports) instead of importing full icon packs.
- Lazy-load images with `loading="lazy"` or an Intersection Observer directive.
