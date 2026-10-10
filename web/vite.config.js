import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, /api/* is forwarded to the Flask backend, so the browser sees a single origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": process.env.API_URL || "http://127.0.0.1:5000",
    },
  },
});
