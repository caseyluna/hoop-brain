// web/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0", // 👈 This is key
    port: 5173, // Optional — just makes it explicit
    strictPort: true, // Optional — fail fast if taken
  },
});
