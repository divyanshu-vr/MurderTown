import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/** The mode that builds the replay site: the console playing its own recorded games, with no server. */
export const REPLAY_SITE_MODE = "site";

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  // the setup form reads its bounds from the protocol schema; nothing else outside the app is served
  server: { fs: { allow: [".", "../protocol"] } },
  // Phaser makes the town's chunk big (about 365 kB gzipped); it loads only when the town is drawn
  build: { chunkSizeWarningLimit: 1500, outDir: mode === REPLAY_SITE_MODE ? "dist-site" : "dist" },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["test/setup.ts"],
  },
}));
