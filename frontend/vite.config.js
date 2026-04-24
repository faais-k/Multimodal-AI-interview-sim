import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    cors: true,
  },
  // Note: do NOT use define to override import.meta.env.VITE_API_BASE here.
  // Set VITE_API_BASE in your .env file or Vercel environment variables before running build.
  // Vite automatically injects all VITE_* env vars from .env at build time.
  // Example: VITE_API_BASE=https://your-space.hf.space/api
});
