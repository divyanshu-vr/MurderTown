import { type FormEvent, useEffect, useState } from "react";

import { failure } from "../net/fetchJson";
import { listGames } from "../net/games";
import type { GameSummary } from "../protocol";
import { GameList } from "./GameList";
import { Page } from "./Page";
import { inputStyle } from "./styles";

/**
 * The game list, and the Host's way in: with the Host token, a new game and every game's
 * cost; without, the games to watch. A wrong token shows up as the list being refused.
 */
export function HomePage({
  hostToken,
  onSignIn,
  onSignOut,
}: {
  hostToken: string | null;
  onSignIn: (token: string) => void;
  onSignOut: () => void;
}) {
  const [games, setGames] = useState<GameSummary[] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    listGames(hostToken).then(
      (listed) => {
        setGames(listed);
        setProblem(null);
      },
      (error: unknown) => setProblem(failure(error)),
    );
  }, [hostToken]);

  return (
    <Page title="Games">
      {hostToken ? (
        <div className="flex items-center gap-4">
          <a href="/setup" className="rounded bg-amber-300 px-4 py-2 font-semibold text-stone-950 hover:bg-amber-200">
            New game
          </a>
          <span className="text-sm text-stone-400">You are the Host.</span>
          <button type="button" className="text-sm text-stone-400 hover:text-stone-200" onClick={onSignOut}>
            Sign out
          </button>
        </div>
      ) : (
        <HostSignIn onSignIn={onSignIn} />
      )}
      {problem && (
        <p role="alert" className="text-sm text-rose-300">
          {problem}
        </p>
      )}
      {games && <GameList games={games} />}
    </Page>
  );
}

function HostSignIn({ onSignIn }: { onSignIn: (token: string) => void }) {
  const [token, setToken] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (token.trim()) onSignIn(token.trim());
  };
  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3 text-sm">
      <label className="flex flex-col gap-1">
        <span className="text-stone-400">
          Host token (open the link <code>mm serve</code> prints, or paste the token)
        </span>
        <input type="password" className={inputStyle} value={token} onChange={(event) => setToken(event.target.value)} />
      </label>
      <button type="submit" className="rounded border border-stone-700 px-3 py-1 hover:border-amber-300">
        Sign in as the Host
      </button>
    </form>
  );
}
