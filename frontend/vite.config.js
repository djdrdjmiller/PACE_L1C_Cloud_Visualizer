import { fileURLToPath } from 'node:url';
export default {
  base: './',
  build: {
    rollupOptions: {
      input: {
        app: fileURLToPath(new URL('./index.html', import.meta.url)),
        showcase: fileURLToPath(new URL('./showcase.html', import.meta.url)),
      },
    },
  },
};
