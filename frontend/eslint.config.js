import js from "@eslint/js";
import { defineConfig } from "eslint/config";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default defineConfig(
  { ignores: ["dist", "dist-site", "src/protocol/murdertown.gen.ts"] },
  js.configs.recommended,
  tseslint.configs.strict,
  reactHooks.configs.flat.recommended,
  { languageOptions: { globals: { ...globals.browser, ...globals.node } } },
  {
    files: ["src/core/**"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["react", "react-dom", "phaser", "**/ui/**", "**/net/**", "**/game/**"],
              message: "core/ stays pure: no React, Phaser, UI, game or network code.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/ui/**", "src/net/**", "src/*.tsx"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["phaser", "**/game/**"],
              allowTypeImports: true,
              message: "Phaser comes only with the town: load game/ with import(), so the console never downloads it.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/game/**"],
    rules: {
      "no-restricted-imports": [
        "error",
        { patterns: [{ group: ["**/ui/**", "**/net/**"], message: "game/ draws what it is given: no UI or network code." }] },
      ],
    },
  },
);
