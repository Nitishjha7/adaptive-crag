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
    // Vite 6 default me sirf localhost allow karta hai aur baaki Host headers pe
    // 403 deta hai. Ye dev server Docker ke andar chalta hai, to browser use
    // `host.docker.internal` ya machine ke LAN IP se hit karta hai — dono block
    // ho jaate the. Ye sirf dev server ka setting hai; production Nginx serve
    // karta hai aur wahan iska koi asar nahi.
    allowedHosts: true,
    proxy: {
      "/api": {
        target: process.env.VITE_BACKEND_URL || "http://localhost:8001",
        changeOrigin: true,
      },
    },
  },
});
