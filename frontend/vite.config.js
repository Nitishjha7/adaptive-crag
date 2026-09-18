import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, `npm run dev` runs the frontend on 5173 while the backend runs on
// 8001 in a separate container. Without a proxy, every fetch would hit CORS.
// Production has Nginx do the same job (see nginx.conf), which is why the app
// code always writes a relative "/api/..." — the same path works in both places.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Vite 6 only allows localhost by default and 403s any other Host header.
    // This dev server runs inside Docker, so the browser reaches it via
    // `host.docker.internal` or the machine's LAN IP — both got blocked. This
    // only affects the dev server; production is served by Nginx and is
    // unaffected.
    allowedHosts: true,
    proxy: {
      "/api": {
        target: process.env.VITE_BACKEND_URL || "http://localhost:8001",
        changeOrigin: true,
      },
    },
  },
});
