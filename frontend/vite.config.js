import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev me `npm run dev` frontend ko 5173 pe chalata hai aur backend 8001 pe alag
// container me hota hai. Proxy ke bina har fetch CORS pe atakti. Production me
// Nginx yahi kaam karta hai (nginx.conf dekho), isliye app code me hamesha
// relative "/api/..." likhte hain — dono jagah same path chalta hai.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_BACKEND_URL || "http://localhost:8001",
        changeOrigin: true,
      },
    },
  },
});
