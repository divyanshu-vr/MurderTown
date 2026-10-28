import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // the setup form reads its bounds from the protocol schema; nothing else outside the app is served
  server: { fs: { allow: [".", "../protocol"] } },
  // Phaser makes the town's chunk big (about 365 kB gzipped); it loads only when the town is drawn
  build: { chunkSizeWarningLimit: 1500 },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["test/setup.ts"],
  },
});
