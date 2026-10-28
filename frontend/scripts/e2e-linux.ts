/**
 * Runs the browser tests in Playwright's own Linux image, as CI does, so screenshots compare with
 * their baselines, which are made there. Needs Docker. Arguments go on to `playwright test`: after
 * changing how the town looks, `pnpm e2e:linux --update-snapshots` makes new baselines.
 */
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const frontend = join(import.meta.dirname, "..");
const versionOf = (file: string) => (JSON.parse(readFileSync(file, "utf-8")) as { version: string }).version;
const playwright = versionOf(join(frontend, "node_modules", "@playwright", "test", "package.json"));
const { packageManager } = JSON.parse(readFileSync(join(frontend, "package.json"), "utf-8")) as { packageManager: string };

const inside = [
  `npm install --global ${packageManager} > /dev/null`,
  "pnpm install --frozen-lockfile --store-dir /pnpm-store > /dev/null",
  `pnpm exec playwright test ${process.argv.slice(2).join(" ")}`,
].join(" && ");
const docker = spawnSync(
  "docker",
  [
    "run",
    "--rm",
    ...["--volume", `${join(frontend, "..")}:/repo`],
    // the image's own packages, and pnpm's store of them, kept apart from this machine's and out of the repo
    ...["--volume", "murdertown-e2e-node-modules:/repo/frontend/node_modules"],
    ...["--volume", "murdertown-e2e-pnpm-store:/pnpm-store"],
    ...["--workdir", "/repo/frontend", "--env", "CI=1"],
    `mcr.microsoft.com/playwright:v${playwright}-noble`,
    ...["bash", "-c", inside],
  ],
  { stdio: "inherit" },
);
process.exit(docker.status ?? 1);
