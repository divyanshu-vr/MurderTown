import { defineConfig, devices } from "@playwright/test";

const CONSOLE = "http://localhost:4173";
const REPLAY_SITE = "http://localhost:4174";

/**
 * The console in a real browser: the built app, with the server mocked by each test; and the
 * replay site, built and served as a static host would, with no server at all.
 */
export default defineConfig({
  testDir: "e2e",
  // one baseline for every platform, made on Linux as CI runs: see docs/recipes.md
  snapshotPathTemplate: "{testDir}/__screenshots__/{testFilePath}/{arg}{ext}",
  forbidOnly: Boolean(process.env.CI),
  projects: [
    {
      name: "chromium",
      testIgnore: "replaySite.spec.ts",
      use: { ...devices["Desktop Chrome"], baseURL: CONSOLE },
    },
    {
      name: "replay-site",
      testMatch: "replaySite.spec.ts",
      use: { ...devices["Desktop Chrome"], baseURL: REPLAY_SITE },
    },
  ],
  webServer: [
    {
      command: "pnpm exec vite build && pnpm exec vite preview --port 4173 --strictPort",
      url: CONSOLE,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "pnpm exec vite build --mode site && pnpm exec vite preview --mode site --port 4174 --strictPort",
      url: REPLAY_SITE,
      reuseExistingServer: !process.env.CI,
    },
  ],
});
