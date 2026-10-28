import { useEffect, useState } from "react";

import { failure } from "../net/fetchJson";
import { addressOf, type SiteGame, siteGames } from "../net/replaySite";
import { Page } from "./Page";
import { gameFilePath } from "./paths";

/**
 * The replay site's landing page: the recorded games it holds, each to watch in full scope
 * (every role, the Den and each Agent's mind) or in Mystery mode (only what the whole town saw).
 * The site is static: every game is a file beside it, played in the browser with no server.
 */
export function ReplaySitePage() {
  const [games, setGames] = useState<SiteGame[] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    siteGames().then(setGames, (error: unknown) => setProblem(failure(error)));
  }, []);

  return (
    <Page title="Recorded games">
      <p className="max-w-prose text-stone-300">
        Every Resident of this town is an AI Agent who knows only what their character could. Each game here was
        played by Agents and recorded whole: watch it in full to see every role, the Den and each Agent's mind, or
        in Mystery mode to see only what the town saw.
      </p>
      {problem && (
        <p role="alert" className="text-sm text-rose-300">
          {problem}
        </p>
      )}
      {games && <SiteGames games={games} />}
    </Page>
  );
}

export function SiteGames({ games }: { games: readonly SiteGame[] }) {
  return (
    <ul aria-label="Recorded games" className="grid gap-4 sm:grid-cols-2">
      {games.map((game) => (
        <li key={game.file} className="flex flex-col gap-3 rounded border border-stone-800 bg-stone-900 p-4">
          <h2 className="font-serif text-xl text-amber-200">{game.title}</h2>
          <p className="text-sm text-stone-300">{game.blurb}</p>
          <div className="mt-auto flex gap-4 text-sm">
            <a href={gameFilePath(addressOf(game))} className="font-semibold text-amber-300 hover:text-amber-200">
              Watch
            </a>
            <a href={gameFilePath(addressOf(game), true)} className="text-stone-300 hover:text-stone-100">
              Watch in Mystery mode
            </a>
          </div>
        </li>
      ))}
    </ul>
  );
}
